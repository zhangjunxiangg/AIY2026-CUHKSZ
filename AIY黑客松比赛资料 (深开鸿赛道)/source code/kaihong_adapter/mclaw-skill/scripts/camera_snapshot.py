#!/usr/bin/env python3
"""Capture fixed-name Astra RGB, raw depth, preview, and metadata files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image


RGB_TOPIC = "/astra_camera/rgb/image_raw"
DEPTH_TOPIC = "/astra_camera/depth/image_raw"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-prefix", default="/tmp/mclaw-camera-latest")
    args = parser.parse_args()
    prefix = Path(args.output_prefix)
    rgb_path = Path(f"{prefix}-rgb.jpg")
    depth_path = Path(f"{prefix}-depth.png")
    preview_path = Path(f"{prefix}-depth-preview.jpg")
    metadata_path = Path(f"{prefix}.json")

    rospy.init_node("mclaw_camera_snapshot", anonymous=True, disable_signals=True)
    bridge = CvBridge()
    try:
        rgb_message = rospy.wait_for_message(RGB_TOPIC, Image, timeout=8.0)
        depth_message = rospy.wait_for_message(DEPTH_TOPIC, Image, timeout=8.0)
        rgb = bridge.imgmsg_to_cv2(rgb_message, desired_encoding="bgr8")
        depth = bridge.imgmsg_to_cv2(depth_message, desired_encoding="passthrough")
        depth = np.asarray(depth, dtype=np.uint16)
        valid = depth[depth > 0]
        if valid.size:
            near_mm = int(np.percentile(valid, 2))
            median_mm = int(np.percentile(valid, 50))
            far_mm = int(np.percentile(valid, 98))
        else:
            near_mm = median_mm = far_mm = 0
        height, width = depth.shape[:2]
        center = depth[
            max(0, height // 2 - 5) : min(height, height // 2 + 6),
            max(0, width // 2 - 5) : min(width, width // 2 + 6),
        ]
        center_valid = center[center > 0]
        center_mm = int(np.median(center_valid)) if center_valid.size else 0

        # JET maps 255 to warm red and 0 to cool blue. Invert normalized depth
        # so nearer valid pixels are warm and farther valid pixels are cool.
        scale_far = max(far_mm, 1)
        normalized = np.clip(depth.astype(np.float32) / scale_far, 0.0, 1.0)
        preview_index = np.uint8((1.0 - normalized) * 255.0)
        preview = cv2.applyColorMap(preview_index, cv2.COLORMAP_JET)
        preview[depth == 0] = 0

        if not cv2.imwrite(str(rgb_path), rgb):
            raise RuntimeError("failed to write RGB JPEG")
        if not cv2.imwrite(str(depth_path), depth):
            raise RuntimeError("failed to write raw 16-bit depth PNG")
        if not cv2.imwrite(str(preview_path), preview):
            raise RuntimeError("failed to write depth preview JPEG")

        payload = {
            "ok": True,
            "rgb_topic": RGB_TOPIC,
            "depth_topic": DEPTH_TOPIC,
            "width": int(rgb.shape[1]),
            "height": int(rgb.shape[0]),
            "rgb_encoding": rgb_message.encoding,
            "depth_encoding": depth_message.encoding,
            "rgb_frame_id": rgb_message.header.frame_id,
            "depth_frame_id": depth_message.header.frame_id,
            "valid_depth_pixels": int(valid.size),
            "center_depth_mm": center_mm,
            "near_depth_mm_p02": near_mm,
            "median_depth_mm_p50": median_mm,
            "far_depth_mm_p98": far_mm,
            "preview_colors": "warm=near,cool=far,black=invalid",
        }
        metadata_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as error:
        payload = {"ok": False, "error": f"{type(error).__name__}: {error}"}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
