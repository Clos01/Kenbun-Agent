#!/bin/bash
# ============================================================================
# 🏛️ Kenbun-Agent Autonomous Installer & Bootstrapper (Sakura Edition)
# ============================================================================
# Automated zero-friction installation script for macOS and Linux.
# Detects runtime constraints, audits local ports, provisions dependencies,
# compiles wrappers, and links the global `kenbun` command into your path.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Clos01/Kenbun-Agent/main/install.sh | bash
# ============================================================================

set -e

# Color definitions (Limestone Haze / Sakura aesthetic wrapped in TTY check)
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


print_banner() {
    echo -e "${PINK}${BOLD}"
    echo "┌─────────────────────────────────────────────────────────┐"
    echo "│             🌸 Kenbun-Agent Installer                    │"
    echo "├─────────────────────────────────────────────────────────┤"
    echo "│  Sovereign Japanese Agentic Swarm (Systems 1-6)         │"
    echo "└─────────────────────────────────────────────────────────┘"
    echo -e "${NC}"
}

log_info() {
    echo -e "${CYAN}→${NC} $1"
}

log_success() {
    echo -e "${ROSE}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${PINK}✗${NC} $1"
}

# ============================================================================
# 🚨 Standardized Error Codes & Exit Handler
# ============================================================================
ERR_001_GIT_MISSING="ERR_001_GIT_MISSING"
ERR_002_PYTHON_MISSING="ERR_002_PYTHON_MISSING"
ERR_003_PYTHON_VERSION="ERR_003_PYTHON_VERSION"
ERR_004_VENV_FAILED="ERR_004_VENV_FAILED"
ERR_005_PIP_FAILED="ERR_005_PIP_FAILED"
ERR_006_BINARY_WRITE="ERR_006_BINARY_WRITE"
ERR_007_SHELL_CONFIG="ERR_007_SHELL_CONFIG"
ERR_008_MACOS_XCODE="ERR_008_MACOS_XCODE"
ERR_009_DOCKER_INACTIVE="ERR_009_DOCKER_INACTIVE"

exit_with_error() {
    local err_code="$1"
    local err_msg="$2"
    local err_solution="$3"
    
    echo ""
    echo -e "${PINK}${BOLD}┌─────────────────────────────────────────────────────────┐"
    echo -e "│                🌸 INSTALLATION FAILURE                  │"
    echo -e "├─────────────────────────────────────────────────────────┘"
    echo -e "${NC}"
    log_error "Error Code: ${BOLD}${err_code}${NC}"
    log_error "Reason:     ${err_msg}"
    echo -e "${CYAN}-----------------------------------------------------------${NC}"
    echo -e "${YELLOW}${BOLD}Recommended Self-Healing Action:${NC}"
    echo -e "  $err_solution"
    echo -e "${PINK}${BOLD}└─────────────────────────────────────────────────────────┘${NC}"
    echo ""
    exit 1
}

# 1. Platform Detection
detect_os() {
    OS="unknown"
    DISTRO="unknown"
    DISTRO_LIKE=""
    IS_APT_BASED=0
    case "$(uname -s)" in
        Linux*)  
            OS="linux"  
            if [ -f /etc/os-release ]; then
                . /etc/os-release
                DISTRO=$ID
                DISTRO_LIKE=${ID_LIKE:-""}
            fi
            ;;
        Darwin*) 
            OS="macos"  
            ;;
        *)       
            OS="unknown"
            ;;
    esac
    
    if [ "$OS" = "unknown" ]; then
        log_warn "Unsupported operating system: $(uname -s)"
    else
        if [ "$OS" = "linux" ]; then
            # Determine if standard Debian/Ubuntu based package manager (apt) is present
            case "$DISTRO" in
                ubuntu|debian|raspbian|pop|mint)
                    IS_APT_BASED=1
                    ;;
                *)
                    case "$DISTRO_LIKE" in
                        *ubuntu*|*debian*)
                            IS_APT_BASED=1
                            ;;
                    esac
                    ;;
            esac
            log_success "Detected Operating System: $OS (Distro: $DISTRO, APT-Compatible: $IS_APT_BASED)"
        else
            log_success "Detected Operating System: $OS"
        fi
    fi
}

# 2. Dependency Audit
audit_dependencies() {
    log_info "Auditing platform dependencies..."

    # Check Xcode on macOS
    if [ "$OS" = "macos" ]; then
        if ! xcode-select -p >/dev/null 2>&1; then
            exit_with_error "$ERR_008_MACOS_XCODE" \
                "Xcode Command Line Tools are missing or inactive." \
                "Run: ${BOLD}xcode-select --install${NC} and accept the prompt to initialize macOS build headers."
        fi
    fi

    # Check Git
    if command -v git >/dev/null 2>&1; then
        if git --version >/dev/null 2>&1; then
            log_success "Git is active ($(git --version | head -n 1))"
        else
            exit_with_error "$ERR_001_GIT_MISSING" \
                "Git exists but is failing to execute properly." \
                "This often happens on macOS when Xcode license terms are not accepted.\n     ➔ Run: ${BOLD}git --version${NC} manually in your terminal to see/resolve the prompt."
        fi
    else
        local git_advice="Please install git and retry."
        if [ "$OS" = "macos" ]; then
            git_advice="Install git using Homebrew: ${BOLD}brew install git${NC}"
        elif [ "$OS" = "linux" ]; then
            if [ "$IS_APT_BASED" -eq 1 ]; then
                git_advice="Install git using apt:\n       Run: ${BOLD}sudo apt update && sudo apt install -y git${NC}"
            else
                case "$DISTRO" in
                    fedora|rhel|centos|rocky|almalinux)
                        git_advice="Install git using dnf:\n       Run: ${BOLD}sudo dnf install -y git${NC}"
                        ;;
                    alpine)
                        git_advice="Install git using apk:\n       Run: ${BOLD}apk add git${NC}"
                        ;;
                    arch)
                        git_advice="Install git using pacman:\n       Run: ${BOLD}sudo pacman -S git${NC}"
                        ;;
                    *)
                        git_advice="Please install git using your package manager (${BOLD}apt, dnf, pacman, apk${NC}) and retry."
                        ;;
                esac
            fi
        fi
        exit_with_error "$ERR_001_GIT_MISSING" \
            "Git is missing from this system." \
            "$git_advice"
    fi

    # Check Python3
    if command -v python3 >/dev/null 2>&1; then
        if python3 -c 'import sys' >/dev/null 2>&1; then
            python_ver=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
            log_success "Python3 is active (Version $python_ver)"
            
            # Check version >= 3.8
            is_valid_ver=$(python3 -c 'import sys; print(1 if sys.version_info >= (3,8) else 0)')
            if [ "$is_valid_ver" -ne 1 ]; then
                exit_with_error "$ERR_003_PYTHON_VERSION" \
                    "Python version ($python_ver) is outdated." \
                    "Kenbun-Agent requires Python 3.8 or newer. Please upgrade your Python installation."
            fi
        else
            exit_with_error "$ERR_002_PYTHON_MISSING" \
                "Python3 executable is registered but fails to launch." \
                "Verify your interpreter installation by running: ${BOLD}python3 --version${NC}."
        fi
    else
        local python_advice="Please install Python 3.8+ and retry."
        if [ "$OS" = "macos" ]; then
            python_advice="Install Python3 using Homebrew: ${BOLD}brew install python${NC}"
        elif [ "$OS" = "linux" ] && [ "$IS_APT_BASED" -eq 1 ]; then
            python_advice="Install Python3 using apt:\n       Run: ${BOLD}sudo apt update && sudo apt install -y python3 python3-pip python3-venv python3-dev build-essential${NC}"
        fi
        exit_with_error "$ERR_002_PYTHON_MISSING" \
            "Python3 is missing from this system." \
            "$python_advice"
    fi

    # Check Python3 venv module presence proactively
    if command -v python3 >/dev/null 2>&1; then
        if python3 -c 'import venv' >/dev/null 2>&1; then
            log_success "Python3 venv module is active"
        else
            python_ver=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
            local venv_advice="Please install python3-venv and retry."
            if [ "$OS" = "macos" ]; then
                venv_advice="Reinstall Python3 using Homebrew: ${BOLD}brew install python${NC}"
            elif [ "$OS" = "linux" ] && [ "$IS_APT_BASED" -eq 1 ]; then
                venv_advice="Install the missing package first:\n       Run: ${BOLD}sudo apt update && sudo apt install -y python3-venv python3.${python_ver}-venv${NC}"
            fi
            exit_with_error "$ERR_004_VENV_FAILED" \
                "Python3 virtual environment module ('venv') is missing." \
                "$venv_advice"
        fi
    fi

    # Check Docker
    if command -v docker >/dev/null 2>&1; then
        # Capture stderr to distinguish permissions error from stopped service
        local docker_output
        docker_output=$(docker info 2>&1 || true)
        
        case "$docker_output" in
            *"permission denied"*)
                log_warn "Docker is running, but you do not have permission to access the socket."
                log_warn "  ➔ Linux (Permissions): Run ${BOLD}sudo usermod -aG docker \$USER && newgrp docker${NC}"
                ;;
            *"Cannot connect to the Docker daemon"*|*"error during connect"*)
                log_warn "Docker CLI is active, but the Docker Daemon is not running or not enabled."
                log_warn "  ➔ Linux (Start & Enable): Run ${BOLD}sudo systemctl enable --now docker${NC}"
                log_warn "  ➔ macOS: Open the Docker Desktop application"
                ;;
            *)
                if docker info >/dev/null 2>&1; then
                    log_success "Docker Engine is active and running ($(docker --version | head -n 1))"
                else
                    log_warn "Docker CLI is active, but the Docker Daemon connection is failing."
                    log_warn "  ➔ Linux (Start & Enable): Run ${BOLD}sudo systemctl enable --now docker${NC}"
                    log_warn "  ➔ macOS: Open the Docker Desktop application"
                fi
                ;;
        esac
    else
        log_warn "Docker is not detected. (Docker Compose Swarm stack requires Docker Engine to run)."
        if [ "$OS" = "linux" ]; then
            if [ "$IS_APT_BASED" -eq 1 ]; then
                log_warn "  ➔ Linux (Self-Healing Install): Run ${BOLD}curl -fsSL https://get.docker.com | sh && sudo systemctl enable --now docker && sudo usermod -aG docker \$USER && newgrp docker${NC}"
            else
                log_warn "  ➔ Linux (Self-Healing Install): Use your package manager to install 'docker' or follow https://docs.docker.com/engine/install/"
            fi
        fi
    fi

    # Check Docker Compose
    if docker compose version >/dev/null 2>&1; then
        log_success "Docker Compose is active ($(docker compose version | head -n 1))"
    elif command -v docker-compose >/dev/null 2>&1; then
        log_success "Docker-Compose (legacy CLI) is active ($(docker-compose --version | head -n 1))"
    else
        log_warn "Docker Compose is missing. You may not be able to spin up local docker swarm containers."
    fi
}

# 3. Resolve Workspace Layout
resolve_layout() {
    # If bootstrap.py exists in the current directory, we are running in-place
    if [ -f "scripts/bootstrap.py" ]; then
        INSTALL_DIR="$(pwd)"
        log_success "Active repository checkout detected. Installing in-place: $INSTALL_DIR"
    else
        INSTALL_DIR="$HOME/.kenbun-agent"
        log_info "No local repository checkout found. Preparing directory: $INSTALL_DIR"
        
        if [ -d "$INSTALL_DIR" ]; then
            log_info "Existing folder found at $INSTALL_DIR. Updating files..."
            cd "$INSTALL_DIR"
            git pull origin main || true
        else
            log_info "Cloning Kenbun-Agent repository..."
            git clone https://github.com/Clos01/Kenbun-Agent.git "$INSTALL_DIR"
            cd "$INSTALL_DIR"
        fi
    fi
}

# 4. Provision Virtual Environment & Dependencies
provision_venv() {
    log_info "Provisioning virtual environment inside $INSTALL_DIR/venv..."
    
    if [ -d "venv" ]; then
        if [ -f "venv/bin/python" ] && [ -f "venv/bin/pip" ]; then
            log_info "Reusing existing virtual environment..."
        else
            log_warn "Existing virtual environment directory is incomplete. Cleaning up..."
            rm -rf venv
        fi
    fi

    if [ ! -d "venv" ]; then
        # Catch venv creation failures gracefully (common on Debian/Ubuntu due to missing python3-venv)
        if ! python3 -m venv venv 2>/dev/null; then
            python_ver=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
            local advice=""
            if [ "$OS" = "macos" ]; then
                advice="Ensure Python3 and pip are properly installed via Homebrew:\n       Run: ${BOLD}brew install python@3.${python_ver}${NC}"
            elif [ "$OS" = "linux" ]; then
                case "$DISTRO" in
                    ubuntu|debian|raspbian|pop)
                        advice="Install the missing package first:\n       Run: ${BOLD}sudo apt update && sudo apt install -y python3.${python_ver}-venv${NC}"
                        ;;
                    fedora|rhel|centos|rocky|almalinux)
                        advice="Install pip and python devel tools:\n       Run: ${BOLD}sudo dnf install -y python3-pip python3-devel${NC}"
                        ;;
                    alpine)
                        advice="Install python, venv, and compilers:\n       Run: ${BOLD}apk add python3 py3-virtualenv gcc musl-dev libffi-dev openssl-dev bash${NC}"
                        ;;
                    arch)
                        advice="Install python-virtualenv:\n       Run: ${BOLD}sudo pacman -S python-virtualenv${NC}"
                        ;;
                    *)
                        advice="Please install the virtual environment package for python3.${python_ver} using your distro package manager."
                        ;;
                esac
            fi
            
            exit_with_error "$ERR_004_VENV_FAILED" \
                "Failed to create Python virtual environment." \
                "$advice"
        fi
    fi

    log_info "Installing runtime Python dependencies..."
    venv/bin/pip install --upgrade pip setuptools wheel || exit_with_error "$ERR_005_PIP_FAILED" \
        "Failed to bootstrap pip packages (pip/setuptools/wheel upgrade failed)." \
        "Verify your internet connection and DNS settings, or check for active proxy blocks."
    
    if [ -f "core/requirements.txt" ]; then
        venv/bin/pip install -r core/requirements.txt || exit_with_error "$ERR_005_PIP_FAILED" \
            "Failed to install requirements.txt dependencies." \
            "This can happen if compiler headers for cryptographic/system packages are missing.\n       ➔ On Alpine: apk add gcc musl-dev openssl-dev libffi-dev\n       ➔ On Ubuntu/Debian: sudo apt install -y build-essential libssl-dev libffi-dev python3-dev"
    fi
    
    venv/bin/pip install cryptography requests requests-mock pytest pydantic pydantic-settings || exit_with_error "$ERR_005_PIP_FAILED" \
        "Failed to install mandatory swarm library dependencies." \
        "Ensure standard compiler tools and headers are available for cryptography compilation."
    
    log_success "Python environment provisioned successfully."
}

# 5. Compile Wrapper and Register link to Shell Profile
register_binary() {
    log_info "Compiling global command wrapper..."

    BIN_DIR="$HOME/.local/bin"
    mkdir -p "$BIN_DIR"
    WRAPPER_PATH="$BIN_DIR/kenbun"

    # Create robust wrapper script with absolute path expanded at install-time
    cat << EOF > "$WRAPPER_PATH" || exit_with_error "$ERR_006_BINARY_WRITE" \
        "Could not write to global wrapper location: $WRAPPER_PATH" \
        "Verify write permissions for: $BIN_DIR"
#!/bin/bash
export PYTHONPATH="$INSTALL_DIR/core:\$PYTHONPATH"
if [ "\$1" = "--mcp" ] || [ "\$1" = "mcp" ]; then
    shift
    exec "$INSTALL_DIR/venv/bin/python" -m tools.infrastructure.server "\$@"
else
    exec "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/scripts/bootstrap.py" "\$@"
fi
EOF

    chmod +x "$WRAPPER_PATH" || exit_with_error "$ERR_006_BINARY_WRITE" \
        "Could not execute chmod +x on wrapper script." \
        "Verify ownership and permissions for: $WRAPPER_PATH"
        
    log_success "Wrapper created at $WRAPPER_PATH"

    # Guide user on system-wide access instead of executing automatic sudo symlinks (Security Best Practice)
    if [ "$(id -u)" -eq 0 ]; then
        log_info "To use Kenbun system-wide, you can manually symlink the wrapper:"
        echo -e "  ➔ Run command: ${BOLD}ln -sf $WRAPPER_PATH /usr/local/bin/kenbun${NC}"
    fi

    # Shell Profile PATH check
    SHELL_CONFIG=""
    case "$SHELL" in
        *zsh*)
            SHELL_CONFIG="$HOME/.zshrc"
            ;;
        *bash*)
            SHELL_CONFIG="$HOME/.bashrc"
            [ ! -f "$SHELL_CONFIG" ] && SHELL_CONFIG="$HOME/.bash_profile"
            ;;
        *)
            if [ -f "$HOME/.zshrc" ]; then
                SHELL_CONFIG="$HOME/.zshrc"
            elif [ -f "$HOME/.bashrc" ]; then
                SHELL_CONFIG="$HOME/.bashrc"
            fi
            ;;
    esac

    if [ -n "$SHELL_CONFIG" ]; then
        touch "$SHELL_CONFIG" 2>/dev/null || true
        
        # Check if ~/.local/bin is already in PATH
        if ! echo "$PATH" | tr ':' '\n' | grep -q "^$BIN_DIR$"; then
            if ! grep -q '\.local/bin' "$SHELL_CONFIG" 2>/dev/null; then
                echo "" >> "$SHELL_CONFIG"
                echo "# Kenbun-Agent — ensure ~/.local/bin is on PATH" >> "$SHELL_CONFIG"
                echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_CONFIG" || exit_with_error "$ERR_007_SHELL_CONFIG" \
                    "Failed to append PATH environment variable to $SHELL_CONFIG." \
                    "Verify file permissions or manually add 'export PATH=\"\$HOME/.local/bin:\$PATH\"' to your shell profile."
                log_success "Added $BIN_DIR to PATH in $SHELL_CONFIG"
            else
                log_success "$BIN_DIR is already registered in $SHELL_CONFIG"
            fi
        else
            log_success "$BIN_DIR is active on your PATH."
        fi
    fi
}

# 6. Launch Wizard
launch_wizard() {
    echo ""
    log_success "Kenbun-Agent has been successfully installed!"
    echo -e " ➔ Command wrapper: ${BOLD}kenbun${NC}"
    echo -e " ➔ Core checkout:   ${BOLD}$INSTALL_DIR${NC}"
    echo ""
    log_info "Launching the Sakura Interactive Setup Wizard..."
    echo ""
    
    # Run bootstrap directly (no exec, allowing post-execution notices if piped)
    export PYTHONPATH="$INSTALL_DIR/core:$PYTHONPATH"
    
    IS_PIPED=0
    if [ ! -t 0 ]; then
        IS_PIPED=1
    fi

    if [ "$IS_PIPED" -eq 1 ] && [ -c /dev/tty ]; then
        "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/scripts/bootstrap.py" < /dev/tty
    else
        "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/scripts/bootstrap.py"
    fi

    # Print a beautiful next-steps PATH activation guide if installed via curl pipe
    if [ "$IS_PIPED" -eq 1 ]; then
        echo ""
        echo -e "${PINK}${BOLD}┌─────────────────────────────────────────────────────────┐"
        echo -e "│            🌸 NEXT STEPS & PATH ACTIVATION              │"
        echo -e "├─────────────────────────────────────────────────────────┤"
        echo -e "│  Because you installed Kenbun-Agent via a piped curl    │"
        echo -e "│  command, standard input was redirected.                │"
        echo -e "│                                                         │"
        echo -e "│  ${YELLOW}⚠️  The current terminal tab cannot run 'kenbun' yet!  │"
        echo -e "│                                                         │"
        echo -e "│  ${NC}${BOLD}➔ Type \"source ~/.bashrc\" and press ENTER to reload:   │"
        echo -e "│     ${ROSE}${BOLD}source ~/.bashrc${PINK}                                    │"
        echo -e "│                                                         │"
        echo -e "│  ${NC}${BOLD}➔ Then configure keys by typing \"kenbun\" & press ENTER:│"
        echo -e "│     ${ROSE}${BOLD}kenbun${PINK}                                              │"
        echo -e "│                                                         │"
        echo -e "│  ${NC}${BOLD}➔ Or launch the wrapper directly by typing this:       │"
        echo -e "│     ${ROSE}${BOLD}~/.local/bin/kenbun${PINK}                                 │"
        echo -e "│                                                         │"
        echo -e "│  For full guidelines, please refer to the README.md:    │"
        echo -e "│  ${CYAN}https://github.com/Clos01/Kenbun-Agent${PINK}                 │"
        echo -e "└─────────────────────────────────────────────────────────┘${NC}"
        echo ""
    fi
}

# Execution Pipeline
print_banner
detect_os
audit_dependencies
resolve_layout
provision_venv
register_binary
launch_wizard
