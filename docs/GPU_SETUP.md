# GPU Support for Kenbun-Agent

This guide covers GPU acceleration on NVIDIA GPUs for faster local model inference.

## Quick Start (Linux/macOS with NVIDIA GPU)

```bash
sudo ./scripts/setup_nvidia_gpu.sh
```

This:
- Detects your NVIDIA GPU
- Installs NVIDIA Container Toolkit
- Configures Docker to use the NVIDIA runtime
- Restarts Kenbun with GPU support enabled

## Architecture: CPU-First, GPU-Opt-In

**Default deployment (CPU-only):**
```bash
docker compose up -d
```
Works on any server with or without a GPU.

**GPU-accelerated deployment:**
```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```
Requires NVIDIA Container Toolkit installed.

### Why This Design?

The GPU reservation was previously in `docker-compose.override.yml`, which Docker auto-merges with the main compose file. On CPU-only servers without the NVIDIA Container Toolkit, `docker compose up` would fail with:

```
Error response from daemon: could not select device driver "nvidia"
```

By keeping GPU config in a separate `docker-compose.gpu.yml`:
- ✅ Default stack boots on any hardware
- ✅ GPU users opt-in explicitly with `-f docker-compose.gpu.yml`
- ✅ CPU-only servers never see GPU errors

## Prerequisites

### For GPU Support:
- **NVIDIA GPU** (any compute-capable model)
- **NVIDIA drivers** (recent, supporting CUDA)
- **Docker** installed
- **NVIDIA Container Toolkit** — installed by the setup script, or manually:

```bash
# Ubuntu/Debian
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

## Verify GPU is Available

After setup, verify GPU is accessible to containers:

```bash
# If Kenbun is running:
docker exec -it portable_ollama nvidia-smi

# Or check Ollama's model status:
docker exec -it portable_ollama ollama ps
# Look at the PROCESSOR column — should show "gpu" instead of "cpu"
```

## Performance Tuning

### Context Window & VRAM

If your GPU has limited VRAM (<4GB), reduce the context window in `.env`:

```env
OLLAMA_CONTEXT_LENGTH=4096      # down from default 8192
```

This frees VRAM while still preventing system-prompt truncation (the #1 hallucination cause).

### Model Selection

Recommended small models for consumer GPUs:
- **2GB VRAM:** `gemma2:2b`, `phi3.5:3.8b`
- **4GB VRAM:** `deepseek-r1:1.5b`, `qwen2.5:1.5b`
- **6GB+ VRAM:** `qwen2:7b`, `llama2:7b`

Set via `.env`:
```env
OLLAMA_PULL_MODELS=qwen2.5:1.5b
```

## Troubleshooting

### GPU Not Detected

```
WARNING: No NVIDIA GPU detected
```

- Check driver: `nvidia-smi` should show your GPU and driver version
- Restart Docker: `sudo systemctl restart docker`
- If using WSL2, ensure `nvidia-docker` is installed: see [WSL2 GPU Support](https://docs.nvidia.com/cuda/wsl-user-guide/)

### "could not select device driver nvidia"

- NVIDIA Container Toolkit is not installed — run `setup_nvidia_gpu.sh` again
- Docker daemon hasn't restarted after toolkit install — run: `sudo systemctl restart docker`
- You're on a CPU-only server and used `docker-compose.override.yml` — delete it and use the standard stack

### Out of VRAM

```
Error: out of memory
```

- Reduce context window: `OLLAMA_CONTEXT_LENGTH=2048`
- Or use a smaller model: `ollama list` to see installed, then set `OLLAMA_PULL_MODELS=<smaller_model>`
- Lower quantization (in future): Ollama's newer models default to q4, but `q3_K_S` saves VRAM further

## Disabling GPU Temporarily

To fall back to CPU inference while keeping NVIDIA toolkit installed:

```bash
# CPU-only (ignores docker-compose.gpu.yml)
docker compose down
docker compose up -d

# GPU-accelerated (if needed again)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

## Manual GPU Config

If you prefer not to use the setup script, you can manually enable GPU by running Kenbun with:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

Make sure NVIDIA Container Toolkit is installed first (see Prerequisites above).
