#!/bin/sh
set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: $0 CAR_IP [AUX_BOARD_IP]" >&2
    exit 2
fi

CAR_IP=$1
AUX_IP=${2:-}

validate_ipv4() {
    value=$1
    old_ifs=$IFS
    IFS=.
    set -- $value
    IFS=$old_ifs
    [ "$#" -eq 4 ] || return 1
    for octet in "$@"; do
        case "$octet" in ''|*[!0-9]*) return 1 ;; esac
        [ "$octet" -le 255 ] || return 1
    done
}

validate_ipv4 "$CAR_IP" || { echo "ERROR: invalid car IPv4 address" >&2; exit 2; }

if [ -z "$AUX_IP" ]; then
    output=$(ip -4 addr show wlan0 2>/dev/null || true)
    previous=""
    for word in $output; do
        if [ "$previous" = "inet" ]; then
            AUX_IP=${word%/*}
            break
        fi
        previous=$word
    done
fi
validate_ipv4 "$AUX_IP" || { echo "ERROR: invalid auxiliary-board IPv4 address" >&2; exit 2; }

ENV_FILE=/data/gemini335/gemini335.env
{
    printf 'GEMINI_ROS_MASTER_URI=http://%s:11311\n' "$CAR_IP"
    printf 'GEMINI_ROS_IP=%s\n' "$AUX_IP"
    printf 'GEMINI_START_LOCAL_ROSCORE=0\n'
} > "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "configured ROS master on car: http://$CAR_IP:11311"
echo "auxiliary board ROS_IP: $AUX_IP"
echo "restart with: /data/gemini335/start-gemini335.sh"
