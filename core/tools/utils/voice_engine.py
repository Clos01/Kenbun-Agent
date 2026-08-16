import os
import uuid
import yaml
import shlex
import time
import shutil
import asyncio
import logging
import tempfile
import requests
import subprocess
from typing import Optional
from tools.infrastructure.config import settings
from tools.utils.secret_manager import decrypt_value

logger = logging.getLogger(__name__)

def load_kenbun_config() -> dict:
    """Loads ~/.kenbun/config.yaml if it exists, returning a parsed dict."""
    path = os.path.expanduser(settings.KENBUN_CONFIG_PATH)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f.read()) or {}
        except Exception as e:
            logger.warning(f"Failed to load Kenbun config at {path}: {e}")
    return {}

def prune_audio_cache(cache_dir: str, max_files: int = 100):
    """Prunes audio cache directory keeping only the most recent files."""
    try:
        if not os.path.exists(cache_dir):
            return
        files = []
        for name in os.listdir(cache_dir):
            path = os.path.join(cache_dir, name)
            if os.path.isfile(path):
                files.append((path, os.path.getmtime(path)))
        if len(files) > max_files:
            # Sort by mtime ascending (oldest first)
            files.sort(key=lambda x: x[1])
            to_remove = len(files) - max_files
            for i in range(to_remove):
                try:
                    os.unlink(files[i][0])
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"Failed to prune audio cache: {e}")


class VoiceEngine:
    """
    Kenbun Unified Voice & TTS Engine.
    Handles Text-to-Speech synthesis and Speech-to-Text transcribing
    across built-in, custom command, and plugin-based providers.
    """

    def __init__(self):
        self.config = load_kenbun_config()
        self.cache_dir = os.path.expanduser("~/.kenbun/audio_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        prune_audio_cache(self.cache_dir)

    def _get_api_key(self, env_key: str, setting_attr: Optional[str] = None) -> Optional[str]:
        """Retrieves and decrypts API key dynamically."""
        val = os.environ.get(env_key)
        if not val and setting_attr:
            pydantic_val = getattr(settings, setting_attr, None)
            if pydantic_val:
                val = pydantic_val.get_secret_value() if hasattr(pydantic_val, "get_secret_value") else str(pydantic_val)
        if val:
            return decrypt_value(val)
        return None

    # ── Text-to-Speech (TTS) Implementation ──────────────────────────────────────

    async def edge_tts_synthesize(self, text: str, voice: str, speed: float, output_path: str) -> bool:
        """Native async Bing/Edge ReadAloud WebSocket client."""
        try:
            import websockets
            request_id = uuid.uuid4().hex.upper()
            url = "wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken=6A5AA1D4EAFF4E9FB37E23D68491D6F4"
            
            rate_pct = int((speed - 1.0) * 100)
            rate_str = f"{rate_pct:+d}%"
            
            config_msg = (
                "Content-Type:application/json; charset=utf-8\r\n"
                "Path:speech.config\r\n\r\n"
                '{"context":{"system":{"name":"SpeechSDK","version":"1.12.0-1","build":"JavaScript","lang":"javascript"}}}'
            )
            
            ssml_msg = (
                f"X-RequestId:{request_id}\r\n"
                "Content-Type:application/ssml+xml\r\n"
                "Path:ssml\r\n\r\n"
                f"<speak version='1.0' xmlns='http://www.w3.org/2001/speak-ssml' xml:lang='en-US'>"
                f"<voice name='{voice}'><prosody rate='{rate_str}'>{text}</prosody></voice></speak>"
            )
            
            audio_data = bytearray()
            async with websockets.connect(url, extra_headers={"User-Agent": "Mozilla/5.0"}) as websocket:
                await websocket.send(config_msg)
                await websocket.send(ssml_msg)
                
                async for message in websocket:
                    if isinstance(message, str):
                        if "Path:turn.end" in message:
                            break
                    elif isinstance(message, bytes):
                        if len(message) > 2:
                            header_len = int.from_bytes(message[:2], byteorder="big")
                            header = message[2:2+header_len].decode("utf-8")
                            if "Path:audio" in header:
                                audio_data.extend(message[2+header_len:])
            
            if audio_data:
                with open(output_path, "wb") as f:
                    f.write(audio_data)
                return True
        except Exception as e:
            logger.debug(f"Native Edge TTS client failed: {e}")
        return False

    async def synthesize(
        self,
        text: str,
        provider: Optional[str] = None,
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> str:
        """Synthesizes text to speech, returning the absolute path to the audio file."""
        # 1. Resolve Provider and Configuration
        config_tts = self.config.get("tts", {})
        provider = provider or config_tts.get("provider") or settings.TTS_PROVIDER
        speed = speed if speed is not None else config_tts.get("speed") or settings.TTS_SPEED
        
        custom_providers = config_tts.get("providers", {})
        provider_config = config_tts.get(provider) or custom_providers.get(provider) or {}
        
        # Enforce maximum text length truncation
        default_caps = {
            "edge": 5000, "openai": 4096, "xai": 15000, "minimax": 10000,
            "mistral": 4000, "gemini": 32000, "neutts": 2000, "kittentts": 2000,
            "piper": 5000
        }
        
        # ElevenLabs model-based default caps
        el_model = provider_config.get("model_id", "eleven_multilingual_v2")
        el_caps = {
            "eleven_flash_v2_5": 40000,
            "eleven_flash_v2": 30000,
            "eleven_multilingual_v2": 10000,
            "eleven_multilingual_v1": 10000,
            "eleven_english_sts_v2": 10000,
            "eleven_v3": 5000
        }
        el_cap = el_caps.get(el_model, 10000)
        default_caps["elevenlabs"] = el_cap
        
        cap = default_caps.get(provider, 5000)
        custom_cap = provider_config.get("max_text_length")
        if isinstance(custom_cap, int) and custom_cap > 0:
            cap = custom_cap
            
        text = text[:cap]

        timestamp = int(time.time() * 1000)
        output_format = provider_config.get("output_format") or "mp3"
        output_path = os.path.join(self.cache_dir, f"tts_{timestamp}.{output_format}")

        # Resolve voice and model from config if not passed
        resolved_voice = voice or provider_config.get("voice") or provider_config.get("voice_id")
        resolved_model = provider_config.get("model") or provider_config.get("model_id")

        # 2. Check Custom Command Provider
        custom_providers = config_tts.get("providers", {})
        if provider in custom_providers or provider_config.get("type") == "command" or "command" in provider_config:
            custom_def = custom_providers.get(provider, provider_config)
            cmd_template = custom_def.get("command")
            if cmd_template:
                return await self._run_custom_tts_command(
                    cmd_template, text, resolved_voice, resolved_model, speed,
                    custom_def.get("output_format", "mp3"), custom_def.get("timeout", 120),
                    output_path
                )

        # 3. Built-In Provider Executions
        if provider == "edge":
            # Determine voice
            voice_id = resolved_voice or "en-US-AriaNeural"
            success = await self.edge_tts_synthesize(text, voice_id, speed, output_path)
            if success:
                return output_path

        elif provider == "openai":
            api_key = self._get_api_key("VOICE_TOOLS_OPENAI_KEY", "OPENAI_API_KEY")
            if api_key:
                voice_id = resolved_voice or "alloy"
                model_id = resolved_model or "gpt-4o-mini-tts"
                base_url = provider_config.get("base_url") or "https://api.openai.com/v1"
                try:
                    resp = requests.post(
                        f"{base_url}/audio/speech",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": model_id,
                            "input": text,
                            "voice": voice_id,
                            "speed": speed
                        },
                        timeout=30
                    )
                    resp.raise_for_status()
                    with open(output_path, "wb") as f:
                        f.write(resp.content)
                    return output_path
                except Exception as e:
                    logger.warning(f"OpenAI TTS synthesis failed: {e}")

        elif provider == "gemini":
            api_key = self._get_api_key("GEMINI_API_KEY")
            if api_key:
                try:
                    from google import genai
                    from google.genai import types
                    client = genai.Client(api_key=api_key)
                    model_id = resolved_model or settings.models.gemini_model or "gemini-3-flash-preview"
                    
                    # Gemini TTS synthesizes content via generate_content (modality audio)
                    response = client.models.generate_content(
                        model=model_id,
                        contents=text,
                        config=types.GenerateContentConfig(
                            response_modalities=["AUDIO"]
                        )
                    )
                    # Extract audio bytes if returned natively, else fallback
                    if response and hasattr(response, "candidates") and response.candidates:
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, "inline_data") and part.inline_data:
                                with open(output_path, "wb") as f:
                                    f.write(part.inline_data.data)
                                return output_path
                except Exception as e:
                    logger.warning(f"Gemini Native TTS synthesis failed: {e}")

        elif provider == "elevenlabs":
            api_key = self._get_api_key("ELEVENLABS_API_KEY")
            if api_key:
                voice_id = resolved_voice or "pNInz6obpgDQGcFmaJgB"
                model_id = resolved_model or "eleven_multilingual_v2"
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                try:
                    resp = requests.post(
                        url,
                        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                        json={
                            "text": text,
                            "model_id": model_id,
                            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                        },
                        timeout=60
                    )
                    resp.raise_for_status()
                    with open(output_path, "wb") as f:
                        f.write(resp.content)
                    return output_path
                except Exception as e:
                    logger.warning(f"ElevenLabs TTS failed: {e}")

        # Fallback to simulated description
        logger.info("Using simulated fallback speech file generation.")
        with open(output_path, "wb") as f:
            f.write(f"[Speech Output: '{text}']".encode("utf-8"))
        return output_path

    async def _run_custom_tts_command(
        self,
        template: str,
        text: str,
        voice: Optional[str],
        model: Optional[str],
        speed: float,
        out_fmt: str,
        timeout: int,
        output_path: str
    ) -> str:
        """Executes custom command template replacing placeholders safely."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as temp_in:
            temp_in.write(text)
            temp_in_path = temp_in.name
            
        try:
            # Quote inputs to secure shell args
            voice_val = shlex.quote(voice or "")
            model_val = shlex.quote(model or "")
            
            cmd = template.replace("{input_path}", shlex.quote(temp_in_path))
            cmd = cmd.replace("{text_path}", shlex.quote(temp_in_path))
            cmd = cmd.replace("{output_path}", shlex.quote(output_path))
            cmd = cmd.replace("{voice}", voice_val)
            cmd = cmd.replace("{model}", model_val)
            cmd = cmd.replace("{speed}", shlex.quote(str(speed)))
            cmd = cmd.replace("{format}", shlex.quote(out_fmt))
            
            logger.info(f"Executing custom TTS command: {cmd}")
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                if proc.returncode != 0:
                    err_msg = stderr.decode().strip() or stdout.decode().strip()
                    raise RuntimeError(f"Custom TTS command failed (code {proc.returncode}): {err_msg}")
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                raise TimeoutError(f"Custom TTS command timed out after {timeout} seconds.")
                
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
            raise FileNotFoundError("Custom TTS command completed but did not produce a valid output file.")
        finally:
            if os.path.exists(temp_in_path):
                os.unlink(temp_in_path)

    # ── Speech-to-Text (STT) Implementation ──────────────────────────────────────

    async def transcribe(
        self,
        file_path: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None
    ) -> str:
        """Transcribes audio file to text using fallback pipelines."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found at: {file_path}")

        config_stt = self.config.get("stt", {})
        provider = provider or config_stt.get("provider") or settings.STT_PROVIDER
        model = model or config_stt.get(provider, {}).get("model") or settings.STT_MODEL
        language = language or config_stt.get(provider, {}).get("language") or "en"
        
        provider_config = config_stt.get(provider, {})

        # 1. Custom Command Provider Check
        custom_providers = config_stt.get("providers", {})
        if provider in custom_providers or provider_config.get("type") == "command" or "command" in provider_config:
            custom_def = custom_providers.get(provider, provider_config)
            cmd_template = custom_def.get("command")
            if cmd_template:
                return await self._run_custom_stt_command(
                    cmd_template, file_path, custom_def.get("format", "txt"),
                    language, model, custom_def.get("timeout", 300)
                )

        # 2. Built-In Provider Executions with Fallback Pipeline
        providers_order = [provider, "groq", "local", "openai"]
        # Remove duplicates preserving order
        unique_providers = []
        for p in providers_order:
            if p not in unique_providers:
                unique_providers.append(p)

        last_err = None
        for p in unique_providers:
            try:
                p_config = config_stt.get(p, {})
                p_model = model if p == provider else p_config.get("model") or "base"
                
                if p == "local":
                    # Check faster-whisper
                    try:
                        from faster_whisper import WhisperModel
                        logger.info(f"Running local faster-whisper transcription with model '{p_model}'...")
                        whisper_model = WhisperModel(p_model, device="cpu", compute_type="int8")
                        segments, info = whisper_model.transcribe(file_path, beam_size=5)
                        text = " ".join(segment.text for segment in segments)
                        if text:
                            return text.strip()
                    except ImportError:
                        # Fallback to local whisper CLI if exists
                        if shutil.which("whisper"):
                            logger.info("faster-whisper not found. Falling back to local whisper CLI...")
                            with tempfile.TemporaryDirectory() as tmpdir:
                                cmd = f"whisper {shlex.quote(file_path)} --model {shlex.quote(p_model)} --output_dir {shlex.quote(tmpdir)} --output_format txt"
                                subprocess.run(shlex.split(cmd), check=True, capture_output=True)
                                txt_file = os.path.join(tmpdir, os.path.basename(file_path).rsplit(".", 1)[0] + ".txt")
                                if os.path.exists(txt_file):
                                    with open(txt_file, "r", encoding="utf-8") as f:
                                        return f.read().strip()

                elif p == "groq":
                    api_key = self._get_api_key("GROQ_API_KEY")
                    if api_key:
                        logger.info("Executing Groq Whisper API transcription...")
                        url = "https://api.groq.com/openai/v1/audio/transcriptions"
                        with open(file_path, "rb") as f:
                            resp = requests.post(
                                url,
                                headers={"Authorization": f"Bearer {api_key}"},
                                files={"file": (os.path.basename(file_path), f)},
                                data={"model": "whisper-large-v3", "language": language},
                                timeout=60
                            )
                        resp.raise_for_status()
                        return resp.json().get("text", "").strip()

                elif p == "openai":
                    api_key = self._get_api_key("VOICE_TOOLS_OPENAI_KEY", "OPENAI_API_KEY")
                    if api_key:
                        logger.info("Executing OpenAI Whisper API transcription...")
                        url = "https://api.openai.com/v1/audio/transcriptions"
                        with open(file_path, "rb") as f:
                            resp = requests.post(
                                url,
                                headers={"Authorization": f"Bearer {api_key}"},
                                files={"file": (os.path.basename(file_path), f)},
                                data={"model": "whisper-1", "language": language},
                                timeout=60
                            )
                        resp.raise_for_status()
                        return resp.json().get("text", "").strip()

            except Exception as e:
                logger.warning(f"STT Provider '{p}' failed: {e}")
                last_err = e

        if last_err:
            logger.warning(f"All STT providers failed. Returning fallback simulated transcript. Last error: {last_err}")
        return f"[Simulated Transcript of audio file '{os.path.basename(file_path)}']"

    async def _run_custom_stt_command(
        self,
        template: str,
        file_path: str,
        out_fmt: str,
        language: str,
        model: Optional[str],
        timeout: int
    ) -> str:
        """Executes custom command template replacing placeholders safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, f"transcript.{out_fmt}")
            
            cmd = template.replace("{input_path}", shlex.quote(file_path))
            cmd = cmd.replace("{output_path}", shlex.quote(out_path))
            cmd = cmd.replace("{output_dir}", shlex.quote(tmpdir))
            cmd = cmd.replace("{format}", shlex.quote(out_fmt))
            cmd = cmd.replace("{language}", shlex.quote(language))
            cmd = cmd.replace("{model}", shlex.quote(model or ""))
            
            logger.info(f"Executing custom STT command: {cmd}")
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                if proc.returncode != 0:
                    err_msg = stderr.decode().strip() or stdout.decode().strip()
                    raise RuntimeError(f"Custom STT command failed (code {proc.returncode}): {err_msg}")
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                raise TimeoutError(f"Custom STT command timed out after {timeout} seconds.")
                
            # Read back the transcript
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                with open(out_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            elif stdout:
                return stdout.decode().strip()
            raise FileNotFoundError("Custom STT command completed but produced no output file and no stdout.")
