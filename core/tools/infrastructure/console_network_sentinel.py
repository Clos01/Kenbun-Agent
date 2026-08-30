"""
Console & Network Sentinel (Kenbun Pre-Flight & Runtime Diagnostics Engine).

Autonomously detects, audits, and diagnoses:
1. Browser & SSR Console Errors (console.error, React hydration errors, Runtime ReferenceError, Next.js error overlays).
2. Network Latency & HTTP Failures (500 Internal Server Error, 504 Gateway Timeout, connection timeouts).
3. Database Query Bottlenecks & Statement Timeouts (canceling statement due to statement timeout, N+1 correlated subqueries).
4. Pre-Flight Route Verification (probing application routes before users see bugs).
"""

from __future__ import annotations

import os
import sys
import time
import json
import re
import logging
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path

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

logger = logging.getLogger("tools.infrastructure.sentinel")

# Known runtime error signatures to detect in HTML/SSR responses and console streams
RUNTIME_ERROR_SIGNATURES = [
    (r"canceling statement due to statement timeout", "Database Statement Timeout (Slow Query / Heavy Subquery)"),
    (r"connection terminated due to connection timeout", "Database Connection Timeout (Firewall / Network Subnet)"),
    (r"ReferenceError:\s*(\w+)\s*is not defined", "Runtime ReferenceError (Undefined Variable / Missing Import)"),
    (r"TypeError:\s*Cannot read propert\w+ of (undefined|null)", "Runtime TypeError (Null / Undefined Property Access)"),
    (r"Hydration failed because the initial UI does not match", "React Hydration Error (SSR / Client Mismatch)"),
    (r"Unhandled Runtime Error", "Next.js Unhandled Runtime Exception"),
    (r"ECONNREFUSED", "Connection Refused (Server or Database Down)"),
    (r"ETIMEDOUT", "Socket Timeout"),
    (r"Error:\s*Next\.js version:", "Next.js Server-Side Exception Overlay"),
    (r"Internal Server Error", "500 Internal Server Error"),
    (r"Gateway Timeout", "504 Gateway Timeout"),
]


class ConsoleNetworkSentinel:
    """Pre-flight auditor for application routes, console logs, and network/DB health."""

    def __init__(self, base_url: str = "http://localhost:3000", default_timeout: float = 12.0):
        self.base_url = base_url.rstrip("/")
        self.default_timeout = default_timeout

    def probe_route(self, route: str) -> Dict[str, Any]:
        """Probes a single HTTP route, measuring latency, checking status code, and scanning for runtime errors."""
        target_url = f"{self.base_url}/{route.lstrip('/')}"
        start_time = time.perf_counter()
        
        req = urllib.request.Request(
            target_url,
            headers={
                "User-Agent": "Kenbun-ConsoleNetworkSentinel/1.0",
                "Accept": "text/html,application/xhtml+xml,application/json,*/*",
            }
        )

        result: Dict[str, Any] = {
            "route": route,
            "url": target_url,
            "status_code": 0,
            "latency_ms": 0.0,
            "status": "UNKNOWN",
            "errors_detected": [],
            "warnings": [],
        }

        try:
            with urllib.request.urlopen(req, timeout=self.default_timeout) as response:
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                result["status_code"] = response.status
                result["latency_ms"] = round(latency_ms, 2)
                
                body_bytes = response.read()
                body_text = body_bytes.decode("utf-8", errors="replace")

                # Scan for embedded error overlays or stack traces
                detected_errors = self._scan_text_for_errors(body_text)
                result["errors_detected"] = detected_errors

                if latency_ms > 2500.0:
                    result["warnings"].append(f"Slow response: {round(latency_ms, 1)}ms (>2500ms)")

                if detected_errors:
                    result["status"] = "ERROR"
                elif response.status >= 400:
                    result["status"] = "HTTP_ERROR"
                else:
                    result["status"] = "HEALTHY"

        except urllib.error.HTTPError as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            result["status_code"] = e.code
            result["latency_ms"] = round(latency_ms, 2)
            result["status"] = "HTTP_ERROR"
            
            try:
                err_body = e.read().decode("utf-8", errors="replace")
                result["errors_detected"] = self._scan_text_for_errors(err_body)
                if not result["errors_detected"]:
                    result["errors_detected"].append({
                        "signature": f"HTTP {e.code}: {e.reason}",
                        "category": "HTTP Error Response"
                    })
            except Exception:
                result["errors_detected"].append({
                    "signature": f"HTTP {e.code}: {e.reason}",
                    "category": "HTTP Error"
                })

        except urllib.error.URLError as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            result["latency_ms"] = round(latency_ms, 2)
            result["status"] = "UNREACHABLE"
            result["errors_detected"].append({
                "signature": str(e.reason),
                "category": "Network Connection Failure (Is server running?)"
            })

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            result["latency_ms"] = round(latency_ms, 2)
            result["status"] = "TIMEOUT" if "timed out" in str(e).lower() else "CRASH"
            result["errors_detected"].append({
                "signature": str(e),
                "category": "Request Timeout / Network Failure"
            })

        return result

    def _scan_text_for_errors(self, text: str) -> List[Dict[str, str]]:
        """Scans response content for known runtime error signatures."""
        found: List[Dict[str, str]] = []
        for pattern, category in RUNTIME_ERROR_SIGNATURES:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                found.append({
                    "signature": match.group(0),
                    "category": category
                })
        return found

    def audit_all_routes(self, routes: Optional[List[str]] = None) -> Dict[str, Any]:
        """Audits a complete list of core application routes."""
        if routes is None:
            routes = [
                "/",
                "/fleet-overview",
                "/voice-agents",
                "/call-telemetry",
                "/feedback",
                "/settings",
            ]

        results = []
        has_errors = False
        slow_routes = []

        for route in routes:
            res = self.probe_route(route)
            results.append(res)
            if res["status"] in ("ERROR", "HTTP_ERROR", "TIMEOUT", "CRASH"):
                has_errors = True
            if res["latency_ms"] > 1500.0:
                slow_routes.append({"route": route, "latency_ms": res["latency_ms"]})

        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base_url": self.base_url,
            "overall_status": "FAILED" if has_errors else "PASSED",
            "total_routes_checked": len(routes),
            "errors_found_count": sum(len(r["errors_detected"]) for r in results),
            "slow_routes_count": len(slow_routes),
            "slow_routes": slow_routes,
            "route_details": results,
        }


@sovereign_tool(name="audit_console_and_network", category="Infrastructure")
def audit_console_and_network(
    base_url: str = "http://localhost:3000",
    routes: Optional[List[str]] = None,
    timeout_sec: float = 12.0
) -> Dict[str, Any]:
    """
    Pre-flight audit tool: Probes application routes to capture console errors, Next.js SSR crashes,
    statement timeouts, React hydration mismatches, and network latency before the user encounters them.
    
    Args:
        base_url: Application root URL (defaults to http://localhost:3000).
        routes: List of specific subpaths to probe (e.g. ['/voice-agents', '/fleet-overview', '/settings']).
        timeout_sec: Maximum timeout per route request in seconds.
    """
    sentinel = ConsoleNetworkSentinel(base_url=base_url, default_timeout=timeout_sec)
    return sentinel.audit_all_routes(routes=routes)


@sovereign_tool(name="profile_database_performance", category="Infrastructure")
def profile_database_performance(
    query_description: str,
    raw_query_sql: Optional[str] = None,
    execution_time_ms: Optional[float] = None
) -> Dict[str, Any]:
    """
    Analyzes SQL query patterns and execution times to identify statement timeout risks,
    correlated subqueries, missing composite indexes, and N+1 query antipatterns.
    
    Args:
        query_description: Brief description of the query or endpoint hitting performance limits.
        raw_query_sql: The SQL query statement to analyze for antipatterns.
        execution_time_ms: Measured execution latency in milliseconds.
    """
    findings = []
    optimizations = []
    risk_level = "LOW"

    if execution_time_ms is not None:
        if execution_time_ms > 10000.0:
            risk_level = "CRITICAL"
            findings.append(f"Execution time {execution_time_ms:.1f}ms exceeds 10,000ms (High probability of Postgres 15s statement_timeout)")
            optimizations.append("Increase client statement_timeout to 30s and rewrite correlated subqueries into CTEs with pre-aggregations.")
        elif execution_time_ms > 2000.0:
            risk_level = "HIGH"
            findings.append(f"Execution time {execution_time_ms:.1f}ms is slow (>2000ms)")
            optimizations.append("Implement caching (React cache / in-memory cache) and optimize joins.")

    if raw_query_sql:
        sql_lower = raw_query_sql.lower()
        if "(select " in sql_lower and ("from transcripts" in sql_lower or "from webhook_events" in sql_lower):
            findings.append("Correlated subqueries detected in SELECT projection list scanning large tables for each returned row.")
            optimizations.append("Refactor correlated subqueries into isolated CTEs (e.g. WITH top_transcripts AS (SELECT DISTINCT ON (call_id) ...)).")
        
        if "substring(" in sql_lower and "join" in sql_lower:
            findings.append("Un-indexed regex substring extraction used inside JOIN or WHERE condition.")
            optimizations.append("Store foreign conversation IDs in dedicated indexed columns instead of running regex over text bodies.")

        if "group by" in sql_lower and "join eval_results" in sql_lower:
            findings.append("Joining large child table (eval_results) before GROUP BY creates massive intermediate Cartesian products.")
            optimizations.append("Pre-aggregate child table in a CTE before joining with parent entity.")

    return {
        "query_description": query_description,
        "risk_level": risk_level,
        "findings": findings,
        "recommended_optimizations": optimizations,
    }
