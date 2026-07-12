# Project: Kenbun Telemetry Expansion

## Architecture
- **PostgreSQL Database**: Stores `bayesian_weights` which track the weights for various tools. Now needs to track `success_count` and `failure_count`.
- **SQLite Database**: Used locally or in certain contexts, which also needs tool stats querying.
- **postgres_client.py**: Standard DB interface containing `init_db()`.
- **strategy_manager.py**: High-level manager orchestrating intelligence updates and statistics retrieval.
- **bayesian.py**: Utility adjusting/tuning weights based on tool performance.
- **telemetry dashboard**: Shows metrics, queries stats via `/stats` endpoint.

## Milestones
| # | Name | Scope | Dependencies | Status | Conversation ID |
|---|------|-------|-------------|--------|-----------------|
| M1 | Exploration | Analyze codebase files and DB schemas | None | DONE | 3f6353dd-558e-4e8e-b540-e55e62d76ec4 |
| M2 | Migration & Implementation | Modify database schema and python codebase | M1 | DONE | faa8c5ba-5627-43f3-87d8-380602b29f51 |
| M3 | Testing & Review | Code review, verification using telemetry stats command | M2 | DONE | f896b5de-ed57-41a3-8c6b-dc7af4d3bcbc, 2073f9b5-ed31-4754-9108-01385b7d3e30, fad61af2-b3ac-472a-bee3-38c99c8f8824, ac555f49-051f-4855-a3aa-1950802bb125, feff1bb8-1d55-43e8-8fdd-3f6e5ccf7b33 |
| M4 | Forensic Audit & Sync | Integrity audit, portable_fastmcp verification, and remote sync | M3 | DONE | b5bc2233-7cef-42eb-b4ef-82d6d9d934b9, b312fae3-c7f1-452b-ab99-e31fc4d032fd |

## Interface Contracts
- `bayesian_weights` schema: includes `success_count` (int) and `failure_count` (int) with default 0.
- `strategy_manager.py`: `get_tool_stats()`, `update_intelligence()`, and `get_all_stats()` must correctly compute, update, and return success/failure counts.
- `bayesian.py`: `tune_swarm()` must update success/failure counts in PostgreSQL.
