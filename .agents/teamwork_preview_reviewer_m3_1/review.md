# Review Report

## Review Summary

**Verdict**: REQUEST_CHANGES

This review evaluates the integration of success and failure trials into the Bayesian weight tuning logic. While the implementation introduces the database schema modifications and parameters update queries correctly, a major logical flaw exists in the retrieval logic of the `BayesianGovernor` when running in PostgreSQL mode. Specifically, the composite primary key of the `bayesian_weights` table is ignored during single-tool statistic queries, leading to non-deterministic weight selection and potential contamination of category-specific weights.

---

## Findings

### [Major] Finding 1: Non-deterministic PostgreSQL Query in `BayesianGovernor.get_tool_stats`
- **What**: In `core/tools/strategy/strategy_manager.py`, `BayesianGovernor.get_tool_stats` executes:
  ```python
  cur.execute("SELECT alpha, beta, success_count, failure_count FROM bayesian_weights WHERE tool_id = %s", (tool_id,))
  ```
- **Where**: `core/tools/strategy/strategy_manager.py`, lines 239-242.
- **Why**: The PostgreSQL schema defines a composite primary key: `PRIMARY KEY (tool_id, category)`. Under this schema, a single tool can have multiple rows (e.g., `'global'` and `'security'`). Because the select query in `get_tool_stats` does not filter by category, running `cur.fetchone()` returns whichever row Postgres retrieves first. This is non-deterministic. When called by `update_intelligence` to get baseline weights before incrementing them, it can retrieve `'global'` weights but update `'security'` weights, contaminating the category-specific statistics.
- **Suggestion**: Update `get_tool_stats` to accept a `category` parameter (defaulting to `'global'`) and filter by it:
  ```python
  cur.execute("SELECT alpha, beta, success_count, failure_count FROM bayesian_weights WHERE tool_id = %s AND category = %s", (tool_id, category))
  ```

### [Minor] Finding 2: Unhandled Division by Zero in `BayesianGovernor.get_tool_confidence`
- **What**: In `core/tools/strategy/strategy_manager.py`, the `get_tool_confidence` method computes the success probability:
  ```python
  def get_tool_confidence(self, tool_id: str) -> float:
      alpha, beta, _, _ = self.get_tool_stats(tool_id)
      return alpha / (alpha + beta)
  ```
- **Where**: `core/tools/strategy/strategy_manager.py`, lines 428-431.
- **Why**: If both `alpha` and `beta` values are zero (or sum to zero due to manual database modification or reset), a `ZeroDivisionError` will be raised. This will bubble up and crash the calling routing path.
- **Suggestion**: Add error handling or a defensive check, similar to `get_avg_success_rate` or `get_confidence` in `bayesian.py`:
  ```python
  if (alpha + beta) == 0:
      return 0.5
  return alpha / (alpha + beta)
  ```

### [Minor] Finding 3: SQLite vs. PostgreSQL Schema Inconsistency
- **What**: The SQLite fallback database schema uses `tool_id TEXT PRIMARY KEY`, whereas PostgreSQL uses `PRIMARY KEY (tool_id, category)`.
- **Where**: `core/tools/strategy/strategy_manager.py` (lines 192-200) vs. `core/tools/memory/postgres_client.py` (lines 20-28).
- **Why**: This inconsistency means that category-specific updates behave differently depending on the database backend. Under SQLite, all category updates collapse into a single record per tool (since SQLite updates are on conflict of `tool_id`), whereas PostgreSQL maintains isolated records for each category.
- **Suggestion**: Standardize the local SQLite schema to match the composite primary key of the PostgreSQL schema:
  ```sql
  PRIMARY KEY (tool_id, category)
  ```

---

## Verified Claims

- **Test Suite Success**: Executed the test suite using `PYTHONPATH=core .venv/bin/python -m pytest core/tests/test_strategy.py core/tests/test_edge_cases.py`. All 23 tests passed successfully.
- **Query Parameter Mapping**: Inspected `tune_swarm` and remote `update_intelligence` queries to ensure that parameter tuple counts match query placeholders. Both match perfectly (9 parameters for the global insert/update, 6 parameters for the category update).
- **Connection Cleanup**: Audited all database connection acquisitions in the scoped files. Every call is wrapped inside a `with get_connection() as conn:` context manager, ensuring correct psycopg connection closing and transactions.

---

## Coverage Gaps

- None. All changed files specified in the request were fully inspected.

---

## Unverified Items

- None.
