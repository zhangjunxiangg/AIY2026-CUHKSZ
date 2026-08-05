#!/bin/bash
# Create /dev/bus/usb nodes inside the container for every USB device the
# host kernel currently sees, on ANY bus. The original create-usb6-nodes.sh
# only covered bus 006; the camera may enumerate on a different bus depending
# on which physical port it is plugged into.
set -eu

for dev in /sys/bus/usb/devices/*; do
    [ -f "$dev/busnum" ] || continue
    bus=$(cat "$dev/busnum")
    num=$(cat "$dev/devnum")
    dir=$(printf '/dev/bus/usb/%03d' "$bus")
    path=$(printf '%s/%03d' "$dir" "$num")
    mkdir -p "$dir"
    if [ ! -e "$path" ]; then
        mknod "$path" c 189 $(( (bus - 1) * 128 + num - 1 ))
        chmod 660 "$path"
    fi
done
