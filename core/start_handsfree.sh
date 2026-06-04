#!/bin/bash
# Kenbun: Elite Native Hands-Free Launcher

echo "🚀 Stopping existing sensory layers..."
pkill -9 -f always_listening.py || true
pkill -9 -f native_ears.py || true

echo "👂 Awakening Native Kenbun Ears (SFSpeech Mode)..."
echo "📍 Note: Please grant Terminal permission to access the Microphone and Speech Recognition if prompted."

# Run the native ears script
python3 tools/infrastructure/native_ears.py
