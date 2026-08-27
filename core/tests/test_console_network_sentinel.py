"""Unit tests for Kenbun Console & Network Sentinel."""

import pytest
from tools.infrastructure.console_network_sentinel import (
    ConsoleNetworkSentinel,
    profile_database_performance,
    RUNTIME_ERROR_SIGNATURES,
)


def test_error_signature_detection():
    sentinel = ConsoleNetworkSentinel()
    
    # Test statement timeout detection
    text_with_timeout = "Error: canceling statement due to statement timeout at q (src/lib/db.ts:207:17)"
    errors = sentinel._scan_text_for_errors(text_with_timeout)
    assert len(errors) > 0
    assert "Database Statement Timeout" in errors[0]["category"]

    # Test ReferenceError detection
    text_with_ref_err = "ReferenceError: Settings is not defined at SettingsClient"
    errors_ref = sentinel._scan_text_for_errors(text_with_ref_err)
    assert len(errors_ref) > 0
    assert "Runtime ReferenceError" in errors_ref[0]["category"]

    # Clean text has 0 errors
    clean_text = "<!DOCTYPE html><html><body><h1>Dashboard Loaded</h1></body></html>"
    errors_clean = sentinel._scan_text_for_errors(clean_text)
    assert len(errors_clean) == 0


def test_profile_database_performance_slow_query():
    sql = """
    SELECT c.id,
           (SELECT t.raw_text FROM transcripts t WHERE t.call_id = c.id LIMIT 1) as transcript
    FROM calls c
    LEFT JOIN eval_results er ON er.call_id = c.id
    GROUP BY c.id
    """
    res = profile_database_performance(
        query_description="Recent calls query",
        raw_query_sql=sql,
        execution_time_ms=15500.0
    )

    assert res["risk_level"] == "CRITICAL"
    assert any("statement_timeout" in f for f in res["findings"])
    assert any("CTEs" in opt for opt in res["recommended_optimizations"])
    assert any("Correlated subqueries" in f for f in res["findings"])


def test_profile_database_performance_fast_query():
    res = profile_database_performance(
        query_description="Fast indexed lookup",
        raw_query_sql="SELECT id, agent_name FROM voice_agents WHERE id = $1",
        execution_time_ms=12.5
    )

    assert res["risk_level"] == "LOW"
    assert len(res["findings"]) == 0
