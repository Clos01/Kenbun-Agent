#!/bin/bash
# ============================================================================
# 🏛️ Kenbun-Agent Sovereign Ubuntu VM Bootstrapper (Portainer Edition)
# ============================================================================
# Idempotent bootstrap script to configure a freshly provisioned Ubuntu Server 
# VM on a home-lab hypervisor or cloud virtualization node.
#
# Functions:
#   1. Installs Docker Engine & Compose using the official Docker APT repository.
#   2. Provisions Portainer Community Edition (Container Management Dashboard).
#   3. Clones the Kenbun-Agent repository and sets up the workspace.
#   4. Dynamically detects resources and builds optimized configurations.
#   5. Configures UFW firewall rules to allow remote LAN access securely.
#
# Usage:
#   sudo bash ubuntu_vm_bootstrap.sh
#   To Dry-Run (Verify only): DRY_RUN=1 bash ubuntu_vm_bootstrap.sh
# ============================================================================

set -e

# Color definitions (Limestone Haze / Sakura aesthetic)
if [ -t 1 ]; then
    PINK='\033[38;5;218m'
    ROSE='\033[38;5;224m'
    GRAY='\033[38;5;246m'
    YELLOW='\033[38;5;226m'
    CYAN='\033[38;5;38m'
    NC='\033[0m' # No Color
    BOLD='\033[1m'
else
    PINK=''
    ROSE=''
    GRAY=''
    YELLOW=''
    CYAN=''
    NC=''
    BOLD=''
fi

# Print beautiful header
echo -e "${PINK}${BOLD}"
echo "┌─────────────────────────────────────────────────────────┐"
echo "│         🏛️ Kenbun-Agent VM Bootstrapper                  │"
echo "├─────────────────────────────────────────────────────────┤"
echo "│  Target Node: Sovereign Home-Lab Virtualization Server │"
echo "│  Hypervisor:  Proxmox VE / KVM / Hyper-V (Ubuntu VM)   │"
echo "└─────────────────────────────────────────────────────────┘"
echo -e "${NC}"

# Log utilities
log_info() { echo -e "${CYAN}→${NC} $1"; }
log_success() { echo -e "${ROSE}✓${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${PINK}✗${NC} $1"; exit 1; }

# Dry-run notification
if [ "${DRY_RUN}" = "1" ]; then
    echo -e "${YELLOW}${BOLD}⚠️ DRY RUN MODE ACTIVE. Commands will be simulated only. ⚠️${NC}\n"
fi

# 1. Root & System Check
audit_environment() {
    log_info "Auditing environment variables & permissions..."
    
    if [ "$DRY_RUN" != "1" ]; then
        if [ "$EUID" -ne 0 ]; then
            log_error "This bootstrapper must be run as root to perform system configurations. Run: sudo bash $0"
        fi
    fi
    
    # Check if OS is Ubuntu
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        if [ "$ID" != "ubuntu" ] && [ "$ID_LIKE" != "ubuntu" ]; then
            log_warn "Detected OS is $NAME ($ID), but this script is customized for Ubuntu/Debian."
        else
            log_success "Target OS verified: Ubuntu Server ($VERSION_ID)"
        fi
    else
        log_warn "Could not read /etc/os-release. Proceeding with standard Debian/Ubuntu assumptions..."
    fi
}

# 2. Package Registry Update & Core Dependencies
install_system_deps() {
    log_info "Installing core system utilities (curl, gnupg, git, ca-certificates)..."
    
    if [ "$DRY_RUN" = "1" ]; then
        log_info "[SIMULATE] apt-get update && apt-get install -y curl gnupg ca-certificates git ufw"
    else
        apt-get update -y
        apt-get install -y curl gnupg ca-certificates git ufw
    fi
    log_success "System utilities verified."
}

# 3. Docker & Docker Compose Installation
install_docker_engine() {
    log_info "Preparing Docker repository credentials and installing Docker Engine..."
    
    if [ "$DRY_RUN" = "1" ]; then
        log_info "[SIMULATE] Adding Docker official GPG key..."
        log_info "[SIMULATE] Adding Docker repository to APT sources..."
        log_info "[SIMULATE] apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"
    else
        # Remove any pre-existing distro-specific packages that collide
        for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do 
            apt-get remove -y $pkg >/dev/null 2>&1 || true
        done

        # Configure official Docker repository
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
        chmod a+r /etc/apt/keyrings/docker.gpg

        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
          $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
          tee /etc/apt/sources.list.d/docker.list > /dev/null

        apt-get update -y
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

        # Enable Docker Daemon
        systemctl enable --now docker
        
        # Test Docker runtime
        if docker info >/dev/null 2>&1; then
            log_success "Docker Engine is active and running ($(docker --version))"
        else
            log_error "Docker Engine was installed but failed to start. Check: systemctl status docker"
        fi
    fi
}

# 4. Provision Portainer Community Edition (Container Management Dashboard)
provision_portainer() {
    log_info "Provisioning Portainer Community Edition (starts with 'P')..."
    
    if [ "$DRY_RUN" = "1" ]; then
        log_info "[SIMULATE] docker network create portainer_net (idempotent)"
        log_info "[SIMULATE] docker volume create portainer_data (idempotent)"
        log_info "[SIMULATE] docker run -d -p 9000:9000 -p 9443:9443 --name portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ce:2.21.5"
    else
        # Ensure there are no running container conflicts
        docker rm -f portainer >/dev/null 2>&1 || true

        # Idempotent bridge network creation
        if ! docker network inspect portainer_net >/dev/null 2>&1; then
            docker network create portainer_net >/dev/null 2>&1 || true
        fi

        # Idempotent volume creation
        if ! docker volume inspect portainer_data >/dev/null 2>&1; then
            docker volume create portainer_data >/dev/null 2>&1 || true
        fi

        # Start Portainer CE (Pinned stable release)
        # Virtualization Security Notice:
        # Mounting the Docker socket grants Portainer container control over the guest VM kernel.
        # Within our sovereign architecture, the primary isolation boundary is the Proxmox VE 
        # Virtual Machine itself. Any container-level escape is restricted to this guest Ubuntu VM
        # and remains strictly isolated from the physical hypervisor node and local host resources.
        docker run -d \
          -p 9000:9000 \
          -p 9443:9443 \
          --name portainer \
          --restart=always \
          --network=portainer_net \
          -v /var/run/docker.sock:/var/run/docker.sock \
          -v portainer_data:/data \
          portainer/portainer-ce:2.21.5
        
        log_info "Waiting for Portainer CE console to initialize..."
        sleep 4
        
        container_status=$(docker inspect -f '{{.State.Status}}' portainer 2>/dev/null || echo "unknown")
        
        if [ "$container_status" != "running" ]; then
            log_error "Portainer failed to initialize cleanly (Container Status: $container_status)."
            log_warning "This is frequently caused by a pre-existing, conflicting data volume (portainer_data) from a different Portainer version."
            log_warning "To safely reset this database volume and resolve the conflict, run:"
            echo -e "${YELLOW}  docker rm -f portainer && docker volume rm portainer_data && sudo bash scripts/ubuntu_vm_bootstrap.sh${NC}"
            echo ""
        else
            log_success "Portainer Dashboard is active and running."
            log_info "  ➔ HTTPS URL: https://<VM_IP_ADDRESS>:9443"
            log_info "  ➔ HTTP URL:  http://<VM_IP_ADDRESS>:9000"
        fi
    fi
}

# 5. Retrieve Kenbun Repository
provision_kenbun() {
    local target_dir="/opt/kenbun-agent"
    
    # Path traversal validation
    if [[ "$target_dir" != /* ]] || [[ "$target_dir" == *..* ]]; then
        log_error "Security Exception: Invalid absolute target directory: $target_dir"
    fi
    
    log_info "Cloning the Kenbun-Agent repository to $target_dir..."
    
    if [ "$DRY_RUN" = "1" ]; then
        log_info "[SIMULATE] git clone https://github.com/Clos01/Kenbun-Agent.git $target_dir"
    else
        if [ -d "$target_dir" ]; then
            log_warn "$target_dir already exists. Fetching updates from GitHub..."
            cd "$target_dir"
            git fetch --all
            git reset --hard origin/main
        else
            mkdir -p "$target_dir"
            git clone https://github.com/Clos01/Kenbun-Agent.git "$target_dir"
        fi
        log_success "Repository successfully cloned."
    fi
}

# 6. Customize Environment Variables (.env) for CPU/GPU-bound Virtualization Nodes
generate_sovereign_env() {
    local target_dir="/opt/kenbun-agent"
    
    # Path traversal and existence validation
    if [ -z "$target_dir" ] || [[ "$target_dir" != /* ]] || [[ "$target_dir" == *..* ]]; then
        log_error "Security Exception: Invalid absolute target directory: $target_dir"
        exit 1
    fi
    
    local env_path="$target_dir/.env"
    
    if [ "$DRY_RUN" = "1" ]; then
        target_dir="./scratch"
        mkdir -p "$target_dir"
        env_path="$target_dir/.env.simulated"
    fi

    # Hardware Detection (Dynamic Scoping)
    local system_ram_gb=8
    if [ -f /proc/meminfo ]; then
        system_ram_gb=$(awk '/MemTotal/ {print int($2/1024/1024)}' /proc/meminfo)
    fi

    local system_cores=4
    if command -v nproc >/dev/null 2>&1; then
        system_cores=$(nproc)
    fi

    # Model recommendations based on hardware capacity
    local rec_model="llama3.2:1b"
    local pull_models="llama3.2:1b nomic-embed-text"
    
    if [ "$system_ram_gb" -ge 16 ]; then
        rec_model="llama3.2:3b"
        pull_models="llama3.2:3b nomic-embed-text"
    fi
    if [ "$system_ram_gb" -ge 32 ]; then
        # On high memory nodes, we can support a small reasoning fallback model
        pull_models="llama3.2:3b deepseek-r1:1.5b nomic-embed-text"
    fi

    log_info "Detected Hardware Capacity: ${system_cores} CPU Cores, ${system_ram_gb}GB RAM"
    log_info "Selected optimal hardware-agnostic models: $rec_model"

    # Security: Apply strict umask 077 so the file is created owner-only (600)
    # This prevents any TOCTOU window between file creation and permission adjustment.
    local old_umask
    old_umask=$(umask)
    umask 077

    log_info "Structuring optimized, memory-efficient configuration at: $env_path"

    cat << EOF > "$env_path"
# ==============================================================================
#                 🏛️ KENBUN-AGENT REMOTE SOVEREIGN NODE CONFIGURATION
# ==============================================================================
# Auto-generated by Sovereign VM Bootstrapper.
# Dynamically provisioned for: ${system_cores} Core CPU, ${system_ram_gb}GB RAM system.

# --- 1. CORE PATHS & STANDALONE DIRECTORIES ---
PROJECT_ROOT=/opt/kenbun-agent
PROJECT_NAME=kenbun-agent

# --- 2. VECTOR DATABASE (LOCAL CHROMA STACK) ---
CHROMA_HOST=chromadb
CHROMA_PORT=8000

# --- 3. HARDWARE-AGNOSTIC LLM GATEWAYS & PROVIDERS ---
# Target local Ollama server container.
PRIMARY_LLM_URL=http://ollama_server:11434/v1
PRIMARY_LLM_MODEL=${rec_model}
OLLAMA_PULL_MODELS="${pull_models}"

# --- 4. FALLBACK GATEWAY ---
FALLBACK_LLM_URL=https://api.openai.com/v1
FALLBACK_LLM_MODEL=gpt-4o-mini

# --- 5. API SECURITY KEYS (Inject manually if using cloud adapters) ---
ANTHROPIC_API_KEY=your_anthropic_key_here
GEMINI_API_KEY=your_gemini_key_here
OPENAI_API_KEY=your_openai_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here

# --- 6. GOVERNANCE & TELEMETRY BUDGETS ---
DAILY_BUDGET=50.00
TELEMETRY_ENABLED=true
NOTIFICATIONS_ENABLED=true
API_PORT=8001
MONITOR_PORT=8002
DASHBOARD_PORT=3000
DOZZLE_PORT=8888
OLLAMA_PORT=11434
EOF

    # Restore default system umask
    umask "$old_umask"

    if [ "$DRY_RUN" != "1" ]; then
        chown root:root "$env_path" || true
        log_info "Secured file ownership (chown root:root) on: $env_path"
    fi

    log_success "Created optimal configuration payload: $env_path"
}

# 7. Configure VM Firewall (UFW)
configure_firewall() {
    log_info "Configuring Uncomplicated Firewall (UFW) to permit secure remote local LAN routing..."
    
    if [ "$DRY_RUN" = "1" ]; then
        log_info "[SIMULATE] ufw limit 22/tcp comment 'Rate-limit SSH'"
        log_info "[SIMULATE] ufw allow 9443/tcp comment 'Portainer HTTPS'"
        log_info "[SIMULATE] ufw allow 9000/tcp comment 'Portainer HTTP'"
        log_info "[SIMULATE] ufw allow 3000/tcp comment 'Kenbun Dashboard'"
        log_info "[SIMULATE] ufw allow 8001/tcp comment 'Kenbun API (FastMCP)'"
        log_info "[SIMULATE] ufw allow 8000/tcp comment 'Kenbun Vector DB'"
        log_info "[SIMULATE] ufw allow 8888/tcp comment 'Kenbun Logs (Dozzle)'"
        log_info "[SIMULATE] ufw --force enable"
    else
        # Ensure SSH is open first to avoid locking out remote administrators
        ufw limit 22/tcp comment 'Rate-limit SSH' || true
        
        # Allow Portainer Management
        ufw allow 9443/tcp comment 'Portainer Secure Console'
        ufw allow 9000/tcp comment 'Portainer Legacy Console'
        
        # Allow Kenbun Observatory Suite
        ufw allow 3000/tcp comment 'Kenbun NextJS UI'
        ufw allow 8001/tcp comment 'Kenbun API FastMCP'
        ufw allow 8000/tcp comment 'Kenbun Chroma DB'
        ufw allow 8888/tcp comment 'Kenbun Logs Dozzle'
        
        # Enable firewall rules
        echo "y" | ufw enable
        ufw reload
        
        log_success "Firewall (UFW) fully configured and locked down."
    fi
}

# 8. Post-installation summary and connection metrics
post_installation_diagnostics() {
    # Resolve the active LAN IP of the VM automatically
    local active_ip
    if command -v ip >/dev/null 2>&1; then
        active_ip=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}' || hostname -I 2>/dev/null | awk '{print $1}')
    elif command -v hostname >/dev/null 2>&1 && hostname -I >/dev/null 2>&1; then
        active_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    else
        active_ip="192.168.1.xxx"
    fi
    if [ -z "$active_ip" ]; then
        active_ip="192.168.1.xxx"
    fi

    echo -e "\n${ROSE}${BOLD}┌─────────────────────────────────────────────────────────┐"
    echo -e "│       🏛️ SOVEREIGN DEPLOYMENT BOOTSTRAP COMPLETE        │"
    echo -e "└─────────────────────────────────────────────────────────┘${NC}"
    echo -e "Your Sovereign virtualization worker node is ready to be configured by the operator!"
    echo ""
    echo -e "${BOLD}📡 Local Access Endpoints (Subnet Address: $active_ip)${NC}"
    echo -e "  ➔ Portainer CE:          ${CYAN}https://$active_ip:9443${NC} (HTTPS)"
    echo -e "  ➔ Portainer HTTP:        ${CYAN}http://$active_ip:9000${NC} (Legacy)"
    echo -e "  ➔ Kenbun Observatory:    ${CYAN}http://$active_ip:3000${NC} (Next.js Dashboard)"
    echo -e "  ➔ Kenbun API:            ${CYAN}http://$active_ip:8001/stats${NC} (FastMCP)"
    echo -e "  ➔ Log Streamer (Dozzle): ${CYAN}http://$active_ip:8888${NC} (Live Logs)"
    echo ""
    echo -e "${BOLD}🛠️ Next Steps for Configuration:${NC}"
    echo -e "  ${BOLD}Option A: Deploy via Portainer Web UI (Headless Server / Home-Lab)${NC}"
    echo -e "    1. Open ${CYAN}https://$active_ip:9443${NC} in a web browser."
    echo -e "    2. Create your administrator account and log in."
    echo -e "    3. Click on your ${BOLD}local${NC} environment, then go to ${BOLD}Stacks${NC} ➔ ${BOLD}Add stack${NC}."
    echo -e "    4. ${YELLOW}⚠️  CRITICAL PORTAINER WARNING:${NC} In Portainer, change the Build method from"
    echo -e "       ${BOLD}'Web editor'${NC} to ${BOLD}'Repository'${NC} (the Web editor will fail to find the Dockerfile)."
    echo -e "       Configure these parameters under the Repository tab:"
    echo -e "       ➔ Repository URL:   ${CYAN}https://github.com/Clos01/Kenbun-Agent.git${NC}"
    echo -e "       ➔ Branch/Reference: ${CYAN}refs/heads/main${NC}"
    echo -e "       ➔ Compose path:     ${CYAN}docker-compose.yml${NC}"
    echo -e "    5. Scroll down to ${BOLD}Environment variables${NC}, click ${BOLD}Load from .env${NC},"
    echo -e "       and paste the contents of '/opt/kenbun-agent/.env'."
    echo -e "    6. Click ${BOLD}Deploy the stack${NC}."
    echo ""
    echo -e "  ${BOLD}Option B: Deploy via Direct Terminal CLI Wizard (Recommended & Easiest)${NC}"
    echo -e "    If you prefer terminal execution to compile directly on the host (bypassing Portainer limitations):"
    echo -e "    1. Simply run the setup wrapper command: ${CYAN}kenbun${NC} (or ${CYAN}sudo bash /opt/kenbun-agent/install.sh${NC})."
    echo -e "    2. Select Option 5: ${BOLD}Start Swarm Stack (Docker Compose up)${NC}."
    echo -e "    ➔ Once completed, open your browser to: ${CYAN}http://$active_ip:3000${NC} (Dashboard)."
    echo ""
    log_success "Bootstrap process finished successfully."
}

# Master execution pipe
audit_environment
install_system_deps
install_docker_engine
provision_portainer
provision_kenbun
generate_sovereign_env
configure_firewall
post_installation_diagnostics
