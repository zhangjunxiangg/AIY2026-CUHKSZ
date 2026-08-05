#!/usr/bin/env python3
"""Gemini 335 web streamer.

Runs inside the rk3588s-gemini335 container. Subscribes to the ROS1 topics
published by the orbbec_camera driver and re-serves them as MJPEG streams
that any browser renders with plain <img> tags. No extra dependencies:
rospy / cv_bridge / cv2 / numpy are all present in the driver image.

The depth stream is filtered (speckle removal + masked median + temporal
EMA with anti-ghosting: spatially coherent motion snaps in one frame) — the
filter class is kept in sync with depth-filter/util_filter.py, which is the
source of truth with offline metric validation (see depth-filter/MANIFEST.md
and run2/metrics_ghost.json). The raw depth stream is still available
side-by-side at /raw for comparison. Raw ROS topics are never modified.

Routes:
    /                    HTML page: color + FILTERED depth
    /raw                 HTML page: color + RAW depth (unfiltered)
    /color.mjpeg         color video stream (MJPEG)
    /depth.mjpeg         filtered depth stream, TURBO colormap (MJPEG)
    /depth_raw.mjpeg     raw depth stream, TURBO colormap (MJPEG)
    /snapshot/color.jpg        latest color frame, single JPEG
    /snapshot/depth.jpg        latest filtered depth frame, single JPEG
    /snapshot/depth_raw.jpg    latest raw depth frame, single JPEG
    /health              JSON: per-stream counters/fps/age + filter stats

Config via environment:
    GEMINI_WEB_PORT       listen port           (default 8080)
    GEMINI_WEB_MAX_FPS    encode rate cap       (default 10)
    GEMINI_JPEG_QUALITY   JPEG quality          (default 80)
    GEMINI_DEPTH_MAX_MM   depth colormap range  (default 5000, mm)
    DF_ALPHA / DF_GATE_MM / DF_HOLD_FRAMES / DF_SNAP_FRAMES / DF_MEDIAN_KSIZE
                          depth filter parameters (see DepthFilter)
"""

import json
import os
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image

COLOR_TOPIC = os.environ.get("GEMINI_COLOR_TOPIC", "/aux_camera/color/image_raw")
DEPTH_TOPIC = os.environ.get("GEMINI_DEPTH_TOPIC", "/aux_camera/depth/image_raw")
PORT = int(os.environ.get("GEMINI_WEB_PORT", "8080"))
MAX_FPS = float(os.environ.get("GEMINI_WEB_MAX_FPS", "10"))
QUALITY = int(os.environ.get("GEMINI_JPEG_QUALITY", "80"))
DEPTH_MAX_MM = float(os.environ.get("GEMINI_DEPTH_MAX_MM", "5000"))
BOUNDARY = b"geminiframe"


class DepthFilterV2:
    """V2: speckle removal + masked median + temporal EMA, with anti-ghosting.
    Spatially coherent depth changes (real motion) snap within one frame via
    a 15x15 density test; isolated disagreements keep 3-frame hysteresis;
    invalid hold shortened to 3 frames so departed objects fade fast.
    Keep in sync with depth-filter/util_filter.py (source of truth)."""

    def __init__(self,
                 alpha=float(os.environ.get("DF_ALPHA", "0.15")),
                 gate_mm=float(os.environ.get("DF_GATE_MM", "250")),
                 hold_frames=int(os.environ.get("DF_HOLD_FRAMES", "3")),
                 snap_frames=int(os.environ.get("DF_SNAP_FRAMES", "3")),
                 median_ksize=int(os.environ.get("DF_MEDIAN_KSIZE", "5")),
                 snap_density=float(os.environ.get("DF_SNAP_DENSITY", "0.20")),
                 box_ksize=int(os.environ.get("DF_BOX_KSIZE", "15"))):
        self.alpha = alpha
        self.gate_mm = gate_mm
        self.hold_frames = hold_frames
        self.snap_frames = snap_frames
        self.median_ksize = median_ksize
        self.snap_density = snap_density
        self.box_ksize = box_ksize
        self._kernel = np.ones((3, 3), np.uint8)
        self.acc = None
        self.hold = None
        self.oog_count = None
        self.last_ms = 0.0

    def process(self, depth):
        t0 = time.perf_counter()
        opened = cv2.morphologyEx((depth > 0).astype(np.uint8),
                                  cv2.MORPH_OPEN, self._kernel)
        x = depth * opened
        big = np.where(x > 0, x, 65535).astype(np.uint16)
        med = cv2.medianBlur(big, self.median_ksize)
        x = np.where(med >= 60000, 0, med).astype(np.uint16)
        valid = x > 0
        xf = x.astype(np.float32)
        if self.acc is None:
            self.acc = xf.copy()
            self.hold = np.where(valid, 0, 32767).astype(np.int16)
            self.oog_count = np.zeros(x.shape, np.uint8)
            self.last_ms = (time.perf_counter() - t0) * 1000.0
            return x
        diff = cv2.absdiff(xf, self.acc)
        oog = valid & (diff >= self.gate_mm)
        fast_snap = np.zeros(oog.shape, bool)
        oog_u8 = oog.view(np.uint8)
        if cv2.countNonZero(oog_u8) >= int(
                self.snap_density * self.box_ksize * self.box_ksize):
            density = cv2.boxFilter(oog_u8 * 255, -1,
                                    (self.box_ksize, self.box_ksize),
                                    normalize=True)
            fast_snap = oog & (density >= int(self.snap_density * 255))
        self.oog_count = np.where(oog & ~fast_snap,
                                  self.oog_count + 1, 0).astype(np.uint8)
        snap = fast_snap | (self.oog_count >= self.snap_frames)
        smooth = valid & ~snap
        cv2.accumulateWeighted(xf, self.acc, self.alpha,
                               mask=smooth.astype(np.uint8))
        if snap.any():
            cv2.copyTo(xf, snap.view(np.uint8) * 255, self.acc)
            self.oog_count[snap] = 0
        np.add(self.hold, 1, out=self.hold)
        self.hold[valid] = 0
        out = np.where(valid | (self.hold <= self.hold_frames),
                       self.acc, 0.0).astype(np.uint16)
        self.last_ms = (time.perf_counter() - t0) * 1000.0
        return out

    def params(self):
        return {"alpha": self.alpha, "gate_mm": self.gate_mm,
                "hold_frames": self.hold_frames,
                "snap_frames": self.snap_frames,
                "median_ksize": self.median_ksize,
                "snap_density": self.snap_density,
                "box_ksize": self.box_ksize}


def colorize(depth, max_mm=DEPTH_MAX_MM):
    gray = np.clip(depth.astype(np.float32) * (255.0 / max_mm), 0, 255)
    gray = gray.astype(np.uint8)
    img = cv2.applyColorMap(255 - gray, cv2.COLORMAP_TURBO)
    img[depth == 0] = 0
    return img


PAGE = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>Gemini 335 双流监视</title>
<style>
  body { margin: 0; background: #111; color: #eee; font-family: sans-serif; }
  header { padding: 10px 16px; display: flex; gap: 16px; align-items: baseline; }
  h1 { font-size: 18px; margin: 0; }
  a { color: #6ab0ff; font-size: 13px; }
  #status { font-size: 13px; color: #aaa; }
  .ok { color: #4caf50; } .bad { color: #f44336; }
  main { display: flex; flex-wrap: wrap; gap: 8px; padding: 0 16px 16px; }
  figure { margin: 0; }
  figcaption { font-size: 13px; color: #bbb; padding: 4px 0; }
  img { width: 640px; max-width: 46vw; background: #000; display: block; }
</style>
</head>
<body>
<header>
  <h1>Gemini 335 &mdash; aux_camera</h1>
  <span id="status">connecting&hellip;</span>
  <a href="%s">%s</a>
</header>
<main>
  <figure>
    <figcaption>color /aux_camera/color/image_raw</figcaption>
    <img src="/color.mjpeg" alt="color stream">
  </figure>
  <figure>
    <figcaption>depth %s (0-%d mm, TURBO)</figcaption>
    <img src="/%s.mjpeg" alt="depth stream">
  </figure>
</main>
<script>
async function poll() {
  try {
    const h = await (await fetch('/health')).json();
    const fmt = s => s.frames === 0 ? 'no frames'
      : s.fps.toFixed(1) + ' fps, age ' + s.age_s.toFixed(1) + 's';
    const ok = h.color.age_s >= 0 && h.color.age_s < 3
            && h.depth.age_s >= 0 && h.depth.age_s < 3;
    document.getElementById('status').innerHTML =
      '<span class="' + (ok ? 'ok' : 'bad') + '">' +
      'color: ' + fmt(h.color) + ' | depth: ' + fmt(h.depth) +
      ' | filter: ' + h.filter.last_ms.toFixed(1) + 'ms</span>';
  } catch (e) {
    document.getElementById('status').textContent = 'health check failed';
  }
}
poll(); setInterval(poll, 3000);
</script>
</body>
</html>
"""


class StreamHub:
    """Latest-frame buffer shared between a ROS subscriber and HTTP clients."""

    def __init__(self, name):
        self.name = name
        self.condition = threading.Condition()
        self.jpeg = None
        self.frames = 0
        self.stamps = deque(maxlen=60)
        self.last_encode = 0.0

    def offer(self, jpeg_bytes):
        now = time.time()
        with self.condition:
            self.jpeg = jpeg_bytes
            self.frames += 1
            self.stamps.append(now)
            self.condition.notify_all()

    def wait_frame(self, last_count):
        with self.condition:
            if self.frames == last_count:
                self.condition.wait(timeout=5.0)
            return self.jpeg, self.frames

    def health(self):
        with self.condition:
            now = time.time()
            fps = 0.0
            if len(self.stamps) >= 2:
                span = self.stamps[-1] - self.stamps[0]
                if span > 0:
                    fps = (len(self.stamps) - 1) / span
            age = now - self.stamps[-1] if self.stamps else -1.0
            return {"frames": self.frames, "fps": fps, "age_s": age}


HUBS = {}
BRIDGE = CvBridge()
FILTER = DepthFilterV2()


def _rate_limited(hub):
    now = time.monotonic()
    if now - hub.last_encode < 1.0 / MAX_FPS:
        return True
    hub.last_encode = now
    return False


def _encode(img):
    ok, encoded = cv2.imencode(".jpg", img,
                               [int(cv2.IMWRITE_JPEG_QUALITY), QUALITY])
    return encoded.tobytes() if ok else None


def on_color(message):
    hub = HUBS["color"]
    if _rate_limited(hub):
        return
    image = BRIDGE.imgmsg_to_cv2(message, desired_encoding="bgr8")
    jpeg = _encode(image)
    if jpeg:
        hub.offer(jpeg)


def on_depth(message):
    hub = HUBS["depth"]
    if _rate_limited(hub):
        return
    depth = BRIDGE.imgmsg_to_cv2(message, desired_encoding="passthrough")
    depth = np.asarray(depth)
    if depth.dtype != np.uint16:
        depth = depth.astype(np.uint16)
    raw_jpeg = _encode(colorize(depth))
    if raw_jpeg:
        HUBS["depth_raw"].offer(raw_jpeg)
    filtered = FILTER.process(depth)
    jpeg = _encode(colorize(filtered))
    if jpeg:
        hub.offer(jpeg)


class Handler(BaseHTTPRequestHandler):
    server_version = "Gemini335Web/2.0"

    def log_message(self, *args):  # keep the container log quiet
        pass

    def _send_bytes(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _stream(self, hub):
        self.send_response(200)
        self.send_header("Content-Type",
                         "multipart/x-mixed-replace; boundary=" + BOUNDARY.decode())
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        last = -1
        while True:
            jpeg, count = hub.wait_frame(last)
            if jpeg is None or count == last:
                continue  # timeout tick, keep waiting for a real frame
            last = count
            try:
                self.wfile.write(b"--" + BOUNDARY + b"\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(("Content-Length: %d\r\n\r\n" % len(jpeg)).encode())
                self.wfile.write(jpeg + b"\r\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/" or path == "/raw":
            if path == "/raw":
                html = PAGE % ("/", "查看滤波后 →", "raw 未滤波",
                               int(DEPTH_MAX_MM), "depth_raw")
            else:
                html = PAGE % ("/raw", "查看未滤波对比 →", "filtered 已滤波",
                               int(DEPTH_MAX_MM), "depth")
            self._send_bytes(html.encode(), "text/html; charset=utf-8")
        elif path == "/color.mjpeg":
            self._stream(HUBS["color"])
        elif path == "/depth.mjpeg":
            self._stream(HUBS["depth"])
        elif path == "/depth_raw.mjpeg":
            self._stream(HUBS["depth_raw"])
        elif path.startswith("/snapshot/"):
            name = path.rsplit("/", 1)[-1].replace(".jpg", "")
            hub = HUBS.get(name)
            if hub is None:
                self.send_error(404)
                return
            jpeg, _ = hub.wait_frame(-1)
            if jpeg is None:
                self.send_error(503, "no frame yet")
            else:
                self._send_bytes(jpeg, "image/jpeg")
        elif path == "/health":
            payload = {
                "color": HUBS["color"].health(),
                "depth": HUBS["depth"].health(),
                "depth_raw": HUBS["depth_raw"].health(),
                "filter": {"active": True, "last_ms": FILTER.last_ms,
                           "params": FILTER.params()},
                "topics": {"color": COLOR_TOPIC, "depth": DEPTH_TOPIC},
            }
            self._send_bytes(json.dumps(payload).encode(), "application/json")
        else:
            self.send_error(404)


def main():
    HUBS["color"] = StreamHub("color")
    HUBS["depth"] = StreamHub("depth")
    HUBS["depth_raw"] = StreamHub("depth_raw")
    rospy.init_node("gemini335_web_stream", anonymous=False, disable_signals=True)
    rospy.Subscriber(COLOR_TOPIC, Image, on_color, queue_size=1,
                     buff_size=4 * 1024 * 1024)
    rospy.Subscriber(DEPTH_TOPIC, Image, on_depth, queue_size=1,
                     buff_size=4 * 1024 * 1024)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    rospy.loginfo("gemini335_web_stream listening on port %d", PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
