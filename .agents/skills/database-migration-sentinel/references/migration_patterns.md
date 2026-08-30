# PostgreSQL & Supabase Migration Reference Patterns

This guide catalogs hardened SQL patterns for Row Level Security (RLS), multi-tenant isolation, CTE performance, and zero-downtime alterations.

---

## 1. Multi-Tenant Row Level Security (RLS) Matrix

Always enforce RLS on all tenant-isolated tables:

```sql
-- 1. Enable RLS
ALTER TABLE client_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_records FORCE ROW LEVEL SECURITY;

-- 2. Create Tenant Isolation Policy
CREATE POLICY tenant_isolation_policy ON client_records
    FOR ALL
    USING (
        tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
    )
    WITH CHECK (
        tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
    );

-- 3. Required Performance Index on tenant_id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_client_records_tenant_id 
ON client_records(tenant_id);
```

---

## 2. Refactoring Statement Timeouts with Pre-Aggregated CTEs

When subqueries cause `canceling statement due to statement timeout`:

### ❌ Anti-Pattern (N+1 Correlated Subquery)
```sql
SELECT 
    b.id,
    b.title,
    (SELECT COUNT(*) FROM cards c WHERE c.board_id = b.id) AS total_cards,
    (SELECT MAX(created_at) FROM cards c WHERE c.board_id = b.id) AS latest_card
FROM boards b;
```

### ✅ Safe Senior Pattern (CTE Pre-Aggregation)
```sql
WITH card_stats AS (
    SELECT 
        board_id,
        COUNT(*) AS total_cards,
        MAX(created_at) AS latest_card
    FROM cards
    GROUP BY board_id
)
SELECT 
    b.id,
    b.title,
    COALESCE(cs.total_cards, 0) AS total_cards,
    cs.latest_card
FROM boards b
LEFT JOIN card_stats cs ON cs.board_id = b.id;
```

---

## 3. Safe Column Renaming & Type Conversions

Never rename live columns directly in one migration:
1. **Phase 1:** Add the new column (`new_column`).
2. **Phase 2:** Dual-write to both `old_column` and `new_column` in application code or trigger.
3. **Phase 3:** Backfill historical rows in batches (`UPDATE ... WHERE id BETWEEN ...`).
4. **Phase 4:** Switch reads to `new_column`.
5. **Phase 5:** Drop `old_column` after 1 release cycle.
