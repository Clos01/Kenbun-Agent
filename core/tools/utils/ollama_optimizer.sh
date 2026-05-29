#!/bin/bash
# 🚀 Kenbun/core: Ollama & WSL2 Optimizer
# Run this script INSIDE your Ubuntu WSL2 instance on the PC.

echo "🔍 Starting Ollama Optimization for WSL2..."

# 1. Set Peak Performance Environment Variables
# Flash Attention significantly reduces VRAM usage for Llama 3/Gemma 2 models.
if ! grep -q "OLLAMA_FLASH_ATTENTION" ~/.bashrc; then
    echo "export OLLAMA_FLASH_ATTENTION=1" >> ~/.bashrc
    echo "✅ Enabled Flash Attention in .bashrc"
fi

# Allow multiple requests to hit the GPU concurrently (if VRAM permits)
if ! grep -q "OLLAMA_NUM_PARALLEL" ~/.bashrc; then
    echo "export OLLAMA_NUM_PARALLEL=4" >> ~/.bashrc
    echo "✅ Set OLLAMA_NUM_PARALLEL=4 in .bashrc"
fi

# Keep models in memory for 24 hours to avoid reload latency
if ! grep -q "OLLAMA_KEEP_ALIVE" ~/.bashrc; then
    echo "export OLLAMA_KEEP_ALIVE=24h" >> ~/.bashrc
    echo "✅ Set OLLAMA_KEEP_ALIVE=24h in .bashrc"
fi

# 2. WSL2 Hardware Allocation Suggestion
echo ""
echo "📂 --- ACTION REQUIRED: Windows Side ---"
echo "To maximize performance, ensure your C:\Users\<User>\.wslconfig contains:"
echo "----------------------------------------"
echo "[wsl2]"
echo "memory=16GB  # Or 50% of your total RAM"
echo "processors=8 # Total logical cores"
echo "----------------------------------------"

# 3. Verify NVIDIA Passthrough
echo ""
echo "🎮 Checking GPU Passthrough..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi
    echo "✅ GPU Passthrough is active."
else
    echo "❌ GPU not found. Ensure NVIDIA Windows Drivers are up to date."
fi

echo ""
echo "🚀 Optimization Complete. Run 'source ~/.bashrc' and restart Ollama."
