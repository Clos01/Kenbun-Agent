#!/bin/bash
# ============================================================================
# 🖥️  Kenbun-Agent: NVIDIA GPU Toolkit Installer (Ubuntu/Debian)
# ============================================================================
# This script installs the NVIDIA Container Toolkit and configures Docker
# and Ollama to utilize your local GPU for significantly faster inference.
#
# Usage:
#   sudo ./scripts/setup_nvidia_gpu.sh
# ============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
  echo -e "\033[38;5;218m✗ Please run this script with sudo:\033[0m sudo $0"
  exit 1
fi

echo -e "\033[38;5;38m→\033[0m Detecting NVIDIA GPU..."
if ! lspci | grep -i nvidia &> /dev/null; then
    echo -e "\033[38;5;226m⚠\033[0m No NVIDIA GPU detected on the PCI bus."
    echo -e "   If you believe this is an error, ensure your drivers are installed."
    echo -e "   Continuing anyway..."
else
    echo -e "\033[38;5;224m✓\033[0m NVIDIA GPU detected."
fi

echo -e "\033[38;5;38m→\033[0m Checking for Docker installation..."
if ! command -v docker &> /dev/null; then
    echo -e "\033[38;5;218m✗\033[0m Docker is not installed. Please run the main install.sh first."
    exit 1
fi

echo -e "\033[38;5;38m→\033[0m Setting up NVIDIA Container Toolkit repository..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

echo -e "\033[38;5;38m→\033[0m Updating package lists..."
sudo apt-get update

echo -e "\033[38;5;38m→\033[0m Installing nvidia-container-toolkit..."
sudo apt-get install -y nvidia-container-toolkit

echo -e "\033[38;5;38m→\033[0m Configuring Docker to use NVIDIA runtime..."
sudo nvidia-ctk runtime configure --runtime=docker

echo -e "\033[38;5;38m→\033[0m Restarting Docker daemon..."
sudo systemctl restart docker

echo -e "\033[38;5;38m→\033[0m Restarting Kenbun-Agent container stack (if running)..."
if [ -f "docker-compose.yml" ]; then
    docker compose down || true
    docker compose up -d
else
    echo -e "\033[38;5;226m⚠\033[0m docker-compose.yml not found in current directory. Please restart Kenbun manually if it is currently running."
fi

echo -e "\033[38;5;224m✓\033[0m NVIDIA Container Toolkit successfully installed!"
echo ""
echo -e "\033[1mTo verify GPU utilization:\033[0m"
echo -e "1. Run a model in Kenbun."
echo -e "2. Open another terminal and run: \033[38;5;38mdocker exec -it kenbun-ollama nvidia-smi\033[0m"
echo -e "   or simply: \033[38;5;38mollama ps\033[0m (look at the PROCESSOR column)"
echo ""
