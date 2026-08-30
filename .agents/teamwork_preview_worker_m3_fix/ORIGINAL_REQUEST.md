## 2026-07-10T15:32:00Z
Refactor the telemetry, strategy manager, and bayesian weight tuning implementations to fix correctness bugs and concurrency race conditions.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please perform the following refactoring tasks:

1. SQLite Composite Key and Self-Healing Migration:
   - In `core/tools/strategy/strategy_manager.py`, update `_init_local_db()` to define the `intelligence` table with composite primary key: `PRIMARY KEY (tool_id, category)`.
   - Add a self-healing migration block inside `_init_local_db()` right after connecting: query the table's info (using `PRAGMA table_info(intelligence)`), check the primary key columns, and if only `tool_id` is the primary key (the old schema), perform an online migration:
     - Rename `intelligence` to `intelligence_old`.
     - Create the new `intelligence` table with the composite primary key `(tool_id, category)` and category defaulting to `'global'`.
     - Copy the data: `INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count, timestamp) SELECT tool_id, COALESCE(category, 'global'), alpha, beta, success_count, failure_count, timestamp FROM intelligence_old`.
     - Drop `intelligence_old`.
     - Commit the transaction.

2. Category-Aware Weight Retrieval:
   - Update `get_tool_stats(self, tool_id: str, category: str = 'global')` in `core/tools/strategy/strategy_manager.py` to accept the category parameter (defaulting to `'global'`).
   - Modify the select queries under both PostgreSQL and SQLite fallback to filter by `tool_id` and `category` (e.g. `WHERE tool_id = ? AND category = ?`).
   - If the specific category is not found and `category != 'global'`, fallback to querying the `'global'` category before returning default values.
   - In `update_intelligence()`, call `get_tool_stats(tool_id, category=category)`.

3. Atomic Database-Level Increments (Thread Safety):
   - In `update_intelligence()`, replace the read-modify-write pattern with atomic SQL updates using set increments:
     - For SQLite fallback: Use `ON CONFLICT(tool_id, category) DO UPDATE SET alpha = alpha + ?, beta = beta + ?, success_count = success_count + ?, failure_count = failure_count + ?, timestamp = excluded.timestamp`.
     - For PostgreSQL: Use `ON CONFLICT(tool_id, category) DO UPDATE SET alpha = bayesian_weights.alpha + EXCLUDED.alpha - 1.0, beta = bayesian_weights.beta + EXCLUDED.beta - 1.0, success_count = bayesian_weights.success_count + EXCLUDED.success_count, failure_count = bayesian_weights.failure_count + EXCLUDED.failure_count, last_updated = CURRENT_TIMESTAMP`.

4. Seeding and SQLite Fallback in Bayesian Weights Tuning:
   - In `core/tools/utils/bayesian.py`, refactor `tune_swarm(tool_id, success, category)` to perform the updates atomically to prevent double counting:
     - First, ensure the `'global'` row exists by running an `INSERT INTO ... VALUES ... ON CONFLICT DO NOTHING` query seeding it with default values (1.0, 1.0, 0, 0) if missing.
     - Second, if `category != 'global'`, ensure the category-specific row exists by running `INSERT INTO bayesian_weights (tool_id, category, alpha, beta, success_count, failure_count) SELECT %s, %s, alpha, beta, success_count, failure_count FROM bayesian_weights WHERE tool_id = %s AND category = 'global' ON CONFLICT (tool_id, category) DO NOTHING`.
     - Third, run an `UPDATE` on `'global'` row to atomically increment alpha/beta and success/failure counts.
     - Fourth, if `category != 'global'`, run an `UPDATE` on the category-specific row to atomically increment alpha/beta and success/failure counts.
   - Add local SQLite fallback: in the `except Exception` handler of `tune_swarm()`, connect to the local SQLite database at `settings.INTELLIGENCE_DB_PATH` and execute the exact same atomic seeding and increment logic on the `intelligence` table.

5. Division by Zero Protection:
   - In `get_confidence()` in `core/tools/utils/bayesian.py`, guard against division by zero: if `alpha + beta == 0`, return `0.5`.

6. Run verification and tests:
   - Run the full test suite and the concurrency stress tests:
     `PYTHONPATH=core .venv/bin/python -m pytest core/tests/test_strategy.py core/tests/test_edge_cases.py core/tests/test_telemetry_stress.py -v`
   - Confirm that all concurrency and telemetry tests now pass cleanly with zero lost updates.

7. Write a handoff report (`handoff.md`) in your working directory summarizing what you refactored, the exact commands you ran, and the results. Send a message when complete.
