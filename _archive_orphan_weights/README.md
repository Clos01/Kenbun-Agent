# Orphan weights.json archive

Moved here by the ghost-bug audit (Phase 3) on 2026-06-21.

- `weights.json.migrated` — pre-migration backup created by `scripts/migrate_to_postgres.py`. The migration target is the Postgres `bayesian_weights` table; this file is a safety copy, not actively read by any code (verified via repo-wide grep).
- `infrastructure_weights.json` — originally at `core/tools/infrastructure/weights.json`. Zero references in the codebase. Different schema (security-tool weights, not bayesian). Almost certainly an abandoned prototype.

Both are kept here in case a recovery is ever needed. They can be deleted outright after the next clean release.

Live file remains at `core/weights.json` — local fallback for `strategy_manager.py`.
