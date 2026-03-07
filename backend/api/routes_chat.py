from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from schemas.models import ChatRequest, ChatResponse
from agents.profiling_agent import ProfilingAgent
from services.dynamodb_service import update_chat_history
from common.agent_sessions import get_agent_session, set_agent_session, has_agent_session
import warnings
import os
import json

# Suppress Pydantic serialization warnings for Strands message objects
# These warnings occur because Strands uses complex internal message structures
# but we're already converting everything to simple types (str, bool, int)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.main")

router = APIRouter()

@router.post("/chat-profile", response_model=ChatResponse, summary="AI Gateway chat using Strands")
async def chat_profile(request: ChatRequest):
    """
    Pass the user message to the ProfilingAgent to extract intent and theory score.
    Uses Strands framework underneath to maintain memory context based on session_id.
    """
    # Retrieve or create agent session
    is_new_session = not has_agent_session(request.session_id)
    
    if is_new_session:
        # Get user's preferred language
        preferred_language = "en-IN"  # default
        if request.user_id:
            try:
                from services.dynamodb_service import get_user
                user_data = get_user(request.user_id)
                if user_data and "preferred_language" in user_data:
                    preferred_language = user_data["preferred_language"]
            except Exception as e:
                print(f"[WARN] Failed to get preferred language: {e}")
        
        set_agent_session(request.session_id, ProfilingAgent(
            session_id=request.session_id,
            user_name=request.user_name or "",
            preferred_language=preferred_language
        ))
        
        # If user_id is provided, try to restore previous chat history
        chat_restored = False
        if request.user_id:
            try:
                from services.dynamodb_service import get_user
                user = get_user(request.user_id)
                if user and "chat_history" in user and user["chat_history"]:
                    # Restore the agent's memory with previous messages
                    chat_history = user["chat_history"]
                    # Convert to Strands message format
                    restored_messages = []
                    for msg in chat_history:
                        restored_messages.append({
                            "role": msg["role"],
                            "content": [{"text": msg["content"]}]
                        })
                    # Set the agent's messages
                    get_agent_session(request.session_id).agent.messages = restored_messages
                    print(f"[INFO] Restored {len(chat_history)} messages from DynamoDB for user {request.user_id}")
                    chat_restored = True
            except Exception as e:
                print(f"[WARN] Failed to restore chat history: {e}")
        
        # If this is a new session and no chat was restored, initialize with greeting
        # Generate greeting based on user's preferred language
        if not chat_restored and request.user_id:
            try:
                from services.dynamodb_service import get_user
                user_data = get_user(request.user_id)
                preferred_language = user_data.get("preferred_language", "hi-IN") if user_data else "hi-IN"
                user_name = request.user_name or ""
                
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
                update_chat_history(request.user_id, initial_chat)
                print(f"[INFO] Initialized chat history with {preferred_language} greeting for user {request.user_id}")
                
                # CRITICAL: Also seed the greeting into agent.messages so it is
                # included in every subsequent DynamoDB save (not just the first one)
                get_agent_session(request.session_id).agent.messages = [
                    {"role": "assistant", "content": [{"text": greeting}]}
                ]
                print(f"[INFO] Seeded greeting into agent.messages to prevent overwrite")
            except Exception as e:
                print(f"[WARN] Failed to initialize chat history: {e}")
        
    agent = get_agent_session(request.session_id)
    
    try:
        # Get response from the Strands LLM
        result = agent.run(request.message)
        
        # Save chat history to DynamoDB if user_id is provided
        if request.user_id:
            try:
                print(f"[DEBUG] Attempting to save chat history for user {request.user_id}")
                # Strands Agent stores conversation history in agent.messages
                if hasattr(agent.agent, "messages") and agent.agent.messages:
                    raw_messages = agent.agent.messages
                    print(f"[DEBUG] Found {len(raw_messages)} raw messages in agent.messages")
                    # Serialize messages for DynamoDB storage
                    serialized_chat = []
                    
                    for idx, msg in enumerate(raw_messages):
                        role = None
                        content_str = ""
                        
                        print(f"[DEBUG] Processing message {idx}: type={type(msg)}")
                        
                        # Extract role
                        if isinstance(msg, dict):
                            role = msg.get("role")
                            content = msg.get("content")
                        elif hasattr(msg, "role"):
                            role = msg.role
                            content = msg.content if hasattr(msg, "content") else None
                        else:
                            print(f"[DEBUG] Message {idx} has no role attribute, skipping")
                            continue
                        
                        if not role:
                            print(f"[DEBUG] Message {idx} has empty role, skipping")
                            continue
                        
                        print(f"[DEBUG] Message {idx} role={role}, content type={type(content)}")
                        
                        # Extract text from content (handle various formats)
                        if content is None:
                            content_str = ""
                        elif isinstance(content, str):
                            content_str = content
                        elif isinstance(content, list):
                            # Handle list of content blocks
                            text_parts = []
                            for block in content:
                                # Try different ways to extract text
                                if isinstance(block, str):
                                    text_parts.append(block)
                                elif isinstance(block, dict):
                                    if "text" in block:
                                        text_parts.append(str(block["text"]))
                                elif hasattr(block, "text"):
                                    text_parts.append(str(block.text))
                                elif hasattr(block, "__dict__") and "text" in block.__dict__:
                                    text_parts.append(str(block.__dict__["text"]))
                            content_str = " ".join(text_parts).strip()
                        else:
                            # Fallback: convert to string
                            content_str = str(content)
                        
                        print(f"[DEBUG] Message {idx} extracted content length: {len(content_str)}")
                        
                        # IMPORTANT: Strip out PROFILE_DATA markers before saving to chat history
                        # These markers are for backend parsing only and should not be shown to users
                        if "PROFILE_DATA_START" in content_str and "PROFILE_DATA_END" in content_str:
                            print(f"[DEBUG] Found PROFILE_DATA markers in message {idx}, stripping them out")
                            start_marker = "PROFILE_DATA_START"
                            end_marker = "PROFILE_DATA_END"
                            start_idx = content_str.find(start_marker)
                            end_idx = content_str.find(end_marker) + len(end_marker)
                            
                            # Remove everything from start_marker to end_marker (inclusive)
                            content_before = content_str[:start_idx].strip()
                            content_after = content_str[end_idx:].strip()
                            
                            # Combine the parts, keeping only the user-facing message
                            content_str = (content_before + "\n\n" + content_after).strip()
                            print(f"[DEBUG] Stripped PROFILE_DATA, new content length: {len(content_str)}")
                        
                        if content_str:  # Only add if we have content
                            serialized_chat.append({
                                "role": role,
                                "content": content_str
                            })
                    
                    print(f"[DEBUG] Serialized {len(serialized_chat)} messages")
                    
                    if serialized_chat:
                        update_chat_history(request.user_id, serialized_chat)
                        print(f"[INFO] Saved {len(serialized_chat)} messages to DynamoDB for user {request.user_id}")
                    else:
                        print(f"[WARN] No messages to save - serialized_chat is empty")
                else:
                    print(f"[WARN] Agent has no messages attribute or messages is empty")
            except Exception as e:
                print(f"[WARN] Failed to persist chat history to DynamoDB: {e}")
                import traceback
                traceback.print_exc()
        
        # Save profile assessment data if complete
        if request.user_id and result.get("profile_data"):
            try:
                print(f"[INFO] Profile data detected, saving to DynamoDB...")
                print(f"[INFO] Profile data content: {result['profile_data']}")
                from services.dynamodb_service import save_profile_assessment
                save_profile_assessment(request.user_id, result["profile_data"])
                print(f"[INFO] Successfully saved profile assessment for user {request.user_id}")
            except Exception as e:
                print(f"[ERROR] Failed to save profile assessment: {e}")
                import traceback
                traceback.print_exc()
        else:
            if request.user_id:
                print(f"[DEBUG] No profile_data in result for user {request.user_id}. Result keys: {result.keys()}")
                
        # Return response - ensure all values are JSON-serializable
        # Create a clean response object with explicit type conversion
        return ChatResponse(
            response=str(result.get("response", "")),
            is_ready_for_photo=bool(result.get("is_ready_for_photo", False)),
            is_complete=bool(result.get("is_complete", False)),
            intent_extracted=str(result["intent_extracted"]) if result.get("intent_extracted") else None,
            profession_skill_extracted=str(result["profession_skill_extracted"]) if result.get("profession_skill_extracted") else None,
            theory_score_extracted=int(result["theory_score_extracted"]) if result.get("theory_score_extracted") is not None else None,
            gender_extracted=str(result["gender_extracted"]) if result.get("gender_extracted") else None,
            location_extracted=str(result["location_extracted"]) if result.get("location_extracted") else None,
        )
    except Exception as e:
        print(f"Agent error: {e}")
        raise HTTPException(status_code=500, detail="Failed to communicate with AI Gateway.")


@router.post("/chat-profile-stream", summary="Streaming AI chat using Server-Sent Events")
async def chat_profile_stream(request: ChatRequest):
    """
    Streaming version of chat-profile endpoint.
    Returns Server-Sent Events (SSE) stream of LLM response chunks.
    
    Enable/disable with ENABLE_STREAMING environment variable.
    """
    # Check if streaming is enabled
    enable_streaming = os.getenv("ENABLE_STREAMING", "false").lower() == "true"
    
    if not enable_streaming:
        # Fallback to non-streaming endpoint
        return await chat_profile(request)
    
    # Retrieve or create agent session (same as non-streaming)
    is_new_session = not has_agent_session(request.session_id)
    
    if is_new_session:
        # Get user's preferred language
        preferred_language = "en-IN"
        if request.user_id:
            try:
                from services.dynamodb_service import get_user
                user_data = get_user(request.user_id)
                if user_data and "preferred_language" in user_data:
                    preferred_language = user_data["preferred_language"]
            except Exception as e:
                print(f"[WARN] Failed to get preferred language: {e}")
        
        set_agent_session(request.session_id, ProfilingAgent(
            session_id=request.session_id,
            user_name=request.user_name or "",
            preferred_language=preferred_language
        ))
        
        # Restore chat history if available
        chat_restored = False
        if request.user_id:
            try:
                from services.dynamodb_service import get_user
                user = get_user(request.user_id)
                if user and "chat_history" in user and user["chat_history"]:
                    chat_history = user["chat_history"]
                    restored_messages = []
                    for msg in chat_history:
                        restored_messages.append({
                            "role": msg["role"],
                            "content": [{"text": msg["content"]}]
                        })
                    get_agent_session(request.session_id).agent.messages = restored_messages
                    print(f"[INFO] Restored {len(chat_history)} messages for streaming session")
                    chat_restored = True
            except Exception as e:
                print(f"[WARN] Failed to restore chat history: {e}")
        
        # Initialize greeting if needed (same as non-streaming)
        if not chat_restored and request.user_id:
            try:
                from services.dynamodb_service import get_user, update_chat_history
                user_data = get_user(request.user_id)
                preferred_language = user_data.get("preferred_language", "hi-IN") if user_data else "hi-IN"
                user_name = request.user_name or ""
                
                # Multilingual greetings (same as non-streaming)
                greetings = {
                    "hi-IN": {
                        "with_name": f"नमस्ते, {user_name}! 😊 मैं आपका स्वावलंबी सहायक हूं। आइए आपकी प्रोफाइल बनाएं। आप किस तरह का काम करते हैं? (जैसे, **दर्जी**, **बढ़ई**, **प्लंबर**, **वेल्डर**, **ब्यूटीशियन**)",
                        "without_name": "नमस्ते! मैं आपका स्वावलंबी सहायक हूं। आइए आपकी प्रोफाइल बनाएं। बताइए, आप किस तरह का काम करते हैं? (जैसे, **दर्जी**, **बढ़ई**, **प्लंबर**, **वेल्डर**, **ब्यूटीशियन**)"
                    },
                    "te-IN": {
                        "with_name": f"నమస్తే, {user_name}! 😊 నేను మీ స్వావలంబి సహాయకుడిని. మీ ప్రొఫైల్ రూపొందించుకుందాం. మీరు ఏ రకమైన పని చేస్తారు? (ఉదా., **టైలర్**, **కార్పెంటర్**, **ప్లంబర్**, **వెల్డర్**, **బ్యూటీషియన్**)",
                        "without_name": "నమస్తే! నేను మీ స్వావలంబి సహాయకుడిని. మీ ప్రొఫైల్ రూపొందించుకుందాం. చెప్పండి, మీరు ఏ రకమైన పని చేస్తారు? (ఉదా., **టైలర్**, **కార్పెంటర్**, **ప్లంబర్**, **వెల్డర్**, **బ్యూటీషియన్**)"
                    },
                    # Add other languages as needed...
                    "en-IN": {
                        "with_name": f"Namaste, {user_name}! 😊 I'm your Swavalambi Assistant. Let's build your profile. What kind of work do you do? (e.g., **Tailor**, **Carpenter**, **Plumber**, **Welder**, **Beautician**)",
                        "without_name": "Namaste! I am your Swavalambi assistant. Let's build your profile. Tell me, what kind of work do you do? (e.g., **Tailor**, **Carpenter**, **Plumber**, **Welder**, **Beautician**)"
                    }
                }
                
                lang_greetings = greetings.get(preferred_language, greetings["en-IN"])
                if user_name and not user_name.isdigit() and len(user_name.strip()) > 1 and not user_name.startswith('+'):
                    greeting = lang_greetings["with_name"]
                else:
                    greeting = lang_greetings["without_name"]
                
                initial_chat = [{"role": "assistant", "content": greeting}]
                update_chat_history(request.user_id, initial_chat)
                print(f"[INFO] Initialized streaming chat with {preferred_language} greeting")
                
                # CRITICAL: Seed greeting into agent.messages to prevent overwrite on first save
                get_agent_session(request.session_id).agent.messages = [
                    {"role": "assistant", "content": [{"text": greeting}]}
                ]
                print(f"[INFO] Seeded greeting into streaming agent.messages")
            except Exception as e:
                print(f"[WARN] Failed to initialize greeting: {e}")
    
    agent = get_agent_session(request.session_id)
    
    # Generator function for SSE streaming
    async def generate_stream():
        try:
            full_response = ""
            
            # Stream chunks from agent
            async for chunk in agent.run_stream(request.message):
                full_response += chunk
                
                # Send chunk as SSE
                yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
            
            # Process complete response for metadata
            result = agent._process_response(full_response)
            
            # Save chat history
            if request.user_id:
                try:
                    from services.dynamodb_service import update_chat_history as save_history
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
                                content_str = " ".join(text_parts).strip()
                            else:
                                content_str = str(content)
                            
                            # Strip PROFILE_DATA markers
                            if "PROFILE_DATA_START" in content_str and "PROFILE_DATA_END" in content_str:
                                start_marker = "PROFILE_DATA_START"
                                end_marker = "PROFILE_DATA_END"
                                start_idx = content_str.find(start_marker)
                                end_idx = content_str.find(end_marker) + len(end_marker)
                                content_before = content_str[:start_idx].strip()
                                content_after = content_str[end_idx:].strip()
                                content_str = (content_before + "\n\n" + content_after).strip()
                            
                            if content_str:
                                serialized_chat.append({
                                    "role": role,
                                    "content": content_str
                                })
                        
                        if serialized_chat:
                            save_history(request.user_id, serialized_chat)
                            print(f"[INFO] Saved {len(serialized_chat)} messages to DynamoDB")
                except Exception as e:
                    print(f"[WARN] Failed to save chat history: {e}")
            
            # Save profile assessment if complete
            if request.user_id and result.get("profile_data"):
                try:
                    from services.dynamodb_service import save_profile_assessment
                    save_profile_assessment(request.user_id, result["profile_data"])
                    print(f"[INFO] Saved profile assessment for user {request.user_id}")
                except Exception as e:
                    print(f"[ERROR] Failed to save profile assessment: {e}")
            
            # Send final metadata
            final_data = {
                "chunk": "",
                "done": True,
                "is_ready_for_photo": result.get("is_ready_for_photo", False),
                "is_complete": result.get("is_complete", False),
                "intent_extracted": result.get("intent_extracted"),
                "profession_skill_extracted": result.get("profession_skill_extracted"),
                "theory_score_extracted": result.get("theory_score_extracted"),
                "gender_extracted": result.get("gender_extracted"),
                "location_extracted": result.get("location_extracted"),
            }
            yield f"data: {json.dumps(final_data)}\n\n"
            
        except Exception as e:
            print(f"[ERROR] Streaming error: {e}")
            error_data = {"error": str(e), "done": True}
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
