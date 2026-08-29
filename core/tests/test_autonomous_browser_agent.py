import unittest
import json
from unittest.mock import patch, MagicMock

from tools.gui.autonomous_browser_agent import AutonomousBrowserAgent, dispatch_autonomous_browser
from tools.gui.ui_tars_tools import trigger_ui_tars


class TestAutonomousBrowserAgent(unittest.TestCase):
    def setUp(self):
        self.agent = AutonomousBrowserAgent()

    def test_playwright_execution_payload_structure(self):
        """Verify Playwright execution returns a well-formed JSON envelope."""
        mock_result = {
            "status": "SUCCESS",
            "engine_used": "playwright",
            "target_url": "https://nevermiss.ai",
            "page_title": "NeverMiss AI",
            "extracted_data": {"title": "NeverMiss AI", "links_count": 12},
            "screenshot_path": "/path/to/shot.png",
            "execution_trace": [{"step": 1, "action": "goto", "status": "ok"}]
        }

        with patch.object(self.agent, "execute_playwright", return_value=mock_result):
            res = self.agent.run(
                url="https://nevermiss.ai",
                goal="Extract stats",
                mode="playwright",
                session_id="test_sess_01"
            )
            self.assertEqual(res["status"], "SUCCESS")
            self.assertEqual(res["engine_used"], "playwright")
            self.assertEqual(res["session_id"], "test_sess_01")
            self.assertIn("duration_seconds", res)

    def test_hybrid_auto_escalation_on_bot_block(self):
        """Verify hybrid mode automatically escalates to P330 UI-TARS when bot-blocked."""
        blocked_pw = {
            "status": "BOT_BLOCKED",
            "engine_used": "playwright",
            "blocked_by_bot": True,
            "execution_trace": [{"step": 1, "action": "bot_detection", "status": "blocked"}]
        }

        tars_success = {
            "status": "SUCCESS",
            "engine_used": "ui_tars_p330",
            "execution_trace": [{"step": 1, "action": "click", "coords": [500, 300]}]
        }

        with patch.object(self.agent, "execute_playwright", return_value=blocked_pw):
            with patch.object(self.agent, "execute_p330_ssh_tars", return_value=tars_success):
                res = self.agent.execute_hybrid(
                    url="https://nevermiss.ai",
                    goal="Bypass blocker and open dashboard",
                    session_id="hybrid_sess"
                )
                self.assertEqual(res["status"], "SUCCESS")
                self.assertEqual(res["engine_used"], "ui_tars_p330")
                self.assertTrue(res.get("hybrid_escalated"))
                self.assertIn("playwright_attempt", res)

    def test_trigger_ui_tars_structured_dict_support(self):
        """Verify trigger_ui_tars handles structured AI dictionary payloads."""
        mock_output = {
            "status": "SUCCESS",
            "engine_used": "playwright",
            "page_title": "NeverMiss AI",
            "target_url": "https://nevermiss.ai"
        }

        with patch("tools.gui.autonomous_browser_agent.AutonomousBrowserAgent.run", return_value=mock_output):
            raw_json = trigger_ui_tars({
                "url": "https://nevermiss.ai",
                "mode": "playwright",
                "goal": "Verify active AI services"
            })
            parsed = json.loads(raw_json)
            self.assertEqual(parsed["status"], "SUCCESS")
            self.assertEqual(parsed["engine_used"], "playwright")

    def test_dispatch_autonomous_browser_sovereign_tool(self):
        """Verify the sovereign tool function dispatches correctly."""
        mock_output = {"status": "SUCCESS", "engine_used": "hybrid"}
        with patch("tools.gui.autonomous_browser_agent.AutonomousBrowserAgent.run", return_value=mock_output):
            res = dispatch_autonomous_browser(url="https://nevermiss.ai", mode="hybrid")
            self.assertEqual(res["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
