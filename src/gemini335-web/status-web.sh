#!/bin/sh
# Status of the camera container and the web streamer.
CONTAINER=rk3588s-gemini335
PORT="${GEMINI_WEB_PORT:-8080}"

docker ps --filter "name=$CONTAINER" --format 'container={{.Names}} status={{.Status}}'

if docker exec "$CONTAINER" pgrep -f gemini_web_stream.py >/dev/null 2>&1; then
    echo "web_stream=RUNNING port=$PORT"
    docker exec "$CONTAINER" python3 - "$PORT" <<'EOF'
import json, sys, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:%s/health" % sys.argv[1], timeout=5) as r:
        print("web_health=" + json.dumps(json.load(r)))
except Exception as exc:
    print("web_health=ERROR %s" % exc)
EOF
else
    echo "web_stream=NOT_RUNNING"
fi
