#!/bin/bash
# Wrapper script to run the Python script inside a local Docker container
# This saves you from having to install chromadb directly on your Mac

echo "Pulling up a temporary python environment to check Chroma..."

# We use --context desktop-linux so the container runs locally on your Mac 
# and can successfully mount the script file.
docker --context desktop-linux run --rm \
    -v "/path/to/Kenbun/scripts/check_chroma.py:/check_chroma.py" \
    python:3.10-slim bash -c "pip install chromadb -q && python /check_chroma.py"
