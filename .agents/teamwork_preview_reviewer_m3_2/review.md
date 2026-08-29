## Review Summary

**Verdict**: REQUEST_CHANGES

The success and failure trials integration introduces a remote PostgreSQL weight store for the Bayesian Governor along with a local SQLite fallback. While the basic database operations, transaction handling, and security parametrization are correct, there is a critical design mismatch between PostgreSQL (supports per-category weights) and SQLite (only supports per-tool weights). This mismatch leads to incorrect database queries that result in data leakage across different tool categories, corrupting the Bayesian weights. Additionally, a double-counting bug was found in the category seeding logic.

---

## Findings

### [Critical] Finding 1: Database Schema Mismatch and Non-Deterministic Category Stats Query

- **What**: The PostgreSQL schema uses a composite primary key `(tool_id, category)` allowing multiple categories per tool. However, the SQLite schema uses `PRIMARY KEY (tool_id)`, and the governor's `get_tool_stats(tool_id)` method does not accept or filter by `category`.
- **Where**: `core/tools/strategy/strategy_manager.py` (lines 220–256) and `core/tools/memory/postgres_client.py` (lines 20–30).
- **Why**: 
  1. In PostgreSQL, executing `SELECT ... WHERE tool_id = %s` matches multiple rows if a tool has weights in multiple categories (e.g., `'global'` and `'security'`). `cur.fetchone()` returns an arbitrary/non-deterministic row.
  2. In `update_intelligence(tool_id, category, success)`, the governor reads the stats via `get_tool_stats(tool_id)` (obtaining a random category's stats), increments them, and inserts/updates them for the specific `category` in PostgreSQL. This causes category weights to leak into each other and corrupts the Bayesian statistics.
  3. The local SQLite fallback is unable to store per-category weights, behaving differently than the remote backend.
- **Suggestion**: 
  1. Align the SQLite schema in `_init_local_db` to use `PRIMARY KEY (tool_id, category)`.
  2. Update `get_tool_stats` to accept `category` and query the DB with both `tool_id` and `category`.
  3. If a specific category record does not exist in the database, query and fall back to the `'global'` record.

### [Major] Finding 2: Double-Counting of First Trial in Category Seeding

- **What**: Seeding a new category record from the `'global'` record in `tune_swarm` results in double-counting the current trial's success or failure.
- **Where**: `core/tools/utils/bayesian.py` (lines 63–85).
- **Why**: 
  1. `tune_swarm` first updates the `'global'` record (adding `1` to success or failure counts).
  2. If the specific category record does not exist, it seeds it using `INSERT INTO ... SELECT ... FROM bayesian_weights WHERE category = 'global'`. This copies the already-updated global stats (which include the current trial).
  3. Next, it runs an `UPDATE` on the category record adding the same trial value again. This causes the first trial in a category to be counted twice.
- **Suggestion**: Either seed the category record from `'global'` *before* updating the global record, or seed it using default priors (e.g. `alpha=2.0`, `beta=2.0`, counts=`0`) instead of copying the updated global record.

### [Major] Finding 3: Cache Invalidation Issues in Multi-Agent and Multithreaded Environments

- **What**: `get_tool_stats` is decorated with `@lru_cache(maxsize=128)`, which is prone to race conditions and stale data in Kenbun's multi-agent / distributed structure.
- **Where**: `core/tools/strategy/strategy_manager.py` (line 220).
- **Why**: If another agent process updates the Postgres weights database, the local process's in-memory LRU cache remains stale. Furthermore, in concurrent scenarios, threads may fetch stale stats from cache before `cache_clear()` completes.
- **Suggestion**: Use a cache with a short Time-To-Live (TTL) or disable in-memory caching for database lookups in distributed environments.

### [Minor] Finding 4: Missing Explicit SQLite Connection Cleanup

- **What**: The persistent SQLite connection `self.local_conn` is opened but never explicitly closed in `BayesianGovernor`.
- **Where**: `core/tools/strategy/strategy_manager.py`.
- **Why**: While Python handles cleaning up file handles on process exit, keeping connection resources open without a destructor (`__del__` or `.close()` method) is an anti-pattern that can cause resource leaks in test suites or situations where the governor is instantiated multiple times.
- **Suggestion**: Implement a `close()` method on `BayesianGovernor` to close the SQLite connection when the object is disposed.

---

## Verified Claims

- **Claim**: The test suite passes successfully.
  - *Verified via*: Running `PYTHONPATH=core .venv/bin/python -m pytest core/tests/test_strategy.py core/tests/test_edge_cases.py` in the workspace.
  - *Result*: **PASS** (23 tests passed, 1 warning).
- **Claim**: Parameterization protects against SQL injection.
  - *Verified via*: Code inspection of all PostgreSQL and SQLite queries in `postgres_client.py`, `strategy_manager.py`, and `bayesian.py`. All parameters are passed as tuples rather than string interpolation.
  - *Result*: **PASS**.
- **Claim**: Remote fallback to SQLite is functional.
  - *Verified via*: running `test_bayesian_governor_local_fallback` which mocks a connection timeout.
  - *Result*: **PASS**.

---

## Coverage Gaps

- **Gap**: Category-specific isolation test.
  - *Risk level*: **High**
  - *Recommendation*: Create a test in `test_edge_cases.py` that updates two different categories (e.g. `'ui'` and `'security'`) for the same `tool_id` and verifies that their stats do not pollute/leak into each other.

---

## Unverified Items

- **Item**: True PostgreSQL database behaviors under high concurrent load.
  - *Reason not verified*: No real PostgreSQL database was configured/available in the sandbox testing environment; queries were verified via unit test mocks.
