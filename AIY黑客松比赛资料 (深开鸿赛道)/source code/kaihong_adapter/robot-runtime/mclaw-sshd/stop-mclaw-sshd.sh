#!/system/bin/sh
set -eu

PID_FILE=/data/robot-host/mclaw-sshd/sshd.pid

if command -v begetctl >/dev/null 2>&1; then
    begetctl stop_service mclaw_sshd >/dev/null 2>&1 || true
fi

if [ ! -f "$PID_FILE" ]; then
    echo "MClaw host SSH is not running"
    exit 0
fi

pid=$(cat "$PID_FILE" 2>/dev/null || true)
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
fi
rm -f "$PID_FILE"
echo "MClaw host SSH stopped"
