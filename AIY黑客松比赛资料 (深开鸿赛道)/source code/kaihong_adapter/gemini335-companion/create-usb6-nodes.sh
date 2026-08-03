#!/bin/bash
set -eu

mkdir -p /dev/bus/usb/006

i=1
while [ "$i" -le 127 ]; do
    path=$(printf '/dev/bus/usb/006/%03d' "$i")
    minor=$((639 + i))
    if [ ! -e "$path" ]; then
        mknod "$path" c 189 "$minor"
        chmod 660 "$path"
    fi
    i=$((i + 1))
done
