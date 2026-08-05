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
from sensor_msgs.msg import CameraInfo, Image

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
  <a href="/locate">机器人定位 →</a>
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


LOCATE_PAGE = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>Gemini 335 机器人定位</title>
<style>
  body { margin: 0; background: #111; color: #eee; font-family: sans-serif; }
  header { padding: 10px 16px; display: flex; gap: 16px; align-items: baseline; flex-wrap: wrap; }
  h1 { font-size: 18px; margin: 0; }
  a, button { color: #6ab0ff; font-size: 13px; background: #222; border: 1px solid #444;
              padding: 4px 10px; cursor: pointer; text-decoration: none; }
  #status { font-size: 13px; color: #aaa; }
  .ok { color: #4caf50; } .bad { color: #f44336; } .warn { color: #ff9800; }
  main { padding: 0 16px 16px; }
  img { width: 640px; max-width: 94vw; background: #000; display: block; }
</style>
</head>
<body>
<header>
  <h1>机器人场地定位</h1>
  <span id="status">connecting&hellip;</span>
  <a href="/">← 返回双流监视</a>
  <button onclick="recal()">重新标定地面</button>
</header>
<main>
  <img src="/locate.mjpeg" alt="localization stream">
</main>
<script>
async function poll() {
  try {
    const h = await (await fetch('/locate/status')).json();
    const el = document.getElementById('status');
    if (!h.plane.fitted) {
      el.innerHTML = '<span class="warn">地面平面: ' +
        (h.plane.fitting ? '标定中…' : '未标定') + '</span>';
    } else if (h.robot) {
      const box = h.robot.box
        ? ` | box px (${h.robot.box.x},${h.robot.box.y}) ${h.robot.box.w}x${h.robot.box.h}` : '';
      el.innerHTML = '<span class="ok">robot: x=' + h.robot.x.toFixed(0) +
        'mm y=' + h.robot.y.toFixed(0) + 'mm' + box + ' | 相机高 ' +
        h.plane.camera_height_mm.toFixed(0) + 'mm | ' +
        h.fps.toFixed(1) + ' fps</span>';
    } else {
      el.innerHTML = '<span class="bad">未检测到机器人 | ' +
        h.fps.toFixed(1) + ' fps</span>';
    }
  } catch (e) {
    document.getElementById('status').textContent = 'status failed';
  }
}
async function recal() {
  document.getElementById('status').textContent = '标定中…';
  await fetch('/locate/recalibrate', {method: 'POST'});
  setTimeout(poll, 1000);
}
poll(); setInterval(poll, 2000);
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

# ---------------- robot localization (/locate) ----------------
# Method mirrors depth-filter/07_robot_localization.py: RANSAC floor plane
# from a live depth window, largest dark blob on the floor ROI in the COLOR
# image (the robot is a weak structured-light target), footprint = blob
# base band ray x floor plane.

INTRINSICS = {"fx": 463.75286865234375, "fy": 464.0082092285156,
              "cx": 322.9681091308594, "cy": 243.6584014892578}
DEPTH_BUF = deque(maxlen=40)          # raw uint16 frames for plane fitting
PLANE = {"n": None, "d": None, "roi": None, "x_f": None, "y_f": None,
         "origin": None, "inlier": None, "fitting": False,
         "fitted_at": None, "error": None}
LOC = {"x": None, "y": None, "area": None, "t": 0.0, "box": None}
DARK_MAX = float(os.environ.get("LOC_DARK_MAX", "110"))
LOC_AREA = (int(os.environ.get("LOC_AREA_MIN", "1500")),
            int(os.environ.get("LOC_AREA_MAX", "30000")))


def _fit_plane_ransac(pts, iterations=400, thresh_mm=60.0, seed=7):
    rng = np.random.default_rng(seed)
    best, best_count = None, 0
    for _ in range(iterations):
        s = pts[rng.choice(len(pts), 3, replace=False)]
        n = np.cross(s[1] - s[0], s[2] - s[0])
        norm = np.linalg.norm(n)
        if norm < 1e-6:
            continue
        n /= norm
        if n[2] > 0:
            n = -n
        inl = np.abs(pts @ n - (s[0] @ n)) < thresh_mm
        if inl.sum() > best_count:
            best_count, best = inl.sum(), inl
    mask = best
    for _ in range(2):
        sel = pts[mask]
        A = np.stack([sel[:, 0], sel[:, 1], np.ones(len(sel))], axis=1)
        a, b, c = np.linalg.lstsq(A, sel[:, 2], rcond=None)[0]
        n = np.array([a, b, -1.0])
        n /= np.linalg.norm(n)
        d = c / np.linalg.norm([a, b, -1.0])
        if d > 0:
            n, d = -n, -d
        mask = np.abs(pts @ n + d) < thresh_mm
    return n, d, mask


def plane_fit_worker():
    PLANE["fitting"] = True
    PLANE["error"] = None
    try:
        frames = list(DEPTH_BUF)
        if len(frames) < 20:
            raise RuntimeError("not enough depth frames (%d)" % len(frames))
        seq = np.stack(frames)
        h, w = seq.shape[1:]
        fx, fy = INTRINSICS["fx"], INTRINSICS["fy"]
        cx, cy = INTRINSICS["cx"], INTRINSICS["cy"]
        u, v = np.meshgrid(np.arange(w, dtype=np.float32),
                           np.arange(h, dtype=np.float32))
        dx, dy = (u - cx) / fx, (v - cy) / fy
        zmed = np.median(seq, axis=0)
        valid = (zmed > 0) & (np.indices((h, w))[0] % 4 == 0) \
                & (np.indices((h, w))[1] % 4 == 0)
        pts = np.stack([dx[valid] * zmed[valid], dy[valid] * zmed[valid],
                        zmed[valid]], axis=1)
        n, d, mask = _fit_plane_ransac(pts)
        inl_full = (np.abs((np.stack([dx * zmed, dy * zmed, zmed],
                                     axis=-1) @ n) + d) < 60.0) & (zmed > 0)
        roi = cv2.dilate(inl_full.astype(np.uint8),
                         np.ones((25, 25), np.uint8)).astype(bool)
        origin = -d * n
        x_f = np.array([1.0, 0, 0]) - n[0] * n
        x_f /= np.linalg.norm(x_f)
        # cached low-res maps for the per-frame locate step (perf):
        # plane ROI and residual coefficient at 1/DS resolution
        hs, ws = h // DS, w // DS
        us, vs = np.meshgrid(np.arange(ws, dtype=np.float32) * DS,
                             np.arange(hs, dtype=np.float32) * DS)
        coef_small = (n[0] * ((us - cx) / fx)
                      + n[1] * ((vs - cy) / fy) + n[2]).astype(np.float32)
        roi_small = cv2.resize(roi.astype(np.uint8), (ws, hs),
                               interpolation=cv2.INTER_NEAREST).astype(bool)
        PLANE.update({"n": n, "d": d, "roi": roi, "x_f": x_f,
                      "y_f": np.cross(n, x_f), "origin": origin,
                      "inlier": float(mask.mean()),
                      "fitted_at": time.time(),
                      "coef_small": coef_small, "roi_small": roi_small})
    except Exception as exc:  # noqa: BLE001
        PLANE["error"] = str(exc)
    finally:
        PLANE["fitting"] = False


def plane_fit_async():
    if not PLANE["fitting"]:
        threading.Thread(target=plane_fit_worker, daemon=True).start()


def _locate_debug():
    """Cluster-level breakdown for the latest color frame."""
    hub = HUBS.get("color")
    if hub is None or hub.jpeg is None or PLANE["n"] is None:
        return {"error": "no frame or no plane"}
    img = cv2.imdecode(np.frombuffer(hub.jpeg, np.uint8), cv2.IMREAD_COLOR)
    res = _locate_step(img)
    clusters = []
    for c in sorted(res["clusters"], key=lambda c: -c["tot_area"]):
        clusters.append({
            "kind": "cone" if c["mean_blue"] > CONE_BLUE_FRAC else "robot?",
            "count": c["count"], "tot_area": c["tot_area"],
            "mean_blue": c["mean_blue"],
            "center_mm": [round(c["center"][0]), round(c["center"][1])],
            "bbox": c["latest"]["bbox"]})
    return {"plane_fitted": True, "candidates_this_frame": res["candidates"],
            "window_size": len(LOC_WINDOW), "clusters": clusters,
            "robot_center_mm": res["robot"] and
            [round(res["robot"]["center"][0]),
             round(res["robot"]["center"][1])]}


def _mat_mask(gray):
    """The white mat: dominant bright connected region, dilated a bit.
    The magenta carpet is coplanar with the mat (same floor plane) but
    counts as 'dark', so the floor-plane ROI alone merges carpet + people
    + bezel + robot into one giant blob. Restrict detection to the mat."""
    bright = (gray > 150).astype(np.uint8)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE,
                              np.ones((25, 25), np.uint8))
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN,
                              np.ones((10, 10), np.uint8))
    nlab, labels, stats, _ = cv2.connectedComponentsWithStats(bright, 8)
    if nlab <= 1:
        return np.zeros(gray.shape, bool)
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    mat = (labels == biggest).astype(np.uint8)
    return cv2.dilate(mat, np.ones((15, 15), np.uint8)).astype(bool)


def dbscan(points, eps, min_samples):
    """Pure-numpy DBSCAN for small point sets (<=~800). Returns int labels
    (-1 = noise). eps in same units as points, min_samples includes self."""
    n = len(points)
    labels = np.full(n, -1, np.int32)
    if n == 0:
        return labels
    d2 = ((points[:, None, :] - points[None, :, :]) ** 2).sum(-1)
    adj = d2 <= eps * eps
    core = adj.sum(1) >= min_samples
    visited = np.zeros(n, bool)
    cid = 0
    for i in range(n):
        if visited[i] or not core[i]:
            continue
        labels[i] = cid
        visited[i] = True
        stack = [i]
        while stack:
            p = stack.pop()
            if not core[p]:
                continue
            for q in np.nonzero(adj[p])[0]:
                if not visited[q]:
                    visited[q] = True
                    labels[q] = cid
                    if core[q]:
                        stack.append(q)
        cid += 1
    return labels


def _footprint_mm(blob, img_shape):
    """Base-band of blob -> ray x floor plane -> field (x, y) mm."""
    h, w = img_shape
    ys, xs = np.nonzero(blob)
    base = ys >= np.percentile(ys, 95)
    bx, by = float(xs[base].mean()), float(ys[base].mean())
    fx, fy = INTRINSICS["fx"], INTRINSICS["fy"]
    cx, cy = INTRINSICS["cx"], INTRINSICS["cy"]
    n, d = PLANE["n"], PLANE["d"]
    dirv = np.array([(bx - cx) / fx, (by - cy) / fy, 1.0])
    p = (-d / float(n @ dirv)) * dirv
    return float((p - PLANE["origin"]) @ PLANE["x_f"]), \
        float((p - PLANE["origin"]) @ PLANE["y_f"]), bx, by


DS = 4                 # downsample factor for pixel-level clustering
PX_EPS = 14.0          # pixel DBSCAN eps, in downsampled cells (=56px)
PX_MIN = 6             # pixel DBSCAN min_samples (density gate vs bridges)
T_EPS = 150.0          # temporal DBSCAN eps, mm on the floor plane
T_MIN = 4              # temporal DBSCAN min_samples (persistence, frames)
T_WINDOW_S = 4.0       # candidate memory window, seconds
CONE_BLUE_FRAC = 0.4   # cluster blue-pixel fraction above which = cone
LOC_WINDOW = []        # recent candidates (dicts), pruned by time


def _locate_step(img):
    """One localization step: dark cells -> pixel DBSCAN -> candidates ->
    temporal DBSCAN -> {cones, robot, candidates, clusters}.
    (Restored to the pre-"cone drift" pipeline: per-pixel blue gating,
    no boundary/elevation/person filters.)"""
    h, w = img.shape[:2]
    gray = img.mean(axis=2)
    # ROI = floor-plane inliers MINUS the magenta carpet (chromatic, not
    # brightness-based: brightness fails when the mat is in shadow)
    pix16 = img.astype(np.int16)
    magenta = (pix16[:, :, 2] - pix16[:, :, 1] > 40) \
        & (pix16[:, :, 0] - pix16[:, :, 1] > 20)
    mat = PLANE["roi"] & ~magenta
    blue_dom = pix16[:, :, 0] - 0.5 * (pix16[:, :, 1] + pix16[:, :, 2])

    # ---- pixel level: dark NEUTRAL cells clustered by density ----
    # Blue-dominant pixels (cone bases) are excluded per-PIXEL up front, so
    # a cone standing next to the robot can never bridge into its cluster.
    dark = ((gray < DARK_MAX) & (blue_dom < 25.0) & mat).astype(np.uint8)
    small = cv2.resize(dark, (w // DS, h // DS),
                       interpolation=cv2.INTER_NEAREST)
    blue_small = cv2.resize(blue_dom.astype(np.float32), (w // DS, h // DS),
                            interpolation=cv2.INTER_NEAREST)
    ys, xs = np.nonzero(small)
    if len(ys) > 1200:  # cap DBSCAN input for O(n^2) cost
        sel = np.random.default_rng(0).choice(len(ys), 1200, replace=False)
        ys, xs = ys[sel], xs[sel]
    pts = np.stack([xs, ys], axis=1).astype(np.float32)
    lab = dbscan(pts, PX_EPS, PX_MIN)
    lab_img = np.full(small.shape, -1, np.int32)
    lab_img[ys, xs] = lab

    now = time.time()
    cands = []
    for cid in range(lab.max() + 1):
        cells = lab_img == cid
        area = int(cells.sum()) * DS * DS
        if not (600 <= area <= LOC_AREA[1]):
            continue
        ys_c, xs_c = np.nonzero(cells)
        x0, x1 = int(xs_c.min()) * DS, (int(xs_c.max()) + 1) * DS
        y0, y1 = int(ys_c.min()) * DS, (int(ys_c.max()) + 1) * DS
        if x0 <= 2 or y0 <= 2 or x1 >= w - 2:
            continue
        if y1 >= h - 2 and (x1 - x0) > 0.6 * w:
            continue
        blue_frac = float((blue_small[cells] > 25.0).mean())
        # footprint from the low-res base band, scaled back to full-res px
        cut = np.percentile(ys_c, 95)
        base = ys_c >= cut
        bx, by = float(xs_c[base].mean()) * DS, float(ys_c[base].mean()) * DS
        fx, fy = INTRINSICS["fx"], INTRINSICS["fy"]
        cx, cy = INTRINSICS["cx"], INTRINSICS["cy"]
        n, d = PLANE["n"], PLANE["d"]
        dirv = np.array([(bx - cx) / fx, (by - cy) / fy, 1.0])
        p = (-d / float(n @ dirv)) * dirv
        fx_mm = float((p - PLANE["origin"]) @ PLANE["x_f"])
        fy_mm = float((p - PLANE["origin"]) @ PLANE["y_f"])
        cands.append({"t": now, "xy": (fx_mm, fy_mm), "area": area,
                      "blue_frac": blue_frac, "bbox": (x0, y0, x1, y1),
                      "base": (bx, by), "src": "dark"})

    # ---- cones: saturated-blue blobs (their own candidates) ----
    blue = ((blue_dom > 30.0) & mat).astype(np.uint8)
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    nc, clabels, cstats, _ = cv2.connectedComponentsWithStats(blue, 8)
    for i in range(1, nc):
        area = int(cstats[i, cv2.CC_STAT_AREA])
        if area < 150:
            continue
        cblob = clabels == i
        fx_mm, fy_mm, bx, by = _footprint_mm(cblob, (h, w))
        cands.append({"t": now, "xy": (fx_mm, fy_mm), "area": area * 4,
                      "blue_frac": 1.0,
                      "bbox": (int(cstats[i, cv2.CC_STAT_LEFT]),
                               int(cstats[i, cv2.CC_STAT_TOP]),
                               int(cstats[i, cv2.CC_STAT_LEFT])
                               + int(cstats[i, cv2.CC_STAT_WIDTH]),
                               int(cstats[i, cv2.CC_STAT_TOP])
                               + int(cstats[i, cv2.CC_STAT_HEIGHT])),
                      "base": (bx, by), "src": "cone"})
    LOC_WINDOW.extend(cands)
    cutoff = now - T_WINDOW_S
    LOC_WINDOW[:] = [c for c in LOC_WINDOW if c["t"] >= cutoff]

    # ---- temporal level: persistent clusters of candidate positions ----
    result = {"candidates": len(cands), "clusters": [], "cones": [],
              "robot": None}
    if len(LOC_WINDOW) < T_MIN:
        return result
    pxy = np.array([c["xy"] for c in LOC_WINDOW])
    tlab = dbscan(pxy, T_EPS, T_MIN)
    for cid in range(tlab.max() + 1):
        members = [c for c, l in zip(LOC_WINDOW, tlab) if l == cid]
        tot_area = sum(c["area"] for c in members)
        mean_blue = sum(c["blue_frac"] for c in members) / len(members)
        cx_mm = sum(c["xy"][0] * c["area"] for c in members) / tot_area
        cy_mm = sum(c["xy"][1] * c["area"] for c in members) / tot_area
        latest = max(members, key=lambda c: c["t"])
        info = {"count": len(members), "tot_area": tot_area,
                "mean_blue": round(mean_blue, 3),
                "center": (cx_mm, cy_mm), "latest": latest}
        result["clusters"].append(info)
        if mean_blue > CONE_BLUE_FRAC:
            result["cones"].append(info)
    robots = [c for c in result["clusters"]
              if c["mean_blue"] <= CONE_BLUE_FRAC
              and abs(c["center"][0]) < 2500
              and -3500 < c["center"][1] < 1000]
    if robots:
        result["robot"] = max(robots, key=lambda c: c["tot_area"])
    return result


def locate_overlay(img):
    """Draw robot detection on a color frame; returns annotated frame."""
    out = img.copy()
    if PLANE["fitting"]:
        cv2.putText(out, "calibrating floor plane...",
                    (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 255, 255), 2)
        return out
    if PLANE["n"] is None:
        cv2.putText(out, "floor plane not calibrated",
                    (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 165, 255), 2)
        return out
    res = _locate_step(out)
    h, w = out.shape[:2]
    for cone in res["cones"]:
        bx, by = cone["latest"]["base"]
        cv2.drawMarker(out, (int(bx), int(by)), (255, 128, 0),
                       cv2.MARKER_DIAMOND, 14, 2)
    robot = res["robot"]
    if robot is None:
        # anti-flicker grace: keep showing the last known position for 3s
        # instead of flashing "not detected" on single-frame dropouts
        if LOC["x"] is not None and time.time() - LOC["t"] < 3.0:
            b = LOC["box"]
            cv2.rectangle(out, (b["x"], b["y"]),
                          (b["x"] + b["w"], b["y"] + b["h"]),
                          (0, 200, 200), 1)
            cv2.putText(out, f"last x={LOC['x']:.0f} y={LOC['y']:.0f} mm",
                        (b["x"], max(20, b["y"] - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 200), 1)
        else:
            cv2.putText(out, "robot not detected", (12, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        return out
    xmm, ymm = robot["center"]
    latest = robot["latest"]
    x0, y0, x1, y1 = latest["bbox"]
    LOC["x"], LOC["y"] = xmm, ymm
    LOC["area"], LOC["t"] = robot["tot_area"], time.time()
    LOC["box"] = {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
    bx, by = latest["base"]
    cv2.rectangle(out, (x0, y0), (x1, y1), (0, 255, 0), 2)
    cv2.drawMarker(out, (int(bx), int(by)), (0, 0, 255),
                   cv2.MARKER_CROSS, 16, 2)
    cv2.putText(out, f"robot x={xmm:.0f} y={ymm:.0f} mm",
                (x0, max(20, y0 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (0, 255, 0), 2)
    cv2.putText(out, f"box px ({x0},{y0}) {x1 - x0}x{y1 - y0}",
                (x0, min(h - 8, y1 + 18)), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (0, 255, 0), 1)
    return out


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
    # locate step is the heaviest consumer; run it capped at LOC_STEP_HZ
    now = time.monotonic()
    if now - on_color._loc_last < 1.0 / LOC_STEP_HZ:
        return
    on_color._loc_last = now
    locate_jpeg = _encode(locate_overlay(image))
    if locate_jpeg:
        HUBS["locate"].offer(locate_jpeg)


on_color._loc_last = 0.0
LOC_STEP_HZ = float(os.environ.get("LOC_STEP_HZ", "5"))


def on_depth(message):
    hub = HUBS["depth"]
    if _rate_limited(hub):
        return
    depth = BRIDGE.imgmsg_to_cv2(message, desired_encoding="passthrough")
    depth = np.asarray(depth)
    if depth.dtype != np.uint16:
        depth = depth.astype(np.uint16)
    DEPTH_BUF.append(depth)
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
        elif path == "/locate":
            self._send_bytes(LOCATE_PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/locate.mjpeg":
            self._stream(HUBS["locate"])
        elif path == "/locate/debugimg":
            hub = HUBS.get("color")
            if hub is None or hub.jpeg is None or PLANE["n"] is None:
                self.send_error(503, "no frame or no plane")
                return
            img = cv2.imdecode(np.frombuffer(hub.jpeg, np.uint8),
                               cv2.IMREAD_COLOR)
            h, w = img.shape[:2]
            gray = img.mean(axis=2)
            pix16 = img.astype(np.int16)
            magenta = (pix16[:, :, 2] - pix16[:, :, 1] > 40) \
                & (pix16[:, :, 0] - pix16[:, :, 1] > 20)
            mat = PLANE["roi"] & ~magenta
            blue_dom = pix16[:, :, 0] - 0.5 * (pix16[:, :, 1] + pix16[:, :, 2])
            dark = ((gray < DARK_MAX) & (blue_dom < 25.0) & mat)
            vis = (img * 0.4).astype(np.uint8)
            vis[mat] = (vis[mat] * 0.5 + np.array([0, 127, 0])).astype(np.uint8)
            vis[dark] = (0, 0, 255)
            ok, jpg = cv2.imencode(".jpg", vis)
            self._send_bytes(jpg.tobytes(), "image/jpeg")
        elif path == "/locate/debug":
            self._send_bytes(json.dumps(_locate_debug()).encode(),
                             "application/json")
        elif path == "/locate/status":
            robot = None
            if LOC["x"] is not None and time.time() - LOC["t"] < 2.0:
                robot = {"x": LOC["x"], "y": LOC["y"], "area": LOC["area"],
                         "box": LOC.get("box")}
            payload = {
                "plane": {
                    "fitted": PLANE["n"] is not None,
                    "fitting": PLANE["fitting"],
                    "error": PLANE["error"],
                    "inlier": PLANE["inlier"],
                    "camera_height_mm": abs(PLANE["d"]) if PLANE["d"] else None,
                },
                "robot": robot,
                "fps": HUBS["locate"].health()["fps"],
            }
            self._send_bytes(json.dumps(payload).encode(),
                             "application/json")
        elif path == "/health":
            payload = {
                "color": HUBS["color"].health(),
                "depth": HUBS["depth"].health(),
                "depth_raw": HUBS["depth_raw"].health(),
                "locate": HUBS["locate"].health(),
                "filter": {"active": True, "last_ms": FILTER.last_ms,
                           "params": FILTER.params()},
                "topics": {"color": COLOR_TOPIC, "depth": DEPTH_TOPIC},
            }
            self._send_bytes(json.dumps(payload).encode(), "application/json")
        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/locate/recalibrate":
            plane_fit_async()
            self._send_bytes(b'{"ok": true}', "application/json")
        else:
            self.send_error(404)


def fetch_intrinsics():
    try:
        msg = rospy.wait_for_message("/aux_camera/depth/camera_info",
                                     CameraInfo, timeout=15.0)
        INTRINSICS.update({"fx": msg.K[0], "fy": msg.K[4],
                           "cx": msg.K[2], "cy": msg.K[5]})
        rospy.loginfo("intrinsics from camera_info: %s", INTRINSICS)
    except rospy.ROSException:
        rospy.logwarn("camera_info unavailable, using stored intrinsics")


def main():
    HUBS["color"] = StreamHub("color")
    HUBS["depth"] = StreamHub("depth")
    HUBS["depth_raw"] = StreamHub("depth_raw")
    HUBS["locate"] = StreamHub("locate")
    rospy.init_node("gemini335_web_stream", anonymous=False, disable_signals=True)
    rospy.Subscriber(COLOR_TOPIC, Image, on_color, queue_size=1,
                     buff_size=4 * 1024 * 1024)
    rospy.Subscriber(DEPTH_TOPIC, Image, on_depth, queue_size=1,
                     buff_size=4 * 1024 * 1024)
    fetch_intrinsics()
    threading.Timer(5.0, plane_fit_async).start()  # auto-calibrate once
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    rospy.loginfo("gemini335_web_stream listening on port %d", PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
