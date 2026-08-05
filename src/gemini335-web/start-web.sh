#!/bin/sh
# Start the Gemini 335 camera stack (standalone mode) plus the web streamer.
# The camera container's entrypoint deploys and supervises the web streamer,
# so after this script the pair survives container restarts.
# Safe to re-run: it recreates the camera container from scratch.
set -eu

CAMBASE=/data/gemini335
CONTAINER=rk3588s-gemini335
PORT="${GEMINI_WEB_PORT:-8080}"

# 1. Camera stack + web streamer (deployed into the container by
#    start-gemini335.sh, started and supervised by its entrypoint).
#    start-gemini335.sh self-checks for a real depth frame first.
sh "$CAMBASE/start-gemini335.sh"

# 2. Verify the streamer answers and frames are flowing (retry while ROS
#    topics settle).
tries=0
until [ "$tries" -ge 6 ]; do
    if docker exec "$CONTAINER" python3 - "$PORT" <<'EOF'
import json, sys, urllib.request
port = sys.argv[1]
with urllib.request.urlopen("http://127.0.0.1:%s/health" % port, timeout=5) as r:
    h = json.load(r)
print("web_health=" + json.dumps(h))
if h["color"]["frames"] == 0 or h["depth"]["frames"] == 0:
    sys.exit(1)
EOF
    then
        echo "web_stream=UP port=$PORT"
        echo "view on PC: ssh -L $PORT:127.0.0.1:$PORT root@<board-ip> -p 2223  ->  http://localhost:$PORT"
        echo "(USB fallback: hdc fport tcp:$PORT tcp:$PORT)"
        exit 0
    fi
    tries=$((tries + 1))
    sleep 3
done
echo "ERROR: web streamer did not come up; see /tmp/gemini-web.log in container" >&2
exit 1
