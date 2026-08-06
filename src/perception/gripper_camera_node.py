#!/usr/bin/env python3
"""Publish the gripper USB camera (icSpring camera on /dev/video20) as a ROS image topic.

Run on the board:
    run python3 /data/local/perception/gripper_camera_node.py --device /dev/video20 --topic /gripper_camera/image_raw

If the frames are black, check that the gripper is open / the lens cap is removed.
"""
from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

import cv2
import numpy as np
import rospy
from sensor_msgs.msg import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="/dev/video20", help="video device path")
    parser.add_argument("--topic", default="/gripper_camera/image_raw", help="ROS topic")
    parser.add_argument("--frame-id", default="gripper_camera_optical_frame", help="frame_id")
    parser.add_argument("--width", type=int, default=640, help="capture width")
    parser.add_argument("--height", type=int, default=480, help="capture height")
    parser.add_argument("--fps", type=int, default=15, help="target fps")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.device)
    if not cap.isOpened():
        print(f"[GRIPPER_CAM] cannot open {args.device}", file=sys.stderr)
        return 1
    # Request MJPEG to cut USB isochronous bandwidth ~10x vs raw YUYV —
    # the board's single USB2 bus is shared with the Astra camera, and the
    # raw stream starved its bandwidth reservation (usb_submit_urb -28).
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    got = "".join(chr((fourcc >> (8 * i)) & 0xFF) for i in range(4))
    if got != "MJPG":
        print(f"[GRIPPER_CAM] WARNING: camera rejected MJPEG, got {got!r}", file=sys.stderr)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)

    rospy.init_node("gripper_camera_publisher", anonymous=False)

    # Graceful shutdown: rospy handles SIGINT itself, but SIGTERM (kill,
    # systemd stop, etc.) bypasses it. Route SIGTERM to rospy.signal_shutdown
    # so the loop exits and the camera is released below.
    signal.signal(signal.SIGTERM, lambda *_: rospy.signal_shutdown("SIGTERM"))

    pub = rospy.Publisher(args.topic, Image, queue_size=1)
    rate = rospy.Rate(args.fps)

    rospy.loginfo("[GRIPPER_CAM] publishing %s (%dx%d @ %d fps) -> %s",
                  args.device, args.width, args.height, args.fps, args.topic)

    try:
        while not rospy.is_shutdown():
            ok, bgr = cap.read()
            if not ok:
                rospy.logwarn_throttle(5.0, "[GRIPPER_CAM] frame capture failed")
                rate.sleep()
                continue

            msg = Image()
            msg.header.stamp = rospy.Time.now()
            msg.header.frame_id = args.frame_id
            msg.height, msg.width = bgr.shape[:2]
            msg.encoding = "bgr8"
            msg.step = msg.width * 3
            msg.data = bgr.tobytes()
            pub.publish(msg)
            rate.sleep()
    finally:
        cap.release()
        rospy.loginfo("[GRIPPER_CAM] camera %s released, node stopped", args.device)
    return 0


if __name__ == "__main__":
    sys.exit(main())
