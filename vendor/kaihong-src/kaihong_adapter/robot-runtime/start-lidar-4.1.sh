#!/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
. "$ROOT/robot-env.sh"
PID_FILE="$ROOT/run/lidar.pid"
LOG_FILE="$ROOT/log/lidar.log"

find_lidar() {
  for node in /dev/ttyUSB*; do
    [ -c "$node" ] || continue
    tty="${node##*/}"
    path="$(readlink -f "/sys/class/tty/$tty/device")"
    vid="$(cat "$path/../../idVendor" 2>/dev/null || true)"
    pid="$(cat "$path/../../idProduct" 2>/dev/null || true)"
    [ "$vid:$pid" = '1a86:7523' ] && { echo "$node"; return 0; }
  done
  return 1
}

if [ -n "${LIDAR_DEVICE:-}" ]; then
  DEVICE="$LIDAR_DEVICE"
else
  DEVICE=""
  # USB enumeration can lag the init service by several seconds after boot.
  device_attempt=0
  while [ "$device_attempt" -lt 30 ] && [ -z "$DEVICE" ]; do
    DEVICE="$(find_lidar || true)"
    [ -n "$DEVICE" ] || sleep 2
    device_attempt=$((device_attempt + 1))
  done
fi
[ -n "$DEVICE" ] && [ -c "$DEVICE" ] || {
  echo 'ERROR: RPLIDAR CH341 1a86:7523 serial node is missing after 60s' >&2
  exit 2
}

ros_attempt=0
while [ "$ros_attempt" -lt 30 ] && ! rostopic list >/dev/null 2>&1; do
  sleep 2
  ros_attempt=$((ros_attempt + 1))
done
rostopic list >/dev/null 2>&1 || { echo 'ERROR: ROS master is unavailable after 60s' >&2; exit 3; }

if [ -f "$PID_FILE" ]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    if timeout 3 rostopic echo -n 1 /scan >/dev/null 2>&1; then
      echo "lidar=RUNNING SCAN=READY DEVICE=$DEVICE"
      exit 0
    fi
  fi
  "$ROOT/stop-lidar-4.1.sh" >/dev/null 2>&1 || true
fi

mkdir -p "$ROOT/run" "$ROOT/log"
start_attempt=0
while [ "$start_attempt" -lt 3 ]; do
  nohup "$ROOT/bin/python3" "$ROOT/rplidar-raw-node.py" \
    _serial_port:="$DEVICE" >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"

  attempt=0
  while [ "$attempt" -lt 20 ]; do
    if timeout 2 rostopic echo -n 1 /scan >/dev/null 2>&1; then
      echo "lidar=RUNNING SCAN=READY DEVICE=$DEVICE DRIVER=raw-standard"
      exit 0
    fi
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    attempt=$((attempt + 1))
    sleep 1
  done
  "$ROOT/stop-lidar-4.1.sh" >/dev/null 2>&1 || true
  start_attempt=$((start_attempt + 1))
  [ "$start_attempt" -lt 3 ] && sleep 2
done

echo 'ERROR: lidar started but /scan has no data after 3 attempts' >&2
tail -n 80 "$LOG_FILE" >&2 || true
exit 5
