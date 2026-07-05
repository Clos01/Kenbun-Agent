from typing import Optional
from tools.registry import sovereign_tool
from tools.utils.voice_engine import VoiceEngine

@sovereign_tool(name="text_to_speech", category="Sensory")
async def text_to_speech(
    text: str,
    provider: Optional[str] = None,
    voice: Optional[str] = None,
    speed: Optional[float] = None
) -> dict:
    """
    Convert text to speech audio file using various TTS providers.
    
    Args:
        text: Character string to synthesize into speech.
        provider: Optional override provider ('edge', 'elevenlabs', 'openai', etc.).
        voice: Optional override voice ID or alias.
        speed: Optional override speed multiplier.
    """
    if not text.strip():
        return {"success": False, "error": "Input text cannot be empty."}
        
    try:
        engine = VoiceEngine()
        audio_path = await engine.synthesize(text, provider=provider, voice=voice, speed=speed)
        return {
            "success": True,
            "path": audio_path,
            "filename": audio_path.split("/")[-1]
        }
    except Exception as e:
        return {"success": False, "error": f"TTS synthesis failed: {e}"}

@sovereign_tool(name="transcribe_audio", category="Sensory")
async def transcribe_audio(
    file_path: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    language: Optional[str] = None
) -> dict:
    """
    Transcribe a voice message or audio file to text.
    
    Args:
        file_path: Absolute path to the audio file to transcribe.
        provider: Optional override provider ('local', 'groq', 'openai', etc.).
        model: Optional override model ID (e.g. 'base', 'whisper-1').
        language: Optional override language code (e.g. 'en', 'es').
    """
    try:
        engine = VoiceEngine()
        text = await engine.transcribe(file_path, provider=provider, model=model, language=language)
        return {
            "success": True,
            "transcript": text
        }
    except Exception as e:
        return {"success": False, "error": f"Audio transcription failed: {e}"}
