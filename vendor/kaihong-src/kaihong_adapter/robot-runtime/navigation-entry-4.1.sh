#!/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
MODE="${1:-}"

case "$MODE" in
  slam)
    exec "$ROOT/start-slam-4.1.sh"
    ;;
  navigation)
    exec "$ROOT/start-navigation-map-4.1.sh" \
      "${2:-/data/robot/maps/real_50cm.yaml}"
    ;;
  stop)
    exec "$ROOT/stop-navigation-4.1.sh"
    ;;
  status)
    exec "$ROOT/status-navigation-4.1.sh"
    ;;
  *)
    echo "usage: $0 {slam|navigation [map.yaml]|stop|status}" >&2
    exit 2
    ;;
esac
