#!/bin/sh
set -eu

VISION="${VISION_CONTAINER:-rk3588s-vision}"
ROOT="${ROBOT_STUDENT_INTERFACE_ROOT:-/data/robot-host/student/interfaces}"
SCRIPT="$ROOT/aux_target_relay.py"
COMMAND="${1:-status}"

[ "$(docker inspect -f '{{.State.Running}}' "$VISION" 2>/dev/null || echo false)" = true ] || {
  echo "ERROR: $VISION is not running" >&2
  exit 2
}

case "$COMMAND" in
  start)
    docker cp "$SCRIPT" "$VISION:/tmp/aux_target_relay.py"
    if docker exec "$VISION" bash -lc '
      set -eu
      source /opt/ros/noetic/setup.bash
      source /vision_ws/devel/setup.bash
      rosnode list 2>/dev/null | grep -qx /aux_target_relay
    '; then
      echo AUX_RELAY=RUNNING
      exit 0
    fi
    docker exec -d "$VISION" bash -lc '
      source /opt/ros/noetic/setup.bash
      source /vision_ws/devel/setup.bash
      exec python3 /tmp/aux_target_relay.py \
        _target_file:=/tmp/d435i-target.json \
        _max_age_s:=5.0 \
        >/tmp/aux-target-relay.log 2>&1
    '
    sleep 1
    docker exec "$VISION" bash -lc '
      source /opt/ros/noetic/setup.bash
      source /vision_ws/devel/setup.bash
      rosnode list | grep -qx /aux_target_relay
      echo AUX_RELAY=RUNNING
    '
    ;;
  stop)
    docker exec "$VISION" bash -lc '
      source /opt/ros/noetic/setup.bash
      source /vision_ws/devel/setup.bash
      rosnode kill /aux_target_relay >/dev/null 2>&1 || true
      rm -f /tmp/aux_target_relay.py /tmp/d435i-target.json
      echo AUX_RELAY=STOPPED
    '
    ;;
  status)
    docker exec "$VISION" bash -lc '
      source /opt/ros/noetic/setup.bash
      source /vision_ws/devel/setup.bash
      if rosnode list 2>/dev/null | grep -qx /aux_target_relay; then
        echo AUX_RELAY=RUNNING
        if ! timeout 5 rostopic echo -n 1 /competition/aux_target 2>/dev/null; then
          echo AUX_TARGET=NO_FRESH_DATA
        fi
        if ! timeout 5 rostopic echo -n 1 /competition/aux_target_valid 2>/dev/null; then
          echo AUX_TARGET_VALID=NO_DATA
        fi
      else
        echo AUX_RELAY=STOPPED
        exit 3
      fi
    '
    ;;
  *)
    echo "usage: $0 {start|stop|status}" >&2
    exit 2
    ;;
esac
