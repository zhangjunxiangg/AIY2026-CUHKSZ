#!/bin/sh
# Stop the web streamer only; the camera container keeps running.
# To stop the camera stack too: sh /data/gemini335/stop-gemini335.sh
set -eu

CONTAINER=rk3588s-gemini335
docker exec "$CONTAINER" pkill -f gemini_web_stream.py 2>/dev/null \
    && echo "web_stream=STOPPED" \
    || echo "web_stream=NOT_RUNNING"
