"""
PhantomDrive - OpenViking File-Based Agent Memory System for Kenbun.

Organizes persistent agent context, architectural decision records (ADRs),
anti-patterns, and session summaries as a fast, searchable file system
that LLMs and coding agents can read and write natively with zero database lag.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class PhantomDrive:
    """File-based memory system for persistent cross-session agent context."""

    def __init__(self, base_path: Optional[str] = None):
        if base_path:
            self.root = Path(base_path)
        else:
            # Default to .kenbun/memory in the Kenbun workspace root
            self.root = Path("/Users/carlosrivas/Dev/Kenbun/.kenbun/memory")

        self.domains_dir = self.root / "domains"
        self.decisions_dir = self.root / "decisions"
        self.anti_patterns_dir = self.root / "anti_patterns"
        self.sessions_dir = self.root / "sessions"

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create all required memory subdirectories."""
        for d in [self.domains_dir, self.decisions_dir, self.anti_patterns_dir, self.sessions_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def write_domain_context(self, domain_name: str, content: str, overwrite: bool = True) -> str:
        """Write or update domain-specific architectural knowledge."""
        filename = f"{domain_name.lower().replace(' ', '_')}.md"
        filepath = self.domains_dir / filename

        if filepath.exists() and not overwrite:
            existing = filepath.read_text(encoding="utf-8")
            content = f"{existing}\n\n## Update ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n{content}"

        filepath.write_text(content.strip() + "\n", encoding="utf-8")
        return str(filepath)

    def read_domain_context(self, domain_name: str) -> Optional[str]:
        """Read domain-specific architectural knowledge."""
        filename = f"{domain_name.lower().replace(' ', '_')}.md"
        filepath = self.domains_dir / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return None

    def record_decision(
        self,
        adr_id: str,
        title: str,
        context: str,
        decision: str,
        consequences: str,
        status: str = "Accepted"
    ) -> str:
        """Record an Architectural Decision Record (ADR)."""
        filename = f"ADR-{adr_id.upper()}-{title.lower().replace(' ', '-')}.md"
        filepath = self.decisions_dir / filename

        content = f"""# ADR-{adr_id.upper()}: {title}

**Date:** {datetime.now().strftime('%Y-%m-%d')}
**Status:** {status}

## Context
{context.strip()}

## Decision
{decision.strip()}

## Consequences
{consequences.strip()}
"""
        filepath.write_text(content.strip() + "\n", encoding="utf-8")
        return str(filepath)

    def record_anti_pattern(
        self,
        pattern_id: str,
        name: str,
        problem: str,
        solution: str,
        reference_id: Optional[str] = None
    ) -> str:
        """Record a confirmed mistake or anti-pattern to permanently avoid."""
        filename = f"AP-{pattern_id.upper()}-{name.lower().replace(' ', '-')}.md"
        filepath = self.anti_patterns_dir / filename

        ref_line = f"**Reference ID:** `{reference_id}`\n" if reference_id else ""
        content = f"""# AP-{pattern_id.upper()}: {name}

**Logged:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
{ref_line}
## The Mistake / Anti-Pattern
{problem.strip()}

## The Verified Solution / Protocol
{solution.strip()}
"""
        filepath.write_text(content.strip() + "\n", encoding="utf-8")
        return str(filepath)

    def append_session_log(
        self,
        session_id: str,
        summary: str,
        tasks_completed: List[str],
        next_steps: Optional[List[str]] = None
    ) -> str:
        """Append session state to cross-session memory."""
        filename = f"session_{session_id}_{datetime.now().strftime('%Y%m%d')}.md"
        filepath = self.sessions_dir / filename

        completed_md = "\n".join([f"- [x] {task}" for task in tasks_completed])
        next_md = "\n".join([f"- [ ] {step}" for step in (next_steps or [])])

        content = f"""# Session State: {session_id}

**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## High-Level Summary
{summary.strip()}

## Tasks Completed
{completed_md}

## Next Recommended Actions
{next_md if next_md else "None pending."}
"""
        filepath.write_text(content.strip() + "\n", encoding="utf-8")
        return str(filepath)

    def search_memory(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Fast keyword & regex search across all markdown memory files."""
        results: List[Dict[str, Any]] = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)

        for category_dir in [self.domains_dir, self.decisions_dir, self.anti_patterns_dir, self.sessions_dir]:
            if not category_dir.exists():
                continue
            for file_path in category_dir.glob("*.md"):
                text = file_path.read_text(encoding="utf-8")
                matches = pattern.findall(text)
                if matches:
                    results.append({
                        "category": category_dir.name,
                        "file": file_path.name,
                        "path": str(file_path),
                        "match_count": len(matches),
                        "snippet": text[:300] + "..." if len(text) > 300 else text
                    })

        results.sort(key=lambda x: x["match_count"], reverse=True)
        return results[:max_results]

    def get_active_context_bundle(self) -> str:
        """Assemble a unified markdown context bundle for agent system prompts."""
        sections = ["# 🧠 KENBUN PHANTOM DRIVE MEMORY BUNDLE\n"]

        # Anti-patterns (Highest priority: mistakes to avoid)
        anti_files = sorted(list(self.anti_patterns_dir.glob("*.md")))
        if anti_files:
            sections.append("## 🛑 Active Anti-Patterns & Constraints")
            for f in anti_files[:4]:
                sections.append(f.read_text(encoding="utf-8").strip())
            sections.append("\n---\n")

        # Active Decisions (ADRs)
        decision_files = sorted(list(self.decisions_dir.glob("*.md")))
        if decision_files:
            sections.append("## 🏛️ Key Architectural Decisions (ADRs)")
            for f in decision_files[:3]:
                sections.append(f.read_text(encoding="utf-8").strip())
            sections.append("\n---\n")

        # Active Domains
        domain_files = sorted(list(self.domains_dir.glob("*.md")))
        if domain_files:
            sections.append("## 🌐 Domain Blueprints")
            for f in domain_files[:3]:
                sections.append(f.read_text(encoding="utf-8").strip())

        return "\n\n".join(sections)


if __name__ == "__main__":
    # Self-test & initialization
    drive = PhantomDrive()
    print("Initializing PhantomDrive files...")
    
    # Initialize Architecture Domain
    drive.write_domain_context(
        "system_architecture",
        """# System Architecture: Kenbun Sovereign Workbench

- **Host Machine:** Apple Silicon MacBook Pro (Coordinator)
- **Execution Satellite:** Lenovo ThinkStation P330 (Ubuntu 24.04, Quadro P600 GPU, Tailscale IP: 100.100.199.127)
- **Local VLM:** UI-TARS-2B + mmproj on P330 Port 8090
- **Display Pipeline:** Xorg on DISPLAY=:0 with HDMI dummy plug, console mirror on Port 5900 (VNC) and Port 3389 (RDP)
- **Core Orchestrator:** FastMCP running in Kenbun core with System 2 Supervisor audits
"""
    )

    # Initialize ADR-001
    drive.record_decision(
        "001",
        "Hardware Accelerated Console Mirror for Remote Desktop",
        "XRDP standard sessions spawned isolated secondary X servers that had no access to the GPU or physical DISPLAY=:0, causing black screens.",
        "Bind x11vnc to DISPLAY=:0 and configure XRDP [console-mirror] proxying to 127.0.0.1:5900. Auto-login configured in GDM3.",
        "Instant 60 FPS remote desktop access over macOS Screen Sharing and Windows App with zero authentication roadblocks."
    )

    # Initialize AP-001
    drive.record_anti_pattern(
        "001",
        "CUDA VLM Out-of-Memory on 2GB Quadro GPU",
        "Running llama-server with --gpus all and full fp16 mmproj (1.27GB) caused cudaMalloc OOM because Xorg already used ~800MB VRAM.",
        "Run UI-TARS multimodal vision encoder on 12-thread Intel i7 CPU with 448x252 Bilinear patch downscaling, achieving sub-5s local inference.",
        reference_id="fix_1787464133_e0767eacc0c4"
    )

    print("PhantomDrive successfully initialized!")
    print(f"Active Memory Files: {len(list(drive.root.rglob('*.md')))}")
    print(drive.get_active_context_bundle()[:500] + "...")
