#!/usr/bin/env bash
# Sync Antigravity IDE session history from this Mac into the Kenbun swarm's
# session_search index on lg2025. Idempotent — re-runs only ship new steps.
#
# Run manually after heavy Antigravity use, or wire into launchd/cron.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_HOST="${KENBUN_REMOTE_HOST:-lg2025}"
CONTAINER="${KENBUN_CONTAINER:-portable_fastmcp}"
IMPORTER="core/tools/sensory/antigravity_importer.py"

# The importer must exist inside the container (baked into the image on
# rebuild; docker cp'd until then). Fail loudly rather than silently no-op.
ssh "$REMOTE_HOST" "docker exec $CONTAINER test -f /app/$IMPORTER" || {
  echo "ERROR: importer missing in $CONTAINER on $REMOTE_HOST — docker cp it first." >&2
  exit 1
}

python3 "$REPO_DIR/$IMPORTER" extract \
  | ssh "$REMOTE_HOST" "docker exec -i $CONTAINER python3 /app/$IMPORTER apply"
