"""
Traceability Manifest Logger for Kenbun Swarm Agents.
Enforces the Heritage Design System's "deterministic auditability" mandate
by generating a SHA-256 cryptographic lineage ledger.
"""

import time
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from tools.infrastructure.config import settings

class TraceabilityManifestLogger:
    """
    Stateful logger that writes cryptographic event records to trace_manifest.jsonl.
    Each entry is chained to the previous entry via a SHA-256 rolling hash.
    """
    def __init__(self, agent_name: str, log_dir: Optional[Path] = None):
        self.agent_name = agent_name
        self.log_dir = log_dir or settings.BRAIN_HEALTH_DIR
        self.log_file = self.log_dir / "trace_manifest.jsonl"
        self.last_hash = "0" * 64  # Genesis block hash seed
        self.index = 0
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _calculate_hash(self, prev_hash: str, index: int, timestamp: float, 
                        decision: str, tool: str, output: str) -> str:
        """Computes the SHA-256 cryptographic signature linking this step to the parent."""
        payload = f"{prev_hash}|{index}|{timestamp}|{decision}|{tool}|{output}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def log_step(self, decision: str, tool_name: str = "none", 
                 tool_args: Optional[Dict[str, Any]] = None, 
                 tool_output: str = "none") -> str:
        """
        Appends a secure, chained audit block to the traceability manifest.
        Returns the SHA-256 signature of the recorded step.
        """
        timestamp = time.time()
        args_str = json.dumps(tool_args or {})
        
        # Calculate chained hash signature
        current_hash = self._calculate_hash(
            prev_hash=self.last_hash,
            index=self.index,
            timestamp=timestamp,
            decision=decision,
            tool=f"{tool_name}:{args_str}",
            output=tool_output
        )
        
        record = {
            "index": self.index,
            "agent": self.agent_name,
            "timestamp": timestamp,
            "previous_hash": self.last_hash,
            "hash": current_hash,
            "decision": decision,
            "tool": tool_name,
            "arguments": tool_args or {},
            "output": tool_output
        }
        
        # Append-only write operation
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            
        print(f"🔒 Chained Trace Logged: Step #{self.index} // Hash: {current_hash[:8]}...")
        
        # Advance chain pointers
        self.last_hash = current_hash
        self.index += 1
        
        return current_hash
