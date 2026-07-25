#!/usr/bin/env bash
# Daily telemetry-integrity guard for the Kenbun swarm.
# Refreshes the brain-health benchmark and runs telemetry_integrity_audit so
# synthetic/frozen/stale data can never silently rot the intelligence store again.
# Installed by Carlos + Claude on 2026-07-25. Logs to brain_health/integrity_cron.log.
set -uo pipefail
C=portable_fastmcp
LOG=/home/carlos/dev/workspace/kenbun/brain_health/integrity_cron.log

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) daily integrity run =====" >> "$LOG"

# 1. Refresh brain-health benchmark (routing accuracy over 150 cases)
docker exec -w /app -e PYTHONPATH=/app/core "$C" python core/benchmarks/nightly_eval.py 2>&1 \
  | grep -E "Accuracy|Error|saved" >> "$LOG"

# 2. Run the integrity audit (posts a Global Workspace alert on WARNING/CRITICAL)
docker exec -i "$C" python - >> "$LOG" 2>&1 <<'PY'
import tools.infrastructure.server as srv
fn = srv.telemetry_integrity_audit
fn = getattr(fn, "fn", fn)
try:
    print(fn(post_alert=True))
except TypeError:
    print(fn())
PY

echo "" >> "$LOG"
