"""Tests for Bayesian database fallback alerts, status reporting, backfill synchronizer, and resilience snapshot."""
import time
import pytest
from unittest.mock import MagicMock, patch

from tools.utils.bayesian import (
    get_db_status,
    record_db_fallback,
    tune_swarm,
    get_posterior_params,
    sync_local_to_postgres,
)
from tools.infrastructure.routers.resilience import _snapshot_database


def test_get_db_status_reports_fallback_when_postgres_fails():
    """Verifies get_db_status reports fallback mode and alert message when PostgreSQL connection fails."""
    with patch("tools.utils.bayesian.get_connection", side_effect=Exception("Connection refused (test)")):
        status = get_db_status()
        assert status["primary_reachable"] is False
        assert status["fallback_active"] is True
        assert status["active_source"] == "sqlite (fallback)"
        assert "Connection refused" in status["alert_message"]


def test_get_db_status_reports_primary_when_postgres_succeeds():
    """Verifies get_db_status reports primary mode when PostgreSQL connection succeeds."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    with patch("tools.utils.bayesian.get_connection", return_value=mock_conn):
        status = get_db_status()
        assert status["primary_reachable"] is True
        assert status["fallback_active"] is False
        assert status["active_source"] == "postgres (primary)"
        assert "Connected to primary" in status["alert_message"]


def test_record_db_fallback_populates_event_and_logs(caplog):
    """Verifies that record_db_fallback captures timestamp, operation, and logs an alert."""
    record_db_fallback("test_operation", "test_reason", {"foo": "bar"})
    status = get_db_status()
    last = status["last_fallback"]
    assert last is not None
    assert last["operation"] == "test_operation"
    assert last["reason"] == "test_reason"
    assert last["details"] == {"foo": "bar"}
    assert any("DATABASE FALLBACK ALERT" in record.message for record in caplog.records)


def test_get_posterior_params_falls_back_and_records_event():
    """Verifies get_posterior_params falls back to SQLite and records a fallback alert."""
    with patch("tools.utils.bayesian.get_connection", side_effect=Exception("PG Down")):
        alpha, beta = get_posterior_params("consult_supervisor", "security")
        assert alpha >= 1.0
        assert beta >= 1.0
        status = get_db_status()
        assert status["last_fallback"]["operation"] == "get_posterior_params"
        assert "PG Down" in status["last_fallback"]["reason"]


def test_resilience_snapshot_database_structure():
    """Verifies that _snapshot_database formats output compatible with Observatory resilience panel."""
    with patch("tools.utils.bayesian.get_connection", side_effect=Exception("Host Unreachable")):
        snap = _snapshot_database()
        assert snap["name"] == "Database & Bayesian intelligence"
        assert len(snap["providers"]) == 2
        names = [p["name"] for p in snap["providers"]]
        assert "postgres" in names
        assert "sqlite_local" in names
        
        # SQLite is healthy fallback
        sqlite_p = next(p for p in snap["providers"] if p["name"] == "sqlite_local")
        assert sqlite_p["healthy"] is True
        assert sqlite_p["primary"] is False
        
        # Postgres is flagged unhealthy
        pg_p = next(p for p in snap["providers"] if p["name"] == "postgres")
        assert pg_p["healthy"] is False
        assert pg_p["primary"] is True


def test_sync_local_to_postgres_handles_unreachable_pg_cleanly():
    """Verifies sync_local_to_postgres returns clean error envelope without crashing if PG is offline."""
    with patch("tools.utils.bayesian.get_connection", side_effect=Exception("PG Timeout")):
        res = sync_local_to_postgres()
        assert res["status"] == "error"
        assert "PG Timeout" in res["message"]
        assert res["synced_count"] == 0


def test_sync_local_to_postgres_upserts_when_connected():
    """Verifies sync_local_to_postgres reads SQLite and executes upserts into PostgreSQL."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("tools.utils.bayesian.get_connection", return_value=mock_conn):
        res = sync_local_to_postgres()
        assert res["status"] == "success"
        assert res["synced_count"] > 0
        assert mock_cur.execute.called
        assert mock_conn.commit.called
