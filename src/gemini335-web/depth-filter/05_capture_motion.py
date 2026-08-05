#!/usr/bin/env python3
"""05_capture_motion: dump a raw depth sequence that CONTAINS real motion.

Same capture as 01 but longer, plus a motion gate: some consecutive frame
pair must show >= MIN_MOTION_FRAC of pixels (valid in both) changing by
more than MOTION_MM. Without real motion the ghost metric in 06 is blind.
Usage: 05_capture_motion.py <out_root>
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
TARGET_FRAMES = int(os.environ.get("DF_TARGET_FRAMES", "150"))
MIN_FRAMES = 120
TIMEOUT_S = 60.0
MOTION_MM = 100.0
MIN_MOTION_FRAC = 0.02


def main(out_root):
    step = Step(out_root, "05_capture_motion")
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

    rospy.init_node("df_capture_motion", anonymous=True, disable_signals=True)
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
    step.gate(n >= MIN_FRAMES, f"frames >= {MIN_FRAMES}", n, f">={MIN_FRAMES}")

    seq = np.stack(state["depth"]).astype(np.uint16)
    np.save(os.path.join(out_root, "depth_seq.npy"), seq)

    vratio = float((seq > 0).mean())
    step.gate(vratio >= 0.05, "valid_ratio >= 0.05", round(vratio, 4), ">=0.05")

    with step.timeit("motion_score"):
        a = seq[:-1].astype(np.int32)
        b = seq[1:].astype(np.int32)
        both = (seq[:-1] > 0) & (seq[1:] > 0)
        changed = (np.abs(b - a) > MOTION_MM) & both
        frac = changed.sum(axis=(1, 2)) / np.maximum(both.sum(axis=(1, 2)), 1)
        motion_score = float(frac.max())
    step.log(f"motion_score={motion_score:.4f}")
    step.gate(motion_score >= MIN_MOTION_FRAC,
              "motion present (max changed fraction >= 2%)",
              f"{motion_score * 100:.2f}%", ">=2%")

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
            "motion_score": motion_score, "captured_unix_s": time.time()}
    with open(os.path.join(out_root, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    step.finish("PASS")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/df/out2")
