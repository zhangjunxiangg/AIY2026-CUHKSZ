#!/usr/bin/env python3
"""Capture ROS image frames to disk for later YOLO dataset generation.

Run on the board (inside the ROS container):
    python3 capture_dataset_frames.py --topic /astra_camera/rgb/image_raw --out /data/local/dataset/aimaterials

The script saves one frame every `--interval` seconds. Press Ctrl-C to stop.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import rospy
from sensor_msgs.msg import Image

from decode import ros_image_to_bgr


class FrameCapture:
    def __init__(self, args):
        self.args = args
        self.out_dir = Path(args.out)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.last_save = 0.0
        self.count = 0

    def callback(self, msg):
        now = time.time()
        if now - self.last_save < self.args.interval:
            return
        try:
            bgr = ros_image_to_bgr(msg)
        except RuntimeError as exc:
            rospy.logwarn("decode failed: %s", exc)
            return
        fname = self.out_dir / f"frame_{now:.3f}.jpg"
        cv2.imwrite(str(fname), bgr)
        self.count += 1
        self.last_save = now
        rospy.loginfo("saved %s (%d total)", fname, self.count)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", default="/astra_camera/rgb/image_raw", help="ROS image topic")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between saved frames")
    args = parser.parse_args()

    rospy.init_node("dataset_frame_capture", anonymous=True)
    cap = FrameCapture(args)
    rospy.Subscriber(args.topic, Image, cap.callback)
    rospy.loginfo("capturing from %s -> %s every %.1fs", args.topic, args.out, args.interval)
    rospy.spin()
    return 0


if __name__ == "__main__":
    sys.exit(main())
