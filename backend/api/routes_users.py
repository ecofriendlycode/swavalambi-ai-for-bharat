"""
routes_users.py — User registration and profile retrieval.

POST /api/users/register  → upsert user in DynamoDB, return user_id
GET  /api/users/{user_id} → fetch full profile from DynamoDB
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging
from schemas.models import UserRegisterRequest, UserRegisterResponse
from services.dynamodb_service import create_or_update_user, get_user, clear_chat_history, delete_user, reset_assessment
from services.cognito_service import admin_delete_user, COGNITO_ENABLED

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/register", response_model=UserRegisterResponse, summary="Register or update a user")
async def register_user(req: UserRegisterRequest):
    """
    Creates a new user or updates the name of an existing one.
    Called when the user verifies their OTP on the Login page.
    """
    try:
        result = create_or_update_user(user_id=req.phone, name=req.name)
        return UserRegisterResponse(user_id=result["user_id"], name=result["name"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register user: {e}")


@router.get("/{user_id}", summary="Get user profile from DynamoDB")
async def get_user_profile(user_id: str):
    """
    Returns the full user profile (name, skill, rating, intent) for the given user_id.
    Frontend uses this to populate the Profile page.
    """
    try:
        user = get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Extract data from profile_assessment (new structure)
        if "profile_assessment" in user and isinstance(user["profile_assessment"], dict):
            profile_assessment = user["profile_assessment"]
            
            # Use work_sample_score if available, otherwise theory_score
            user["skill_rating"] = profile_assessment.get("work_sample_score") or profile_assessment.get("theory_score", 0)
            user["skill"] = profile_assessment.get("profession_skill", "")
            user["intent"] = profile_assessment.get("intent", "job")
        else:
            # No profile assessment yet - set defaults
            user["skill_rating"] = 0
            user["skill"] = user.get("skill", "")
            user["intent"] = user.get("intent", "job")
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch user: {e}")


@router.delete("/{user_id}", summary="Delete a user from DynamoDB (and optionally Cognito)")
async def delete_user_endpoint(
    user_id: str,
    email: Optional[str] = Query(None, description="User's email to also delete from Cognito")
):
    """
    Deletes a user from DynamoDB. If an email is provided, also removes them from Cognito.
    Use this when a user registered via email/password (Cognito) and you want to fully reset them.
    """
    try:
        # Delete from DynamoDB (warn if not found but don't block)
        user = get_user(user_id)
        if user:
            delete_user(user_id)

        # Optionally delete from Cognito
        cognito_result = None
        if email and COGNITO_ENABLED:
            try:
                admin_delete_user(email)
                cognito_result = f"Also deleted '{email}' from Cognito"
            except Exception as e:
                cognito_result = f"DynamoDB deleted, but Cognito delete failed: {e}"

        return {
            "message": f"User '{user_id}' deleted from DynamoDB",
            "cognito": cognito_result or "Cognito not touched (no email provided)",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {e}")


@router.get("/{user_id}/chat-history", summary="Get user's chat history")
async def get_user_chat_history(user_id: str):
    """
    Returns just the chat_history field for the given user_id.
    Used by the Assistant page to restore previous conversations.
    Automatically regenerates fresh presigned S3 URLs for any work sample photos.
    """
    import boto3, os
    try:
        user = get_user(user_id)
        if not user:
            return {"chat_history": []}
        
        chat_history = user.get("chat_history", [])
        
        # Regenerate fresh presigned URLs for any messages with S3 keys
        has_s3_images = any(msg.get("s3Key") for msg in chat_history)
        if has_s3_images:
            try:
                session = boto3.Session(
                    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
                    region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
                )
                s3_client = session.client("s3")
                
                for msg in chat_history:
                    if msg.get("s3Key") and msg.get("s3Bucket"):
                        # Regenerate a fresh 7-day presigned URL
                        msg["imagePreviewUrl"] = s3_client.generate_presigned_url(
                            "get_object",
                            Params={"Bucket": msg["s3Bucket"], "Key": msg["s3Key"]},
                            ExpiresIn=604800
                        )
            except Exception as e:
                print(f"[WARN] Failed to regenerate presigned URLs: {e}")
        
        return {"chat_history": chat_history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch chat history: {e}")


@router.post("/{user_id}/chat-history", summary="Update user's chat history")
async def update_user_chat_history(user_id: str, request: dict):
    """
    Updates the chat history for the given user_id.
    Used to save greeting message or update conversation history.
    
    Request body:
    {
        "chat_history": [
            {"role": "assistant", "content": "greeting message"},
            {"role": "user", "content": "user message"},
            ...
        ]
    }
    """
    try:
        from services.dynamodb_service import update_chat_history
        
        chat_history = request.get("chat_history", [])
        if not isinstance(chat_history, list):
            raise HTTPException(status_code=400, detail="chat_history must be a list")
        
        update_chat_history(user_id, chat_history)
        logger.info(f"Updated chat history for user {user_id} with {len(chat_history)} messages")
        
        return {
            "message": "Chat history updated successfully",
            "user_id": user_id,
            "message_count": len(chat_history)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update chat history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update chat history: {e}")


@router.delete("/{user_id}/chat-history", summary="Clear user's chat history")
async def clear_user_chat_history(user_id: str):
    """
    Clears the chat history for the given user_id.
    Used when user clicks "Retake Assessment" to start fresh.
    """
    try:
        clear_chat_history(user_id)
        return {"message": "Chat history cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {e}")


@router.post("/{user_id}/reset-assessment", summary="Reset user's assessment data")
async def reset_user_assessment(user_id: str):
    """
    Completely resets a user's assessment data for retaking the assessment.
    Clears: skill, skill_rating, theory_score, intent, chat_history, session_id
    Keeps: name, created_at, profile_picture, vision_upload_history
    """
    try:
        reset_assessment(user_id)
        return {
            "message": "Assessment data reset successfully",
            "reset_fields": [
                "skill",
                "skill_rating",
                "theory_score",
                "intent",
                "chat_history",
                "session_id"
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset assessment: {e}")


@router.put("/{user_id}/preferences", summary="Update user preferences")
async def update_preferences(
    user_id: str,
    language: Optional[str] = None,
    voice_autoplay: Optional[bool] = None
):
    """
    Update user preferences like language and voice auto-play settings.
    
    Query parameters:
    - language: Language code (e.g., 'hi-IN', 'te-IN', 'ta-IN')
    - voice_autoplay: Whether voice auto-play is enabled (true/false)
    """
    try:
        from services.dynamodb_service import update_user_preferences
        
        # Validate user exists
        user = get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update preferences
        update_user_preferences(user_id, language=language, voice_autoplay=voice_autoplay)
        
        return {
            "message": "Preferences updated successfully",
            "user_id": user_id,
            "language": language,
            "voice_autoplay": voice_autoplay
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update preferences: {e}")


@router.delete("/{user_id}/account", summary="Delete user account and all associated data")
async def delete_account(user_id: str):
    """
    Permanently deletes a user account and all associated data:
    - User profile from DynamoDB
    - Chat history
    - Profile picture from S3
    - Work sample images from S3
    - Cognito account (if user_id is an email)
    
    This action is irreversible.
    """
    try:
        from services.s3_service import S3Service
        
        # Get user data before deletion
        user = get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        s3_service = S3Service()
        deletion_summary = {
            "user_id": user_id,
            "deleted_items": []
        }
        
        # Delete profile picture from S3
        if user.get("profile_picture"):
            try:
                s3_service.delete_profile_picture(user["profile_picture"])
                deletion_summary["deleted_items"].append("profile_picture")
            except Exception as e:
                logger.warning(f"Failed to delete profile picture: {e}")
        
        # Delete work sample images from S3 (from chat history)
        chat_history = user.get("chat_history", [])
        deleted_images = 0
        for msg in chat_history:
            if msg.get("s3Key") and msg.get("s3Bucket"):
                try:
                    s3_url = f"https://{msg['s3Bucket']}.s3.amazonaws.com/{msg['s3Key']}"
                    s3_service.delete_profile_picture(s3_url)  # Reuse the delete method
                    deleted_images += 1
                except Exception as e:
                    logger.warning(f"Failed to delete work sample image: {e}")
        
        if deleted_images > 0:
            deletion_summary["deleted_items"].append(f"{deleted_images}_work_sample_images")
        
        # Delete from Cognito if user_id is an email (contains @)
        # For Cognito users, user_id IS the email
        if "@" in user_id and COGNITO_ENABLED:
            try:
                admin_delete_user(user_id)  # user_id is the email
                deletion_summary["deleted_items"].append("cognito_account")
                logger.info(f"Deleted Cognito account for {user_id}")
            except Exception as e:
                logger.warning(f"Failed to delete from Cognito: {e}")
        
        # Delete from DynamoDB (this also clears chat history)
        delete_user(user_id)
        deletion_summary["deleted_items"].append("dynamodb_profile")
        deletion_summary["deleted_items"].append("chat_history")
        
        return {
            "message": "Account deleted successfully",
            "details": deletion_summary
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete account: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {e}")
