#!/usr/bin/env python3
"""Simple on-board camera viewer: subscribe to a ROS image topic and show it via cv2.imshow.

Run on the board (inside the vision container):
    run python3 /data/local/perception/view_camera.py --ros --topic /astra_camera/rgb/image_raw

Use VNC client to connect to <board-ip>:5900 to see the window.
"""
from __future__ import annotations

import argparse
import sys

import cv2
import rospy
from sensor_msgs.msg import Image

from decode import ros_image_to_bgr


def callback(msg, window_name):
    try:
        bgr = ros_image_to_bgr(msg)
    except RuntimeError as exc:
        rospy.logwarn_throttle(2.0, "[VIEW] decode failed: %s", exc)
        return
    cv2.imshow(window_name, bgr)
    cv2.waitKey(1)


def main():
    parser = argparse.ArgumentParser(description="ROS camera viewer")
    parser.add_argument("--topic", default="/astra_camera/rgb/image_raw",
                        help="ROS image topic to display")
    parser.add_argument("--window", default="Camera",
                        help="cv2 window title")
    args = parser.parse_args()

    rospy.init_node("student_camera_viewer", anonymous=True)
    rospy.loginfo("[VIEW] subscribing to %s", args.topic)
    rospy.Subscriber(args.topic, Image, lambda msg: callback(msg, args.window))
    rospy.spin()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
