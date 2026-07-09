#!/usr/bin/env bash
# Sync Antigravity IDE session history from this machine into Kenbun's
# session_search index. Idempotent — re-runs only ship new steps.
#
# Local mode (default): applies straight into ~/.kenbun/state.db here.
# Remote mode: set KENBUN_REMOTE_HOST (and optionally KENBUN_CONTAINER)
# to pipe the extract into a Kenbun container over ssh, so the index
# lives where session_search actually executes.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMPORTER="core/tools/sensory/antigravity_importer.py"
REMOTE_HOST="${KENBUN_REMOTE_HOST:-}"
CONTAINER="${KENBUN_CONTAINER:-kenbun_server}"

if [[ -z "$REMOTE_HOST" ]]; then
  python3 "$REPO_DIR/$IMPORTER" extract | python3 "$REPO_DIR/$IMPORTER" apply
else
  ssh "$REMOTE_HOST" "docker exec $CONTAINER test -f /app/$IMPORTER" || {
    echo "ERROR: importer missing in $CONTAINER on $REMOTE_HOST — deploy the repo there first." >&2
    exit 1
  }
  python3 "$REPO_DIR/$IMPORTER" extract \
    | ssh "$REMOTE_HOST" "docker exec -i $CONTAINER python3 /app/$IMPORTER apply"
fi
