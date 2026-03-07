"""
dynamodb_service.py — DynamoDB CRUD helpers for Swavalambi user profiles.

Table: swavalambi_users
PK:   user_id  (phone number, e.g. "+919876543210")
"""

import boto3
import os
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_TABLE_NAME = os.getenv("DYNAMODB_TABLE", "swavalambi_users")


def _get_table():
    # Use default boto3 credential chain - works for Lambda IAM role, ECS task role, and local dev
    # For local dev, set AWS_ACCESS_KEY_ID/SECRET in .env or use aws configure
    dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    return dynamodb.Table(_TABLE_NAME)


def create_or_update_user(user_id: str, name: str) -> dict:
    """
    Upsert a user record. Only sets name + created_at if not already present
    (so re-registration doesn't wipe assessment data).
    
    Note: For Cognito users, user_id is the email address.
    """
    table = _get_table()
    now = datetime.now(timezone.utc).isoformat()

    table.update_item(
        Key={"user_id": user_id},
        UpdateExpression=(
            "SET #n = if_not_exists(#n, :name), "
            "created_at = if_not_exists(created_at, :now), "
            "updated_at = :now"
        ),
        ExpressionAttributeNames={"#n": "name"},
        ExpressionAttributeValues={":name": name, ":now": now},
    )
    logger.info(f"Upserted user {user_id}")
    return {"user_id": user_id, "name": name}


def update_user_preferences(
    user_id: str,
    language: Optional[str] = None,
    voice_autoplay: Optional[bool] = None
) -> None:
    """
    Update user preferences like language and voice auto-play settings.
    
    Args:
        user_id: User's phone number
        language: Language code (e.g., 'hi-IN', 'te-IN')
        voice_autoplay: Whether voice auto-play is enabled
    """
    table = _get_table()
    now = datetime.now(timezone.utc).isoformat()
    
    update_parts = []
    attr_values = {":now": now}
    
    if language is not None:
        update_parts.append("preferred_language = :lang")
        attr_values[":lang"] = language
    
    if voice_autoplay is not None:
        update_parts.append("voice_autoplay = :voice")
        attr_values[":voice"] = voice_autoplay
    
    if not update_parts:
        return  # Nothing to update
    
    update_expr = "SET " + ", ".join(update_parts) + ", updated_at = :now"
    
    table.update_item(
        Key={"user_id": user_id},
        UpdateExpression=update_expr,
        ExpressionAttributeValues=attr_values
    )
    logger.info(f"Updated preferences for user {user_id}: language={language}, voice_autoplay={voice_autoplay}")


def save_assessment(
    user_id: str,
    skill: str,
    intent: str,
    skill_rating: int,
    theory_score: int = 0,
    session_id: Optional[str] = None,
) -> None:
    """
    DEPRECATED: Use save_profile_assessment() instead.
    
    Legacy function that saves assessment data to root-level fields.
    This creates duplication and is kept only for backward compatibility.
    Will be removed in a future version.
    """
    logger.warning(f"save_assessment() is deprecated. Use save_profile_assessment() instead.")
    
    table = _get_table()
    now = datetime.now(timezone.utc).isoformat()

    update_expr = (
        "SET skill = :skill, intent = :intent, "
        "skill_rating = :rating, theory_score = :theory, "
        "updated_at = :now"
    )
    values = {
        ":skill": skill,
        ":intent": intent,
        ":rating": skill_rating,
        ":theory": theory_score,
        ":now": now,
    }
    if session_id:
        update_expr += ", session_id = :sid"
        values[":sid"] = session_id

    table.update_item(
        Key={"user_id": user_id},
        UpdateExpression=update_expr,
        ExpressionAttributeValues=values,
    )
    logger.info(f"Saved assessment for {user_id}: skill={skill}, rating={skill_rating}")


def save_profile_assessment(
    user_id: str,
    profile_data: dict,
    merge: bool = True
) -> None:
    """
    Save or update the profile assessment data.
    All data is stored in the profile_assessment object only - no duplication.
    
    Args:
        user_id: User's phone number
        profile_data: Dictionary containing assessment data
        merge: If True, merges with existing profile_assessment; if False, replaces it
    """
    logger.info(f"[SAVE_PROFILE] Starting save for user {user_id}")
    logger.info(f"[SAVE_PROFILE] Profile data: {profile_data}")
    
    table = _get_table()
    now = datetime.now(timezone.utc).isoformat()
    
    if merge:
        # Get existing profile_assessment to merge with new data
        try:
            existing_user = get_user(user_id)
            existing_profile = existing_user.get("profile_assessment", {}) if existing_user else {}
            
            # Merge: existing data + new data (new data overwrites on conflict)
            merged_data = {**existing_profile, **profile_data}
            merged_data["updated_at"] = now
            
            # Keep the original assessment_timestamp if it exists
            if "assessment_timestamp" not in merged_data:
                merged_data["assessment_timestamp"] = now
            
            # Update version
            merged_data["assessment_version"] = "1.0"
            
            profile_to_save = merged_data
        except Exception as e:
            logger.warning(f"Failed to merge profile data, saving as new: {e}")
            profile_to_save = {
                **profile_data,
                "assessment_timestamp": now,
                "updated_at": now,
                "assessment_version": "1.0"
            }
    else:
        # Replace completely
        profile_to_save = {
            **profile_data,
            "assessment_timestamp": now,
            "updated_at": now,
            "assessment_version": "1.0"
        }
    
    # Save only to profile_assessment - no root-level duplication
    table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET profile_assessment = :profile, updated_at = :now",
        ExpressionAttributeValues={
            ":profile": profile_to_save,
            ":now": now
        }
    )
    logger.info(f"[SAVE_PROFILE] Successfully saved profile assessment for {user_id}")


def get_user(user_id: str) -> Optional[dict]:
    """
    Fetch a user record by user_id (phone number).
    Returns None if the user does not exist.
    """
    table = _get_table()
    resp = table.get_item(Key={"user_id": user_id})
    item = resp.get("Item")
    if not item:
        return None
    # Convert Decimal → int for JSON serialisation
    for key in ("skill_rating", "theory_score"):
        if key in item:
            item[key] = int(item[key])
    return item


def delete_user(user_id: str) -> None:
    """
    Permanently delete a user record from DynamoDB by user_id.
    """
    table = _get_table()
    table.delete_item(Key={"user_id": user_id})
    logger.info(f"Deleted user {user_id}")

def update_chat_history(user_id: str, chat_history: list) -> None:
    """
    Appends or overwrites the chat history for a specific user.
    """
    table = _get_table()
    now = datetime.now(timezone.utc).isoformat()
    
    table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET chat_history = :history, updated_at = :now",
        ExpressionAttributeValues={
            ":history": chat_history,
            ":now": now
        }
    )
    logger.info(f"Updated chat history for user {user_id}")


def clear_chat_history(user_id: str) -> None:
    """
    Clears the chat history for a specific user (for reassessment).
    """
    table = _get_table()
    now = datetime.now(timezone.utc).isoformat()
    
    table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET chat_history = :empty, updated_at = :now",
        ExpressionAttributeValues={
            ":empty": [],
            ":now": now
        }
    )
    logger.info(f"Cleared chat history for user {user_id}")


def reset_assessment(user_id: str) -> None:
    """
    Completely resets a user's assessment data for retaking the assessment.
    Clears: profile_assessment, chat_history, session_id, preferred_language
    Keeps: name, created_at, profile_picture, vision_upload_history, user_id
    
    Note: Old root-level fields (skill, skill_rating, theory_score, intent, gender, 
    preferred_location) are also cleared for backward compatibility.
    """
    table = _get_table()
    now = datetime.now(timezone.utc).isoformat()
    
    table.update_item(
        Key={"user_id": user_id},
        UpdateExpression=(
            "SET skill = :empty_str, "
            "skill_rating = :zero, "
            "theory_score = :zero, "
            "intent = :default_intent, "
            "chat_history = :empty_list, "
            "updated_at = :now "
            "REMOVE session_id, profile_assessment, gender, preferred_location, preferred_language"
        ),
        ExpressionAttributeValues={
            ":empty_str": "",
            ":zero": 0,
            ":default_intent": "job",
            ":empty_list": [],
            ":now": now
        }
    )
    logger.info(f"Reset assessment data for user {user_id}")

