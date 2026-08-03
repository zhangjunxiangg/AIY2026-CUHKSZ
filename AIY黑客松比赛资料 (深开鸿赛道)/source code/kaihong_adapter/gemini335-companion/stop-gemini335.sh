#!/bin/sh
set -eu

docker stop rk3588s-gemini335 >/dev/null 2>&1 || true
echo "gemini335=STOPPED"
