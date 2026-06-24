import os
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# Inject core directory in sys.path
core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from tools.utils.voice_engine import VoiceEngine, load_hermes_config
from tools.sensory.voice_tools import text_to_speech, transcribe_audio

class TestVoiceEngine(unittest.IsolatedAsyncioTestCase):

    def test_load_hermes_config_missing(self):
        """Tests fallback behavior when configuration file is absent."""
        with patch("tools.infrastructure.config.settings.HERMES_CONFIG_PATH", "/tmp/nonexistent_config.yaml"):
            cfg = load_hermes_config()
            self.assertEqual(cfg, {})

    @patch("tools.utils.voice_engine.VoiceEngine.edge_tts_synthesize")
    async def test_edge_tts_synthesis_trigger(self, mock_edge):
        """Tests that Edge TTS synthesis runs with expected voice and rate."""
        mock_edge.return_value = True
        engine = VoiceEngine()
        
        with patch("tools.utils.voice_engine.load_hermes_config", return_value={"tts": {"provider": "edge"}}):
            path = await engine.synthesize("Hello Swarm", provider="edge", voice="en-US-AriaNeural", speed=1.2)
            self.assertTrue(path.endswith(".mp3"))
            mock_edge.assert_called_once_with("Hello Swarm", "en-US-AriaNeural", 1.2, path)

    @patch("asyncio.create_subprocess_shell")
    async def test_custom_command_tts_placeholder(self, mock_subproc):
        """Tests that custom command placeholders are correctly formatted and executed."""
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"success", b""))
        mock_proc.returncode = 0
        mock_subproc.return_value = mock_proc
        
        custom_config = {
            "tts": {
                "provider": "voxcpm",
                "providers": {
                    "voxcpm": {
                        "command": "voxcpm --voice {voice} --speed {speed} --in {input_path} --out {output_path}",
                        "voice": "cloned_user",
                        "model": "vox_v2",
                        "output_format": "wav",
                        "timeout": 30
                    }
                }
            }
        }
        
        with patch("tools.utils.voice_engine.load_hermes_config", return_value=custom_config):
            engine = VoiceEngine()
            with patch("tools.utils.voice_engine.os.path.exists", return_value=True):
                with patch("tools.utils.voice_engine.os.path.getsize", return_value=100):
                    path = await engine.synthesize("Custom speed test", provider="voxcpm", speed=1.5)
                    self.assertTrue(path.endswith(".wav"))
                    mock_subproc.assert_called_once()
                    cmd_args = mock_subproc.call_args[0][0]
                    self.assertIn("--voice cloned_user", cmd_args)
                    self.assertIn("--speed 1.5", cmd_args)

    @patch("requests.post")
    async def test_stt_fallback_pipeline(self, mock_post):
        """Tests that STT fallback pipeline orders from Groq to Local to OpenAI on failures."""
        # Mock API calls to fail to trigger sequential fallback
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = Exception("API Server Error")
        mock_post.return_value = mock_resp
        
        engine = VoiceEngine()
        
        # Test fallback with file existing
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", unittest.mock.mock_open(read_data=b"audio-bytes")):
                with patch("tools.utils.voice_engine.VoiceEngine._get_api_key", return_value="fake_key"):
                    # We expect it to try Groq, fail, try local (fails since no module), then OpenAI (fails), returning simulated text
                    res = await engine.transcribe("/tmp/sample_audio.mp3", provider="groq")
                    self.assertIn("[Simulated Transcript", res)
                    self.assertEqual(mock_post.call_count, 2) # Groq and OpenAI posts tried

    @patch("tools.utils.voice_engine.VoiceEngine.synthesize")
    async def test_sovereign_tts_tool(self, mock_synth):
        """Tests that text_to_speech sovereign tool returns path correctly."""
        mock_synth.return_value = "/tmp/tts_output.mp3"
        res = await text_to_speech("Welcome home", provider="edge")
        self.assertTrue(res["success"])
        self.assertEqual(res["path"], "/tmp/tts_output.mp3")
        self.assertEqual(res["filename"], "tts_output.mp3")

    @patch("tools.utils.voice_engine.VoiceEngine.transcribe")
    async def test_sovereign_stt_tool(self, mock_transcribe):
        """Tests that transcribe_audio sovereign tool returns transcript correctly."""
        mock_transcribe.return_value = "System operational."
        res = await transcribe_audio("/tmp/audio.mp3", provider="local")
        self.assertTrue(res["success"])
        self.assertEqual(res["transcript"], "System operational.")
