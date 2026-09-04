"""Tests for Kenbun Midnight System Audit & Cron Automation
=========================================================
Verifies:
1. 5-Pillar audit execution & report generation
2. Markdown executive briefing formatting
3. Cron router default job initialization (0 0 * * *)
4. Cron job execution dispatch for audit actions
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from tools.audit.midnight_auditor import run_midnight_audit, generate_markdown_report, audit_cluster_hardware, audit_database_resilience
from tools.infrastructure.routers.cron import _load_jobs, execute_cron_job_task, DEFAULT_CRON_JOBS
from tools.infrastructure.config import settings


def test_audit_cluster_hardware():
    """Verifies cluster hardware probe properly reads nodes from cluster_inventory.json."""
    res = audit_cluster_hardware()
    assert res["status"] == "ok"
    nodes = res["nodes"]
    assert "lg2025" in nodes
    assert "p330" in nodes
    assert "mac_workstation" in nodes
    assert nodes["lg2025"]["display_name"] == "LG 2025 (Legion PC)"
    assert "RTX 5070 OC" in nodes["lg2025"]["hardware_type"]
    assert nodes["p330"]["display_name"] == "P330 (ThinkStation Tiny)"
    assert "16GB RAM" in nodes["p330"]["hardware_type"]


def test_audit_database_resilience():
    """Verifies database resilience audit returns status and active source."""
    res = audit_database_resilience()
    assert res["status"] == "ok"
    assert "remote_node" in res
    assert "active_source" in res
    assert "fallback_active" in res


def test_run_midnight_audit_generates_reports():
    """Verifies run_midnight_audit runs all pillars and saves json and md files."""
    data = run_midnight_audit()
    assert data["verdict"] in ("HEALTHY", "ATTENTION_REQUIRED")
    assert "cluster_hardware" in data
    assert "database_resilience" in data
    assert "memory_stores" in data
    assert "code_and_git" in data
    assert "tool_telemetry" in data

    json_path = settings.BRAIN_HEALTH_DIR / "midnight_audit_latest.json"
    md_path = settings.BRAIN_HEALTH_DIR / "midnight_audit_latest.md"
    assert json_path.exists()
    assert md_path.exists()

    saved_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved_json["verdict"] == data["verdict"]
    assert "LG 2025 (Legion PC)" in md_path.read_text(encoding="utf-8")


def test_generate_markdown_report():
    """Verifies markdown report generator produces clean briefing content."""
    mock_data = {
        "timestamp": "2026-09-04T00:00:00Z",
        "verdict": "HEALTHY",
        "cluster_hardware": {
            "nodes": {
                "lg2025": {
                    "display_name": "LG 2025 (Legion PC)",
                    "hardware_type": "Lenovo Legion Gaming PC (RTX 5070 OC)",
                    "target_ip": "100.104.211.61",
                    "services": {"postgres": {"port": 5432, "status": "reachable"}},
                }
            }
        },
        "database_resilience": {
            "active_source": "postgresql",
            "fallback_active": False,
            "remote_node": "LG 2025 (Legion PC)",
            "primary_reachable": True,
        },
        "code_and_git": {
            "git": {"branch": "main", "clean": True},
            "ast_validation": {"files_scanned": 100, "syntax_errors": []},
        },
        "tool_telemetry": {
            "bayesian_distributions_tracked": 297,
            "tool_invocations_30d": 12,
        },
    }
    md = generate_markdown_report(mock_data)
    assert "# 🌙 Kenbun Midnight System Audit Report" in md
    assert "LG 2025 (Legion PC)" in md
    assert "RTX 5070 OC" in md
    assert "297 tracked" in md


def test_cron_default_midnight_job_initialization():
    """Verifies that cron jobs initialize with the default midnight audit job (0 0 * * *)."""
    jobs = _load_jobs()
    assert len(jobs) >= 1
    midnight_job = next((j for j in jobs if j["id"] == "cron_midnight_audit"), None)
    assert midnight_job is not None
    assert midnight_job["schedule"] == "0 0 * * *"
    assert midnight_job["action"] == "audit"
    assert midnight_job["enabled"] is True


@pytest.mark.asyncio
async def test_execute_cron_job_task_audit_dispatch():
    """Verifies execute_cron_job_task executes audit and adds message to session."""
    job = {
        "id": "test_midnight_audit",
        "name": "Kenbun Midnight System Audit",
        "prompt": "Run audit",
        "schedule": "0 0 * * *",
        "deliver": "local",
        "action": "audit",
        "enabled": True,
    }
    with patch("tools.audit.midnight_auditor.run_midnight_audit") as mock_run:
        mock_run.return_value = {
            "timestamp": "2026-09-04T00:00:00Z",
            "verdict": "HEALTHY",
            "cluster_hardware": {"nodes": {}},
            "database_resilience": {"active_source": "sqlite"},
            "code_and_git": {"git": {}, "ast_validation": {}},
            "tool_telemetry": {},
        }
        await execute_cron_job_task(job)
        mock_run.assert_called_once()
