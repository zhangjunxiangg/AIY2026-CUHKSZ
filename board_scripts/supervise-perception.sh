#!/bin/sh
# Supervisor for the Astra UVC publisher + perception node.
# Run on the board host (not inside the container). It restarts the whole
# pipeline whenever the publisher dies, the perception node dies, or the
# camera topic stops producing fresh frames.
set -e

ROOT=/data/robot-host
RUN_SCRIPT="$ROOT/board_scripts/run-perception-uvc.sh"
LOG="$ROOT/logs/perception-supervisor.log"
mkdir -p "$ROOT/logs"

# Max restarts within a window to avoid infinite crash loops.
RESTART_WINDOW_S=120
MAX_RESTARTS=5
restarts=0
window_start=$(date +%s)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

is_publisher_running() {
    docker exec rk3588s-vision bash -c 'pgrep -f uvc_astra_publisher.py >/dev/null 2>&1'
}

is_perception_running() {
    docker exec rk3588s-vision bash -c 'pgrep -f perception_node.py >/dev/null 2>&1'
}

camera_topic_alive() {
    docker exec rk3588s-vision bash -c \
      'source /opt/ros/noetic/setup.bash && timeout 5 rostopic hz -w 2 /astra_camera/rgb/image_raw >/dev/null 2>&1'
}

stop_all() {
    log "stopping all perception processes"
    docker exec rk3588s-vision sh -c 'pkill -f uvc_astra_publisher.py || true; pkill -f perception_node.py || true' || true
    sleep 1
}

start_all() {
    log "starting perception pipeline"
    # Run the launch script in the background; the script itself starts publisher,
    # verifies the topic, then runs perception_node in the foreground inside the
    # container. We background the docker exec call.
    nohup "$RUN_SCRIPT" >>"$LOG" 2>&1 &
}

# Reset the restart counter if the window has elapsed.
update_restart_window() {
    now=$(date +%s)
    if [ $((now - window_start)) -gt "$RESTART_WINDOW_S" ]; then
        restarts=0
        window_start=$now
    fi
}

log "supervisor started (PID $$)"
while true; do
    update_restart_window

    need_restart=0
    if ! is_publisher_running; then
        log "publisher not running -> restart"
        need_restart=1
    elif ! is_perception_running; then
        log "perception node not running -> restart"
        need_restart=1
    elif ! camera_topic_alive; then
        log "camera topic stale -> restart"
        need_restart=1
    fi

    if [ "$need_restart" -eq 1 ]; then
        restarts=$((restarts + 1))
        if [ "$restarts" -gt "$MAX_RESTARTS" ]; then
            log "too many restarts ($restarts) in ${RESTART_WINDOW_S}s, giving up"
            exit 1
        fi
        log "restart attempt $restarts/$MAX_RESTARTS"
        stop_all
        start_all
        # Wait a bit for the pipeline to come up before checking again.
        sleep 8
    else
        sleep 5
    fi
done
