---
name: database-migration-sentinel
description: Autonomous zero-downtime database migration auditor and PostgreSQL/Supabase schema sentinel. Use when writing, reviewing, or applying database migrations, schema alterations, index additions, RLS policies, table partitioning, or debugging PostgreSQL statement timeouts.
---

# 🗄️ Database Migration & Schema Sentinel

The **Database Migration Sentinel** guarantees that all PostgreSQL / Supabase database alterations, DDL scripts, and schema migrations execute with **zero downtime, zero statement timeouts, and complete reversibility**.

---

## 🎯 When to Activate

Trigger this skill immediately when:
- Creating or editing SQL migration files (e.g. `supabase/migrations/*.sql`).
- Adding, altering, or dropping tables, columns, indexes, foreign keys, or constraints.
- Modifying Row Level Security (RLS) policies, triggers, or Postgres functions.
- Investigating `canceling statement due to statement timeout` errors.
- Designing schemas for high-scale multi-tenant SaaS tables (>1M rows).

---

## 🛡️ The 5 Golden Rules of Safe PostgreSQL Migrations

### 1. Concurrent Index Creation
Never run `CREATE INDEX` on live tables—it acquires an `EXCLUSIVE` lock that blocks all reads/writes.
```sql
-- ❌ DANGEROUS: Blocks table traffic
CREATE INDEX idx_orders_user_id ON orders(user_id);

-- ✅ SAFE: Builds index concurrently without locking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_user_id ON orders(user_id);
```

### 2. Foreign Key Creation with `NOT VALID`
Adding a foreign key constraint validates every existing row under an exclusive table lock.
```sql
-- ✅ SAFE 2-Stage Pattern:
-- Stage 1: Add constraint without scanning existing rows
ALTER TABLE orders 
ADD CONSTRAINT fk_orders_user 
FOREIGN KEY (user_id) REFERENCES users(id) 
NOT VALID;

-- Stage 2: Validate existing rows concurrently in the background
ALTER TABLE orders 
VALIDATE CONSTRAINT fk_orders_user;
```

### 3. Adding Columns with Defaults
In modern PostgreSQL (v11+), adding a column with a constant `DEFAULT` is fast metadata-only. However, never use dynamic defaults (like `DEFAULT gen_random_uuid()` or function calls) without testing lock times.
```sql
-- ✅ SAFE: Fast metadata update
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active' NOT NULL;
```

### 4. Statement Timeouts on DDL
Always guard DDL blocks with a tight `statement_timeout` to prevent hung transactions from piling up connection pools.
```sql
SET statement_timeout = '5s';
-- Run migration DDL here
RESET statement_timeout;
```

### 5. Always Provide Down Migrations (Reversibility)
Every `.sql` migration must have an exact teardown block or companion rollback script.

---

## 📚 Deep-Dive References
- [references/migration_patterns.md](references/migration_patterns.md) — Complete guide on RLS security matrices, CTE query optimization, and Supabase CLI workflows.
