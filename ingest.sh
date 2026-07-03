#!/bin/bash
export PYTHONPATH="$(pwd)/core"
FILES=(
    "STRUCTURE.md"
    "KENBUN.md"
    "docs/OBSERVATORY.md"
    "docs/SVE.md"
    "docs/MODELS.md"
    "docs/SCHEDULING.md"
    "docs/HONCHO.md"
    "POST_MORTEM.md"
)

for f in "${FILES[@]}"; do
    echo "Ingesting $f..."
    .venv/bin/python scripts/bootstrap.py ingest_file_to_hivemind file_path="$(pwd)/$f" tags="architecture,core,system-map"
done
