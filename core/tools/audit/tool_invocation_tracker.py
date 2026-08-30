"""
30-Day Tool Invocation & Telemetry Ledger (Kenbun System 4 Audit Engine).

Tracks, persists, and audits all tool calls across a rolling 30-day window:
1. Validates that required tools are invoked reliably by smaller models.
2. Identifies hallucination freeze points and malformed argument payloads.
3. Quantifies failure rates, execution latencies, and tool calling compliance.
"""

from __future__ import annotations

import os
import sys
import time
import json
import sqlite3
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
from datetime import datetime, timedelta

try:
    from tools.registry import sovereign_tool
except (ImportError, ModuleNotFoundError):
    try:
        from core.tools.registry import sovereign_tool
    except (ImportError, ModuleNotFoundError):
        def sovereign_tool(*args, **kwargs):
            def decorator(f):
                return f
            return decorator

logger = logging.getLogger("tools.audit.tool_tracker")

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "tool_telemetry_30d.db"


class ToolInvocationTracker:
    """Manages SQLite-backed 30-day tool telemetry and compliance auditing."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_invocations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT,
                    status TEXT NOT NULL, -- 'SUCCESS', 'FAILED', 'FREEZE_HALLUCINATION'
                    latency_ms REAL NOT NULL,
                    caller_model TEXT,
                    error_message TEXT,
                    task_context TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_name ON tool_invocations(tool_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON tool_invocations(timestamp)")
            conn.commit()

    def log_invocation(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        status: str = "SUCCESS",
        latency_ms: float = 0.0,
        caller_model: str = "unknown",
        error_message: Optional[str] = None,
        task_context: Optional[str] = None,
    ) -> int:
        """Logs a single tool execution into the 30-day ledger."""
        now_iso = datetime.utcnow().isoformat()
        args_str = json.dumps(arguments) if arguments else "{}"

        with self._get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO tool_invocations (
                    timestamp, tool_name, arguments_json, status,
                    latency_ms, caller_model, error_message, task_context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_iso,
                    tool_name,
                    args_str,
                    status.upper(),
                    round(latency_ms, 2),
                    caller_model,
                    error_message,
                    task_context,
                ),
            )
            conn.commit()
            return cur.lastrowid or 0

    def prune_old_records(self, days: int = 30) -> int:
        """Prunes records older than N days to keep database lightweight."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM tool_invocations WHERE timestamp < ?", (cutoff,))
            conn.commit()
            return cur.rowcount

    def get_stats(self, days: int = 30) -> Dict[str, Any]:
        """Generates a comprehensive 30-day audit summary of tool invocations."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with self._get_connection() as conn:
            total_invocations = conn.execute(
                "SELECT COUNT(*) as count FROM tool_invocations WHERE timestamp >= ?", (cutoff,)
            ).fetchone()["count"]

            status_breakdown = {}
            for row in conn.execute(
                "SELECT status, COUNT(*) as count FROM tool_invocations WHERE timestamp >= ? GROUP BY status",
                (cutoff,),
            ):
                status_breakdown[row["status"]] = row["count"]

            tool_breakdown = []
            for row in conn.execute(
                """
                SELECT tool_name,
                       COUNT(*) as total_calls,
                       SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successes,
                       SUM(CASE WHEN status != 'SUCCESS' THEN 1 ELSE 0 END) as failures,
                       AVG(latency_ms) as avg_latency_ms
                FROM tool_invocations
                WHERE timestamp >= ?
                GROUP BY tool_name
                ORDER BY total_calls DESC
                LIMIT 25
                """,
                (cutoff,),
            ):
                tool_breakdown.append({
                    "tool_name": row["tool_name"],
                    "total_calls": row["total_calls"],
                    "success_rate_pct": round((row["successes"] / max(row["total_calls"], 1)) * 100.0, 1),
                    "failures": row["failures"],
                    "avg_latency_ms": round(row["avg_latency_ms"] or 0.0, 1),
                })

        return {
            "window_days": days,
            "total_tool_calls": total_invocations,
            "status_breakdown": status_breakdown,
            "tools": tool_breakdown,
            "timestamp": datetime.utcnow().isoformat(),
        }


# Global singleton
tracker = ToolInvocationTracker()


@sovereign_tool(name="get_tool_telemetry_30d", category="Audit")
def get_tool_telemetry_30d(days: int = 30) -> Dict[str, Any]:
    """
    Returns rolling 30-day telemetry and execution statistics for all tools,
    measuring call volume, success rates, failure points, and average latencies.
    """
    return tracker.get_stats(days=days)


@sovereign_tool(name="verify_workflow_compliance", category="Audit")
def verify_workflow_compliance(
    task_description: str,
    required_tools: List[str]
) -> Dict[str, Any]:
    """
    Audits whether a given workflow or subagent task properly invoked the mandatory tools
    rather than hallucinating results or skipping required verification steps.
    """
    recent_stats = tracker.get_stats(days=1)
    invoked_tools = {t["tool_name"] for t in recent_stats.get("tools", [])}
    
    missing_tools = [tool for tool in required_tools if tool not in invoked_tools]
    compliant = len(missing_tools) == 0

    return {
        "task": task_description,
        "is_compliant": compliant,
        "required_tools": required_tools,
        "missing_tools": missing_tools,
        "recommendation": "Compliant execution verified." if compliant else f"Workflow bypassed required tool calls: {missing_tools}. Re-execute with required tools."
    }
