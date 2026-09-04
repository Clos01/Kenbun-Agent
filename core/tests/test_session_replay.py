"""Tests for DSH-09 Automated Session Replay & Regression Eval Gate."""
import json
import pytest
from tools.memory.session_log import SessionEvent
from tools.strategy.session_replay import SessionReplayEngine, ReplayTurn


def test_partition_turns_groups_by_user_message():
    events = [
        SessionEvent(seq=1, kind="system_prompt", role="system", content="You are Kenbun."),
        SessionEvent(seq=2, kind="user_message", role="user", content="Turn 1 question"),
        SessionEvent(seq=3, kind="assistant_message", role="assistant", content="Turn 1 answer"),
        SessionEvent(seq=4, kind="user_message", role="user", content="Turn 2 question"),
        SessionEvent(seq=5, kind="tool_result", role="tool", content="data", tool_name="scan_repo"),
        SessionEvent(seq=6, kind="assistant_message", role="assistant", content="Turn 2 answer"),
    ]
    engine = SessionReplayEngine(strict=True)
    turns = engine.partition_turns(events)
    assert len(turns) == 2
    assert turns[0].turn_index == 0
    assert turns[0].user_event.content == "Turn 1 question"
    assert turns[0].assistant_event.content == "Turn 1 answer"
    assert len(turns[0].tool_events) == 0

    assert turns[1].turn_index == 1
    assert turns[1].user_event.content == "Turn 2 question"
    assert turns[1].assistant_event.content == "Turn 2 answer"
    assert len(turns[1].tool_events) == 1
    assert turns[1].tool_events[0].tool_name == "scan_repo"


def test_session_replay_passes_valid_deterministic_session():
    events = [
        SessionEvent(seq=1, kind="system_prompt", role="system", content="System prompt"),
        SessionEvent(seq=2, kind="user_message", role="user", content="Hello"),
        SessionEvent(seq=3, kind="assistant_message", role="assistant", content="Hi there"),
    ]
    engine = SessionReplayEngine(strict=True)
    report = engine.evaluate_session(events, session_id="test_pass")
    assert report.passed is True
    assert report.metrics.total_turns == 1
    assert report.metrics.passed_turns == 1
    assert report.metrics.failed_turns == 0
    assert report.metrics.fidelity_score == 1.0
    assert len(report.violations) == 0


def test_session_replay_catches_unlogged_input_injection(monkeypatch):
    from tools.strategy.session_replay import SessionReplayEngine
    from tools.memory import session_log

    events = [
        SessionEvent(seq=1, kind="system_prompt", role="system", content="System prompt"),
        SessionEvent(seq=2, kind="user_message", role="user", content="Hello"),
        SessionEvent(seq=3, kind="assistant_message", role="assistant", content="Hi there"),
    ]

    def fake_assert(sent, events):
        raise session_log.UnloggedModelInput("Unlogged model input detected in test")

    monkeypatch.setattr(session_log, "assert_model_visible_is_logged", fake_assert)

    engine = SessionReplayEngine(strict=True)
    report = engine.evaluate_session(events, session_id="test_injection")
    assert report.passed is False
    assert report.metrics.failed_turns > 0
    assert any(v.violation_type == "unlogged_model_input" for v in report.violations)


def test_session_replay_catches_missing_response_and_invalid_tool_schema():
    events = [
        SessionEvent(seq=1, kind="system_prompt", role="system", content="System prompt"),
        SessionEvent(seq=2, kind="user_message", role="user", content="Run tool"),
        # Tool missing tool_name:
        SessionEvent(seq=3, kind="tool_result", role="tool", content="some output", tool_name=None),
    ]
    engine = SessionReplayEngine(strict=True)
    report = engine.evaluate_session(events, session_id="test_schema")
    assert report.passed is False
    violations = [v.violation_type for v in report.violations]
    assert "schema_violation" in violations
    assert "missing_response" in violations


def test_load_events_from_json_and_suite_evaluation(tmp_path):
    session_file1 = tmp_path / "sess1.json"
    session_file2 = tmp_path / "sess2.json"

    data1 = [
        {"seq": 1, "kind": "system_prompt", "role": "system", "content": "You are Kenbun."},
        {"seq": 2, "kind": "user_message", "role": "user", "content": "Q1"},
        {"seq": 3, "kind": "assistant_message", "role": "assistant", "content": "A1"},
    ]
    data2 = [
        {"seq": 1, "kind": "system_prompt", "role": "system", "content": "You are Kenbun."},
        {"seq": 2, "kind": "user_message", "role": "user", "content": "Q2"},
        {"seq": 3, "kind": "tool_result", "role": "tool", "content": "data", "tool_name": "scan"},
        {"seq": 4, "kind": "assistant_message", "role": "assistant", "content": "A2"},
    ]

    session_file1.write_text(json.dumps(data1), encoding="utf-8")
    session_file2.write_text(json.dumps(data2), encoding="utf-8")

    engine = SessionReplayEngine(strict=True)
    suite_res = engine.evaluate_suite([session_file1, session_file2])

    assert suite_res["total_sessions"] == 2
    assert suite_res["passed_sessions"] == 2
    assert suite_res["overall_passed"] is True
    assert suite_res["mean_fidelity"] == 1.0
