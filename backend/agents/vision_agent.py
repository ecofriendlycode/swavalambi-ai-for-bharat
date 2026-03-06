import boto3
import json
import base64
import os
import anthropic

class VisionAgent:
    def __init__(self):
        # Check if we should use the direct Anthropic API or AWS Bedrock
        self.use_anthropic = os.getenv("USE_ANTHROPIC", "false").lower() == "true"
        
        if self.use_anthropic:
            self.model_id = os.getenv("ANTHROPIC_MODEL_ID", "claude-3-5-sonnet-latest")
            api_key = os.getenv("ANTHROPIC_API_KEY")
            
            # Using synchronous client as we're not in an async context here natively
            self.anthropic_client = anthropic.Anthropic(
                api_key=api_key,
            )
        else:
            # Initialize boto3 client for Bedrock using explicit credentials
            # Supports temporary credentials (AWS_SESSION_TOKEN) from STS/SSO
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                aws_session_token=os.getenv('AWS_SESSION_TOKEN'),
            )
            # Use the same model for vision — Claude Sonnet 4.5 supports vision
            self.model_id = os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0")


    def analyze_image(self, image_bytes: bytes, mime_type: str = "image/jpeg", skill: str = None, preferred_language: str = "en-IN") -> dict:
        """
        Sends an image to Claude (via Anthropic API or Bedrock) to evaluate the skill rating.
        Returns a dict with `vision_score` and `feedback`.
        """
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # Language instruction mapping
        language_instructions = {
            "hi-IN": "Respond in Hindi (हिंदी)",
            "te-IN": "Respond in Telugu (తెలుగు)",
            "ta-IN": "Respond in Tamil (தமிழ்)",
            "mr-IN": "Respond in Marathi (मराठी)",
            "kn-IN": "Respond in Kannada (ಕನ್ನಡ)",
            "bn-IN": "Respond in Bengali (বাংলা)",
            "gu-IN": "Respond in Gujarati (ગુજરાતી)",
            "ml-IN": "Respond in Malayalam (മലയാളം)",
            "pa-IN": "Respond in Punjabi (ਪੰਜਾਬੀ)",
            "en-IN": "Respond in English"
        }
        language_instruction = language_instructions.get(preferred_language, "Respond in English")
        
        # Skill-specific evaluation prompts
        skill_prompts = {
            "tailor": "Evaluate this tailoring work sample. Look for stitch quality, pattern alignment, finishing, fabric handling, and overall craftsmanship.",
            "carpenter": "Evaluate this carpentry work sample. Look for joint quality, surface finish, precision, structural integrity, and overall craftsmanship.",
            "plumber": "Evaluate this plumbing work sample. Look for installation neatness, pipe alignment, professional finish, proper connections, and overall workmanship.",
            "welder": "Evaluate this welding work sample. Look for weld bead quality, joint strength, surface finish, structural alignment, and overall craftsmanship.",
            "beautician": "Evaluate this beauty/makeup work sample. Look for application quality, color matching, blending, technique, and overall professional finish."
        }
        
        skill_context = skill_prompts.get(skill, "Evaluate this work sample for quality and craftsmanship.") if skill else "Evaluate this work sample for quality and craftsmanship."
        
        system_prompt = f"You are a master evaluator of {skill or 'professional'} skills and craftsmanship. Provide honest, constructive feedback. Output ONLY valid JSON, nothing else. {language_instruction}."
        
        prompt = f"""
        {skill_context}
        
        IMPORTANT: {language_instruction}. Write your feedback in the user's language.
        
        Provide a 'vision_score' between 1 and 5 indicating the quality of the work:
        1 = Beginner/Poor quality
        2 = Developing/Below average
        3 = Intermediate/Average
        4 = Advanced/Good quality
        5 = Expert/Excellent quality
        
        Also provide 'feedback' (2-3 sentences) explaining what you observe - be specific about strengths and areas for improvement.
        
        ⚠️ CRITICAL OUTPUT RULES - FOLLOW EXACTLY:
        1. Output ONLY valid JSON with exactly 2 fields: vision_score and feedback
        2. The feedback field should contain ONLY your assessment of the work quality
        3. DO NOT add any text before or after the JSON
        4. DO NOT mention: "Level", "assigned", "dashboard", "redirecting", "personalized"
        5. DO NOT add congratulations or next steps - ONLY evaluate the work shown
        6. Write feedback in {preferred_language.split('-')[0]} language
        7. Keep feedback focused on: technique, quality, craftsmanship, areas to improve
        
        CORRECT OUTPUT EXAMPLE:
        {{
            "vision_score": 4,
            "feedback": "The stitching shows good attention to detail and the fabric handling is neat. The seam alignment could be improved for a more professional finish."
        }}
        
        WRONG OUTPUT (DO NOT DO THIS):
        {{
            "vision_score": 4,
            "feedback": "Great work! You have been assigned Level 4. Redirecting you to your dashboard..."
        }}
        
        Now evaluate the work sample and output ONLY the JSON.
        """

        try:
            if self.use_anthropic:
                # Format for direct Anthropic API
                # Anthropic API uses base64 encoding with media_type
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime_type,
                                    "data": base64_image
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
                
                message = self.anthropic_client.messages.create(
                    model=self.model_id,
                    system=system_prompt,
                    messages=messages,
                    max_tokens=1000,
                    temperature=0.7
                )
                output_text = message.content[0].text
                
            else:
                # Format for AWS Bedrock Converse API
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": {
                                    "format": mime_type.split('/')[-1], # e.g. "jpeg", "png"
                                    "source": {
                                        "bytes": image_bytes
                                    }
                                }
                            },
                            {
                                "text": prompt
                            }
                        ]
                    }
                ]
                
                # Note: Converse API is recommended for Claude 3 on Bedrock
                response = self.bedrock_client.converse(
                    modelId=self.model_id,
                    messages=messages,
                    system=[{"text": system_prompt}]
                )
                
                output_text = response['output']['message']['content'][0]['text']
            
            # Extract JSON block
            json_str = output_text[output_text.find("{"):output_text.rfind("}")+1]
            result = json.loads(json_str)
            
            # Clean up feedback - remove any unwanted text
            feedback = result.get("feedback", "No feedback provided.")
            
            # Remove any mentions of "Level X", "dashboard", "redirecting", etc.
            import re
            # Remove "You have been assigned Level X"
            feedback = re.sub(r'You have been assigned\s+Level\s+\d+\.?\s*', '', feedback, flags=re.IGNORECASE)
            # Remove standalone "Level X"
            feedback = re.sub(r'Level\s+\d+\.?\s*', '', feedback, flags=re.IGNORECASE)
            # Remove "Redirecting you to your personalized dashboard"
            feedback = re.sub(r'Redirecting you to your personalized dashboard\.?\s*', '', feedback, flags=re.IGNORECASE)
            feedback = re.sub(r'Redirecting you to.*?dashboard.*?\.?\s*', '', feedback, flags=re.IGNORECASE)
            feedback = re.sub(r'Redirecting.*?\.?\s*', '', feedback, flags=re.IGNORECASE)
            # Remove extra whitespace
            feedback = re.sub(r'\s+', ' ', feedback).strip()
            
            return {
                "vision_score": result.get("vision_score", 1),
                "feedback": feedback
            }
            
        except Exception as e:
            print(f"Error calling Vision API ({'Anthropic' if self.use_anthropic else 'Bedrock'}): {e}")
            import traceback
            traceback.print_exc()
            # Fallback mock for MVP if API fails
            return {
                "vision_score": 3,
                "feedback": "Fallback score. Unable to process image due to internal error."
            }
