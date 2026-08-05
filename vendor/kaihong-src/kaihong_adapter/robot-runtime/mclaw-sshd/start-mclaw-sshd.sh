#!/system/bin/sh
set -eu

ROOT=/data/robot-host/mclaw-sshd
CONFIG="$ROOT/sshd_config"
PID_FILE="$ROOT/sshd.pid"
LOG_FILE="$ROOT/sshd.log"
HOST_KEY="$ROOT/ssh_host_ed25519_key"
AUTHORIZED_KEYS="$ROOT/authorized_keys"
RUNTIME_AUTHORIZED_KEYS=/var/empty/mclaw_authorized_keys

mkdir -p "$ROOT" /var/empty /run/sshd
chmod 700 "$ROOT"
if [ -f "$AUTHORIZED_KEYS" ]; then
    cp "$AUTHORIZED_KEYS" "$RUNTIME_AUTHORIZED_KEYS"
    chmod 600 "$RUNTIME_AUTHORIZED_KEYS"
fi

if [ ! -f "$HOST_KEY" ]; then
    /bin/run ssh-keygen -q -t ed25519 -N "" -f "$HOST_KEY"
    chmod 600 "$HOST_KEY"
    chmod 644 "$HOST_KEY.pub"
fi

if [ -f "$PID_FILE" ]; then
    old_pid=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
        echo "MClaw host SSH is already running: pid=$old_pid port=2223"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

# OpenSSH 10 requires an absolute path for its re-exec.  Keep /bin/run so the
# board runtime supplies its shared-library search path.
SSHD=/data/local/release/usr/sbin/sshd
/bin/run "$SSHD" -t -f "$CONFIG"
nohup /bin/run "$SSHD" -D -e -f "$CONFIG" >"$LOG_FILE" 2>&1 &
sshd_pid=$!
echo "$sshd_pid" >"$PID_FILE"

sleep 1
if ! kill -0 "$sshd_pid" 2>/dev/null; then
    echo "ERROR: host sshd failed to start" >&2
    tail -n 50 "$LOG_FILE" >&2 || true
    exit 1
fi

echo "MClaw host SSH started: pid=$sshd_pid port=2223"
