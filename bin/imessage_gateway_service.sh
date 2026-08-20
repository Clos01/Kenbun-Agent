#!/usr/bin/env bash
# ==============================================================================
# 📱 Antigravity / Kenbun iMessage Gateway Service Controller
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$ROOT_DIR/brain_health/imessage_gateway.pid"
LOG_FILE="$ROOT_DIR/brain_health/imessage_gateway.log"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python3"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

start() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "⚠️  iMessage Gateway is already running (PID: $(cat "$PID_FILE"))."
        exit 0
    fi

    echo "🚀 Starting iMessage Gateway daemon in background..."
    nohup "$PYTHON_BIN" "$ROOT_DIR/scripts/imessage_gateway.py" > /dev/null 2>&1 &
    GATEWAY_PID=$!
    echo "$GATEWAY_PID" > "$PID_FILE"

    sleep 1
    if kill -0 "$GATEWAY_PID" 2>/dev/null; then
        echo "✅ iMessage Gateway successfully started! (PID: $GATEWAY_PID)"
        echo "📄 Logs: $LOG_FILE"
    else
        echo "❌ Failed to start iMessage Gateway. Check logs at: $LOG_FILE"
        exit 1
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "ℹ️  No PID file found. Gateway might not be running."
        pkill -f "scripts/imessage_gateway.py" 2>/dev/null || true
        return
    fi

    PID="$(cat "$PID_FILE")"
    if kill -0 "$PID" 2>/dev/null; then
        echo "🛑 Stopping iMessage Gateway (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        echo "✅ Stopped."
    else
        echo "ℹ️  Process $PID is not running. Removing stale PID file."
        rm -f "$PID_FILE"
    fi
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "🟢 iMessage Gateway is RUNNING (PID: $(cat "$PID_FILE"))"
    else
        echo "🔴 iMessage Gateway is STOPPED"
    fi
}

logs() {
    tail -f "$LOG_FILE"
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
