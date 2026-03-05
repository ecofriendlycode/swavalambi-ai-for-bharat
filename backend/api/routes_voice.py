"""
routes_voice.py — Voice API endpoints for speech-to-text and text-to-speech
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from pydantic import BaseModel
from services.voice_service import get_voice_service
from agents.profiling_agent import ProfilingAgent
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory agent sessions (shared with routes_chat.py)
_agent_sessions = {}


class SynthesizeRequest(BaseModel):
    text: str
    language: str = "hi-IN"
    voice_id: Optional[str] = None


class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "auto"
    target_lang: str = "en"


@router.post("/transcribe", summary="Transcribe audio to text")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form("hi-IN"),
    user_id: Optional[str] = Form(None),
):
    """
    Transcribe audio file to text using AWS Transcribe or Sarvam AI
    
    Supported languages:
    - hi-IN: Hindi
    - ta-IN: Tamil
    - te-IN: Telugu
    - mr-IN: Marathi
    - kn-IN: Kannada (Sarvam only)
    - ml-IN: Malayalam (Sarvam only)
    - bn-IN: Bengali (Sarvam only)
    - gu-IN: Gujarati (Sarvam only)
    """
    try:
        # Read audio file
        audio_bytes = await audio.read()
        
        # Validate file size (max 10MB)
        if len(audio_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Audio file too large (max 10MB)")
        
        # Get audio format from filename
        audio_format = audio.filename.split(".")[-1].lower()
        if audio_format not in ["wav", "mp3", "webm", "ogg"]:
            audio_format = "wav"  # Default
        
        # Transcribe
        voice_service = get_voice_service()
        result = voice_service.transcribe(
            audio_bytes=audio_bytes,
            language_code=language,
            audio_format=audio_format
        )
        
        logger.info("Transcribed audio for user %s: %s...", user_id, result['text'][:50])
        
        return result
        
    except Exception as e:
        logger.error("Transcription failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@router.post("/synthesize", summary="Convert text to speech")
async def synthesize_speech(request: SynthesizeRequest):
    """
    Convert text to speech using AWS Polly or Sarvam AI
    
    Returns base64-encoded audio
    """
    try:
        voice_service = get_voice_service()
        result = voice_service.synthesize(
            text=request.text,
            language_code=request.language,
            voice_id=request.voice_id
        )
        
        logger.info("Synthesized speech: %s...", request.text[:50])
        
        return result
        
    except Exception as e:
        logger.error("Synthesis failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")


@router.post("/translate", summary="Translate text between languages")
async def translate_text(request: TranslateRequest):
    """
    Translate text using AWS Translate or Sarvam AI
    """
    try:
        voice_service = get_voice_service()
        result = voice_service.translate(
            text=request.text,
            source_lang=request.source_lang,
            target_lang=request.target_lang
        )
        
        logger.info("Translated: %s -> %s", request.source_lang, request.target_lang)
        
        return result
        
    except Exception as e:
        logger.error("Translation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")


@router.post("/chat", summary="Voice chat with AI assistant")
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    user_id: Optional[str] = Form(None),
    language: str = Form("hi-IN"),
):
    """
    Complete voice chat flow:
    1. Transcribe user's audio to text
    2. Send transcribed text directly to AI agent (LLM handles multilingual conversation)
    3. Get response from AI agent in user's language
    4. Synthesize response to speech
    
    Returns both text and audio response
    
    Note: Translation layer removed - Claude LLM handles multilingual conversation natively
    """
    try:
        # Step 1: Transcribe audio
        audio_bytes = await audio.read()
        audio_format = audio.filename.split(".")[-1].lower()
        if audio_format not in ["wav", "mp3", "webm", "ogg"]:
            audio_format = "wav"
        
        voice_service = get_voice_service()
        transcription = voice_service.transcribe(
            audio_bytes=audio_bytes,
            language_code=language,
            audio_format=audio_format
        )
        
        user_text = transcription["text"]
        logger.info("User said (%s): %s", language, user_text)
        
        # Step 3: Get AI response
        is_new_session = session_id not in _agent_sessions
        
        if is_new_session:
            # Get user's preferred language and name
            preferred_language = language  # Use voice language as default
            user_name = ""
            
            if user_id:
                try:
                    from services.dynamodb_service import get_user
                    user_data = get_user(user_id)
                    if user_data:
                        if "preferred_language" in user_data:
                            preferred_language = user_data["preferred_language"]
                        if "name" in user_data:
                            user_name = user_data["name"]
                except Exception as e:
                    logger.warning("Failed to get user preferences: %s", e)
            
            # Create agent with preferred language
            _agent_sessions[session_id] = ProfilingAgent(
                session_id=session_id,
                user_name=user_name,
                preferred_language=preferred_language
            )
            
            # Restore chat history if user_id is provided
            chat_restored = False
            if user_id:
                try:
                    from services.dynamodb_service import get_user
                    user = get_user(user_id)
                    if user and "chat_history" in user and user["chat_history"]:
                        chat_history = user["chat_history"]
                        restored_messages = []
                        for msg in chat_history:
                            restored_messages.append({
                                "role": msg["role"],
                                "content": [{"text": msg["content"]}]
                            })
                        _agent_sessions[session_id].agent.messages = restored_messages
                        logger.info("Restored %d messages from DynamoDB for voice chat %s", len(chat_history), user_id)
                        chat_restored = True
                except Exception as e:
                    logger.warning("Failed to restore chat history for voice: %s", e)
            
            # If this is a new session and no chat was restored, initialize with greeting
            if not chat_restored and user_id:
                try:
                    from services.dynamodb_service import update_chat_history
                    
                    # Multilingual greetings
                    greetings = {
                        "hi-IN": {
                            "with_name": f"नमस्ते, {user_name}! 😊 मैं आपका स्वावलंबी सहायक हूं। आइए आपकी प्रोफाइल बनाएं। आप किस तरह का काम करते हैं? (जैसे, **दर्जी**, **बढ़ई**, **प्लंबर**, **वेल्डर**, **ब्यूटीशियन**)",
                            "without_name": "नमस्ते! मैं आपका स्वावलंबी सहायक हूं। आइए आपकी प्रोफाइल बनाएं। बताइए, आप किस तरह का काम करते हैं? (जैसे, **दर्जी**, **बढ़ई**, **प्लंबर**, **वेल्डर**, **ब्यूटीशियन**)"
                        },
                        "te-IN": {
                            "with_name": f"నమస్తే, {user_name}! 😊 నేను మీ స్వావలంబి సహాయకుడిని. మీ ప్రొఫైల్ రూపొందించుకుందాం. మీరు ఏ రకమైన పని చేస్తారు? (ఉదా., **టైలర్**, **కార్పెంటర్**, **ప్లంబర్**, **వెల్డర్**, **బ్యూటీషియన్**)",
                            "without_name": "నమస్తే! నేను మీ స్వావలంబి సహాయకుడిని. మీ ప్రొఫైల్ రూపొందించుకుందాం. చెప్పండి, మీరు ఏ రకమైన పని చేస్తారు? (ఉదా., **టైలర్**, **కార్పెంటర్**, **ప్లంబర్**, **వెల్డర్**, **బ్యూటీషియన్**)"
                        },
                        "ta-IN": {
                            "with_name": f"வணக்கம், {user_name}! 😊 நான் உங்கள் ஸ்வாவலம்பி உதவியாளர். உங்கள் சுயவிவரத்தை உருவாக்குவோம். நீங்கள் என்ன வேலை செய்கிறீர்கள்? (எ.கா., **தையல்காரர்**, **தச்சர்**, **பிளம்பர்**, **வெல்டர்**, **அழகுக் கலைஞர்**)",
                            "without_name": "வணக்கம்! நான் உங்கள் ஸ்வாவலம்பி உதவியாளர். உங்கள் சுயவிவரத்தை உருவாக்குவோம். சொல்லுங்கள், நீங்கள் என்ன வேலை செய்கிறீர்கள்? (எ.கா., **தையல்காரர்**, **தச்சர்**, **பிளம்பர்**, **வெல்டர்**, **அழகுக் கலைஞர்**)"
                        },
                        "mr-IN": {
                            "with_name": f"नमस्कार, {user_name}! 😊 मी तुमचा स्वावलंबी सहाय्यक आहे. चला तुमचे प्रोफाइल तयार करूया. तुम्ही कोणत्या प्रकारचे काम करता? (उदा., **शिंपी**, **सुतार**, **प्लंबर**, **वेल्डर**, **ब्युटिशियन**)",
                            "without_name": "नमस्कार! मी तुमचा स्वावलंबी सहाय्यक आहे. चला तुमचे प्रोफाइल तयार करूया. सांगा, तुम्ही कोणत्या प्रकारचे काम करता? (उदा., **शिंपी**, **सुतार**, **प्लंबर**, **वेल्डर**, **ब्युटिशियन**)"
                        },
                        "kn-IN": {
                            "with_name": f"ನಮಸ್ಕಾರ, {user_name}! 😊 ನಾನು ನಿಮ್ಮ ಸ್ವಾವಲಂಬಿ ಸಹಾಯಕ. ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ ರಚಿಸೋಣ. ನೀವು ಯಾವ ರೀತಿಯ ಕೆಲಸ ಮಾಡುತ್ತೀರಿ? (ಉದಾ., **ಟೈಲರ್**, **ಬಡಗಿ**, **ಪ್ಲಂಬರ್**, **ವೆಲ್ಡರ್**, **ಬ್ಯೂಟಿಶಿಯನ್**)",
                            "without_name": "ನಮಸ್ಕಾರ! ನಾನು ನಿಮ್ಮ ಸ್ವಾವಲಂಬಿ ಸಹಾಯಕ. ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ ರಚಿಸೋಣ. ಹೇಳಿ, ನೀವು ಯಾವ ರೀತಿಯ ಕೆಲಸ ಮಾಡುತ್ತೀರಿ? (ಉದಾ., **ಟೈಲರ್**, **ಬಡಗಿ**, **ಪ್ಲಂಬರ್**, **ವೆಲ್ಡರ್**, **ಬ್ಯೂಟಿಶಿಯನ್**)"
                        },
                        "bn-IN": {
                            "with_name": f"নমস্কার, {user_name}! 😊 আমি আপনার স্বাবলম্বী সহায়ক। আসুন আপনার প্রোফাইল তৈরি করি। আপনি কী ধরনের কাজ করেন? (যেমন, **দর্জি**, **ছুতোর**, **প্লাম্বার**, **ওয়েল্ডার**, **বিউটিশিয়ান**)",
                            "without_name": "নমস্কার! আমি আপনার স্বাবলম্বী সহায়ক। আসুন আপনার প্রোফাইল তৈরি করি। বলুন, আপনি কী ধরনের কাজ করেন? (যেমন, **দর্জি**, **ছুতোর**, **প্লাম্বার**, **ওয়েল্ডার**, **বিউটিশিয়ান**)"
                        },
                        "gu-IN": {
                            "with_name": f"નમસ્તે, {user_name}! 😊 હું તમારો સ્વાવલંબી સહાયક છું. ચાલો તમારી પ્રોફાઇલ બનાવીએ. તમે કેવા પ્રકારનું કામ કરો છો? (દા.ત., **દરજી**, **સુથાર**, **પ્લમ્બર**, **વેલ્ડર**, **બ્યુટિશિયન**)",
                            "without_name": "નમસ્તે! હું તમારો સ્વાવલંબી સહાયક છું. ચાલો તમારી પ્રોફાઇલ બનાવીએ. કહો, તમે કેવા પ્રકારનું કામ કરો છો? (દા.ત., **દરજી**, **સુથાર**, **પ્લમ્બર**, **વેલ્ડર**, **બ્યુટિશિયન**)"
                        },
                        "ml-IN": {
                            "with_name": f"നമസ്കാരം, {user_name}! 😊 ഞാൻ നിങ്ങളുടെ സ്വാവലംബി സഹായകനാണ്. നിങ്ങളുടെ പ്രൊഫൈൽ സൃഷ്ടിക്കാം. നിങ്ങൾ ഏത് തരത്തിലുള്ള ജോലി ചെയ്യുന്നു? (ഉദാ., **ടെയിലർ**, **ആശാരി**, **പ്ലംബർ**, **വെൽഡർ**, **ബ്യൂട്ടീഷ്യൻ**)",
                            "without_name": "നമസ്കാരം! ഞാൻ നിങ്ങളുടെ സ്വാവലംബി സഹായകനാണ്. നിങ്ങളുടെ പ്രൊഫൈൽ സൃഷ്ടിക്കാം. പറയൂ, നിങ്ങൾ ഏത് തരത്തിലുള്ള ജോലി ചെയ്യുന്നു? (ഉദാ., **ടെയിലർ**, **ആശാരി**, **പ്ലംബർ**, **വെൽഡർ**, **ബ്യൂട്ടീഷ്യൻ**)"
                        },
                        "pa-IN": {
                            "with_name": f"ਸਤ ਸ੍ਰੀ ਅਕਾਲ, {user_name}! 😊 ਮੈਂ ਤੁਹਾਡਾ ਸਵਾਵਲੰਬੀ ਸਹਾਇਕ ਹਾਂ। ਆਓ ਤੁਹਾਡੀ ਪ੍ਰੋਫਾਈਲ ਬਣਾਈਏ। ਤੁਸੀਂ ਕਿਸ ਤਰ੍ਹਾਂ ਦਾ ਕੰਮ ਕਰਦੇ ਹੋ? (ਜਿਵੇਂ, **ਦਰਜ਼ੀ**, **ਤਰਖਾਣ**, **ਪਲੰਬਰ**, **ਵੈਲਡਰ**, **ਬਿਊਟੀਸ਼ੀਅਨ**)",
                            "without_name": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ ਤੁਹਾਡਾ ਸਵਾਵਲੰਬੀ ਸਹਾਇਕ ਹਾਂ। ਆਓ ਤੁਹਾਡੀ ਪ੍ਰੋਫਾਈਲ ਬਣਾਈਏ। ਦੱਸੋ, ਤੁਸੀਂ ਕਿਸ ਤਰ੍ਹਾਂ ਦਾ ਕੰਮ ਕਰਦੇ ਹੋ? (ਜਿਵੇਂ, **ਦਰਜ਼ੀ**, **ਤਰਖਾਣ**, **ਪਲੰਬਰ**, **ਵੈਲਡਰ**, **ਬਿਊਟੀਸ਼ੀਅਨ**)"
                        },
                        "en-IN": {
                            "with_name": f"Namaste, {user_name}! 😊 I'm your Swavalambi Assistant. Let's build your profile. What kind of work do you do? (e.g., **Tailor**, **Carpenter**, **Plumber**, **Welder**, **Beautician**)",
                            "without_name": "Namaste! I am your Swavalambi assistant. Let's build your profile. Tell me, what kind of work do you do? (e.g., **Tailor**, **Carpenter**, **Plumber**, **Welder**, **Beautician**)"
                        }
                    }
                    
                    # Get greeting in user's language
                    lang_greetings = greetings.get(preferred_language, greetings["en-IN"])
                    
                    # Check if user_name is valid (not empty, not a phone number)
                    if user_name and not user_name.isdigit() and len(user_name.strip()) > 1 and not user_name.startswith('+'):
                        greeting = lang_greetings["with_name"]
                    else:
                        greeting = lang_greetings["without_name"]
                    
                    # Initialize chat history with greeting
                    initial_chat = [{"role": "assistant", "content": greeting}]
                    update_chat_history(user_id, initial_chat)
                    logger.info("Initialized voice chat history with %s greeting for user %s", preferred_language, user_id)
                except Exception as e:
                    logger.warning("Failed to initialize voice chat greeting: %s", e)
                    
        agent = _agent_sessions[session_id]
        # Send user's original language text directly to LLM (no translation needed)
        result = agent.run(user_text)
        # LLM responds in user's language (based on system prompt and input language)
        response_text = result["response"]
        logger.info("Agent response (%s): %s...", language, response_text[:100])
        
        # Save chat history to DynamoDB if user_id is provided
        if user_id:
            try:
                from services.dynamodb_service import update_chat_history
                if hasattr(agent.agent, "messages") and agent.agent.messages:
                    raw_messages = agent.agent.messages
                    serialized_chat = []
                    
                    for msg in raw_messages:
                        role = None
                        content_str = ""
                        
                        if isinstance(msg, dict):
                            role = msg.get("role")
                            content = msg.get("content")
                        elif hasattr(msg, "role"):
                            role = msg.role
                            content = msg.content if hasattr(msg, "content") else None
                        else:
                            continue
                            
                        if not role:
                            continue
                            
                        if content is None:
                            content_str = ""
                        elif isinstance(content, str):
                            content_str = content
                        elif isinstance(content, list):
                            text_parts = []
                            for block in content:
                                if isinstance(block, str):
                                    text_parts.append(block)
                                elif isinstance(block, dict) and "text" in block:
                                    text_parts.append(str(block["text"]))
                                elif hasattr(block, "text"):
                                    text_parts.append(str(block.text))
                                elif hasattr(block, "__dict__") and "text" in block.__dict__:
                                    text_parts.append(str(block.__dict__["text"]))
                            content_str = " ".join(text_parts).strip()
                        else:
                            content_str = str(content)
                            
                        if content_str:
                            serialized_chat.append({
                                "role": role,
                                "content": content_str
                            })
                            
                    if serialized_chat:
                        update_chat_history(user_id, serialized_chat)
                        logger.info("Saved %d messages to DynamoDB for voice chat %s", len(serialized_chat), user_id)
            except Exception as e:
                logger.warning("Failed to persist voice chat history to DynamoDB: %s", e)
        
        # Save profile assessment data if complete
        if user_id and result.get("profile_data"):
            try:
                from services.dynamodb_service import save_profile_assessment
                save_profile_assessment(user_id, result["profile_data"])
                logger.info("Saved profile assessment for voice chat user %s", user_id)
            except Exception as e:
                logger.warning("Failed to save profile assessment: %s", e)
        
        # Step 4: Synthesize response to speech (response is already in user's language)
        synthesis = voice_service.synthesize(
            text=response_text,
            language_code=language
        )
        
        return {
            "transcribed_text": user_text,
            "response_text": response_text,
            "audio_base64": synthesis["audio_base64"],
            "audio_format": synthesis["audio_format"],
            "provider": transcription["provider"],
            "is_ready_for_photo": result.get("is_ready_for_photo", False),
            "is_complete": result.get("is_complete", False),
            "intent_extracted": result.get("intent_extracted"),
            "profession_skill_extracted": result.get("profession_skill_extracted"),
            "theory_score_extracted": result.get("theory_score_extracted"),
        }
        
    except Exception as e:
        logger.error("Voice chat failed: %s", e)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Voice chat failed: {str(e)}")
