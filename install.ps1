<#
.SYNOPSIS
    Kenbun-Agent Autonomous Installer & Bootstrapper (Windows Native)
.DESCRIPTION
    Automated zero-friction installation script for Windows.
    Detects runtime constraints, audits dependencies, provisions virtual
    environments, compiles wrappers, and links the global `kenbun` command.
#>

$ErrorActionPreference = "Stop"

function Print-Banner {
    Write-Host "┌─────────────────────────────────────────────────────────┐" -ForegroundColor Magenta
    Write-Host "│             🌸 Kenbun-Agent Installer                    │" -ForegroundColor Magenta
    Write-Host "├─────────────────────────────────────────────────────────┤" -ForegroundColor Magenta
    Write-Host "│  Sovereign Japanese Agentic Assembly (Systems 1-6)         │" -ForegroundColor Magenta
    Write-Host "└─────────────────────────────────────────────────────────┘" -ForegroundColor Magenta
}

function Log-Info ($Message) {
    Write-Host "→ " -NoNewline -ForegroundColor Cyan
    Write-Host $Message
}

function Log-Success ($Message) {
    Write-Host "✓ " -NoNewline -ForegroundColor Green
    Write-Host $Message
}

function Log-Warn ($Message) {
    Write-Host "⚠ " -NoNewline -ForegroundColor Yellow
    Write-Host $Message
}

function Log-Error ($Message) {
    Write-Host "✗ " -NoNewline -ForegroundColor Red
    Write-Host $Message
}

function Exit-WithError ($ErrCode, $ErrMsg, $ErrSolution) {
    Write-Host "`n┌─────────────────────────────────────────────────────────┐" -ForegroundColor Red
    Write-Host "│                🌸 INSTALLATION FAILURE                  │" -ForegroundColor Red
    Write-Host "├─────────────────────────────────────────────────────────┘" -ForegroundColor Red
    Log-Error "Error Code: $ErrCode"
    Log-Error "Reason:     $ErrMsg"
    Write-Host "-----------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "Recommended Self-Healing Action:" -ForegroundColor Yellow
    Write-Host "  $ErrSolution"
    Write-Host "└─────────────────────────────────────────────────────────┘`n" -ForegroundColor Red
    exit 1
}

# 1. Dependency Audit
function Audit-Dependencies {
    Log-Info "Auditing platform dependencies..."

    # Check Git
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $gitVer = git --version
        Log-Success "Git is active ($gitVer)"
    } else {
        Exit-WithError "ERR_001_GIT_MISSING" "Git is missing from this system." "Please install Git for Windows (https://git-scm.com/download/win) and retry."
    }

    # Check Python3
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $pyVer = python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
        $isValidVer = python -c "import sys; print(1 if sys.version_info >= (3,8) else 0)"
        if ($isValidVer -eq 1) {
            Log-Success "Python is active (Version $pyVer)"
        } else {
            Exit-WithError "ERR_003_PYTHON_VERSION" "Python version ($pyVer) is outdated." "Kenbun-Agent requires Python 3.8 or newer. Please upgrade your Python installation."
        }
    } else {
        Exit-WithError "ERR_002_PYTHON_MISSING" "Python is missing from this system." "Please install Python 3.8+ (https://www.python.org/downloads/windows/) and retry."
    }

    # Check Docker
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        $dockerVer = docker --version
        Log-Success "Docker Engine is active ($dockerVer)"
    } else {
        Log-Warn "Docker is not detected. (Docker Compose Assembly stack requires Docker Desktop to run)."
        Log-Warn "  ➔ Install Docker Desktop for Windows: https://docs.docker.com/desktop/install/windows-install/"
    }
}

# 2. Resolve Workspace Layout
function Resolve-Layout {
    if (Test-Path "scripts\bootstrap.py") {
        $global:INSTALL_DIR = (Get-Location).Path
        Log-Success "Active repository checkout detected. Installing in-place: $INSTALL_DIR"
    } else {
        $global:INSTALL_DIR = Join-Path $env:USERPROFILE ".kenbun-agent"
        Log-Info "No local repository checkout found. Preparing directory: $INSTALL_DIR"
        
        if (Test-Path $INSTALL_DIR) {
            Log-Info "Existing folder found at $INSTALL_DIR. Updating files..."
            Set-Location $INSTALL_DIR
            git pull origin main
        } else {
            Log-Info "Cloning Kenbun-Agent repository..."
            git clone https://github.com/Clos01/Kenbun-Agent.git $INSTALL_DIR
            Set-Location $INSTALL_DIR
        }
    }
}

# 3. Provision Virtual Environment
function Provision-Venv {
    Log-Info "Provisioning virtual environment inside $INSTALL_DIR\venv..."
    
    if (Test-Path "venv") {
        if ((Test-Path "venv\Scripts\python.exe") -and (Test-Path "venv\Scripts\pip.exe")) {
            Log-Info "Reusing existing virtual environment..."
        } else {
            Log-Warn "Existing virtual environment directory is incomplete. Cleaning up..."
            Remove-Item -Recurse -Force "venv"
        }
    }

    if (!(Test-Path "venv")) {
        python -m venv venv
        if ($LASTEXITCODE -ne 0) {
            Exit-WithError "ERR_004_VENV_FAILED" "Failed to create Python virtual environment." "Ensure Python is installed correctly and allows creating venvs."
        }
    }

    Log-Info "Installing runtime Python dependencies..."
    & "venv\Scripts\pip.exe" install --upgrade pip setuptools wheel
    
    if (Test-Path "core\requirements.txt") {
        & "venv\Scripts\pip.exe" install -r core\requirements.txt
    }
    
    & "venv\Scripts\pip.exe" install cryptography requests requests-mock pytest pydantic pydantic-settings
    
    if ($LASTEXITCODE -ne 0) {
        Exit-WithError "ERR_005_PIP_FAILED" "Failed to bootstrap pip packages." "Verify your internet connection."
    }

    Log-Success "Python environment provisioned successfully."
}

# 4. Compile Wrapper and Register to PATH
function Register-Binary {
    Log-Info "Compiling global command wrapper..."

    $BIN_DIR = Join-Path $env:USERPROFILE ".local\bin"
    if (!(Test-Path $BIN_DIR)) {
        New-Item -ItemType Directory -Path $BIN_DIR | Out-Null
    }

    $WRAPPER_BAT = Join-Path $BIN_DIR "kenbun.bat"
    $WRAPPER_PS1 = Join-Path $BIN_DIR "kenbun.ps1"

    # Create Batch wrapper
    $batContent = @"
@echo off
set PYTHONPATH=$INSTALL_DIR\core;%PYTHONPATH%
if "%1"=="--mcp" (
    shift
    "%INSTALL_DIR%\venv\Scripts\python.exe" -m tools.infrastructure.server %*
) else if "%1"=="mcp" (
    shift
    "%INSTALL_DIR%\venv\Scripts\python.exe" -m tools.infrastructure.server %*
) else (
    "%INSTALL_DIR%\venv\Scripts\python.exe" "%INSTALL_DIR%\scripts\bootstrap.py" %*
)
"@
    Set-Content -Path $WRAPPER_BAT -Value $batContent

    # Create PS1 wrapper
    $ps1Content = @"
`$env:PYTHONPATH = "$INSTALL_DIR\core;" + `$env:PYTHONPATH
if (`$args[0] -eq "--mcp" -or `$args[0] -eq "mcp") {
    & "$INSTALL_DIR\venv\Scripts\python.exe" -m tools.infrastructure.server `$args[1..`$args.Length]
} else {
    & "$INSTALL_DIR\venv\Scripts\python.exe" "$INSTALL_DIR\scripts\bootstrap.py" `$args
}
"@
    Set-Content -Path $WRAPPER_PS1 -Value $ps1Content

    Log-Success "Wrapper created at $WRAPPER_BAT and $WRAPPER_PS1"

    # Add to User PATH if not exists
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notmatch [regex]::Escape($BIN_DIR)) {
        $newUserPath = $userPath + ";" + $BIN_DIR
        [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
        Log-Success "Added $BIN_DIR to User PATH."
    } else {
        Log-Success "$BIN_DIR is already registered in User PATH."
    }
}

# 5. Launch Wizard
function Launch-Wizard {
    Write-Host "`n"
    Log-Success "Kenbun-Agent has been successfully installed!"
    Write-Host " ➔ Command wrapper: kenbun"
    Write-Host " ➔ Core checkout:   $INSTALL_DIR`n"
    Log-Info "Launching the Sakura Interactive Setup Wizard...`n"
    
    $env:PYTHONPATH = "$INSTALL_DIR\core;" + $env:PYTHONPATH
    & "$INSTALL_DIR\venv\Scripts\python.exe" "$INSTALL_DIR\scripts\bootstrap.py"
}

# Execution Pipeline
Print-Banner
Audit-Dependencies
Resolve-Layout
Provision-Venv
Register-Binary
Launch-Wizard
