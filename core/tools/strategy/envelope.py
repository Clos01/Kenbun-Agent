"""
Sovereign Software Factory — Strict JSON Context Envelopes
Provides deterministic, structured handoffs between AI agent phases
(Scout -> Plan -> Build -> Test -> Review -> Document).
"""
import os
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("tools.envelope")

def get_sessions_dir() -> Path:
    """Returns the dedicated directory for storing ADW session envelopes."""
    # Check for workspace-local brain_health directory first
    try:
        from tools.infrastructure.config import settings
        base_dir = settings.BRAIN_HEALTH_DIR / "adw_sessions"
    except Exception:
        base_dir = Path(__file__).resolve().parent.parent.parent / "brain_health" / "adw_sessions"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

class TokenStats(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

class GateCheckResult(BaseModel):
    check_name: str
    passed: bool
    details: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class AgentEnvelope(BaseModel):
    """
    Standardized JSON envelope passed across subagents during SDLC workflows.
    Ensures zero context drift, full observability, and deterministic handoffs.
    """
    task_id: str
    phase: str  # 'scout', 'plan', 'build', 'test', 'review', 'document'
    model_name: str = "claude-sonnet-5"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    plan_summary: str = ""
    target_files: List[str] = Field(default_factory=list)
    required_tests: List[str] = Field(default_factory=list)
    handoff_notes: str = ""
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    gate_checks: List[GateCheckResult] = Field(default_factory=list)
    token_stats: TokenStats = Field(default_factory=TokenStats)
    status: str = "completed"  # 'pending', 'in_progress', 'completed', 'failed'

def create_envelope(
    task_id: str,
    phase: str,
    plan_summary: str = "",
    target_files: Optional[List[str]] = None,
    required_tests: Optional[List[str]] = None,
    handoff_notes: str = "",
    model_name: str = "claude-sonnet-5",
    artifacts: Optional[Dict[str, Any]] = None,
    gate_checks: Optional[List[GateCheckResult]] = None,
    token_stats: Optional[TokenStats] = None,
    status: str = "completed"
) -> AgentEnvelope:
    """Factory method to construct a validated AgentEnvelope."""
    return AgentEnvelope(
        task_id=task_id,
        phase=phase,
        model_name=model_name,
        plan_summary=plan_summary,
        target_files=target_files or [],
        required_tests=required_tests or [],
        handoff_notes=handoff_notes,
        artifacts=artifacts or {},
        gate_checks=gate_checks or [],
        token_stats=token_stats or TokenStats(),
        status=status
    )

def save_envelope(envelope: AgentEnvelope) -> Path:
    """Persists an envelope to ~/.kenbun/adw_sessions/<task_id>/envelope_<phase>.json."""
    session_dir = get_sessions_dir() / envelope.task_id
    session_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = session_dir / f"envelope_{envelope.phase}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(envelope.model_dump_json(indent=2))
        
    # Also update the manifest index
    manifest_path = session_dir / "workflow_manifest.json"
    manifest_data = {}
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception:
            pass
            
    manifest_data["task_id"] = envelope.task_id
    manifest_data["last_updated"] = datetime.now(timezone.utc).isoformat()
    if "phases" not in manifest_data:
        manifest_data["phases"] = {}
    manifest_data["phases"][envelope.phase] = {
        "status": envelope.status,
        "model": envelope.model_name,
        "timestamp": envelope.timestamp,
        "summary": envelope.plan_summary[:200],
        "file": str(file_path)
    }
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
        
    logger.info("Saved envelope for task %s (phase: %s) to %s", envelope.task_id, envelope.phase, file_path)
    return file_path

def load_envelope(task_id: str, phase: str) -> Optional[AgentEnvelope]:
    """Loads a specific phase envelope for a given task."""
    file_path = get_sessions_dir() / task_id / f"envelope_{phase}.json"
    if not file_path.exists():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return AgentEnvelope.model_validate(data)
    except Exception as e:
        logger.error("Failed to parse envelope from %s: %e", file_path, e)
        return None

def list_all_workflows(limit: int = 30) -> List[Dict[str, Any]]:
    """Lists all active and historical workflow sessions with their phases."""
    sessions_dir = get_sessions_dir()
    if not sessions_dir.exists():
        return []
        
    workflows = []
    for manifest_file in sorted(sessions_dir.glob("*/workflow_manifest.json"), key=os.path.getmtime, reverse=True)[:limit]:
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                workflows.append(data)
        except Exception:
            continue
            
    return workflows
