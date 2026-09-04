"""DSH-09 -- Automated Session Replay & Regression Eval Gate.

Keyless deterministic session playback and regression gating harness mirroring
the DeepSeek-Harness test protocol.

Replays recorded conversational turns, projects model messages, validates the
DeepSeek-Harness invariant (model-visible <=> logged), detects unlogged context
injections, and calculates replay fidelity scores with zero external API key
dependencies.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple, Union

from tools.memory import session_log
from tools.memory.session_log import SessionEvent, SessionLog, UnloggedModelInput

logger = logging.getLogger("kenbun.session_replay")


class ReplayViolation(NamedTuple):
    """Immutable record of an evaluation or invariant violation during replay."""
    violation_type: str  # e.g. "unlogged_input", "tool_mismatch", "schema_violation"
    turn_index: int
    detail: str


class ReplayTurn(NamedTuple):
    """Immutable record representing one conversational turn in a session."""
    turn_index: int
    user_event: SessionEvent
    context_events: Tuple[SessionEvent, ...]
    assistant_event: Optional[SessionEvent]
    tool_events: Tuple[SessionEvent, ...]


class ReplayMetrics(NamedTuple):
    """Evaluation metrics for a completed session replay."""
    total_turns: int
    passed_turns: int
    failed_turns: int
    tool_calls_count: int
    violations_count: int
    fidelity_score: float  # 0.0 to 1.0
    duration_ms: float


class ReplayEvalReport(NamedTuple):
    """Complete evaluation report for a session replay run."""
    session_id: str
    passed: bool
    metrics: ReplayMetrics
    violations: Tuple[ReplayViolation, ...]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "passed": self.passed,
            "timestamp": self.timestamp,
            "metrics": {
                "total_turns": self.metrics.total_turns,
                "passed_turns": self.metrics.passed_turns,
                "failed_turns": self.metrics.failed_turns,
                "tool_calls_count": self.metrics.tool_calls_count,
                "violations_count": self.metrics.violations_count,
                "fidelity_score": round(self.metrics.fidelity_score, 4),
                "duration_ms": round(self.metrics.duration_ms, 2),
            },
            "violations": [
                {
                    "violation_type": v.violation_type,
                    "turn_index": v.turn_index,
                    "detail": v.detail,
                }
                for v in self.violations
            ],
        }

    def to_markdown(self) -> str:
        status_badge = "✅ PASSED" if self.passed else "❌ FAILED"
        lines = [
            f"# Session Replay Evaluation: {self.session_id}",
            f"**Status**: {status_badge} | **Fidelity Score**: {self.metrics.fidelity_score * 100:.1f}%",
            f"**Timestamp**: {self.timestamp} | **Duration**: {self.metrics.duration_ms:.2f}ms",
            "",
            "## Summary Metrics",
            f"- **Total Turns**: {self.metrics.total_turns}",
            f"- **Passed Turns**: {self.metrics.passed_turns}",
            f"- **Failed Turns**: {self.metrics.failed_turns}",
            f"- **Tool Calls Tracked**: {self.metrics.tool_calls_count}",
            f"- **Violations**: {self.metrics.violations_count}",
            "",
        ]
        if self.violations:
            lines.append("## Invariant Violations")
            for v in self.violations:
                lines.append(f"- **Turn {v.turn_index}** [`{v.violation_type}`]: {v.detail}")
            lines.append("")
        return "\n".join(lines)


class SessionReplayEngine:
    """Deterministic, keyless session playback and regression evaluator."""

    def __init__(self, strict: bool = True) -> None:
        self.strict = strict

    @staticmethod
    def load_events_from_json(path_or_str: Union[str, Path]) -> List[SessionEvent]:
        """Loads session events from a JSON or JSONL file or raw JSON string."""
        raw_data: List[Dict[str, Any]] = []
        if isinstance(path_or_str, (str, Path)) and os.path.exists(str(path_or_str)):
            content = Path(path_or_str).read_text(encoding="utf-8").strip()
            if content.startswith("["):
                raw_data = json.loads(content)
            else:
                for line in content.splitlines():
                    if line.strip():
                        raw_data.append(json.loads(line.strip()))
        elif isinstance(path_or_str, str):
            content = path_or_str.strip()
            if content.startswith("["):
                raw_data = json.loads(content)
            elif content.startswith("{"):
                raw_data = [json.loads(line.strip()) for line in content.splitlines() if line.strip()]
            else:
                raise ValueError("Input string is neither a valid file path nor JSON content.")
        else:
            raise ValueError(f"Invalid input source: {path_or_str}")

        events: List[SessionEvent] = []
        for i, row in enumerate(raw_data):
            events.append(
                SessionEvent(
                    seq=int(row.get("seq", row.get("id", i + 1))),
                    kind=row.get("kind", "user_message"),
                    role=row.get("role", "user"),
                    content=row.get("content", ""),
                    tool_name=row.get("tool_name"),
                    ts=row.get("ts", row.get("timestamp", "")),
                    meta=row.get("meta", {}),
                )
            )
        return events

    def partition_turns(self, events: Sequence[SessionEvent]) -> List[ReplayTurn]:
        """Partitions an event stream into sequential ReplayTurn blocks."""
        ordered = sorted(events, key=lambda e: e.seq)
        turns: List[ReplayTurn] = []

        system_events: List[SessionEvent] = []
        current_user: Optional[SessionEvent] = None
        current_context: List[SessionEvent] = []
        current_assistant: Optional[SessionEvent] = None
        current_tools: List[SessionEvent] = []

        turn_idx = 0

        for ev in ordered:
            if ev.kind == "system_prompt":
                system_events.append(ev)
            elif ev.kind == "user_message":
                if current_user is not None:
                    # Flush prior turn
                    turns.append(
                        ReplayTurn(
                            turn_index=turn_idx,
                            user_event=current_user,
                            context_events=tuple(current_context),
                            assistant_event=current_assistant,
                            tool_events=tuple(current_tools),
                        )
                    )
                    turn_idx += 1
                    current_context = []
                    current_assistant = None
                    current_tools = []
                current_user = ev
            elif ev.kind == "context_injection":
                current_context.append(ev)
            elif ev.kind == "assistant_message":
                current_assistant = ev
            elif ev.kind == "tool_result":
                current_tools.append(ev)

        if current_user is not None:
            turns.append(
                ReplayTurn(
                    turn_index=turn_idx,
                    user_event=current_user,
                    context_events=tuple(current_context),
                    assistant_event=current_assistant,
                    tool_events=tuple(current_tools),
                )
            )

        return turns

    def evaluate_turn(
        self,
        turn: ReplayTurn,
        history_events: Sequence[SessionEvent],
    ) -> List[ReplayViolation]:
        """Evaluates a single conversational turn in the context of preceding events."""
        violations: List[ReplayViolation] = []

        # 1. Invariant Check: Verify model-visible <=> logged for this turn's prompt
        current_turn_events = list(history_events)
        current_turn_events.extend(turn.context_events)
        current_turn_events.append(turn.user_event)

        projected_model_messages = session_log.derive_model_messages(current_turn_events)

        try:
            session_log.assert_model_visible_is_logged(projected_model_messages, current_turn_events)
        except UnloggedModelInput as exc:
            violations.append(
                ReplayViolation(
                    violation_type="unlogged_model_input",
                    turn_index=turn.turn_index,
                    detail=str(exc),
                )
            )

        # 2. Assistant Response Completeness
        if turn.assistant_event is None:
            violations.append(
                ReplayViolation(
                    violation_type="missing_response",
                    turn_index=turn.turn_index,
                    detail=f"Turn {turn.turn_index} has no assistant response recorded.",
                )
            )

        # 3. Tool Result Invariant Check
        for tool_ev in turn.tool_events:
            if not tool_ev.tool_name:
                violations.append(
                    ReplayViolation(
                        violation_type="schema_violation",
                        turn_index=turn.turn_index,
                        detail=f"Tool result event {tool_ev.seq} is missing a tool_name.",
                    )
                )

        return violations

    def evaluate_session(
        self,
        source: Union[str, Path, Sequence[SessionEvent]],
        session_id: Optional[str] = None,
    ) -> ReplayEvalReport:
        """Executes keyless replay evaluation on an entire session."""
        start_time = time.perf_counter()

        if isinstance(source, (str, Path)) and os.path.exists(str(source)):
            events = self.load_events_from_json(source)
            effective_sid = session_id or Path(source).stem
        elif isinstance(source, str) and not source.startswith(("[", "{")):
            # Interpreted as session_id from SessionLog
            effective_sid = source
            log = SessionLog(effective_sid)
            events = log.events()
        elif isinstance(source, (list, tuple)):
            events = list(source)
            effective_sid = session_id or f"session_{int(time.time())}"
        else:
            events = self.load_events_from_json(source)
            effective_sid = session_id or f"session_{int(time.time())}"

        turns = self.partition_turns(events)
        all_violations: List[ReplayViolation] = []
        passed_turns = 0
        total_tool_calls = 0

        # System prompt events serve as the baseline history
        active_history: List[SessionEvent] = [e for e in events if e.kind == "system_prompt"]

        for turn in turns:
            total_tool_calls += len(turn.tool_events)
            turn_violations = self.evaluate_turn(turn, active_history)
            if turn_violations:
                all_violations.extend(turn_violations)
            else:
                passed_turns += 1

            # Accumulate history for next turn
            active_history.extend(turn.context_events)
            active_history.append(turn.user_event)
            if turn.assistant_event:
                active_history.append(turn.assistant_event)
            active_history.extend(turn.tool_events)

        total_turns = len(turns)
        failed_turns = total_turns - passed_turns
        fidelity_score = (passed_turns / total_turns) if total_turns > 0 else 1.0
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        passed = len(all_violations) == 0 if self.strict else fidelity_score >= 0.8

        metrics = ReplayMetrics(
            total_turns=total_turns,
            passed_turns=passed_turns,
            failed_turns=failed_turns,
            tool_calls_count=total_tool_calls,
            violations_count=len(all_violations),
            fidelity_score=fidelity_score,
            duration_ms=duration_ms,
        )

        return ReplayEvalReport(
            session_id=effective_sid,
            passed=passed,
            metrics=metrics,
            violations=tuple(all_violations),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    def evaluate_suite(
        self,
        sources: Sequence[Union[str, Path]],
    ) -> Dict[str, Any]:
        """Runs replay evaluations over multiple sessions and aggregates results."""
        reports: List[ReplayEvalReport] = []
        for src in sources:
            report = self.evaluate_session(src)
            reports.append(report)

        total_sessions = len(reports)
        passed_sessions = sum(1 for r in reports if r.passed)
        overall_fidelity = (
            sum(r.metrics.fidelity_score for r in reports) / total_sessions
            if total_sessions > 0
            else 1.0
        )

        return {
            "total_sessions": total_sessions,
            "passed_sessions": passed_sessions,
            "failed_sessions": total_sessions - passed_sessions,
            "overall_passed": passed_sessions == total_sessions,
            "mean_fidelity": round(overall_fidelity, 4),
            "reports": [r.to_dict() for r in reports],
        }
