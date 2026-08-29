# Telemetry Dashboard Expansion Plan

## Project Objective
Add `success_count` and `failure_count` to `bayesian_weights` schema in PostgreSQL, update python scripts to capture, tune, and retrieve these counts, and display them on the telemetry dashboard.

## Technical Scope
1. **Database Migration**: Update `bayesian_weights` table to include `success_count` and `failure_count` columns.
2. **PostgreSQL Client Upgrades**: Modify `core/tools/memory/postgres_client.py` to declare these fields in `init_db()`.
3. **Strategy Manager Upgrades**: Update `core/tools/strategy/strategy_manager.py` to retrieve these counts from both SQLite and PostgreSQL, update PostgreSQL during `update_intelligence()`, and retrieve actual metrics for `/stats`.
4. **Bayesian Logic Upgrades**: Update `core/tools/utils/bayesian.py` to increment counts in PostgreSQL during `tune_swarm()`.
5. **Hot Reload & Sync**: Verify changes compile, hot reload in `portable_fastmcp`, and sync to Gitea and remote containers.

## Milestones & Task Breakdown
### Milestone 1: Exploration and Analysis
- **Goal**: Research current schemas, exact connection strings/credentials, and existing data structures in `postgres_client.py`, `strategy_manager.py`, and `bayesian.py`.
- **Assignee**: `teamwork_preview_explorer` (Conv ID: `TBD`)
- **Verification**: Exploration report containing source code locations, schema details, and database migration plan.

### Milestone 2: Implementation and Database Migration
- **Goal**: Apply PostgreSQL table migrations (adding columns `success_count` and `failure_count` with appropriate default values, e.g. 0), and update python files (`postgres_client.py`, `strategy_manager.py`, `bayesian.py`).
- **Assignee**: `teamwork_preview_worker` (Conv ID: `TBD`)
- **Verification**: Local build and execution logs verifying syntax correctness and schema updates.

### Milestone 3: Testing & Review
- **Goal**: Review codebase changes for correctness, scalability, and adherence to design principles. Perform empirical verification of success/failure updates and API metrics.
- **Assignee**: `teamwork_preview_reviewer` (Conv ID: `TBD`), `teamwork_preview_challenger` (Conv ID: `TBD`)
- **Verification**: Run `python3 -m tools.utils.bayesian` and query `/stats` to verify non-zero values.

### Milestone 4: Forensic Audit & Synchronization
- **Goal**: Perform integrity audit (ensure no hardcoding, bypasses, or cheats). Hot reload in `portable_fastmcp`, and sync to Gitea/remote containers.
- **Assignee**: `teamwork_preview_auditor` (Conv ID: `TBD`)
- **Verification**: Clean audit verdict and successful sync verification.
