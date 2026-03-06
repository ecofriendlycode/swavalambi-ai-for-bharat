from strands import Agent
from strands.models import BedrockModel, AnthropicModel
import boto3
import os
import json

# Supported skills - limited to these 5 only
SUPPORTED_SKILLS = {
    "tailor": ["tailor", "tailoring", "sewing", "stitching", "garment"],
    "carpenter": ["carpenter", "carpentry", "wood", "woodwork", "woodworking"],
    "plumber": ["plumber", "plumbing"],
    "welder": ["welder", "welding", "weld"],
    "beautician": ["beautician", "beauty", "makeup", "hair", "salon", "cosmetology"]
}

# Skill-specific questions based on job market analysis
SKILL_QUESTIONS = {
    "tailor": {
        "specialization": "What type of tailoring work do you do? (**Men's wear**, **Women's wear**, **Alterations**, **Custom design**, **All types**)",
        "fabric_skills": "Which fabrics can you work with? (**Cotton/basic**, **Silk/delicate**, **Synthetic**, **All fabrics**)",
        "equipment": "Do you have your own sewing machine? (**Yes, own equipment**, **No, need workplace equipment**)",
        "work_setting": "What work setting do you prefer? (**Factory/garment unit**, **Boutique/shop**, **Home-based**, **Any setting**)",
    },
    "carpenter": {
        "specialization": "What type of carpentry work do you specialize in? (**Furniture making**, **Door/window fitting**, **Interior woodwork**, **Kitchen cabinets**, **All types**)",
        "tools": "Do you have your own carpentry tools? (**Yes, complete tools**, **Yes, basic tools**, **No, need workplace tools**)",
        "materials": "What materials can you work with? (**Wood (teak/pine)**, **Laminate/veneer**, **MDF/particle board**, **All materials**)",
        "work_type": "What projects do you prefer? (**Residential**, **Commercial**, **Both**)",
    },
    "plumber": {
        "specialization": "What type of plumbing work are you experienced in? (**Pipe fitting**, **Bathroom/kitchen installation**, **Repairs/maintenance**, **Drainage systems**, **All types**)",
        "work_setting": "What type of work do you prefer? (**Residential**, **Commercial**, **Both**)",
        "tools": "Do you have your own plumbing tools? (**Yes, complete tools**, **Yes, basic tools**, **No, need workplace tools**)",
        "skills": "Can you handle? (**Water supply systems**, **Sanitary fittings**, **Drainage systems**, **All of the above**)",
    },
    "welder": {
        "techniques": "What welding techniques do you know? (**Arc welding**, **Gas welding**, **MIG welding**, **TIG welding**, **Multiple techniques**)",
        "materials": "What materials can you weld? (**Mild steel**, **Stainless steel**, **Aluminum**, **All metals**)",
        "work_type": "What type of welding work do you do? (**Fabrication**, **Structural**, **Pipe welding**, **Repair/maintenance**, **All types**)",
        "certification": "Do you have welding certifications? (**Yes, certified**, **No, but experienced**)",
    },
    "beautician": {
        "services": "What beauty services can you provide? (**Hair cutting/styling**, **Makeup (daily/party)**, **Bridal makeup**, **Skincare/facials**, **Nail art**, **All services**)",
        "specialization": "Do you have any special skills? (**Bridal makeup**, **Hair coloring**, **Skin treatment**, **General beautician**)",
        "work_setting": "Where do you prefer to work? (**Beauty salon/parlor**, **Spa/wellness center**, **Freelance/home service**, **Any setting**)",
        "certification": "Do you have beauty course certification? (**Yes, certified**, **No, but experienced**)",
    }
}

def normalize_skill(skill_input: str) -> str:
    """
    Normalize user skill input to one of the 5 supported skills.
    Returns the normalized skill or the original input if no match.
    """
    if not skill_input:
        return skill_input
    
    skill_lower = skill_input.lower().strip()
    
    # Check each supported skill and its variations
    for canonical_skill, variations in SUPPORTED_SKILLS.items():
        if skill_lower in variations or any(var in skill_lower for var in variations):
            return canonical_skill
    
    # Return original if no match (agent will handle guiding user)
    return skill_input

class ProfilingAgent:
    def __init__(self, session_id: str, user_name: str = "", preferred_language: str = "en-IN"):
        self.session_id = session_id
        self.preferred_language = preferred_language
        
        # Build a boto3 session for Bedrock models
        self.boto3_session = boto3.Session(
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        )
        
        # Check if we should use the direct Anthropic API or AWS Bedrock
        self.use_anthropic = os.getenv("USE_ANTHROPIC", "false").lower() == "true"
        
        # Initialize primary model (Claude)
        if self.use_anthropic:
            model_id = os.getenv("ANTHROPIC_MODEL_ID", "claude-3-5-sonnet-latest")
            api_key = os.getenv("ANTHROPIC_API_KEY")
            
            self.primary_model = AnthropicModel(
                model_id=model_id,
                max_tokens=1000,
                params={"temperature": 0.7},
                client_args={"api_key": api_key}
            )
        else:
            model_id = os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0")
            
            self.primary_model = BedrockModel(
                model_id=model_id,
                temperature=0.7,
                boto_session=self.boto3_session,
            )
        
        # Initialize fallback model (Amazon Nova)
        fallback_model_id = os.getenv("FALLBACK_MODEL_ID", "us.amazon.nova-lite-v1:0")
        self.fallback_model = BedrockModel(
            model_id=fallback_model_id,
            temperature=0.7,
            boto_session=self.boto3_session,
        )

        # Build user-context preamble if name is known
        if user_name and not user_name.isdigit() and len(user_name.strip()) > 1:
            known_user_context = (
                f"\n\n        IMPORTANT USER CONTEXT: The user's name is already known — it is '{user_name}'. "
                f"You MUST NOT ask for their name again. Address them as '{user_name}' naturally in conversation. "
                f"Skip the name-collection step and go directly to asking about their profession/skill.\n"
            )
        else:
            known_user_context = ""

        # Language mapping for instruction
        language_names = {
            "hi-IN": "Hindi (हिंदी)",
            "te-IN": "Telugu (తెలుగు)",
            "ta-IN": "Tamil (தமிழ்)",
            "mr-IN": "Marathi (मराठी)",
            "kn-IN": "Kannada (ಕನ್ನಡ)",
            "bn-IN": "Bengali (বাংলা)",
            "gu-IN": "Gujarati (ગુજરાતી)",
            "ml-IN": "Malayalam (മലയാളം)",
            "pa-IN": "Punjabi (ਪੰਜਾਬੀ)",
            "en-IN": "English"
        }
        user_language = language_names.get(preferred_language, "English")

        self.system_prompt = f"""
        You are 'Swavalambi Assistant', a supportive, friendly, and encouraging AI profiler for skilled workers and artisans in India.
        Your goal is to have a natural, engaging conversation to build a comprehensive profile. Extract the following information:
        {known_user_context}
        
        CRITICAL - LANGUAGE INSTRUCTION:
        The user's preferred language is {user_language} ({preferred_language}).
        You MUST respond in {user_language} throughout the entire conversation.
        Reply in the same language the user speaks to you.
        
        IMPORTANT - SUPPORTED SKILLS ONLY:
        We ONLY support these 5 skills: **Tailor**, **Carpenter**, **Plumber**, **Welder**, **Beautician**
        If the user mentions any other profession, politely guide them to choose one of these 5 skills.
        
        CONVERSATION FLOW:
        
        1. **Profession & Demographics**: 
           - Greet warmly and ask what kind of work they do from our supported skills
           - Infer their gender based on their name, or lightly ask them
        
        2. **Intent**: Ask what brings them to the platform:
           - "**job**" (Looking for employment opportunities)
           - "**upskill**" (Want to learn and improve their skills)
           - "**loan**" (Want to start a business or explore government schemes)
        
        3. **Location** (ONLY if intent = "job"):
           - Ask: "Which city or state are you looking for work in?"
           - Popular cities: **Bangalore**, **Mumbai**, **Delhi**, **Kolkata**, **Chennai**, **Any location**
           - If they say "any" or "anywhere", set preferred_location to ""
           - Skip this entirely for upskill/loan intents
        
        4. **Experience**: 
           - Ask: "How many years of experience do you have in [their skill]?"
           - This helps assess their level.
           - ⚠️ CRITICAL: When the user answers with a number (e.g., "2", "5"), ALWAYS interpret it as years of experience, NOT as an option number from a previous list.
        
        5. **Skill-Specific Questions** (Ask 2-3 based on their profession):
           
           FOR TAILORS:
           - Specialization: "What type of tailoring work do you do? (**Men's wear**, **Women's wear**, **Alterations**, **Custom design**, **All types**)"
           - Fabric skills: "Which fabrics can you work with? (**Cotton/basic**, **Silk/delicate**, **Synthetic**, **All fabrics**)"
           - Equipment: "Do you have your own sewing machine? (**Yes**, **No**)"
           
           FOR CARPENTERS:
           - Specialization: "What type of carpentry work do you do? (**Furniture making**, **Door/window fitting**, **Interior woodwork**, **All types**)"
           - Tools: "Do you have your own carpentry tools? (**Yes, complete tools**, **Yes, basic tools**, **No**)"
           - Materials: "What materials can you work with? (**Wood**, **Laminate**, **MDF**, **All materials**)"
           
           FOR PLUMBERS:
           - Specialization: "What plumbing work are you experienced in? (**Pipe fitting**, **Bathroom/kitchen**, **Repairs**, **All types**)"
           - Work setting: "Do you prefer **Residential** or **Commercial** work, or **Both**?"
           - Tools: "Do you have your own plumbing tools? (**Yes**, **No**)"
           
           FOR WELDERS:
           - Techniques: "What welding techniques do you know? (**Arc welding**, **Gas welding**, **MIG**, **TIG**, **Multiple**)"
           - Materials: "What materials can you weld? (**Mild steel**, **Stainless steel**, **Aluminum**, **All metals**)"
           - Certification: "Do you have welding certifications? (**Yes, certified**, **No, but experienced**)"
           
           FOR BEAUTICIANS:
           - Services: "What beauty services can you provide? (**Hair cutting**, **Makeup**, **Bridal makeup**, **Skincare**, **All services**)"
           - Specialization: "Any special skills? (**Bridal makeup**, **Hair coloring**, **Skin treatment**, **General**)"
           - Work setting: "Where do you prefer to work? (**Salon**, **Spa**, **Freelance**, **Any**)"
        
        6. **Skill Level Assessment**:
           Based on their experience and answers, assess:
           - **Beginner (1-2)**: Less than 2 years, basic tasks, needs supervision
           - **Intermediate (3-4)**: 2-5 years, handles variety independently, some complex work
           - **Advanced (5)**: 5+ years, expert-level, trains others, complex projects
        
        7. **Salary Expectations** (ONLY if intent = "job"):
           - Ask: "What monthly salary are you expecting?"
           - Typical ranges: Tailor ₹15-40k, Carpenter ₹15-30k, Plumber ₹18-35k, Welder ₹18-30k, Beautician ₹15-35k
        
        8. **Conclude / Work Sample Prompt**:
           ⚠️ CRITICAL: You MUST ALWAYS output the PROFILE_DATA_START/END JSON block for ALL users.
           This is MANDATORY regardless of intent (job/upskill/loan) or skill level (beginner/intermediate/advanced).
           
           - For **beginners** (theory_score 1-2): 
             * Output JSON with is_ready_for_photo: false
             * Add encouraging message about learning and growth opportunities
             * DO NOT ask for work sample photo
             * Example: "Great! Your profile is ready. We'll help you find learning opportunities to grow your skills! 🌱"
           
           - For **intermediate/advanced** (theory_score 3-5):
             * Output JSON with is_ready_for_photo: true
             * Ask them to upload a photo of their WORK (not personal photo)
             * Skill-specific examples:
               - Tailor: "Photo of clothes you've stitched"
               - Carpenter: "Photo of furniture or woodwork you've made"
               - Plumber: "Photo of plumbing installation you've done"
               - Welder: "Photo of welded items or structures"
               - Beautician: "Photo of makeup/hair styling work you've done"
        
        CONVERSATION STYLE:
        - Keep responses short (1-2 sentences per turn)
        - Be warm, encouraging, and conversational
        - Ask ONE question at a time
        - Show genuine interest in their work
        - Use emojis sparingly (1-2 per message max)
        - Reply in the same language the user speaks
        
        IMPORTANT - OPTION FORMATTING & INTERPRETATION:
        1. When presenting options, ALWAYS use **bold text** (double asterisks) to make them clickable.
           Example: "Are you looking for **job opportunities**, wanting to **improve your skills**, or interested in **starting a business**?"
        2. DO NOT use numbered lists (1., 2., 3.) for options. This causes confusion when asking for numeric answers (like years of experience or salary).
        3. If the user replies with a number right after you asked for experience, treat it purely as years of experience. Never retroactively apply a number to a previous multiple-choice question.
        
        CRITICAL - PROFILE OUTPUT RULES:
        ⚠️ MANDATORY: You MUST ALWAYS output the JSON profile when you have gathered ALL required information.
        ⚠️ This applies to ALL intents (job/upskill/loan) and ALL skill levels (beginner/intermediate/advanced).
        ⚠️ Even for beginners who want to upskill, you MUST output the profile JSON.
        
        When you have gathered ALL information, output the JSON profile in this EXACT format:
        
        PROFILE_DATA_START
        {{
            "profession_skill": "tailor",
            "intent": "job",
            "theory_score": 4,
            "years_experience": 3,
            "work_type": "women's wear tailoring, custom stitching",
            "specialization": "women's wear, silk fabrics",
            "has_own_tools": true,
            "has_training": true,
            "is_ready_for_photo": true,
            "gender": "female",
            "preferred_location": "Mumbai",
            "salary_expectation": "25000-35000"
        }}
        PROFILE_DATA_END
        
        FIELD REQUIREMENTS BY INTENT:
        - For intent="job": Include preferred_location and salary_expectation
        - For intent="upskill" or "loan": Set preferred_location="" and salary_expectation=""
        
        ⚠️ CRITICAL - USER-FACING MESSAGE RULES:
        After outputting the JSON, add a SHORT message in the user's language ({user_language}):
        
        - If is_ready_for_photo is true: 
          * Ask them to upload a WORK SAMPLE photo (their actual work, not personal photo)
          * Keep it simple and encouraging
          * Example (Hindi): "बहुत बढ़िया! अब अपने काम की एक फोटो अपलोड करें। 📸"
          * Example (Telugu): "చాలా బాగుంది! ఇప్పుడు మీ పని యొక్క ఫోటో అప్‌లోడ్ చేయండి। 📸"
        
        - If is_ready_for_photo is false:
          * Add a warm, encouraging message about learning opportunities
          * Example (Hindi): "बहुत अच्छा! हम आपको सीखने के अवसर खोजने में मदद करेंगे। 🌱"
          * Example (Telugu): "చాలా బాగుంది! మేము మీకు నేర్చుకునే అవకాశాలను కనుగొనడంలో సహాయం చేస్తాము। 🌱"
        
        ⚠️ DO NOT MENTION:
        - "Level 5" or any level numbers
        - "Redirecting to dashboard"
        - "You have been assigned"
        - Any English text if user's language is not English
        - Technical terms like "theory_score" or "profile_data"
        
        Keep the message SHORT (1-2 sentences), WARM, and in the USER'S LANGUAGE.
        
        SCORING RULES:
        - theory_score: 1-2 (beginner), 3-4 (intermediate), 5 (advanced)
        - years_experience: Actual number of years they mentioned
        - work_type: Brief summary of what they do
        - specialization: Specific area within their skill
        - has_own_tools: true if they have equipment (for carpenter/plumber/welder/tailor)
        - has_training: true if they mentioned any formal training/certification
        - is_ready_for_photo: true ONLY for intermediate/advanced (theory_score >= 3)
        - gender: "male", "female", or "other"
        - preferred_location: city/state if intent=job, empty "" if intent=upskill/loan or "any"
        - salary_expectation: "min-max" range if intent=job, empty "" otherwise
        """

        # Initialize the Strands Agent with the primary model (Claude)
        self.agent = Agent(
            system_prompt=self.system_prompt,
            model=self.primary_model,
        )
        
        # Initialize fallback agent with Nova model
        self.fallback_agent = Agent(
            system_prompt=self.system_prompt,
            model=self.fallback_model,
        )

    def run(self, user_message: str) -> dict:
        """
        Runs the conversational agent with the user's latest message.
        Uses the correct Strands API: agent(prompt) returns a response object.
        Automatically falls back to Amazon Nova if Claude fails.
        """
        response_text = None
        used_fallback = False
        
        # Try primary model (Claude) first
        try:
            print(f"[INFO] Attempting with primary model (Claude)...")
            response = self.agent(user_message)
            response_text = str(response)
            print(f"[INFO] Primary model succeeded")
        except Exception as e:
            print(f"[WARN] Primary model (Claude) failed: {e}")
            print(f"[INFO] Falling back to Amazon Nova...")
            
            # Fallback to Nova model
            try:
                # Sync conversation history from primary to fallback agent
                if hasattr(self.agent, "messages") and self.agent.messages:
                    self.fallback_agent.messages = self.agent.messages.copy()
                
                response = self.fallback_agent(user_message)
                response_text = str(response)
                used_fallback = True
                print(f"[INFO] Fallback model (Nova) succeeded")
                
                # Sync back to primary agent for next turn
                if hasattr(self.fallback_agent, "messages"):
                    self.agent.messages = self.fallback_agent.messages.copy()
                    
            except Exception as fallback_error:
                print(f"[ERROR] Fallback model (Nova) also failed: {fallback_error}")
                raise Exception(f"Both primary and fallback models failed. Primary: {e}, Fallback: {fallback_error}")
        
        if not response_text:
            raise Exception("No response generated from any model")

        return self._process_response(response_text)
    
    async def run_stream(self, user_message: str):
        """
        Streams the conversational agent response using Strands streaming.
        Yields chunks of text as they arrive from the LLM.
        
        Filters out PROFILE_DATA markers and JSON only when they appear,
        otherwise streams normally for fast UI updates.
        
        Stores the complete unfiltered response in self.last_full_response
        for profile data extraction.
        
        Uses Strands' stream_async() method for async streaming.
        """
        try:
            print(f"[INFO] Starting streaming response with Strands...")
            
            full_response = ""
            markers_detected = False
            buffer = ""  # Buffer to check for "PROFILE" before yielding
            
            # Use Strands' stream_async() method for async streaming
            async for event in self.agent.stream_async(user_message):
                # Extract text from "data" field in events
                if "data" in event:
                    chunk_text = event["data"]
                    full_response += chunk_text
                    
                    # If markers already detected, just buffer (don't stream)
                    if markers_detected:
                        continue
                    
                    # Add to buffer
                    buffer += chunk_text
                    
                    # Check if buffer contains start of "PROFILE"
                    if "PROFILE" in buffer:
                        markers_detected = True
                        # Remove "PROFILE" and everything after from buffer
                        clean_buffer = buffer[:buffer.find("PROFILE")]
                        if clean_buffer:
                            yield clean_buffer
                        buffer = ""
                        print(f"[INFO] Profile markers detected, stopping stream to UI")
                        continue
                    
                    # If buffer is getting long without "PROFILE", yield it
                    # Keep last 10 chars in buffer to catch "PROFILE" across chunks
                    if len(buffer) > 10:
                        yield_text = buffer[:-10]
                        yield yield_text
                        buffer = buffer[-10:]
                
            # Yield any remaining buffer (if no markers detected)
            if not markers_detected and buffer:
                yield buffer
            
            # Store the complete unfiltered response for profile extraction
            self.last_full_response = full_response
                
            print(f"[INFO] Streaming complete, total length: {len(full_response)}")
            
            # If profile markers were found, yield the clean message after markers
            if markers_detected and "PROFILE_DATA_END" in full_response:
                end_marker = "PROFILE_DATA_END"
                end_idx = full_response.find(end_marker) + len(end_marker)
                text_after = full_response[end_idx:].strip()
                
                # Yield the message after markers (photo request or closing)
                if text_after:
                    print(f"[INFO] Yielding text after markers: {text_after[:100]}")
                    yield "\n\n" + text_after
            
        except Exception as e:
            print(f"[ERROR] Streaming failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback to non-streaming
            print("[INFO] Falling back to non-streaming")
            response = self.agent(user_message)
            self.last_full_response = str(response)
            yield str(response)
            yield str(response)
    
    def _process_response(self, response_text: str) -> dict:
        """
        Process the complete response text and extract profile data if present.
        """
        # Check if the LLM outputted the final JSON profile with markers
        if "PROFILE_DATA_START" in response_text and "PROFILE_DATA_END" in response_text:
            try:
                print(f"[INFO] Found profile data markers in response")
                # Extract JSON between markers
                start_marker = "PROFILE_DATA_START"
                end_marker = "PROFILE_DATA_END"
                start_idx = response_text.find(start_marker) + len(start_marker)
                end_idx = response_text.find(end_marker)
                json_str = response_text[start_idx:end_idx].strip()
                
                print(f"[INFO] Extracted JSON string: {json_str}")
                profile = json.loads(json_str)
                print(f"[INFO] Parsed profile data: {profile}")
                
                # Normalize the profession_skill to one of the 5 supported skills
                if "profession_skill" in profile:
                    original_skill = profile["profession_skill"]
                    normalized_skill = normalize_skill(original_skill)
                    profile["profession_skill"] = normalized_skill
                    if original_skill != normalized_skill:
                        print(f"[INFO] Normalized skill from '{original_skill}' to '{normalized_skill}'")
                
                is_ready = profile.get("is_ready_for_photo", False)
                
                # CRITICAL FIX: Remove the profile data markers from the response
                # Extract text before markers (if any)
                text_before_markers = response_text[:response_text.find(start_marker)].strip()
                
                # Extract any message after the JSON markers (photo request or closing)
                message_after_json = response_text[end_idx + len(end_marker):].strip()
                
                # Combine text before and after markers, excluding the markers themselves
                clean_response = (text_before_markers + "\n\n" + message_after_json).strip()
                
                # Use the cleaned message from LLM if present, otherwise use default
                if clean_response:
                    final_response = clean_response
                elif is_ready:
                    # Skill-specific work sample message
                    skill = profile.get("profession_skill", "")
                    work_sample_examples = {
                        "tailor": "clothes you've stitched or tailored",
                        "carpenter": "furniture or woodwork you've made",
                        "plumber": "plumbing installation or repair work you've done",
                        "welder": "welded items, structures, or fabrication work",
                        "beautician": "makeup or hair styling work you've done"
                    }
                    example = work_sample_examples.get(skill, "your work")
                    final_response = f"Great! Now please upload a photo of {example}. This will help us assess your skills and match you with better opportunities. 📸"
                else:
                    final_response = "Thank you! Your profile information has been successfully saved. We look forward to helping you grow!"
                
                print(f"[INFO] Returning profile_data with {len(profile)} fields")
                return {
                    "response": final_response,
                    "is_ready_for_photo": is_ready,
                    "is_complete": not is_ready,
                    "intent_extracted": profile.get("intent"),
                    "profession_skill_extracted": profile.get("profession_skill"),
                    "theory_score_extracted": profile.get("theory_score"),
                    "gender_extracted": profile.get("gender"),
                    "location_extracted": profile.get("preferred_location") or None,
                    "profile_data": profile,  # Pass the complete profile for storage
                }
            except Exception as e:
                print(f"[ERROR] Failed to parse profile JSON: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[DEBUG] No profile markers found in response. Response preview: {response_text[:200]}")

        # Normal conversational turn
        return {
            "response": response_text,
            "is_ready_for_photo": False,
            "is_complete": False,
            "intent_extracted": None,
            "profession_skill_extracted": None,
            "theory_score_extracted": None,
            "gender_extracted": None,
            "location_extracted": None,
            "profile_data": None,
        }
