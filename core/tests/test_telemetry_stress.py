import os
import time
import threading
import sqlite3
import pytest

# Proxy classes to route psycopg Postgres queries to SQLite for testing
class SqlitePostgresCursorProxy:
    def __init__(self, sqlite_conn, lock):
        self.sqlite_conn = sqlite_conn
        self.lock = lock
        self.last_dict_rows = None
        self.last_row_index = 0

    def execute(self, query, params=None):
        # Translate PG style %s to SQLite style ?
        sqlite_query = query.replace('%s', '?')
        
        with self.lock:
            cur = self.sqlite_conn.cursor()
            if params:
                cur.execute(sqlite_query, params)
            else:
                cur.execute(sqlite_query)
            
            # Save results if SELECT query
            if sqlite_query.strip().upper().startswith("SELECT"):
                self.last_rows = cur.fetchall()
                if cur.description:
                    cols = [desc[0] for desc in cur.description]
                    self.last_dict_rows = [dict(zip(cols, r)) for r in self.last_rows]
                else:
                    self.last_dict_rows = []
                self.last_row_index = 0
            else:
                self.last_dict_rows = None
                self.sqlite_conn.commit()

    def fetchone(self):
        if self.last_dict_rows is not None:
            if self.last_row_index < len(self.last_dict_rows):
                r = self.last_dict_rows[self.last_row_index]
                self.last_row_index += 1
                return r
        return None

    def fetchall(self):
        return self.last_dict_rows or []

    def __iter__(self):
        return iter(self.last_dict_rows or [])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class SqlitePostgresConnectionProxy:
    def __init__(self, sqlite_conn, lock):
        self.sqlite_conn = sqlite_conn
        self.lock = lock

    def cursor(self):
        return SqlitePostgresCursorProxy(self.sqlite_conn, self.lock)

    def commit(self):
        with self.lock:
            self.sqlite_conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_telemetry_sqlite_stress(tmp_path, monkeypatch):
    """Stress test telemetry updates via local SQLite."""
    from tools.strategy.strategy_manager import BayesianGovernor
    gov = BayesianGovernor()
    gov.use_local = True
    
    db_path = tmp_path / "test_intel_stress.db"
    monkeypatch.setattr("tools.strategy.strategy_manager.LOCAL_DB_PATH", str(db_path))
    
    # Initialize the local database and bootstrap
    gov._init_local_db()
    
    # Target tool for testing
    tool_id = "test_stress_tool"
    category = "Strategy"
    
    # Ensure tool exists with default stats
    cursor = gov.local_conn.cursor()
    cursor.execute("DELETE FROM intelligence WHERE tool_id = ?", (tool_id,))
    cursor.execute(
        "INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count) VALUES (?, ?, 2.0, 2.0, 0, 0)",
        (tool_id, category)
    )
    gov.local_conn.commit()
    gov.get_tool_stats.cache_clear()

    # Define stress parameters
    num_threads = 5
    successes_per_thread = 10
    failures_per_thread = 10
    
    expected_success = num_threads * successes_per_thread
    expected_failure = num_threads * failures_per_thread
    
    def worker():
        for _ in range(successes_per_thread):
            gov.update_intelligence(tool_id, category, success=True)
        for _ in range(failures_per_thread):
            gov.update_intelligence(tool_id, category, success=False)
            
    threads = []
    start_time = time.time()
    for _ in range(num_threads):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    duration = time.time() - start_time
    print(f"\nSQLite Stress Test Duration: {duration:.4f}s")
    
    # Fetch final stats
    stats = gov.get_all_stats()
    tool_stats = next((s for s in stats if s["tool_id"] == tool_id), None)
    
    assert tool_stats is not None, "Tool not found in stats"
    
    actual_success = tool_stats["success_count"]
    actual_failure = tool_stats["failure_count"]
    
    print(f"SQLite Stats: Expected Success={expected_success}, Actual={actual_success}")
    print(f"SQLite Stats: Expected Failure={expected_failure}, Actual={actual_failure}")
    
    # Check if there was any loss of updates due to race conditions
    assert actual_success == expected_success, f"Race condition! Expected {expected_success} successes, got {actual_success}"
    assert actual_failure == expected_failure, f"Race condition! Expected {expected_failure} failures, got {actual_failure}"


def test_telemetry_postgres_stress(tmp_path, monkeypatch):
    """Stress test telemetry updates via Postgres (using SQL proxy to SQLite)."""
    # Create a SQLite DB to simulate Postgres
    pg_db_path = tmp_path / "mock_postgres.db"
    pg_sqlite_conn = sqlite3.connect(pg_db_path, check_same_thread=False)
    
    # Create the bayesian_weights table matching the Postgres schema
    pg_sqlite_conn.execute("""
        CREATE TABLE IF NOT EXISTS bayesian_weights (
            tool_id TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'global',
            alpha REAL NOT NULL DEFAULT 1.0,
            beta REAL NOT NULL DEFAULT 1.0,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (tool_id, category)
        );
    """)
    pg_sqlite_conn.commit()
    
    # Set up locks and proxies
    db_lock = threading.Lock()
    def mock_get_connection():
        return SqlitePostgresConnectionProxy(pg_sqlite_conn, db_lock)
        
    # Monkeypatch get_connection in both postgres_client and bayesian
    monkeypatch.setattr("tools.memory.postgres_client.get_connection", mock_get_connection, raising=False)
    monkeypatch.setattr("tools.utils.bayesian.get_connection", mock_get_connection, raising=False)
    
    # Set up BayesianGovernor configured for Postgres (use_local=False)
    from tools.strategy.strategy_manager import BayesianGovernor
    from tools.utils.bayesian import tune_swarm

    gov = BayesianGovernor()
    gov.use_local = False
    gov._ensure_db = lambda: None # Bypass remote connection checking
    
    tool_id = "postgres_stress_tool"
    category = "Strategy"
    
    # Seed the mock PG database with initial weights
    pg_sqlite_conn.execute(
        "INSERT INTO bayesian_weights (tool_id, category, alpha, beta, success_count, failure_count) VALUES (?, 'global', 2.0, 2.0, 0, 0)",
        (tool_id,)
    )
    pg_sqlite_conn.execute(
        "INSERT INTO bayesian_weights (tool_id, category, alpha, beta, success_count, failure_count) VALUES (?, ?, 2.0, 2.0, 0, 0)",
        (tool_id, category)
    )
    pg_sqlite_conn.commit()
    gov.get_tool_stats.cache_clear()
    
    # Concurrency parameters
    num_threads = 5
    updates_per_thread = 10
    
    expected_success = num_threads * updates_per_thread
    expected_failure = num_threads * updates_per_thread
    
    def worker():
        for _ in range(updates_per_thread):
            # Call tune_swarm (which updates Postgres atomically using ON CONFLICT DO UPDATE)
            tune_swarm(tool_id, success=True, category=category)
            # Call update_intelligence (which updates Postgres using read-modify-write)
            gov.update_intelligence(tool_id, category, success=False)
            
    threads = []
    start_time = time.time()
    for _ in range(num_threads):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    duration = time.time() - start_time
    print(f"\nPostgres Stress Test Duration: {duration:.4f}s")
    
    # Fetch final stats via get_all_stats
    stats = gov.get_all_stats()
    tool_stats = next((s for s in stats if s["tool_id"] == tool_id and s["category"] == category), None)
    
    assert tool_stats is not None, "Tool category not found in stats"
    
    actual_success = tool_stats["success_count"]
    actual_failure = tool_stats["failure_count"]
    
    print(f"Postgres/Proxy Stats: Expected Success={expected_success}, Actual={actual_success}")
    print(f"Postgres/Proxy Stats: Expected Failure={expected_failure}, Actual={actual_failure}")
    
    # Close connection
    pg_sqlite_conn.close()
    
    # Assert counts
    assert actual_success == expected_success, f"PG Success Race! Expected {expected_success}, got {actual_success}"
    assert actual_failure == expected_failure, f"PG Failure Race! Expected {expected_failure}, got {actual_failure}"
