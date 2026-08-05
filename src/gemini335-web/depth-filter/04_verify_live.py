#!/usr/bin/env python3
"""04_verify_live: verify the deployed filtered stream through the real
browser path (PC -> hdc fport -> board), and record a live video dump.

Records both depth MJPEG endpoints concurrently (exactly what the browser
renders), builds a side-by-side comparison video, and gates:
  - /health: color & depth fps >= 5, frame age < 3s, filter active
  - recorded >= 30 frames per stream
  - live_compare.mp4 artifact written
Usage: python 04_verify_live.py <out_root> [base_url] [seconds]
"""

import json
import os
import sys
import threading
import time
import urllib.request

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from util_gate import Step

BASE_URL = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8080"
SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 8.0


def record_mjpeg(url, seconds, frames, errors):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            buf = b""
            t_end = time.monotonic() + seconds
            while time.monotonic() < t_end:
                chunk = r.read(65536)
                if not chunk:
                    break
                buf += chunk
                while True:
                    i = buf.find(b"\xff\xd8")
                    j = buf.find(b"\xff\xd9", i + 2) if i >= 0 else -1
                    if i >= 0 and j > 0:
                        img = cv2.imdecode(
                            np.frombuffer(buf[i:j + 2], np.uint8),
                            cv2.IMREAD_COLOR)
                        if img is not None:
                            frames.append(img)
                        buf = buf[j + 2:]
                    else:
                        if i > 0:
                            buf = buf[i:]
                        break
    except Exception as exc:  # noqa: BLE001 - record and gate on frame count
        errors.append(str(exc))


def main(out_root):
    step = Step(out_root, "04_verify_live")
    os.makedirs(out_root, exist_ok=True)

    with urllib.request.urlopen(BASE_URL + "/health", timeout=10) as r:
        health = json.load(r)
    step.log(f"health: {json.dumps(health)}")

    step.gate(health["color"]["fps"] >= 5.0, "color fps >= 5",
              round(health["color"]["fps"], 2), ">=5")
    step.gate(health["depth"]["fps"] >= 5.0, "depth fps >= 5",
              round(health["depth"]["fps"], 2), ">=5")
    step.gate(0 <= health["depth"]["age_s"] < 3.0, "depth age < 3s",
              round(health["depth"]["age_s"], 2), "<3s")
    step.gate(health.get("filter", {}).get("active") is True,
              "filter active", health.get("filter", {}).get("active"), "True")

    raw_frames, flt_frames, errors = [], [], []
    t0 = time.monotonic()
    threads = [
        threading.Thread(target=record_mjpeg,
                         args=(BASE_URL + "/depth.mjpeg", SECONDS,
                               flt_frames, errors)),
        threading.Thread(target=record_mjpeg,
                         args=(BASE_URL + "/depth_raw.mjpeg", SECONDS,
                               raw_frames, errors)),
    ]
    with step.timeit("record"):
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    elapsed = time.monotonic() - t0
    step.log(f"recorded filtered={len(flt_frames)} raw={len(raw_frames)} "
             f"in {elapsed:.1f}s errors={errors}")

    step.gate(len(flt_frames) >= 30, "filtered frames >= 30",
              len(flt_frames), ">=30")
    step.gate(len(raw_frames) >= 30, "raw frames >= 30",
              len(raw_frames), ">=30")

    n = min(len(flt_frames), len(raw_frames))
    h, w = flt_frames[0].shape[:2]
    fps = n / max(elapsed, 0.1)
    font = cv2.FONT_HERSHEY_SIMPLEX
    with step.timeit("write_video"):
        vw = cv2.VideoWriter(os.path.join(out_root, "live_compare.mp4"),
                             cv2.VideoWriter_fourcc(*"mp4v"), fps, (w * 2, h))
        for i in range(n):
            left = raw_frames[i].copy()
            right = flt_frames[i].copy()
            cv2.putText(left, "raw (live)", (8, 24), font, 0.7,
                        (255, 255, 255), 2)
            cv2.putText(right, "filtered (live)", (8, 24), font, 0.7,
                        (255, 255, 255), 2)
            vw.write(np.hstack([left, right]))
        vw.release()

    path = os.path.join(out_root, "live_compare.mp4")
    ok = os.path.exists(path) and os.path.getsize(path) > 10000
    step.gate(ok, "artifact live_compare.mp4 exists",
              os.path.getsize(path) if os.path.exists(path) else 0, ">10KB")

    with open(os.path.join(out_root, "live_health.json"), "w") as fh:
        json.dump({"health": health, "recorded_fps": fps,
                   "frames": {"filtered": len(flt_frames), "raw": len(raw_frames)},
                   "seconds": elapsed}, fh, indent=2)

    step.finish("PASS")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "live")
