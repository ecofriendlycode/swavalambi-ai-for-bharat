import os
import boto3
import uuid

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from schemas.models import VisionScoreResponse
from agents.vision_agent import VisionAgent
from services.dynamodb_service import save_assessment, get_user, update_chat_history

router = APIRouter()
_vision_agent = None

def get_vision_agent():
    global _vision_agent
    if _vision_agent is None:
        _vision_agent = VisionAgent()
    return _vision_agent

@router.post("/analyze-vision", response_model=VisionScoreResponse, summary="Analyze uploaded work sample using Bedrock Vision")
async def analyze_vision(
    session_id: str = Form(...),
    photo: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    skill: Optional[str] = Form(None),
    intent: Optional[str] = Form(None),
    theory_score: Optional[int] = Form(None),
):
    content = await photo.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    mime_type = photo.content_type or "image/jpeg"
    result = get_vision_agent().analyze_image(content, mime_type)
    vision_score = result["vision_score"]
    
    if theory_score is not None and theory_score > 0:
        final_skill_rating = round((theory_score * 0.4) + (vision_score * 0.6))
        final_skill_rating = max(1, min(5, final_skill_rating))
    else:
        final_skill_rating = vision_score

    # Persist assessment to DynamoDB if we have a user_id
    if user_id:
        try:
            save_assessment(
                user_id=user_id,
                skill=skill or "",
                intent=intent or "job",
                skill_rating=final_skill_rating,
                theory_score=theory_score or 0,
                session_id=session_id,
            )
        except Exception as e:
            print(f"[WARN] DynamoDB save_assessment failed (non-fatal): {e}")
            
        try:
            # Upload photo to S3
            session = boto3.Session(
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
                region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            )
            s3_client = session.client("s3")
            bucket_name = os.getenv("AWS_S3_BUCKET", "swavalambi-voice")
            
            file_ext = photo.filename.split(".")[-1] if photo.filename else "jpg"
            file_key = f"work-samples/{user_id}/{uuid.uuid4().hex}.{file_ext}"
            
            s3_client.put_object(
                Bucket=bucket_name,
                Key=file_key,
                Body=content,
                ContentType=mime_type
            )
            
            s3_url = f"https://{bucket_name}.s3.amazonaws.com/{file_key}"
            
            # Update chat history with photo upload and AI response
            user_record = get_user(user_id)
            if user_record:
                chat_history = user_record.get("chat_history", [])
                
                chat_history.append({
                    "role": "user",
                    "content": "Uploaded work sample",
                    "imagePreviewUrl": s3_url
                })
                chat_history.append({
                    "role": "assistant",
                    "content": f"I've analyzed your work! {result['feedback']} You have been assigned **Level {final_skill_rating}**."
                })
                
                update_chat_history(user_id, chat_history)
        except Exception as e:
            print(f"[WARN] Failed to upload photo or update chat history: {e}")

    return VisionScoreResponse(
        vision_score=vision_score,
        skill_rating=final_skill_rating,
        feedback=result["feedback"]
    )

