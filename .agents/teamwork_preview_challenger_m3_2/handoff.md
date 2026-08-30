# Handoff Report - 2026-07-10T15:31:00Z

## 1. Observation
We observed the following output when executing the test suite with the new concurrency stress tests on telemetry updates:

Command executed:
```bash
PYTHONPATH=core .venv/bin/pytest core/tests/test_edge_cases.py core/tests/test_telemetry_stress.py -v
```

Verbatim results:
```
core/tests/test_edge_cases.py::TestEdgeCases::test_bayesian_governor_local_fallback PASSED [  4%]
core/tests/test_edge_cases.py::TestEdgeCases::test_bayesian_governor_sqlite_operations PASSED [  9%]
core/tests/test_edge_cases.py::TestEdgeCases::test_bayesian_governor_sample_strategy PASSED [ 13%]
core/tests/test_edge_cases.py::TestEdgeCases::test_bayesian_governor_telemetry_pulse PASSED [ 18%]
core/tests/test_edge_cases.py::TestEdgeCases::test_bayesian_governor_postgres_operations PASSED [ 22%]
...
core/tests/test_telemetry_stress.py::test_telemetry_sqlite_stress FAILED [ 95%]
core/tests/test_telemetry_stress.py::test_telemetry_postgres_stress FAILED [100%]

=================================== FAILURES ===================================
_________________________ test_telemetry_sqlite_stress _________________________
core/tests/test_telemetry_stress.py:144: in test_telemetry_sqlite_stress
    assert actual_success == expected_success, f"Race condition! Expected {expected_success} successes, got {actual_success}"
E   AssertionError: Race condition! Expected 50 successes, got 12
E   assert 12 == 50
----------------------------- Captured stderr call -----------------------------
SQLite Stats: Expected Success=50, Actual=12
SQLite Stats: Expected Failure=50, Actual=10

________________________ test_telemetry_postgres_stress ________________________
core/tests/test_telemetry_stress.py:244: in test_telemetry_postgres_stress
    assert actual_success == expected_success, f"PG Success Race! Expected {expected_success}, got {actual_success}"
E   AssertionError: PG Success Race! Expected 50, got 28
E   assert 28 == 50
----------------------------- Captured stderr call -----------------------------
Postgres/Proxy Stats: Expected Success=50, Actual=28
Postgres/Proxy Stats: Expected Failure=50, Actual=19
```

In `core/tools/strategy/strategy_manager.py` (lines 264-289):
```python
        alpha, beta, s, f = self.get_tool_stats(tool_id)
        
        if success:
            alpha += 1
            s += 1
        else:
            beta += 1
            f += 1
            
        timestamp = str(time.time())

        if self.use_local and self.local_conn:
            try:
                with self._lock:
                    cursor = self.local_conn.cursor()
                    cursor.execute('''
                    INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tool_id) DO UPDATE SET
                        category=excluded.category,
...
```

## 2. Logic Chain
1. In `update_intelligence()`, the current counts are read from the database using `self.get_tool_stats(tool_id)` *outside* of any thread lock or transactional isolation boundary.
2. Multiple threads calling `update_intelligence()` concurrently for the same tool ID can clear the cache, execute `get_tool_stats()` concurrently, and read identical metric counts (e.g. `success_count = 0`).
3. Each thread computes the increment locally in Python (e.g. `s += 1` becomes `1`), then writes the full incremented values to the database.
4. When SQLite writes are executed within `with self._lock:`, they are serialized, meaning they execute one after another. However, because both threads computed the new count starting from `0`, both write the value `1`. The second write overwrites the first write, losing one success update.
5. In PostgreSQL mode, the same read-modify-write pattern exists. Additionally, because `update_intelligence()` writes using a full row overwrite (`ON CONFLICT DO UPDATE SET alpha = EXCLUDED.alpha, success_count = EXCLUDED.success_count`), it overwrites the correct, atomic increments performed concurrently by `tune_swarm()`.
6. Therefore, the counts retrieved via `get_all_stats()` are significantly lower than the actual number of executions.

## 3. Caveats
No caveats. The bug has been reproduced cleanly, and the logic has been verified.

## 4. Conclusion
The telemetry updates codebase is not thread-safe. Concurrent calls to `update_intelligence()` and `tune_swarm()` suffer from critical race conditions that lead to telemetry data loss. This compromises the Thompson sampling routing. The implementation must be refactored to perform atomic increments directly on the database engine.

## 5. Verification Method
To independently verify the bug:
1. Run the stress tests using pytest:
   ```bash
   PYTHONPATH=core .venv/bin/pytest core/tests/test_telemetry_stress.py -v
   ```
2. Observe both `test_telemetry_sqlite_stress` and `test_telemetry_postgres_stress` failing with `AssertionError` showing actual counts falling short of the expected 50 updates.
