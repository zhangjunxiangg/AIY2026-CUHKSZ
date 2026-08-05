#!/system/bin/sh
set -eu

ROOT=/data/robot-host/mclaw-sshd
CONFIG="$ROOT/sshd_config"
LOG_FILE="$ROOT/sshd.log"
HOST_KEY="$ROOT/ssh_host_ed25519_key"
AUTHORIZED_KEYS="$ROOT/authorized_keys"
RUNTIME_AUTHORIZED_KEYS=/var/empty/mclaw_authorized_keys
SSHD=/data/local/release/usr/sbin/sshd

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

rm -f "$ROOT/sshd.pid"
/bin/run "$SSHD" -t -f "$CONFIG"

# Stay in the foreground so OpenHarmony init can supervise the daemon.
exec /bin/run "$SSHD" -D -E "$LOG_FILE" -f "$CONFIG"
