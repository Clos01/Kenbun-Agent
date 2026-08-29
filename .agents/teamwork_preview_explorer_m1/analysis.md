# Kenbun Telemetry & Database Analysis Report

## Summary
This analysis report details the changes required to accurately capture, store, and display success and failure counts for tools on the `/telemetry` dashboard. The Kenbun system uses a hybrid model of a remote PostgreSQL database (when reachable) and a local SQLite database fallback. Currently, the local SQLite database fully implements `success_count` and `failure_count` storage and updates, whereas the remote PostgreSQL database schema only tracks the `alpha` and `beta` values. By updating the PostgreSQL schema, adjusting the queries in the three core Python modules, and leveraging the existing `/stats` API endpoint, we can successfully restore full telemetry capability across both backends.

---

## 1. Schema Analysis & Database Migration

### Current Schema (`bayesian_weights`)
Defined in `core/tools/memory/postgres_client.py`:
```sql
CREATE TABLE IF NOT EXISTS bayesian_weights (
    tool_id VARCHAR(255) NOT NULL,
    category VARCHAR(255) NOT NULL DEFAULT 'global',
    alpha FLOAT NOT NULL DEFAULT 1.0,
    beta FLOAT NOT NULL DEFAULT 1.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tool_id, category)
);
```

### PostgreSQL Migration SQL Script
To add the success and failure trials columns to the PostgreSQL database, execute the following SQL migration script:
```sql
-- Migration: Add Success and Failure Trial Count Columns to bayesian_weights
ALTER TABLE bayesian_weights 
ADD COLUMN IF NOT EXISTS success_count INTEGER NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS failure_count INTEGER NOT NULL DEFAULT 0;
```

---

## 2. Codebase Implementation Plan

### A. File 1: `core/tools/memory/postgres_client.py`
We need to update the `init_db()` table creation query to ensure new systems are provisioned with the updated schema.

**Proposed Changes:**
```python
<<<<
                # 1. bayesian_weights
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bayesian_weights (
                        tool_id VARCHAR(255) NOT NULL,
                        category VARCHAR(255) NOT NULL DEFAULT 'global',
                        alpha FLOAT NOT NULL DEFAULT 1.0,
                        beta FLOAT NOT NULL DEFAULT 1.0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (tool_id, category)
                    );
                """)
====
                # 1. bayesian_weights
                cur.execute("""
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
                """)
>>>>
```

### B. File 2: `core/tools/strategy/strategy_manager.py`
The `BayesianGovernor` class manages weights retrieval and update. Currently, it hardcodes success and failure counts to `0` when fetching from PostgreSQL, and omits writing them to PostgreSQL.

**Proposed Changes:**

1. Update `get_tool_stats()` to query and return success/failure counts:
```python
<<<<
    @lru_cache(maxsize=128)
    def get_tool_stats(self, tool_id: str):
        """Retrieves weights from PostgreSQL or local SQLite."""
        self._ensure_db()
        if self.use_local and self.local_conn:
            try:
                with self._lock:
                    cursor = self.local_conn.cursor()
                    cursor.execute("SELECT alpha, beta FROM intelligence WHERE tool_id = ?", (tool_id,))
                    row = cursor.fetchone()
                    if row:
                        return float(row[0]), float(row[1]), 0, 0
            except Exception as e:
                print(f"Debug: Error getting local stats for {tool_id}: {e}")
            return 2.0, 2.0, 0, 0

        try:
            from tools.memory.postgres_client import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT alpha, beta FROM bayesian_weights WHERE tool_id = %s", (tool_id,))
                    row = cur.fetchone()
                    if row:
                        return float(row["alpha"]), float(row["beta"]), 0, 0
        except Exception as e:
            print(f"Debug: Error getting remote stats for {tool_id}: {e}")
            # Fallback to local SQLite if remote query fails
            if self.local_conn:
                try:
                    with self._lock:
                        cursor = self.local_conn.cursor()
                        cursor.execute("SELECT alpha, beta FROM intelligence WHERE tool_id = ?", (tool_id,))
                        row = cursor.fetchone()
                        if row:
                            return float(row[0]), float(row[1]), 0, 0
                except Exception as local_err:
                    print(f"Debug: Fallback to local stats also failed: {local_err}")
        return 2.0, 2.0, 0, 0
====
    @lru_cache(maxsize=128)
    def get_tool_stats(self, tool_id: str):
        """Retrieves weights from PostgreSQL or local SQLite."""
        self._ensure_db()
        if self.use_local and self.local_conn:
            try:
                with self._lock:
                    cursor = self.local_conn.cursor()
                    cursor.execute("SELECT alpha, beta, success_count, failure_count FROM intelligence WHERE tool_id = ?", (tool_id,))
                    row = cursor.fetchone()
                    if row:
                        return float(row[0]), float(row[1]), int(row[2]), int(row[3])
            except Exception as e:
                print(f"Debug: Error getting local stats for {tool_id}: {e}")
            return 2.0, 2.0, 0, 0

        try:
            from tools.memory.postgres_client import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT alpha, beta, success_count, failure_count FROM bayesian_weights WHERE tool_id = %s", (tool_id,))
                    row = cur.fetchone()
                    if row:
                        return float(row["alpha"]), float(row["beta"]), int(row["success_count"]), int(row["failure_count"])
        except Exception as e:
            print(f"Debug: Error getting remote stats for {tool_id}: {e}")
            # Fallback to local SQLite if remote query fails
            if self.local_conn:
                try:
                    with self._lock:
                        cursor = self.local_conn.cursor()
                        cursor.execute("SELECT alpha, beta, success_count, failure_count FROM intelligence WHERE tool_id = ?", (tool_id,))
                        row = cursor.fetchone()
                        if row:
                            return float(row[0]), float(row[1]), int(row[2]), int(row[3])
                except Exception as local_err:
                    print(f"Debug: Fallback to local stats also failed: {local_err}")
        return 2.0, 2.0, 0, 0
>>>>
```

2. Update PostgreSQL branch in `update_intelligence()` to persist success and failure counts:
```python
<<<<
        # Remote update to PostgreSQL
        try:
            from tools.memory.postgres_client import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute('''
                        INSERT INTO bayesian_weights (tool_id, category, alpha, beta, last_updated)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (tool_id, category) DO UPDATE SET
                            alpha = EXCLUDED.alpha,
                            beta = EXCLUDED.beta,
                            last_updated = CURRENT_TIMESTAMP
                    ''', (tool_id, category or 'global', alpha, beta))
                    conn.commit()
====
        # Remote update to PostgreSQL
        try:
            from tools.memory.postgres_client import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute('''
                        INSERT INTO bayesian_weights (tool_id, category, alpha, beta, success_count, failure_count, last_updated)
                        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (tool_id, category) DO UPDATE SET
                            alpha = EXCLUDED.alpha,
                            beta = EXCLUDED.beta,
                            success_count = EXCLUDED.success_count,
                            failure_count = EXCLUDED.failure_count,
                            last_updated = CURRENT_TIMESTAMP
                    ''', (tool_id, category or 'global', alpha, beta, s, f))
                    conn.commit()
>>>>
```

3. Update `get_all_stats()` to query PostgreSQL success and failure counts:
```python
<<<<
        try:
            from tools.memory.postgres_client import get_connection
            
            tool_data = {}
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT tool_id, category, alpha, beta, last_updated FROM bayesian_weights")
                    for row in cur:
                        t_id = row["tool_id"]
                        cat = row["category"]
                        alpha = row["alpha"]
                        beta = row["beta"]
                        ts = row["last_updated"]

                        # We have 'global' and specific categories. Prefer specific categories over 'global'.
                        if t_id not in tool_data or (cat != 'global' and tool_data[t_id]['category'] == 'global'):
                            tool_data[t_id] = {
                                "tool_id": t_id,
                                "category": cat,
                                "alpha": round(float(alpha), 2),
                                "beta": round(float(beta), 2),
                                "success_count": 0,
                                "failure_count": 0,
                                "timestamp": str(ts)
                            }
            return list(tool_data.values())
====
        try:
            from tools.memory.postgres_client import get_connection
            
            tool_data = {}
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT tool_id, category, alpha, beta, success_count, failure_count, last_updated FROM bayesian_weights")
                    for row in cur:
                        t_id = row["tool_id"]
                        cat = row["category"]
                        alpha = row["alpha"]
                        beta = row["beta"]
                        s = row["success_count"]
                        f = row["failure_count"]
                        ts = row["last_updated"]

                        # We have 'global' and specific categories. Prefer specific categories over 'global'.
                        if t_id not in tool_data or (cat != 'global' and tool_data[t_id]['category'] == 'global'):
                            tool_data[t_id] = {
                                "tool_id": t_id,
                                "category": cat,
                                "alpha": round(float(alpha), 2),
                                "beta": round(float(beta), 2),
                                "success_count": int(s),
                                "failure_count": int(f),
                                "timestamp": str(ts)
                            }
            return list(tool_data.values())
>>>>
```

### C. File 3: `core/tools/utils/bayesian.py`
`tune_swarm()` provides standalone weight tuning that updates database columns natively. We need to update its SQL queries to increment and update `success_count` and `failure_count`.

**Proposed Changes:**
```python
<<<<
def tune_swarm(tool_id: str, success: bool, category: str = "global"):
    """
    Updates the Bayesian weights for a specific tool natively in Postgres.
    Uses Beta distribution logic: Alpha (successes) and Beta (failures).
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Update Global
                cur.execute("""
                    INSERT INTO bayesian_weights (tool_id, category, alpha, beta)
                    VALUES (%s, 'global', %s, %s)
                    ON CONFLICT (tool_id, category) DO UPDATE 
                    SET alpha = bayesian_weights.alpha + %s,
                        beta = bayesian_weights.beta + %s,
                        last_updated = CURRENT_TIMESTAMP
                """, (
                    tool_id,
                    1.0 if success else 0.0, 
                    0.0 if success else 1.0,
                    1.0 if success else 0.0,
                    0.0 if success else 1.0
                ))

                # 2. Update Category-specific (if not global)
                if category != "global":
                    # If category record doesn't exist, we must seed it from the current global value first.
                    cur.execute("""
                        INSERT INTO bayesian_weights (tool_id, category, alpha, beta)
                        SELECT %s, %s, alpha, beta FROM bayesian_weights WHERE tool_id = %s AND category = 'global'
                        ON CONFLICT (tool_id, category) DO NOTHING
                    """, (tool_id, category, tool_id))

                    cur.execute("""
                        UPDATE bayesian_weights
                        SET alpha = alpha + %s,
                            beta = beta + %s,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE tool_id = %s AND category = %s
                    """, (
                        1.0 if success else 0.0,
                        0.0 if success else 1.0,
                        tool_id, category
                    ))
                conn.commit()
====
def tune_swarm(tool_id: str, success: bool, category: str = "global"):
    """
    Updates the Bayesian weights for a specific tool natively in Postgres.
    Uses Beta distribution logic: Alpha (successes) and Beta (failures).
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Update Global
                cur.execute("""
                    INSERT INTO bayesian_weights (tool_id, category, alpha, beta, success_count, failure_count)
                    VALUES (%s, 'global', %s, %s, %s, %s)
                    ON CONFLICT (tool_id, category) DO UPDATE 
                    SET alpha = bayesian_weights.alpha + %s,
                        beta = bayesian_weights.beta + %s,
                        success_count = bayesian_weights.success_count + %s,
                        failure_count = bayesian_weights.failure_count + %s,
                        last_updated = CURRENT_TIMESTAMP
                """, (
                    tool_id,
                    1.0 if success else 0.0, 
                    0.0 if success else 1.0,
                    1 if success else 0,
                    0 if success else 1,
                    1.0 if success else 0.0,
                    0.0 if success else 1.0,
                    1 if success else 0,
                    0 if success else 1
                ))

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
                conn.commit()
>>>>
```

### D. Dashboard Backend Router: `core/tools/infrastructure/routers/legacy.py`
No changes are required in the FastAPI stats route (`GET /stats`) because it already correctly reads:
```python
"success_count": t.get("success_count", 0),
"failure_count": t.get("failure_count", 0),
```
from each tool object returned by `governor.get_all_stats()`. Once the governor retrieves actual counts from the database, they will flow dynamically to the `/stats` API response and display on the dashboard UI.

---

## 3. Verification & Testing Instructions

### A. Environment Configuration & Connection Verification
Database credentials and settings are located in the project's root `.env` file:
- `POSTGRES_HOST=100.104.211.61` (Tailscale PC host)
- `POSTGRES_PORT=5432`
- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=kenbun`
- `POSTGRES_DB=kenbun_intelligence`

To check if the database is reachable and verify active credentials, run:
```bash
PYTHONPATH=core .venv/bin/python -c "from tools.memory.postgres_client import get_connection; conn=get_connection(); print('Postgres Connected Info:', conn.info); conn.close()"
```
*Note: If the Tailscale network connection or remote PC is offline, this command will raise a `psycopg.errors.ConnectionTimeout`, which causes the system to fallback gracefully to local SQLite.*

### B. SQLite Telemetry Verification
To verify telemetry is running and updating locally in SQLite, execute the test script:
```bash
PYTHONPATH=core .venv/bin/python core/tests/bayesian_hme_test.py
```
This script updates the `local-ollama` tool weights and counts, simulating success and failure runs, and confirms that HME behaves as expected.

### C. Running Standard Pytest Suite
To ensure the proposed changes do not break existing routing logic or bandit heuristics, run the pytest suite:
```bash
PYTHONPATH=core .venv/bin/python -m pytest core/tests/test_strategy.py core/tests/test_edge_cases.py
```
