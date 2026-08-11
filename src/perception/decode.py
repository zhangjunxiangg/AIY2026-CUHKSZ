# ROS 图像手工解码（不用 cv_bridge）：照官方 color_detect_demo.py 的 np.frombuffer 模式。
# 仅依赖 cv2/numpy，不 import rospy —— 消息按 duck-typing 处理，本机无 ROS 也能 import 本模块。
"""Manual decoding of sensor_msgs/Image into numpy arrays (no cv_bridge).

Ported from the official kaihong color_detect_demo.py:
  - ros_image_to_bgr:  rgb8 / bgr8 / mono8  -> HxWx3 uint8 BGR image
  - ros_image_to_depth: 16UC1 / mono16      -> HxW uint16 depth in mm
"""
from __future__ import annotations

import cv2
import numpy as np


def ros_image_to_bgr(msg):
    """sensor_msgs/Image (rgb8/bgr8/mono8) -> BGR uint8 数组。"""
    encoding = msg.encoding.lower()
    if encoding in ("rgb8", "bgr8"):
        raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, int(msg.step))
        image = raw[:, : msg.width * 3].reshape(msg.height, msg.width, 3)
        if encoding == "rgb8":
            return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image.copy()
    if encoding == "mono8":
        raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, int(msg.step))
        gray = raw[:, : msg.width]
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    raise RuntimeError(f"unsupported color encoding: {msg.encoding}")


def ros_compressed_image_to_bgr(msg):
    """sensor_msgs/CompressedImage (jpeg/png) -> BGR uint8 数组。

    Gemini335 辅助相机走的是压缩 JPEG 话题，需要这条路。
    """
    if not hasattr(msg, "format") or not hasattr(msg, "data"):
        raise RuntimeError("message does not look like sensor_msgs/CompressedImage")
    fmt = msg.format.lower() if msg.format else ""
    if "jpeg" in fmt or "jpg" in fmt or "png" in fmt:
        buf = np.frombuffer(msg.data, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError(f"failed to decode compressed image (format={msg.format})")
        return img
    raise RuntimeError(f"unsupported compressed image format: {msg.format}")


def ros_image_to_depth(msg):
    """sensor_msgs/Image (16UC1/mono16) -> uint16 深度数组，单位 mm。"""
    if msg.encoding.upper() not in ("16UC1", "MONO16"):
        raise RuntimeError(f"unsupported depth encoding: {msg.encoding}")
    byte_order = ">u2" if msg.is_bigendian else "<u2"
    values_per_row = int(msg.step) // 2
    raw = np.frombuffer(msg.data, dtype=np.dtype(byte_order)).reshape(
        msg.height, values_per_row
    )
    return raw[:, : msg.width].astype(np.uint16, copy=False)
