#!/usr/bin/env python3
"""Publish Astra UVC color stream as ROS topics with auto-reconnect.

Runs inside rk3588s-vision container. Discards initial buffered frames and
publishes to /astra_camera/rgb/image_raw + /astra_camera/rgb/camera_info.

Robustness additions for the hackathon:
- V4L2 buffer size set to 1 to avoid stale frames.
- On consecutive capture failures the camera is reopened automatically.
- A watchdog timer exits the process if no frame has been published for a
  configurable timeout, so an external supervisor can restart it.
"""
from __future__ import annotations

import glob
import signal
import sys
import time

import cv2
import numpy as np
import rospy
from sensor_msgs.msg import CameraInfo, Image


DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480
DEFAULT_RATE = 5.0
MAX_FAIL_BEFORE_REOPEN = 5          # consecutive read failures -> reopen device
DEFAULT_WATCHDOG_TIMEOUT_S = 3.0    # no successful publish -> exit


def find_astra_uvc_dev():
    for dev in sorted(glob.glob('/dev/video*')):
        idx = int(dev.replace('/dev/video', ''))
        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        if not cap.isOpened():
            continue
        try:
            name = open(f'/sys/class/video4linux/video{idx}/name').read().strip()
        except Exception:
            name = ''
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None and frame.size > 0 and 'USB 2.0 Camera' in name:
            return idx
    raise RuntimeError('Astra UVC device not found')


def open_capture(dev: int, width: int, height: int):
    """Open V4L2 capture with minimal buffering."""
    cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
    if not cap.isOpened():
        return None
    # Request minimal internal buffering so we do not publish old frames
    # after a temporary stall.
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    # Warm-up and flush any stale buffered frames from previous sessions.
    for _ in range(10):
        cap.read()
    return cap


def main():
    rospy.init_node('astra_uvc_publisher', anonymous=False)

    img_pub = rospy.Publisher('/astra_camera/rgb/image_raw', Image, queue_size=2)
    info_pub = rospy.Publisher('/astra_camera/rgb/camera_info', CameraInfo, queue_size=2)

    rate_hz = float(rospy.get_param('~rate', DEFAULT_RATE))
    dev = int(rospy.get_param('~device', find_astra_uvc_dev()))
    frame_id = rospy.get_param('~frame_id', 'astra_camera_color_optical_frame')
    width = int(rospy.get_param('~width', DEFAULT_WIDTH))
    height = int(rospy.get_param('~height', DEFAULT_HEIGHT))
    watchdog_timeout = float(rospy.get_param('~watchdog_timeout', DEFAULT_WATCHDOG_TIMEOUT_S))

    rospy.loginfo('[UVC] Astra UVC /dev/video%d -> %s (watchdog %.1fs)', dev, img_pub.name, watchdog_timeout)

    cap = open_capture(dev, width, height)
    if cap is None:
        rospy.logerr('[UVC] cannot open /dev/video%d', dev)
        sys.exit(1)

    rate = rospy.Rate(rate_hz)
    seq = 0
    fail_count = 0
    last_publish_time = time.time()

    def reopen():
        nonlocal cap
        rospy.logwarn('[UVC] reopening /dev/video%d...', dev)
        try:
            cap.release()
        except Exception:
            pass
        # Give the kernel a moment to release the V4L2 node.
        rospy.sleep(0.5)
        cap = open_capture(dev, width, height)
        if cap is None:
            rospy.logerr('[UVC] reopen failed for /dev/video%d', dev)
        else:
            rospy.loginfo('[UVC] reopened /dev/video%d', dev)

    def shutdown_handler(_signum, _frame):
        rospy.loginfo('[UVC] shutting down')
        try:
            cap.release()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    while not rospy.is_shutdown():
        now = time.time()
        # Watchdog: if we have not published a fresh frame for too long,
        # exit so a supervisor can restart the whole node cleanly.
        if now - last_publish_time > watchdog_timeout:
            rospy.logerr(
                '[UVC] watchdog timeout: no frame published for %.1fs, exiting',
                now - last_publish_time,
            )
            try:
                cap.release()
            except Exception:
                pass
            sys.exit(2)

        ret, frame = cap.read()
        if not ret or frame is None or frame.size == 0:
            fail_count += 1
            rospy.logwarn_throttle(5.0, '[UVC] capture failed (%d/%d)', fail_count, MAX_FAIL_BEFORE_REOPEN)
            if fail_count >= MAX_FAIL_BEFORE_REOPEN:
                reopen()
                fail_count = 0
                last_publish_time = time.time()  # reset watchdog while we recover
            rate.sleep()
            continue

        fail_count = 0
        msg = Image()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = frame_id
        msg.header.seq = seq
        msg.height, msg.width = frame.shape[:2]
        msg.encoding = 'bgr8'
        msg.step = msg.width * 3
        msg.data = frame.tobytes()
        img_pub.publish(msg)

        info = CameraInfo()
        info.header = msg.header
        info.height = msg.height
        info.width = msg.width
        info.K = [520.0, 0.0, 320.0, 0.0, 520.0, 240.0, 0.0, 0.0, 1.0]
        info.D = [0.0, 0.0, 0.0, 0.0, 0.0]
        info.P = [520.0, 0.0, 320.0, 0.0, 0.0, 520.0, 240.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        info_pub.publish(info)

        seq += 1
        last_publish_time = time.time()
        rate.sleep()

    try:
        cap.release()
    except Exception:
        pass


if __name__ == '__main__':
    main()
