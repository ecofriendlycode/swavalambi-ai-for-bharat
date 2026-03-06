"""
voice_service.py — Voice services with AWS and Sarvam AI providers

Supports:
- Speech-to-Text (Transcribe / Sarvam Saaras)
- Text-to-Speech (Polly / Sarvam Bulbul)
- Text-to-Speech Streaming (Sarvam Bulbul WebSocket)
- Translation (AWS Translate / Sarvam Mayura)
"""

import boto3
import os
import requests
import base64
import json
import asyncio
import re
from typing import Optional, Dict, Any, AsyncGenerator
from enum import Enum
from sarvamai import AsyncSarvamAI, AudioOutput, EventResponse


def clean_text_for_tts(text: str) -> str:
    """
    Clean text for TTS by removing markdown formatting, emojis, and special characters.
    
    Removes:
    - Markdown bold (**text**)
    - Markdown italic (*text*)
    - Emojis and emoticons
    - Forward slashes (/)
    - Backslashes (\\)
    - Extra whitespace
    
    Args:
        text: Raw text with markdown and emojis
    
    Returns:
        Cleaned text suitable for TTS
    """
    if not text:
        return ""
    
    # Remove markdown bold (**text**)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    
    # Remove markdown italic (*text*)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    
    # Remove forward slashes and backslashes
    text = text.replace('/', ' ')
    text = text.replace('\\', ' ')
    
    # Remove emojis (Unicode emoji ranges)
    # This covers most common emojis
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # extended symbols
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    
    # Remove extra whitespace (including multiple spaces created by slash removal)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


class VoiceProvider(Enum):
    AWS = "aws"
    SARVAM = "sarvam"


class VoiceService:
    def __init__(self):
        self.provider = VoiceProvider(os.getenv("VOICE_PROVIDER", "aws"))
        self.fallback_enabled = os.getenv("VOICE_FALLBACK_ENABLED", "true").lower() == "true"
        self._init_aws()
        self._init_sarvam()
    
    def _init_aws(self):
        """Initialize AWS clients"""
        session = boto3.Session(
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        )
        self.transcribe_client = session.client("transcribe")
        self.polly_client = session.client("polly")
        self.translate_client = session.client("translate")
        self.s3_client = session.client("s3")
    
    def _init_sarvam(self):
        """Initialize Sarvam AI configuration"""
        self.sarvam_api_key = os.getenv("SARVAM_API_KEY")
        self.sarvam_base_url = "https://api.sarvam.ai"
        # Initialize async client for streaming TTS
        self.sarvam_async_client = None
    
    def _get_async_sarvam_client(self):
        """Get or create async Sarvam client"""
        if self.sarvam_async_client is None:
            self.sarvam_async_client = AsyncSarvamAI(
                api_subscription_key=self.sarvam_api_key
            )
        return self.sarvam_async_client
    
    async def synthesize_stream(
        self,
        text_stream: AsyncGenerator[str, None],
        language_code: str = "hi-IN"
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream text-to-speech using Sarvam's WebSocket streaming API.
        
        Args:
            text_stream: Async generator yielding text chunks from LLM
            language_code: Language code (e.g., 'hi-IN', 'te-IN')
        
        Yields:
            Audio bytes chunks as they're generated
        """
        from sarvamai import EventResponse
        
        client = self._get_async_sarvam_client()
        
        # Get speaker from .env based on language
        # Extract language code (e.g., 'hi' from 'hi-IN')
        lang_code = language_code.split('-')[0].upper()
        env_key = f"SARVAM_TTS_SPEAKER_{lang_code}"
        speaker = os.getenv(env_key, os.getenv("SARVAM_TTS_SPEAKER", "shubh"))
        
        # Collect all text first (Sarvam works best with complete text)
        full_text = ""
        try:
            async for text_chunk in text_stream:
                if text_chunk:
                    full_text += text_chunk
        except Exception as e:
            print(f"[ERROR] Failed to collect text from LLM: {e}")
        
        if not full_text:
            print("[WARN] No text to synthesize")
            return
        
        # Clean text before TTS (remove markdown and emojis)
        cleaned_text = clean_text_for_tts(full_text)
        
        # Use send_completion_event=True to get proper stream termination
        try:
            async with client.text_to_speech_streaming.connect(
                model="bulbul:v3",
                send_completion_event=True
            ) as ws:
                # Configure the WebSocket
                await ws.configure(
                    target_language_code=language_code,
                    speaker=speaker
                )
                
                # Send complete cleaned text (Sarvam's recommended approach)
                await ws.convert(cleaned_text)
                print(f"[INFO] Sent {len(cleaned_text)} chars to Sarvam TTS with speaker: {speaker} (lang: {language_code})")
                
                # Flush to signal end of text
                await ws.flush()
                print(f"[INFO] Flushed text buffer")
                
                # Receive and yield audio chunks as they arrive
                chunk_count = 0
                async for message in ws:
                    if isinstance(message, AudioOutput):
                        chunk_count += 1
                        audio_chunk = base64.b64decode(message.data.audio)
                        yield audio_chunk
                    elif isinstance(message, EventResponse):
                        # Check for completion event
                        if message.data.event_type == "final":
                            print(f"[INFO] Received TTS completion event after {chunk_count} chunks")
                            break
                            
        except Exception as e:
            print(f"[ERROR] TTS streaming failed: {e}")
            import traceback
            traceback.print_exc()
    
    def transcribe(
        self,
        audio_bytes: bytes,
        language_code: str = "hi-IN",
        audio_format: str = "wav"
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text
        
        Args:
            audio_bytes: Audio file bytes
            language_code: Language code (e.g., 'hi-IN', 'ta-IN')
            audio_format: Audio format ('wav', 'mp3', 'webm')
        
        Returns:
            {
                "text": "transcribed text",
                "language": "hi-IN",
                "confidence": 0.95,
                "provider": "aws"
            }
        """
        try:
            if self.provider == VoiceProvider.AWS:
                return self._transcribe_aws(audio_bytes, language_code, audio_format)
            else:
                return self._transcribe_sarvam(audio_bytes, language_code)
        except Exception as e:
            print(f"[ERROR] Transcription failed with {self.provider.value}: {e}")
            if not self.fallback_enabled:
                raise
            # Fallback to other provider
            if self.provider == VoiceProvider.AWS:
                print("[INFO] Falling back to Sarvam AI")
                return self._transcribe_sarvam(audio_bytes, language_code)
            else:
                print("[INFO] Falling back to AWS")
                return self._transcribe_aws(audio_bytes, language_code, audio_format)
    
    def _transcribe_aws(
        self,
        audio_bytes: bytes,
        language_code: str,
        audio_format: str
    ) -> Dict[str, Any]:
        """Transcribe using AWS Transcribe"""
        # AWS Transcribe requires S3 upload for batch processing
        # For real-time, we'd use StartStreamTranscription
        # For MVP, using synchronous approach with temp S3 upload
        
        bucket_name = os.getenv("AWS_S3_BUCKET", "swavalambi-voice-temp")
        file_key = f"temp/{os.urandom(16).hex()}.{audio_format}"
        
        # Upload to S3
        self.s3_client.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=audio_bytes
        )
        
        job_name = f"transcribe-{os.urandom(8).hex()}"
        file_uri = f"s3://{bucket_name}/{file_key}"
        
        # Start transcription job
        self.transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": file_uri},
            MediaFormat=audio_format,
            LanguageCode=language_code
        )
        
        # Wait for completion (in production, use async/webhook)
        import time
        while True:
            status = self.transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            job_status = status["TranscriptionJob"]["TranscriptionJobStatus"]
            
            if job_status in ["COMPLETED", "FAILED"]:
                break
            time.sleep(1)
        
        # Clean up S3
        self.s3_client.delete_object(Bucket=bucket_name, Key=file_key)
        
        if job_status == "FAILED":
            raise Exception("Transcription job failed")
        
        # Get transcript
        transcript_uri = status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        transcript_response = requests.get(transcript_uri)
        transcript_data = transcript_response.json()
        
        text = transcript_data["results"]["transcripts"][0]["transcript"]
        confidence = transcript_data["results"]["items"][0].get("alternatives", [{}])[0].get("confidence", 0.0)
        
        return {
            "text": text,
            "language": language_code,
            "confidence": float(confidence),
            "provider": "aws"
        }
    
    def _transcribe_sarvam(
        self,
        audio_bytes: bytes,
        language_code: str
    ) -> Dict[str, Any]:
        """
        Transcribe using Sarvam AI Saaras v3
        
        Explicitly sets language_code to prevent auto-detection errors.
        Uses 'codemix' mode for natural code-switching (English + Indic).
        """
        url = f"{self.sarvam_base_url}/speech-to-text"
        headers = {
            "api-subscription-key": self.sarvam_api_key,
        }
        
        print(f"[INFO] Transcribing audio with language: {language_code}")
        
        files = {
            "file": ("audio.wav", audio_bytes, "audio/wav")
        }
        data = {
            "model": os.getenv("SARVAM_STT_MODEL", "saaras:v3"),
            "language_code": language_code,  # ✅ Force specific language (no auto-detection)
            "mode": "codemix",  # ✅ Handle code-switching (English words + Indic script)
        }

        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()

        result = response.json()
        detected_lang = result.get("language_code", language_code)
        transcript = result.get("transcript", "")
        
        print(f"[INFO] Transcription complete: {transcript[:100]}")
        print(f"[INFO] Language: {detected_lang}")

        return {
            "text": transcript,
            "language": detected_lang,
            "confidence": result.get("confidence", 0.0),
            "provider": "sarvam"
        }

    
    def synthesize(
        self,
        text: str,
        language_code: str = "hi-IN",
        voice_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesize text to speech
        
        Args:
            text: Text to convert to speech (will be cleaned of markdown/emojis)
            language_code: Language code
            voice_id: Optional voice ID (AWS: 'Aditi', 'Kajal', etc.)
        
        Returns:
            {
                "audio_base64": "base64 encoded audio",
                "audio_format": "mp3",
                "duration": 3.5,
                "provider": "aws"
            }
        """
        # Clean text before TTS (remove markdown and emojis)
        cleaned_text = clean_text_for_tts(text)
        
        try:
            if self.provider == VoiceProvider.AWS:
                return self._synthesize_aws(cleaned_text, language_code, voice_id)
            else:
                return self._synthesize_sarvam(cleaned_text, language_code)
        except Exception as e:
            print(f"[ERROR] Synthesis failed with {self.provider.value}: {e}")
            if not self.fallback_enabled:
                raise
            # Fallback
            if self.provider == VoiceProvider.AWS:
                print("[INFO] Falling back to Sarvam AI")
                return self._synthesize_sarvam(cleaned_text, language_code)
            else:
                print("[INFO] Falling back to AWS")
                return self._synthesize_aws(cleaned_text, language_code, voice_id)
    
    def _synthesize_aws(
        self,
        text: str,
        language_code: str,
        voice_id: Optional[str]
    ) -> Dict[str, Any]:
        """Synthesize using AWS Polly"""
        # Map language to voice
        if not voice_id:
            voice_map = {
                "hi-IN": "Aditi",  # Hindi female (standard engine)
                "ta-IN": "Kajal",  # Tamil female (neural engine)
                "te-IN": "Kajal",  # Telugu (use Tamil voice, neural engine)
            }
            voice_id = voice_map.get(language_code, "Aditi")
        
        # Determine engine based on voice
        # Aditi only supports standard engine, Kajal requires neural
        engine = "neural" if voice_id == "Kajal" else "standard"
        
        response = self.polly_client.synthesize_speech(
            Text=text,
            OutputFormat="mp3",
            VoiceId=voice_id,
            Engine=engine
        )
        
        audio_bytes = response["AudioStream"].read()
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        
        return {
            "audio_base64": audio_base64,
            "audio_format": "mp3",
            "duration": len(audio_bytes) / 16000,  # Rough estimate
            "provider": "aws"
        }
    
    def _synthesize_sarvam(
        self,
        text: str,
        language_code: str
    ) -> Dict[str, Any]:
        """Synthesize using Sarvam AI Bulbul v3"""
        url = f"{self.sarvam_base_url}/text-to-speech"
        headers = {
            "api-subscription-key": self.sarvam_api_key,
            "Content-Type": "application/json"
        }

        # Get speaker from .env based on language
        # Extract language code (e.g., 'hi' from 'hi-IN')
        lang_code = language_code.split('-')[0].upper()
        env_key = f"SARVAM_TTS_SPEAKER_{lang_code}"
        speaker = os.getenv(env_key, os.getenv("SARVAM_TTS_SPEAKER", "shubh"))

        data = {
            "text": text,
            "target_language_code": language_code,
            "model": "bulbul:v3",
            "speaker": speaker,
            "speech_sample_rate": 8000,  # Use 8kHz for better browser compatibility
        }

        print(f"[DEBUG] Sarvam TTS request: lang={language_code}, speaker={speaker}, text_len={len(text)}")
        
        response = requests.post(url, headers=headers, json=data)
        
        # Log error details if request fails
        if not response.ok:
            print(f"[ERROR] Sarvam TTS failed: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
        
        response.raise_for_status()

        result = response.json()
        # Sarvam TTS returns audio in an 'audios' array (base64 strings)
        audios = result.get("audios", [])
        audio_b64 = audios[0] if audios else result.get("audio", "")

        return {
            "audio_base64": audio_b64,
            "audio_format": "wav",
            "duration": result.get("duration", 0.0),
            "provider": "sarvam"
        }

    
    def translate(
        self,
        text: str,
        source_lang: str = "auto",
        target_lang: str = "en"
    ) -> Dict[str, Any]:
        """
        Translate text between languages
        
        Args:
            text: Text to translate
            source_lang: Source language code ('auto' for detection)
            target_lang: Target language code
        
        Returns:
            {
                "translated_text": "translated text",
                "source_language": "hi",
                "target_language": "en",
                "provider": "aws"
            }
        """
        try:
            if self.provider == VoiceProvider.AWS:
                return self._translate_aws(text, source_lang, target_lang)
            else:
                return self._translate_sarvam(text, source_lang, target_lang)
        except Exception as e:
            print(f"[ERROR] Translation failed with {self.provider.value}: {e}")
            if not self.fallback_enabled:
                raise
            # Fallback
            if self.provider == VoiceProvider.AWS:
                return self._translate_sarvam(text, source_lang, target_lang)
            else:
                return self._translate_aws(text, source_lang, target_lang)
    
    def _translate_aws(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Dict[str, Any]:
        """Translate using AWS Translate"""
        response = self.translate_client.translate_text(
            Text=text,
            SourceLanguageCode=source_lang,
            TargetLanguageCode=target_lang
        )
        
        return {
            "translated_text": response["TranslatedText"],
            "source_language": response["SourceLanguageCode"],
            "target_language": response["TargetLanguageCode"],
            "provider": "aws"
        }
    
    def _translate_sarvam(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Dict[str, Any]:
        """Translate using Sarvam AI Mayura"""
        url = f"{self.sarvam_base_url}/translate"
        # Sarvam uses api-subscription-key header, NOT Authorization: Bearer
        headers = {
            "api-subscription-key": self.sarvam_api_key,
            "Content-Type": "application/json"
        }
        
        # Normalize language codes to full BCP-47 format (e.g. hi -> hi-IN)
        _lang_map = {
            "hi": "hi-IN", "ta": "ta-IN", "te": "te-IN",
            "mr": "mr-IN", "kn": "kn-IN", "ml": "ml-IN",
            "bn": "bn-IN", "gu": "gu-IN", "or": "or-IN",
            "pa": "pa-IN", "en": "en-IN",
        }
        source_code = _lang_map.get(source_lang, source_lang)
        target_code = _lang_map.get(target_lang, target_lang)
        
        data = {
            "input": text,
            "source_language_code": source_code,
            "target_language_code": target_code,
            "model": os.getenv("SARVAM_TRANSLATE_MODEL", "mayura:v1"),
            "mode": "formal",
            "enable_preprocessing": False,
        }
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        
        return {
            "translated_text": result.get("translated_text", ""),
            "source_language": source_lang,
            "target_language": target_lang,
            "provider": "sarvam"
        }


# Singleton instance
_voice_service = None

def get_voice_service() -> VoiceService:
    """Get or create voice service instance"""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service
