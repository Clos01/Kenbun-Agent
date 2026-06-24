import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Inject core directory in sys.path
core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from tools.utils.clipboard_helper import is_wsl, read_clipboard_image
from tools.utils.vision_helper import is_vision_capable_model, describe_image_with_aux
from tools.sensory.vision_tools import vision_analyze

class TestVisionPaste(unittest.IsolatedAsyncioTestCase):

    def test_wsl_detection_true(self):
        """Tests that is_wsl returns True when /proc/version contains Microsoft."""
        with patch("sys.platform", "linux"):
            with patch("builtins.open", unittest.mock.mock_open(read_data="Linux version ... Microsoft-standard-WSL2 ...")):
                self.assertTrue(is_wsl())

    def test_wsl_detection_false(self):
        """Tests that is_wsl returns False on normal Linux or macOS."""
        with patch("sys.platform", "darwin"):
            self.assertFalse(is_wsl())
        with patch("sys.platform", "linux"):
            with patch("builtins.open", unittest.mock.mock_open(read_data="Linux version ... Ubuntu ...")):
                self.assertFalse(is_wsl())

    @patch("subprocess.run")
    def test_clipboard_read_wsl(self, mock_run):
        """Tests WSL clipboard image extraction via powershell.exe."""
        mock_res = MagicMock()
        mock_res.returncode = 0
        # base64 for "fake-png-data"
        mock_res.stdout = "ZmFrZS1wbmctZGF0YQ==\n"
        mock_run.return_value = mock_res
        
        with patch("tools.utils.clipboard_helper.is_wsl", return_value=True):
            img = read_clipboard_image()
            self.assertEqual(img, b"fake-png-data")
            mock_run.assert_called_once()
            self.assertIn("powershell.exe", mock_run.call_args[0][0])

    @patch("subprocess.run")
    def test_clipboard_read_mac_pngpaste(self, mock_run):
        """Tests macOS clipboard image extraction via pngpaste."""
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_run.return_value = mock_res
        
        # Mock file operations to read/write fake bytes
        with patch("sys.platform", "darwin"):
            with patch("tools.utils.clipboard_helper.is_wsl", return_value=False):
                with patch("builtins.open", unittest.mock.mock_open(read_data=b"mac-png-bytes")):
                    with patch("os.path.exists", return_value=True):
                        img = read_clipboard_image()
                        self.assertEqual(img, b"mac-png-bytes")

    def test_vision_model_detection(self):
        """Tests model vision capabilities classification."""
        self.assertTrue(is_vision_capable_model("gemini-3-flash", "https://generativelanguage.googleapis.com/v1"))
        self.assertTrue(is_vision_capable_model("claude-3-5-sonnet", "https://api.anthropic.com/v1"))
        self.assertTrue(is_vision_capable_model("gpt-4o", "https://api.openai.com/v1"))
        self.assertTrue(is_vision_capable_model("qwen-vl-max", "http://localhost:11434/v1"))
        self.assertFalse(is_vision_capable_model("deepseek-chat", "https://api.deepseek.com/v1"))
        self.assertFalse(is_vision_capable_model("qwen2.5:1.5b", "http://localhost:11434/v1"))

    def test_vision_helper_fallback(self):
        """Tests that auxiliary vision analysis falls back cleanly on missing keys."""
        # Force setting.GEMINI_API_KEY to None
        with patch("tools.infrastructure.config.settings.GEMINI_API_KEY", None):
            res = describe_image_with_aux(b"test-bytes", "Describe this")
            self.assertIn("[Vision Analysis Fallback]", res)
            self.assertIn("10", res)

    @patch("tools.sensory.vision_tools.describe_image_with_aux")
    async def test_vision_analyze_tool_text_only(self, mock_describe):
        """Tests sovereign vision_analyze tool routing to text when model is text-only."""
        mock_describe.return_value = "A beautiful sunset."
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", unittest.mock.mock_open(read_data=b"image-bytes")):
                with patch("tools.infrastructure.config.settings.PRIMARY_LLM_MODEL", "qwen2.5:1.5b"):
                    with patch("tools.infrastructure.config.settings.PRIMARY_LLM_URL", "http://localhost:11434/v1"):
                        res = await vision_analyze("/tmp/ sunset.png", "What is this?")
                        self.assertTrue(res["success"])
                        self.assertEqual(res["format"], "text")
                        self.assertEqual(res["data"], "A beautiful sunset.")

    async def test_vision_analyze_tool_multimodal(self):
        """Tests sovereign vision_analyze tool routing to multimodal when model supports vision."""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", unittest.mock.mock_open(read_data=b"image-bytes")):
                with patch("tools.infrastructure.config.settings.PRIMARY_LLM_MODEL", "gemini-3-flash"):
                    with patch("tools.infrastructure.config.settings.PRIMARY_LLM_URL", "https://generativelanguage.googleapis.com/v1"):
                        res = await vision_analyze("/tmp/sunset.png", "What is this?")
                        self.assertTrue(res["success"])
                        self.assertEqual(res["format"], "multimodal")
                        self.assertIn("image_url", res["data"])
                        # Check base64 data
                        self.assertIn("data:image/png;base64,", res["data"]["image_url"]["url"])
