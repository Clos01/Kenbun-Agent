# Handoff Report — Review of Success and Failure Trials Integration

## 1. Observation

- **PostgreSQL Schema Definition**:
  In `core/tools/memory/postgres_client.py` (lines 20-30):
  ```python
  CREATE TABLE IF NOT EXISTS bayesian_weights (
      tool_id VARCHAR(255) NOT NULL,
      category VARCHAR(255) NOT NULL DEFAULT 'global',
      alpha FLOAT NOT NULL DEFAULT 1.0,
      beta FLOAT NOT NULL DEFAULT 1.0,
      success_count INTEGER NOT NULL DEFAULT 0,
      failure_count INTEGER NOT NULL DEFAULT 0,
      last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (tool_id, category)
  );
  ```

- **SQLite Schema Definition**:
  In `core/tools/strategy/strategy_manager.py` (lines 191-201):
  ```python
  CREATE TABLE IF NOT EXISTS intelligence (
      tool_id TEXT PRIMARY KEY,
      category TEXT,
      alpha REAL DEFAULT 2.0,
      beta REAL DEFAULT 2.0,
      success_count INTEGER DEFAULT 0,
      failure_count INTEGER DEFAULT 0,
      timestamp TEXT
  )
  ```

- **BayesianGovernor Query**:
  In `core/tools/strategy/strategy_manager.py` (lines 238-240):
  ```python
  cur.execute("SELECT alpha, beta, success_count, failure_count FROM bayesian_weights WHERE tool_id = %s", (tool_id,))
  row = cur.fetchone()
  ```

- **Tuning Seeding logic**:
  In `core/tools/utils/bayesian.py` (lines 65-85):
  ```python
  # 2. Update Category-specific (if not global)
  if category != "global":
      # If category record doesn't exist, we must seed it from the current global value first.
      cur.execute("""
          INSERT INTO bayesian_weights (tool_id, category, alpha, beta, success_count, failure_count)
          SELECT %s, %s, alpha, beta, success_count, failure_count FROM bayesian_weights WHERE tool_id = %s AND category = 'global'
          ON CONFLICT (tool_id, category) DO NOTHING
      """, (tool_id, category, tool_id))

      cur.execute("""
          UPDATE bayesian_weights
          SET alpha = alpha + %s,
              beta = beta + %s,
              success_count = success_count + %s,
              failure_count = failure_count + %s,
              last_updated = CURRENT_TIMESTAMP
          WHERE tool_id = %s AND category = %s
      """, (
          1.0 if success else 0.0,
          0.0 if success else 1.0,
          1 if success else 0,
          0 if success else 1,
          tool_id, category
      ))
  ```

- **Test execution command and output**:
  Command: `PYTHONPATH=core .venv/bin/python -m pytest core/tests/test_strategy.py core/tests/test_edge_cases.py`
  Result: `23 passed, 1 warning in 3.95s`

---

## 2. Logic Chain

1. **Schema Mismatch**:
   - The PostgreSQL schema uses `PRIMARY KEY (tool_id, category)`, allowing multiple records for a single `tool_id`.
   - The SQLite fallback uses `PRIMARY KEY (tool_id)`, allowing only a single record for a single `tool_id`.
   - Therefore, the SQLite fallback cannot store per-category weights, violating functional parity.

2. **Query Flaw & Data Leakage**:
   - Because `get_tool_stats(tool_id)` does not filter on `category`, PostgreSQL executes `WHERE tool_id = %s` matching all category rows for that tool.
   - Because `cur.fetchone()` returns the first matching row, the selected values are arbitrary/non-deterministic when multiple category rows exist.
   - In `update_intelligence(tool_id, category, success)`, these arbitrary values are read, incremented, and written to the target category.
   - Therefore, statistics leak across categories, corrupting the Bayesian learning data.

3. **Double Counting**:
   - In `tune_swarm`, when a category-specific trial runs, it first updates the `'global'` row.
   - If the category row doesn't exist, it copies `'global'` (which already contains the updated current trial counts).
   - It then immediately executes an `UPDATE` on the category record adding the current trial counts a second time.
   - Therefore, the first category trial is double-counted.

---

## 3. Caveats

- We did not connect to a live PostgreSQL server; findings are based on static analysis of queries and database structures.
- Tests passed because the current unit test suite only verifies operations with single-row tools (no tests verify category isolation).

---

## 4. Conclusion

The trial integration code changes contain critical correctness defects and database schema mismatches:
- Non-deterministic SELECT in `get_tool_stats()` leading to statistics leakage across categories under Postgres.
- Schema inconsistency where SQLite has no composite key on `category`.
- Double-counting bug during category seeding in `tune_swarm()`.

The final verdict is **REQUEST_CHANGES**.

---

## 5. Verification Method

- **Files to Inspect**:
  - `core/tools/strategy/strategy_manager.py` (lines 220–256)
  - `core/tools/utils/bayesian.py` (lines 62–85)
- **Test execution**:
  `PYTHONPATH=core .venv/bin/python -m pytest core/tests/test_strategy.py core/tests/test_edge_cases.py`
- **Invalidation Condition**:
  Insert two rows with same `tool_id` but different categories (e.g. `'global'` with alpha=2.0 and `'security'` with alpha=10.0) into PostgreSQL. Run `governor.get_tool_stats(tool_id)` multiple times and verify if it returns the correct category stats or if it exhibits non-deterministic outputs.
