#!/usr/bin/env python3
"""Capture one frame from Astra Pro Plus RGB, depth, and IR topics and save as images."""
import os
import sys
import rospy
from sensor_msgs.msg import Image
import numpy as np
import cv2

SAVE_DIR = "/tmp/captures"
os.makedirs(SAVE_DIR, exist_ok=True)

rgb_done = False
depth_done = False
ir_done = False


def save_rgb(msg):
    global rgb_done
    if rgb_done:
        return
    arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
    # BGR->RGB for OpenCV if needed, but sensor_msgs Image RGB8 is usually RGB.
    # cv2.imwrite expects BGR; saving RGB as-is gives a color-swapped JPG, which is fine for inspection.
    path = os.path.join(SAVE_DIR, "astra_rgb.jpg")
    cv2.imwrite(path, arr)
    rospy.loginfo(f"Saved RGB to {path} ({msg.width}x{msg.height})")
    rgb_done = True


def save_depth(msg):
    global depth_done
    if depth_done:
        return
    # 16UC1: uint16 millimeters
    arr = np.frombuffer(msg.data, dtype=np.uint16).reshape((msg.height, msg.width))

    # Primary: raw numpy dump (always safe)
    raw_path = os.path.join(SAVE_DIR, "astra_depth_raw.npy")
    np.save(raw_path, arr)
    rospy.loginfo(f"Saved depth raw array to {raw_path} ({msg.width}x{msg.height})")

    # Best-effort: 16-bit PNG via OpenCV
    png_path = os.path.join(SAVE_DIR, "astra_depth.png")
    cv2.imwrite(png_path, arr)
    rospy.loginfo(f"Saved depth PNG to {png_path}")

    depth_done = True


def save_ir(msg):
    global ir_done
    if ir_done:
        return
    # IR is typically mono (8UC1 or 16UC1)
    if msg.encoding in ("mono16", "16UC1", "Y10", "Y11"):
        dtype = np.uint16
    else:
        dtype = np.uint8
    arr = np.frombuffer(msg.data, dtype=dtype).reshape((msg.height, msg.width))
    path = os.path.join(SAVE_DIR, "astra_ir.jpg")
    cv2.imwrite(path, arr)
    rospy.loginfo(f"Saved IR to {path} ({msg.width}x{msg.height}, encoding={msg.encoding})")
    ir_done = True


def main():
    rospy.init_node("capture_camera", anonymous=True)
    rospy.Subscriber("/astra_camera/rgb/image_raw", Image, save_rgb, queue_size=1)
    rospy.Subscriber("/astra_camera/depth/image_raw", Image, save_depth, queue_size=1)
    rospy.Subscriber("/astra_camera/ir/image_raw", Image, save_ir, queue_size=1)
    rospy.loginfo("Waiting for RGB, depth and IR frames...")
    timeout = rospy.Time.now() + rospy.Duration(15)
    while not rospy.is_shutdown() and (not rgb_done or not depth_done or not ir_done):
        if rospy.Time.now() > timeout:
            rospy.logerr("Timeout waiting for camera frames")
            break
        rospy.sleep(0.1)
    rospy.sleep(0.5)
    sys.exit(0 if (rgb_done and depth_done) else 1)


if __name__ == "__main__":
    main()
