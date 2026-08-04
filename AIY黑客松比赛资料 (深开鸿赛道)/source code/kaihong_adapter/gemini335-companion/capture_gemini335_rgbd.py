#!/usr/bin/env python3
import json
import os
import time

import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image


COLOR_TOPIC = os.environ.get("GEMINI_COLOR_TOPIC", "/aux_camera/color/image_raw")
DEPTH_TOPIC = os.environ.get("GEMINI_DEPTH_TOPIC", "/aux_camera/depth/image_raw")
OUTPUT_DIR = os.environ.get("GEMINI_OUTPUT_DIR", "/output")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    rospy.init_node("capture_gemini335_rgbd", anonymous=True, disable_signals=True)
    bridge = CvBridge()

    color_msg = rospy.wait_for_message(COLOR_TOPIC, Image, timeout=20.0)
    depth_msg = rospy.wait_for_message(DEPTH_TOPIC, Image, timeout=20.0)

    color = bridge.imgmsg_to_cv2(color_msg, desired_encoding="bgr8")
    depth = bridge.imgmsg_to_cv2(depth_msg, desired_encoding="passthrough")
    depth = np.asarray(depth)
    if depth.dtype != np.uint16:
        depth = depth.astype(np.uint16)

    color_path = os.path.join(OUTPUT_DIR, "latest-color.jpg")
    depth_path = os.path.join(OUTPUT_DIR, "latest-depth.png")
    preview_path = os.path.join(OUTPUT_DIR, "latest-depth-preview.jpg")
    metadata_path = os.path.join(OUTPUT_DIR, "latest-metadata.json")

    valid = depth > 0
    preview = np.zeros(depth.shape, dtype=np.uint8)
    if np.any(valid):
        lo, hi = np.percentile(depth[valid], [2, 98])
        if hi <= lo:
            hi = lo + 1
        preview[valid] = np.clip((depth[valid] - lo) * 255.0 / (hi - lo), 0, 255)
    preview = cv2.applyColorMap(255 - preview, cv2.COLORMAP_TURBO)
    preview[~valid] = 0

    if not cv2.imwrite(color_path, color):
        raise RuntimeError("failed to save color image")
    if not cv2.imwrite(depth_path, depth):
        raise RuntimeError("failed to save 16-bit depth image")
    if not cv2.imwrite(preview_path, preview):
        raise RuntimeError("failed to save depth preview")

    h, w = depth.shape[:2]
    cy, cx = h // 2, w // 2
    center = depth[max(0, cy - 5):min(h, cy + 6), max(0, cx - 5):min(w, cx + 6)]
    center_valid = center[center > 0]
    metadata = {
        "captured_unix_s": time.time(),
        "color_topic": COLOR_TOPIC,
        "depth_topic": DEPTH_TOPIC,
        "color_shape": list(color.shape),
        "depth_shape": list(depth.shape),
        "depth_dtype": str(depth.dtype),
        "valid_depth_pixels": int(np.count_nonzero(valid)),
        "valid_depth_ratio": float(np.count_nonzero(valid) / depth.size),
        "center_depth_mm_median": (
            float(np.median(center_valid)) if center_valid.size else None
        ),
        "note": "The Orbbec ROS1 wrapper scales the 16UC1 depth image to millimetres; divide by 1000 for metres.",
    }
    with open(metadata_path, "w", encoding="utf-8") as stream:
        json.dump(metadata, stream, ensure_ascii=False, indent=2)

    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
