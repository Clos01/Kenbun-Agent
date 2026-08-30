#!/bin/bash
#
# Antigravity CLI - Remote Control Daemon Setup (Linux/macOS)
#
# Installs, updates, and manages 'agy --remote-control' as a background daemon
# via systemd (Linux) or launchd (macOS).
#
# For Windows, use agy_daemon.cmd instead.
#

set -e

# 1. Default Setup & Constants
AGY_BIN="${HOME}/.local/bin/agy"
LOG_FILE="${HOME}/.antigravity/agy_daemon.log"
WRAPPER_DIR="${HOME}/.antigravity/bin"
WRAPPER_FILE="${WRAPPER_DIR}/run_agy_remote_control.sh"
TOKEN_FILE="${HOME}/.gemini/jetski-standalone-oauth-token"
# Persisted user settings. The language server saves the instance name here as
# userSettings.cliRemoteControlHostname.
CONFIG_JSON="${HOME}/.gemini/config/config.json"

# Linux (systemd)
SERVICE_NAME="agy-remote-control.service"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${SERVICE_DIR}/${SERVICE_NAME}"
UPDATE_SERVICE_NAME="agy-remote-control-update.service"
UPDATE_TIMER_NAME="agy-remote-control-update.timer"
UPDATE_SERVICE_FILE="${SERVICE_DIR}/${UPDATE_SERVICE_NAME}"
UPDATE_TIMER_FILE="${SERVICE_DIR}/${UPDATE_TIMER_NAME}"

# macOS (launchd)
LABEL="com.antigravity.remote-control"
UPDATE_LABEL="com.antigravity.remote-control.update"
PLIST_DIR="${HOME}/Library/LaunchAgents"
PLIST_FILE="${PLIST_DIR}/${LABEL}.plist"
UPDATE_PLIST_FILE="${PLIST_DIR}/${UPDATE_LABEL}.plist"

action="${1:-install}"
shift || true

# 2. Parse Arguments
AUTO_UPDATE=true
NO_PROMPT=false
RC_NAME=""                # optional instance name shown in the instance list
UPDATE_INTERVAL="daily"   # systemd OnCalendar value; mapped to seconds on macOS
while [[ $# -gt 0 ]]; do
    case "$1" in
        --auto-update)    AUTO_UPDATE=true ;;
        --no-auto-update) AUTO_UPDATE=false ;;
        --no-prompt)      NO_PROMPT=true ;;
        --name)           shift; RC_NAME="${1:-}" ;;
        --name=*)         RC_NAME="${1#*=}" ;;
        --interval)       shift; UPDATE_INTERVAL="${1:-daily}" ;;
        --interval=*)     UPDATE_INTERVAL="${1#*=}" ;;
        *)                echo "[ERROR] Unknown parameter: $1" >&2 ;;
    esac
    shift || true
done

# 3. Detect Platform
OS="$(uname -s)"
case "$OS" in
    Linux)  PLATFORM="linux" ;;
    Darwin) PLATFORM="macos" ;;
    *)
        echo "Fatal: Unsupported operating system: $OS. This script supports Linux and macOS; use agy_daemon.cmd on Windows." >&2
        exit 1
        ;;
esac

# Map a systemd-style interval to seconds for macOS StartInterval.
interval_to_seconds() {
    case "$1" in
        hourly)  echo 3600 ;;
        daily)   echo 86400 ;;
        weekly)  echo 604800 ;;
        *[0-9]h) echo $(( ${1%h} * 3600 )) ;;
        *[0-9]m) echo $(( ${1%m} * 60 )) ;;
        *[0-9]) echo "$1" ;;
        *)       echo 86400 ;;
    esac
}

# 4. Ensure the agy Binary Is Installed
ensure_agy() {
    if [[ ! -x "$AGY_BIN" ]]; then
        AGY_BIN=$(command -v agy || true)
        if [[ -z "$AGY_BIN" ]]; then
            echo "⠋ 'agy' not found. Installing via the official Antigravity CLI installer..."
            if ! command -v curl >/dev/null 2>&1; then
                echo "Fatal: 'curl' is required to install 'agy' but is not available." >&2
                echo "Please install curl, or install 'agy' manually and re-run this script." >&2
                exit 1
            fi
            curl -fsSL https://antigravity.google/cli/install.sh | bash
            AGY_BIN="${HOME}/.local/bin/agy"
            [[ -x "$AGY_BIN" ]] || AGY_BIN=$(command -v agy || true)
            if [[ -z "$AGY_BIN" || ! -x "$AGY_BIN" ]]; then
                echo "Fatal: 'agy' installation failed." >&2
                echo "Please install it manually from https://antigravity.google/cli and re-run this script." >&2
                exit 1
            fi
            echo "✓ Installed agy at: $AGY_BIN"
            return 0
        fi
    fi
    # Already installed: pick up the latest release before setting up.
    "$AGY_BIN" update || \
        echo "Warning: 'agy update' failed; continuing with the current version." >&2
}

# 5. Instance Name and Launcher Wrapper
# Resolves the agy binary at launch time so the service keeps working if agy is
# reinstalled to a different location.

# Read the instance name the language server last persisted. Deliberately a
# plain sed match rather than a JSON parser so the script keeps zero
# dependencies; a miss just yields an empty default.
current_rc_name() {
    [[ -f "$CONFIG_JSON" ]] || return 0
    sed -n 's/.*"cliRemoteControlHostname"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
        "$CONFIG_JSON" 2>/dev/null | head -1
}

# Ask for the instance name as part of setup. Skipped when --name was given,
# when --no-prompt was passed, or when stdin is not a terminal, so unattended
# installs behave exactly as before.
prompt_name() {
    [[ -n "$RC_NAME" ]] && return 0
    [[ "$NO_PROMPT" == "true" ]] && return 0
    # Piped installs (curl | bash) have no usable stdin; prompt via the real
    # terminal when there is one, otherwise skip so unattended installs work.
    local read_src="/dev/stdin"
    if [[ -t 0 ]]; then
        read_src="/dev/stdin"
    elif ( : </dev/tty ) 2>/dev/null; then
        read_src="/dev/tty"
    else
        return 0
    fi

    local current reply
    current="$(current_rc_name)"

    echo ""
    echo "Instance name (how this machine appears in Remote Control)."
    echo "Lowercase letters, numbers, and hyphens work best (e.g. my-cloudtop)."
    if [[ -n "$current" ]]; then
        echo "Press Enter to keep the current name."
        read -r -p "Name [$current]: " reply <"$read_src" || reply=""
    else
        echo "Leave it blank and a name will be generated for you."
        read -r -p "Name (optional): " reply <"$read_src" || reply=""
    fi

    # A blank reply leaves RC_NAME empty so the flag is omitted entirely. That
    # lets the saved name keep applying, or, when nothing is saved, lets the
    # language server generate one on first run.
    if [[ -z "$reply" ]]; then
        if [[ -n "$current" ]]; then
            echo "  Keeping: $current"
        else
            echo "  A name will be generated for you on first run."
        fi
        return 0
    fi

    # Unchanged: leave the flag off so the saved setting keeps winning.
    if [[ "$reply" == "$current" ]]; then
        echo "  Keeping: $current"
        return 0
    fi
    RC_NAME="$reply"
}

# The CLI exits at startup if its local web UI port is already taken (e.g. by
# another agy instance), so pick a free one instead of relying on the default.
find_free_port() {
    local port=4400
    while (( port < 4500 )) && (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null; do
        port=$((port + 1))
    done
    echo "$port"
}

write_wrapper() {
    prompt_name
    mkdir -p "$WRAPPER_DIR" "$(dirname "$LOG_FILE")"
    local name_arg=""
    if [[ -n "$RC_NAME" ]]; then
        name_arg=" --remote-control-name \"${RC_NAME}\""
    fi
    # Unquoted heredoc so ${name_arg} is interpolated now; runtime variables are
    # escaped (\$) so they are evaluated when the wrapper runs instead.
    cat <<EOF > "$WRAPPER_FILE"
#!/bin/bash
AGY_BIN="\${HOME}/.local/bin/agy"
[[ -x "\$AGY_BIN" ]] || AGY_BIN=\$(command -v agy)
# The CLI exits at startup if this port is taken, so probe for a free one on
# every launch (the daemon manager restarts this wrapper, re-picking a port).
PORT=4400
while (( PORT < 4500 )) && (exec 3<>"/dev/tcp/127.0.0.1/\${PORT}") 2>/dev/null; do
    PORT=\$((PORT + 1))
done
exec "\$AGY_BIN" --remote-control --hub-port "\$PORT"${name_arg} "\$@"
EOF
    chmod +x "$WRAPPER_FILE"
    echo "✓ Created wrapper launcher at: $WRAPPER_FILE"
    if [[ -n "$RC_NAME" ]]; then
        echo "  Instance name: $RC_NAME"
    fi
}

# 6. First-Time Interactive Login
# The background daemon has no stdin, so the paste-a-code login flow cannot run
# there. Do it once interactively now; the token is saved to $TOKEN_FILE and the
# daemon reuses it. A watchdog stops the CLI automatically once the token
# appears, so setup continues without manual intervention.
do_login() {
    if [[ -s "$TOKEN_FILE" ]]; then
        echo "Notice: Already authenticated; skipping login."
        return 0
    fi
    echo "--------------------------------------------------------------"
    echo "First-time login required before the daemon can run headlessly."
    echo "A sign-in URL will be printed below. Open it and paste the code"
    echo "if prompted. Setup continues automatically once you're signed in"
    echo "(or press Ctrl+C after signing in)."
    echo "--------------------------------------------------------------"
    # Watchdog: stop the interactive CLI once the token file appears.
    ( while [[ ! -s "$TOKEN_FILE" ]]; do sleep 2; done; sleep 2;
      pkill -P $$ -f -- "--remote-control" 2>/dev/null ) &
    local wd=$!
    trap 'echo' INT
    # Piped runs (curl | bash) leave stdin exhausted; give the CLI the real
    # terminal so the paste-a-code prompt works.
    if [[ -t 0 ]]; then
        "$AGY_BIN" --remote-control --hub-port "$(find_free_port)" >/dev/null || true
    elif ( : </dev/tty ) 2>/dev/null; then
        "$AGY_BIN" --remote-control --hub-port "$(find_free_port)" </dev/tty >/dev/null || true
    else
        echo "[ERROR] Sign-in needs an interactive terminal, but stdin is not a TTY" >&2
        echo "        (e.g. the script was piped into bash). Download it and run directly:" >&2
        echo "        bash agy_daemon.sh install" >&2
        exit 1
    fi
    trap - INT
    kill "$wd" 2>/dev/null || true
    wait "$wd" 2>/dev/null || true
    if [[ -s "$TOKEN_FILE" ]]; then
        echo "✓ Login detected. Continuing setup..."
    else
        echo "[ERROR] Sign-in did not complete (no auth token found)." >&2
        echo "        Install aborted: the daemon would only crash-loop unauthenticated." >&2
        echo "        Re-run '$0 install' to try again." >&2
        exit 1
    fi
}

# ===========================================================================
# 7. Platform Implementation: Linux (systemd)
# ===========================================================================
install_linux() {
    mkdir -p "$SERVICE_DIR"

    cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Antigravity CLI (agy) Remote Control Daemon
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Environment=AGY_CLI_DISABLE_AUTO_UPDATE=false
ExecStartPre=-$AGY_BIN --bg-updater
ExecStart=$WRAPPER_FILE
Restart=always
RestartSec=5
StandardOutput=append:$LOG_FILE
StandardError=append:$LOG_FILE

[Install]
WantedBy=default.target
EOF
    echo "Created systemd service file at: $SERVICE_FILE"

    if command -v loginctl >/dev/null 2>&1; then
        loginctl enable-linger "$USER" 2>/dev/null || true
    fi

    systemctl --user daemon-reload
    systemctl --user enable "$SERVICE_NAME"
    systemctl --user restart "$SERVICE_NAME"

    if [[ "$AUTO_UPDATE" == "true" ]]; then
        echo "Enabling scheduled auto-update restarts (interval: $UPDATE_INTERVAL)"
        cat <<EOF > "$UPDATE_SERVICE_FILE"
[Unit]
Description=Restart Antigravity CLI Remote Control Daemon to apply updates

[Service]
Type=oneshot
ExecStart=$(command -v systemctl) --user restart $SERVICE_NAME
EOF
        cat <<EOF > "$UPDATE_TIMER_FILE"
[Unit]
Description=Periodically restart Antigravity CLI Remote Control Daemon to apply updates

[Timer]
OnCalendar=$UPDATE_INTERVAL
Persistent=true

[Install]
WantedBy=timers.target
EOF
        systemctl --user daemon-reload
        systemctl --user enable "$UPDATE_TIMER_NAME"
        systemctl --user restart "$UPDATE_TIMER_NAME"
        echo "Created auto-update timer at: $UPDATE_TIMER_FILE"
    else
        systemctl --user stop "$UPDATE_TIMER_NAME" 2>/dev/null || true
        systemctl --user disable "$UPDATE_TIMER_NAME" 2>/dev/null || true
        rm -f "$UPDATE_SERVICE_FILE" "$UPDATE_TIMER_FILE"
        systemctl --user daemon-reload
        echo "Scheduled auto-update restarts: disabled (--no-auto-update)"
    fi

    if systemctl --user is-active --quiet "$SERVICE_NAME"; then
        echo "=== Success! Daemon is active ==="
    else
        echo "Warning: the daemon did not report active; run '$0 status' for details." >&2
    fi
}

status_linux() {
    systemctl --user --no-pager status "$SERVICE_NAME"
    if [[ -f "$UPDATE_TIMER_FILE" ]]; then
        echo "--- Auto-update timer ---"
        systemctl --user --no-pager list-timers "$UPDATE_TIMER_NAME" || true
    fi
    echo "--- Recent Logs ---"
    tail -n 10 "$LOG_FILE" 2>/dev/null || true
}

restart_linux() {
    systemctl --user restart "$SERVICE_NAME"
    echo "Restarted $SERVICE_NAME"
}

logout_linux() {
    systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
}

uninstall_linux() {
    systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user stop "$UPDATE_TIMER_NAME" 2>/dev/null || true
    systemctl --user disable "$UPDATE_TIMER_NAME" 2>/dev/null || true
    rm -f "$SERVICE_FILE" "$WRAPPER_FILE" "$UPDATE_SERVICE_FILE" "$UPDATE_TIMER_FILE"
    systemctl --user daemon-reload
    echo "Removed $SERVICE_NAME, wrapper, and auto-update timer"
}

# ===========================================================================
# 8. Platform Implementation: macOS (launchd)
# ===========================================================================
GUI_DOMAIN="gui/$(id -u 2>/dev/null || echo "$UID")"

install_macos() {
    mkdir -p "$PLIST_DIR"

    cat <<EOF > "$PLIST_FILE"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${WRAPPER_FILE}</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>AGY_CLI_DISABLE_AUTO_UPDATE</key>
        <string>false</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_FILE}</string>
    <key>StandardErrorPath</key>
    <string>${LOG_FILE}</string>
</dict>
</plist>
EOF
    echo "Created launchd plist at: $PLIST_FILE"

    # (Re)load the agent. bootout first to clear any previous instance.
    launchctl bootout "$GUI_DOMAIN/$LABEL" 2>/dev/null || true
    if ! launchctl bootstrap "$GUI_DOMAIN" "$PLIST_FILE" 2>/dev/null; then
        # Fallback for older macOS.
        launchctl unload "$PLIST_FILE" 2>/dev/null || true
        launchctl load -w "$PLIST_FILE"
    fi
    launchctl enable "$GUI_DOMAIN/$LABEL" 2>/dev/null || true
    launchctl kickstart -k "$GUI_DOMAIN/$LABEL" 2>/dev/null || true

    if [[ "$AUTO_UPDATE" == "true" ]]; then
        local secs
        secs=$(interval_to_seconds "$UPDATE_INTERVAL")
        echo "Enabling scheduled auto-update restarts (every ${secs}s)"
        cat <<EOF > "$UPDATE_PLIST_FILE"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${UPDATE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/launchctl</string>
        <string>kickstart</string>
        <string>-k</string>
        <string>${GUI_DOMAIN}/${LABEL}</string>
    </array>
    <key>StartInterval</key>
    <integer>${secs}</integer>
</dict>
</plist>
EOF
        launchctl bootout "$GUI_DOMAIN/$UPDATE_LABEL" 2>/dev/null || true
        if ! launchctl bootstrap "$GUI_DOMAIN" "$UPDATE_PLIST_FILE" 2>/dev/null; then
            launchctl unload "$UPDATE_PLIST_FILE" 2>/dev/null || true
            launchctl load -w "$UPDATE_PLIST_FILE"
        fi
        echo "Created auto-update agent at: $UPDATE_PLIST_FILE"
    else
        launchctl bootout "$GUI_DOMAIN/$UPDATE_LABEL" 2>/dev/null || true
        launchctl unload "$UPDATE_PLIST_FILE" 2>/dev/null || true
        rm -f "$UPDATE_PLIST_FILE"
        echo "Scheduled auto-update restarts: disabled (--no-auto-update)"
    fi

    if launchctl print "$GUI_DOMAIN/$LABEL" >/dev/null 2>&1; then
        echo "=== Success! Daemon is active ==="
    else
        echo "Warning: the daemon did not report active; run '$0 status' for details." >&2
    fi
}

status_macos() {
    echo "--- Daemon ($LABEL) ---"
    launchctl print "$GUI_DOMAIN/$LABEL" 2>/dev/null | head -n 20 || \
        launchctl list | grep "$LABEL" || echo "Not loaded."
    if [[ -f "$UPDATE_PLIST_FILE" ]]; then
        echo "--- Auto-update agent ($UPDATE_LABEL) ---"
        launchctl list | grep "$UPDATE_LABEL" || echo "Not loaded."
    fi
    echo "--- Recent Logs ---"
    tail -n 10 "$LOG_FILE" 2>/dev/null || true
}

restart_macos() {
    launchctl kickstart -k "$GUI_DOMAIN/$LABEL"
    echo "Restarted $LABEL"
}

logout_macos() {
    launchctl bootout "$GUI_DOMAIN/$LABEL" 2>/dev/null || true
    launchctl disable "$GUI_DOMAIN/$LABEL" 2>/dev/null || true
}

uninstall_macos() {
    launchctl bootout "$GUI_DOMAIN/$LABEL" 2>/dev/null || launchctl unload "$PLIST_FILE" 2>/dev/null || true
    launchctl bootout "$GUI_DOMAIN/$UPDATE_LABEL" 2>/dev/null || launchctl unload "$UPDATE_PLIST_FILE" 2>/dev/null || true
    rm -f "$PLIST_FILE" "$UPDATE_PLIST_FILE" "$WRAPPER_FILE"
    echo "Removed $LABEL, auto-update agent, and wrapper"
}

# 9. Helper: Display usage instructions
show_usage() {
    echo "Usage: $0 [install [--no-auto-update] [--interval <interval>] | status | restart | logout | uninstall]"
    echo ""
    echo "  install                 Install and start the daemon (starts on login/boot)."
    echo "                          Auto-update is ON by default: periodically restarts"
    echo "                          the daemon to apply downloaded updates."
    echo "  install --no-auto-update  Install without the scheduled auto-update."
    echo "  install --name <name>   Set the instance name shown in the instance list."
    echo "                          If omitted, setup asks for it interactively."
    echo "  install --no-prompt     Don't ask for a name; keep whatever is saved."
    echo "  install --interval weekly Customize the auto-update cadence (default: daily)."
    echo "                          Linux accepts systemd OnCalendar values; macOS accepts"
    echo "                          hourly/daily/weekly or Nh/Nm/seconds."
    echo "  status                  Show daemon status and recent logs."
    echo "  restart                 Restart the daemon (also applies any update)."
    echo "  logout                  Sign out: stop the daemon and delete the saved auth token."
    echo "  uninstall               Stop and remove the daemon and auto-update job."
    echo ""
    echo "  Detected platform: $PLATFORM. (Windows: use agy_daemon.cmd)"
}

# 10. Dispatch
case "$action" in
    install)
        echo "=== Setting up agy Remote Control Daemon ($PLATFORM) ==="
        ensure_agy
        echo "Using agy binary: $AGY_BIN"
        write_wrapper
        do_login
        install_"$PLATFORM"
        echo ""
        echo "Logs are being appended to: $LOG_FILE"
        echo "To check status anytime: $0 status"
        ;;
    status)    status_"$PLATFORM" ;;
    restart)   restart_"$PLATFORM" ;;
    logout)
        logout_"$PLATFORM"
        rm -f "$TOKEN_FILE"
        echo "Signed out: removed the saved auth token and stopped the daemon."
        echo "Run '$0 install' to sign in again and re-enable it."
        ;;
    uninstall) uninstall_"$PLATFORM" ;;
    *)
        echo "[ERROR] Unknown command: $action" >&2
        show_usage
        exit 1
        ;;
esac
