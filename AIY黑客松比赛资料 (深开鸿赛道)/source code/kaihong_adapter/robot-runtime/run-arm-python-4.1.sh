#!/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
SCRIPT="${1:-}"
[ -n "$SCRIPT" ] || {
    echo "usage: $0 SCRIPT.py [args...]" >&2
    exit 2
}
shift

case "$SCRIPT" in
    */*|*..*)
        echo "ERROR: SCRIPT must be a basename under $ROOT" >&2
        exit 2
        ;;
esac
[ -f "$ROOT/$SCRIPT" ] || {
    echo "ERROR: arm script not found: $ROOT/$SCRIPT" >&2
    exit 3
}

if "$ROOT/status-host-arm-4.1.sh" >/dev/null 2>&1; then
    . "$ROOT/robot-env.sh"
    . "$ROOT/host-arm-env.sh"
    exec "$ROOT/bin/python3" "$ROOT/$SCRIPT" "$@"
fi

echo "ERROR: host arm is not running" >&2
exit 4
