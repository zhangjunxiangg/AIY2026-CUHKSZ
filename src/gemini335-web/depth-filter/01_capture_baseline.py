#!/usr/bin/env python3
"""01_capture_baseline: dump raw depth sequence + videos from the live camera.

Runs inside the rk3588s-gemini335 container. Records TARGET_FRAMES raw depth
frames (16UC1 mm) plus the color stream, and writes:
  out/depth_seq.npy      (T,H,W) uint16 raw depth sequence
  out/raw_depth.mp4      colorized raw depth video (as seen on the webpage)
  out/color.mp4          color video for context
  out/meta.json
Gates: >= MIN_FRAMES frames, mean valid ratio >= 0.05.
Usage: 01_capture_baseline.py <out_root>
"""

import json
import os
import sys
import time

import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from util_gate import Step
from util_filter import colorize

COLOR_TOPIC = os.environ.get("GEMINI_COLOR_TOPIC", "/aux_camera/color/image_raw")
DEPTH_TOPIC = os.environ.get("GEMINI_DEPTH_TOPIC", "/aux_camera/depth/image_raw")
TARGET_FRAMES = int(os.environ.get("DF_TARGET_FRAMES", "100"))
MIN_FRAMES = 80
TIMEOUT_S = 40.0


def main(out_root):
    step = Step(out_root, "01_capture_baseline")
    step.log(f"target={TARGET_FRAMES} frames, timeout={TIMEOUT_S}s")
    os.makedirs(out_root, exist_ok=True)

    bridge = CvBridge()
    state = {"depth": [], "color": [], "t0": None}

    def on_depth(msg):
        if state["t0"] is None:
            state["t0"] = time.monotonic()
        if len(state["depth"]) < TARGET_FRAMES:
            state["depth"].append(
                bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough").copy())

    def on_color(msg):
        if len(state["color"]) < TARGET_FRAMES:
            state["color"].append(
                bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8").copy())

    rospy.init_node("df_capture_baseline", anonymous=True, disable_signals=True)
    rospy.Subscriber(DEPTH_TOPIC, Image, on_depth, queue_size=2,
                     buff_size=8 * 1024 * 1024)
    rospy.Subscriber(COLOR_TOPIC, Image, on_color, queue_size=2,
                     buff_size=8 * 1024 * 1024)

    with step.timeit("capture_wait"):
        while len(state["depth"]) < TARGET_FRAMES:
            if state["t0"] is not None and \
                    time.monotonic() - state["t0"] > TIMEOUT_S:
                break
            time.sleep(0.05)

    n = len(state["depth"])
    step.log(f"captured depth={n} color={len(state['color'])}")
    step.gate(n >= MIN_FRAMES, "frames >= 80", n, ">=80")

    seq = np.stack(state["depth"]).astype(np.uint16)
    if seq.dtype != np.uint16:
        seq = seq.astype(np.uint16)
    np.save(os.path.join(out_root, "depth_seq.npy"), seq)

    vratio = float((seq > 0).mean())
    step.log(f"valid_ratio={vratio:.4f} shape={seq.shape}")
    step.gate(vratio >= 0.05, "valid_ratio >= 0.05", round(vratio, 4), ">=0.05")

    h, w = seq.shape[1:]
    with step.timeit("write_videos"):
        vw = cv2.VideoWriter(os.path.join(out_root, "raw_depth.mp4"),
                             cv2.VideoWriter_fourcc(*"mp4v"), 10, (w, h))
        for f in seq:
            vw.write(colorize(f))
        vw.release()
        if state["color"]:
            ch, cw = state["color"][0].shape[:2]
            cw2 = cv2.VideoWriter(os.path.join(out_root, "color.mp4"),
                                  cv2.VideoWriter_fourcc(*"mp4v"), 10, (cw, ch))
            for f in state["color"]:
                cw2.write(f)
            cw2.release()

    meta = {"frames": n, "shape": list(seq.shape), "valid_ratio": vratio,
            "depth_topic": DEPTH_TOPIC, "color_topic": COLOR_TOPIC,
            "captured_unix_s": time.time()}
    with open(os.path.join(out_root, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)

    for name in ("depth_seq.npy", "raw_depth.mp4", "color.mp4"):
        ok = os.path.exists(os.path.join(out_root, name)) and \
            os.path.getsize(os.path.join(out_root, name)) > 1000
        step.gate(ok, f"artifact {name} exists", name, ">1KB")

    step.finish("PASS")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/df/out")
