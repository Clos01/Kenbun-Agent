#!/bin/bash
# Kenbun: Terminal Bridge Launcher

echo "🚀 Stopping background sensory layer..."
pkill -9 -f assembly_voice.py || true

echo "🎙️ Starting Kenbun Sensory Layer in CLI mode..."
python3 tools/infrastructure/assembly_voice.py
