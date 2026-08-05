#!/bin/sh
set -u

NAME="rk3588s-vision"
if docker inspect "$NAME" >/dev/null 2>&1; then
  docker stop -t 5 "$NAME" >/dev/null 2>&1 || true
  docker rm "$NAME" >/dev/null 2>&1 || true
fi
echo "vision=STOPPED"

