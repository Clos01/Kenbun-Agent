# Handoff Report — Telemetry Concurrency Verification

## 1. Observation
We observed the following:
- In `core/tools/strategy/strategy_manager.py`, the function `update_intelligence(self, tool_id: str, category: str, success: bool)` (lines 258-296) performs a read-modify-write operation:
  ```python
  264:         alpha, beta, s, f = self.get_tool_stats(tool_id)
  265:         
  266:         if success:
  267:             alpha += 1
  268:             s += 1
  269:         else:
  270:             beta += 1
  271:             f += 1
  ```
  And then executes the database update inside a `self._lock` lock for local SQLite:
  ```python
  277:                 with self._lock:
  278:                     cursor = self.local_conn.cursor()
  279:                     cursor.execute(...)
  ```
  However, the read operation `get_tool_stats` is executed *outside* the lock.
- In `core/tools/utils/bayesian.py`, `tune_swarm(tool_id: str, success: bool, category: str = "global")` (lines 32-91) connects directly to PostgreSQL:
  ```python
  38:         with get_connection() as conn:
  39:             with conn.cursor() as cur:
  ...
  ```
  And catches exceptions without fallback to SQLite:
  ```python
  87:     except Exception as e:
  88:         logger.error(f"❌ DB tuning error: {e}")
  89:         return f"❌ Tuning failed: {e}"
  ```
- Running the stress test script `core/tests/test_telemetry_stress.py` with 100 concurrent tasks (50 successes, 50 failures) using 5 threads resulted in:
  - SQLite: Expected Success=50, Actual=13. Expected Failure=50, Actual=10.
  - Postgres: Expected Success=50, Actual=25. Expected Failure=50, Actual=19.

---

## 2. Logic Chain
1. Because `update_intelligence()` fetches current stats (`alpha, beta, s, f`) outside of the write lock `self._lock`, concurrent threads can fetch the same stale values before any thread commits its write.
2. When multiple threads fetch the same stale values, they all calculate the increment based on the same state (e.g. `s = 1 + 1 = 2`), and sequentially write this value back to the database.
3. This leads to lost updates where the database state represents only a fraction of the actual executed updates, causing massive data loss under concurrency (observed up to 77% lost updates in SQLite stress test).
4. Because `tune_swarm()` uses relative increment syntax (`SET success_count = success_count + %s`), its database-level updates are atomic and do not suffer from race conditions.
5. However, since `update_intelligence()` uses read-modify-write and overwrites the database with absolute values, concurrent executions of `update_intelligence()` will overwrite and wipe out any atomic updates made by concurrent `tune_swarm()` calls.
6. Furthermore, because `tune_swarm()` does not implement local SQLite fallback, all of its updates fail when PostgreSQL is offline, whereas `update_intelligence()` successfully falls back to SQLite, causing data divergence between the two interfaces.

---

## 3. Caveats
- The concurrency test was executed using a mocked PostgreSQL client that redirects queries to an in-memory/local SQLite database structure. While this accurately models the logical SQL behavior of the postgres connection, physical lock contention may differ on a production PostgreSQL database.
- We did not evaluate the impact of this telemetry data loss on the Thompson Sampling choice probability drift, although mathematically it will lead to delayed or incorrect convergence.

---

## 4. Conclusion
The integration of success and failure trials is functionally incomplete and prone to severe race conditions. Specifically:
1. `update_intelligence()` suffers from a critical race condition under concurrency, leading to massive lost telemetry updates.
2. `tune_swarm()` lacks local SQLite database fallback, which leads to silent failure and data divergence when PostgreSQL is offline.

---

## 5. Verification Method
To independently verify:
1. Run the stress test suite using pytest:
   ```bash
   PYTHONPATH=core .venv/bin/pytest core/tests/test_telemetry_stress.py -s
   ```
2. Verify that both tests fail with assertions showing discrepancies between expected and actual successes/failures.
3. Inspect `core/tools/strategy/strategy_manager.py` (lines 258-296) to confirm the read operation `get_tool_stats` is called before and outside the locking block.
