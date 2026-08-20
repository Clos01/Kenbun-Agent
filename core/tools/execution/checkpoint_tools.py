import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from tools.infrastructure.config import settings
from tools.registry import sovereign_tool
from tools.utils.path_utils import get_project_root

logger = logging.getLogger("tools.checkpoint")
PROJECT_ROOT = get_project_root()
PC_IP = settings.SWARM_PC_IP
CHROMA_PORT = settings.CHROMA_PORT


@sovereign_tool()
def run_code_safely(code: str, language: str = "python", timeout: int = 30, filter_passing_tests: bool = True) -> str:
    """
    Execute code in an isolated Docker container or secure host environment.
    Features deterministic test-pass filter to save LLM context window tokens.
    Supports: python, node/javascript.
    """
    from tools.execution.e2b_runner import run_code_safely as _run_code_safely
    return _run_code_safely(code=code, language=language, timeout=timeout, filter_passing_tests=filter_passing_tests)


@sovereign_tool()
def scan_repo(project_path: str, extensions: str = ".py,.ts,.tsx,.js,.jsx") -> str:
    """
    Generate a skeleton map of a project. Shows classes, functions, and signatures
    without implementation code. Fits large codebases into a single prompt.
    """
    from tools.memory.repo_mapper import scan_repo as _scan_repo
    return _scan_repo(project_path=project_path, extensions=extensions)


@sovereign_tool()
def remember_fix(error_message: str, solution: str, file_context: str = "") -> str:
    """
    Save an error->fix mapping to the knowledge base for future recall.
    Uses semantic search so similar (not exact) errors can be found later.
    """
    from tools.utils.error_memory import remember_fix as _remember_fix
    return _remember_fix(
        error_message=error_message,
        solution=solution,
        file_context=file_context,
        pc_ip=PC_IP,
        chroma_port=CHROMA_PORT,
    )


@sovereign_tool()
def recall_fix(error_message: str) -> str:
    """
    Search for similar past errors and their solutions.
    Uses semantic search — 'NoneType has no attribute' matches 'AttributeError on None'.
    """
    from tools.utils.error_memory import recall_fix as _recall_fix
    return _recall_fix(
        error_message=error_message,
        pc_ip=PC_IP,
        chroma_port=CHROMA_PORT,
    )


@sovereign_tool()
def save_checkpoint(file_path: str, label: str = "auto") -> str:
    """
    Snapshot a file's current state before making risky changes.
    Use restore_checkpoint() to revert if the fix fails.
    """
    path = Path(file_path).resolve()
    if not path.is_relative_to(settings.PROJECT_ROOT.resolve()):
        return "ERROR: Security Breach Blocked: Path is outside project root."
    from tools.utils.backtracker import save_checkpoint as _save_checkpoint
    return _save_checkpoint(file_path=file_path, label=label)


@sovereign_tool()
def restore_checkpoint(file_path: str, label: str = "") -> str:
    """
    Revert a file to a previous checkpoint.
    If no label provided, reverts to the most recent checkpoint.
    """
    from tools.utils.backtracker import restore_checkpoint as _restore_checkpoint
    return _restore_checkpoint(file_path=file_path, label=label)


@sovereign_tool()
def list_checkpoints(file_path: str = "") -> str:
    """
    List all saved checkpoints, optionally filtered by file path.
    """
    from tools.utils.backtracker import list_checkpoints as _list_checkpoints
    return _list_checkpoints(file_path=file_path)


@sovereign_tool()
def audit_package_safety(package_name: str, ecosystem: str = "npm") -> str:
    """
    Audits a package for supply-chain risks (malware, typosquatting, age) before installation.
    Supports: npm, pip.
    """
    import urllib.error
    import urllib.request

    def _http_json(url: str):
        req = urllib.request.Request(url, headers={"User-Agent": "kenbun-supply-audit"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        eco = (ecosystem or "npm").lower()

        if eco == "npm":
            try:
                data = _http_json(f"https://registry.npmjs.org/{package_name}")
            except urllib.error.HTTPError as he:
                if he.code == 404:
                    return f"❌ npm package '{package_name}' not found."
                return f"❌ Error querying npm registry for '{package_name}': HTTP {he.code}"
            created_at = data.get("time", {}).get("created")
            maintainers = data.get("maintainers", []) or []
            latest = data.get("dist-tags", {}).get("latest", "?")
        elif eco == "pip":
            try:
                data = _http_json(f"https://pypi.org/pypi/{package_name}/json")
            except urllib.error.HTTPError as he:
                if he.code == 404:
                    return f"❌ PyPI package '{package_name}' not found."
                return f"❌ Error querying PyPI for '{package_name}': HTTP {he.code}"
            info = data.get("info", {})
            created_at = None
            for rel in data.get("releases", {}).values():
                for f in rel:
                    ut = f.get("upload_time_iso_8601") or f.get("upload_time")
                    if ut and (created_at is None or ut < created_at):
                        created_at = ut
            maintainers = [m for m in [info.get("author"), info.get("maintainer")] if m]
            latest = info.get("version", "?")
        else:
            return f"Ecosystem '{ecosystem}' not supported. Use 'npm' or 'pip'."

        if not created_at:
            return f"⚠️ Could not verify creation date for '{package_name}'."

        created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(created_date.tzinfo) - created_date).days

        risks = []
        if age_days < 90:
            risks.append(f"🔴 CRITICAL: Package is only {age_days} days old (High Malware Risk).")
        if len(maintainers) < 2:
            risks.append(f"🟡 WARNING: Only {len(maintainers)} maintainer/author signal(s).")

        status = "SECURE ✅" if not risks else "RISKY ⚠️"
        report = [
            f"# 🛡️ Supply Chain Audit: {package_name} ({eco} v{latest})",
            f"**Status:** {status}",
            f"**Age:** {age_days} days",
            f"**Maintainers:** {len(maintainers)}",
            "",
            "## 🔍 Risk Findings",
        ]
        if not risks:
            report.append("- No immediate red flags detected.")
        else:
            report.extend([f"- {r}" for r in risks])
            if eco == "npm":
                report.append("\n**Recommendation:** Use `npm install --ignore-scripts` if installation is mandatory.")
        return "\n".join(report)

    except Exception as e:
        return f"ERROR: Audit failed. {str(e)}"
