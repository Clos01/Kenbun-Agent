"""Unit tests for Kenbun 30-day Tool Invocation Tracker."""

import pytest
import tempfile
from pathlib import Path
from tools.audit.tool_invocation_tracker import ToolInvocationTracker


def test_tool_invocation_logging():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_telemetry.db"
        tracker = ToolInvocationTracker(db_path=db_path)

        # Log a successful invocation
        inv_id1 = tracker.log_invocation(
            tool_name="consult_supervisor",
            arguments={"query": "Check security"},
            status="SUCCESS",
            latency_ms=120.5,
            caller_model="gemini-2.0-flash",
        )
        assert inv_id1 > 0

        # Log a failure / freeze
        inv_id2 = tracker.log_invocation(
            tool_name="save_to_hivemind",
            arguments={"concept": "invalid"},
            status="FAILED",
            latency_ms=45.0,
            error_message="Missing required field 'title'",
        )
        assert inv_id2 > 0

        stats = tracker.get_stats(days=30)
        assert stats["total_tool_calls"] == 2
        assert stats["status_breakdown"]["SUCCESS"] == 1
        assert stats["status_breakdown"]["FAILED"] == 1

        tools = {t["tool_name"]: t for t in stats["tools"]}
        assert "consult_supervisor" in tools
        assert tools["consult_supervisor"]["success_rate_pct"] == 100.0
        assert "save_to_hivemind" in tools
        assert tools["save_to_hivemind"]["failures"] == 1
