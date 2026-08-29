"""
Unit Tests for Video Feedback Intelligence, Codebase Grounding, and Triple-Memory Persistence.
"""

import os
import tempfile
import unittest
from pathlib import Path

from tools.multimodal.video_feedback_transcriber import VideoFeedbackTranscriber
from tools.codebase.codebase_feedback_mapper import CodebaseFeedbackMapper
from tools.memory.feedback_knowledge_store import FeedbackKnowledgeStore


class TestVideoFeedbackIntelligence(unittest.TestCase):
    """Tests the multimodal video ingestion, semantic decomposition, and code grounding pipeline."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_feedback.db")
        self.store = FeedbackKnowledgeStore(db_path=self.db_path)
        self.transcriber = VideoFeedbackTranscriber()

        # Create mock Next.js project fixture
        self.mock_project = Path(self.temp_dir.name) / "mock_project"
        fleet_dir = self.mock_project / "src" / "app" / "(dashboard)" / "fleet-overview"
        voice_dir = self.mock_project / "src" / "app" / "(dashboard)" / "voice-agents"
        fleet_dir.mkdir(parents=True, exist_ok=True)
        voice_dir.mkdir(parents=True, exist_ok=True)

        (fleet_dir / "page.tsx").write_text("export default function FleetOverview() { return <div>Fleet Overview</div>; }")
        (voice_dir / "page.tsx").write_text("export default function VoiceAgents() { return <div>Voice Agents</div>; }")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_transcript_decomposition_and_ui_routing(self):
        """Test parsing of natural language client walkthrough into quotes, routes, and action items."""
        sample_transcript = (
            "Hey Carlos, I went through the fleet overview dashboard today. "
            "The active agents look good, but why is the prompt approval feed not updating immediately? "
            "We should add a real-time badge on the voice agents tab. "
            "Also on call telemetry, the eval pass rate calculation seems a bit slow."
        )

        segments = [
            {"start": 0.0, "end": 6.5, "text": "Hey Carlos, I went through the fleet overview dashboard today."},
            {"start": 6.5, "end": 14.2, "text": "The active agents look good, but why is the prompt approval feed not updating immediately?"},
            {"start": 14.2, "end": 20.0, "text": "We should add a real-time badge on the voice agents tab."},
            {"start": 20.0, "end": 28.5, "text": "Also on call telemetry, the eval pass rate calculation seems a bit slow."}
        ]

        result = self.transcriber.decompose_transcript(sample_transcript, segments=segments)

        self.assertIn("/fleet-overview", result["detected_ui_routes"])
        self.assertIn("/voice-agents", result["detected_ui_routes"])
        self.assertIn("/call-telemetry", result["detected_ui_routes"])
        self.assertEqual(len(result["verbatim_quotes"]), 4)
        self.assertTrue(len(result["action_items"]) >= 2)

    def test_codebase_symbol_and_route_grounding(self):
        """Test AST and symbol mapping against mock and real project files."""
        mapper = CodebaseFeedbackMapper(str(self.mock_project))

        # Verify route index indexed mock Next.js page routes
        self.assertIn("/fleet-overview", mapper.route_index)
        self.assertIn("/voice-agents", mapper.route_index)

        quote = "Why is the prompt approval feed not updating immediately on fleet overview?"
        grounding = mapper.ground_quote_to_code(quote, ui_route="/fleet-overview")

        self.assertIn("quote", grounding)
        self.assertIn(mapper.route_index["/fleet-overview"], grounding["matched_files"])
        self.assertTrue(grounding["proactive_audit"]["gap_detected"])

    def test_triple_memory_persistence_and_query(self):
        """Test full SQLite relational storage, quote retrieval, and database statistics."""
        video_envelope = {
            "video_filename": "adrian_walkthrough_part1.mp4",
            "project_name": "eko-veritas-prod",
            "transcript_text": "On the fleet overview, we need faster prompt sync with ElevenLabs.",
            "intelligence": {
                "executive_summary": "Adrian reviewed the fleet overview and requested faster ElevenLabs prompt sync.",
                "detected_ui_routes": ["/fleet-overview"],
                "verbatim_quotes": [
                    {
                        "start_timestamp": 12.4,
                        "end_timestamp": 18.2,
                        "quote": "On the fleet overview, we need faster prompt sync with ElevenLabs."
                    }
                ],
                "action_items": [
                    {
                        "category": "ENHANCEMENT",
                        "description": "Accelerate ElevenLabs prompt synchronization pipeline",
                        "status": "OPEN"
                    }
                ]
            }
        }

        grounding_envelope = {
            "total_quotes_grounded": 1,
            "involved_codebase_files": ["src/app/(dashboard)/fleet-overview/page.tsx"],
            "grounded_quotes": [
                {
                    "quote": "On the fleet overview, we need faster prompt sync with ElevenLabs.",
                    "associated_route": "/fleet-overview",
                    "matched_files": ["src/app/(dashboard)/fleet-overview/page.tsx"],
                    "matched_symbols": [{"symbol": "FleetOverview", "type": "component", "file": "src/app/(dashboard)/fleet-overview/page.tsx", "line": 15}],
                    "proactive_audit": {"gap_detected": False, "recommended_investigation": "Inspect webhook latency"},
                    "start_timestamp": 12.4,
                    "end_timestamp": 18.2
                }
            ]
        }

        res = self.store.persist_feedback_envelope(video_envelope, grounding_envelope)

        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["sqlite_saved"]["quotes_count"], 1)
        self.assertEqual(res["sqlite_saved"]["action_items_count"], 1)

        # Test querying quotes
        query_results = self.store.query_feedback("ElevenLabs")
        self.assertEqual(len(query_results), 1)
        self.assertEqual(query_results[0]["ui_route"], "/fleet-overview")
        self.assertEqual(query_results[0]["timestamp_range"], "12.4s - 18.2s")

        # Test stats
        stats = self.store.get_stats()
        self.assertEqual(stats["total_videos"], 1)
        self.assertEqual(stats["total_quotes"], 1)
        self.assertEqual(stats["total_action_items"], 1)


if __name__ == "__main__":
    unittest.main()
