#!/system/bin/sh
set -u

ROOT=/data/robot-host
LOG="$ROOT/log/boot-stack.log"
mkdir -p "$ROOT/log" "$ROOT/run"
rm -rf /tmp/kaihong-ros-log
mkdir -p /tmp/kaihong-ros-log
: >"$LOG"
exec >>"$LOG" 2>&1

echo "boot_stack_begin=$(date 2>/dev/null || true)"

attempt=0
while [ "$attempt" -lt 60 ]; do
    if [ -c /dev/ttyCH343USB0 ] && docker info >/dev/null 2>&1; then
        break
    fi
    attempt=$((attempt + 1))
    sleep 2
done

if [ ! -c /dev/ttyCH343USB0 ]; then
    echo "ERROR: /dev/ttyCH343USB0 unavailable"
else
    "$ROOT/start-all-4.1.sh" || echo "ERROR: robot stack start failed"
fi

echo "boot_stack_ready=$(date 2>/dev/null || true)"
"$ROOT/status-all-4.1.sh" || true

trap '"$ROOT/stop-all-4.1.sh" >/dev/null 2>&1 || true; exit 0' TERM INT
while :; do
    sleep 3600 &
    wait $!
done
