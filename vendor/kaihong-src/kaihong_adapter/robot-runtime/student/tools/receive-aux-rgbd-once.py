#!/usr/bin/env python3
import json
import os
import socket
import struct
import time
import zlib

import numpy as np
import rospy
from sensor_msgs.msg import CompressedImage, Image


COLOR_TOPIC = os.environ.get(
    "AUX_COLOR_TOPIC", "/aux_camera/color/image_raw/compressed"
)
DEPTH_TOPIC = os.environ.get("AUX_DEPTH_TOPIC", "/aux_camera/depth/image_raw")
OUTPUT_DIR = os.environ.get(
    "AUX_OUTPUT_DIR", "/data/robot-host/student/output"
)


def decode_depth(message):
    if message.encoding not in ("16UC1", "mono16"):
        raise RuntimeError("unsupported depth encoding: %s" % message.encoding)
    dtype = np.dtype(">u2" if message.is_bigendian else "<u2")
    row_values = message.step // dtype.itemsize
    depth = np.frombuffer(message.data, dtype=dtype)
    depth = depth.reshape(message.height, row_values)[:, : message.width]
    return depth.astype(np.uint16, copy=True)


def make_depth_preview(depth):
    valid = depth > 0
    scaled = np.zeros(depth.shape, dtype=np.uint8)
    if np.any(valid):
        low, high = np.percentile(depth[valid], [2, 98])
        if high <= low:
            high = low + 1
        scaled[valid] = np.clip(
            (depth[valid] - low) * 255.0 / (high - low), 0, 255
        )
    preview = 255 - scaled
    preview[~valid] = 0
    return preview


def png_chunk(chunk_type, payload):
    body = chunk_type + payload
    return (
        struct.pack(">I", len(payload))
        + body
        + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    )


def write_depth_png(path, depth):
    height, width = depth.shape
    big_endian = depth.astype(">u2", copy=False)
    rows = b"".join(b"\x00" + row.tobytes() for row in big_endian)
    header = struct.pack(">IIBBBBB", width, height, 16, 0, 0, 0, 0)
    with open(path, "wb") as stream:
        stream.write(b"\x89PNG\r\n\x1a\n")
        stream.write(png_chunk(b"IHDR", header))
        stream.write(png_chunk(b"IDAT", zlib.compress(rows, 6)))
        stream.write(png_chunk(b"IEND", b""))


def write_preview_pgm(path, preview):
    height, width = preview.shape
    with open(path, "wb") as stream:
        stream.write(("P5\n%d %d\n255\n" % (width, height)).encode("ascii"))
        stream.write(preview.tobytes())


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    rospy.init_node("receive_aux_rgbd_once", anonymous=True, disable_signals=True)

    color_message = rospy.wait_for_message(COLOR_TOPIC, CompressedImage, timeout=20.0)
    depth_message = rospy.wait_for_message(DEPTH_TOPIC, Image, timeout=20.0)

    if not color_message.data.startswith(b"\xff\xd8"):
        raise RuntimeError("auxiliary color payload is not a JPEG image")
    depth = decode_depth(depth_message)
    preview = make_depth_preview(depth)

    color_path = os.path.join(OUTPUT_DIR, "aux-camera-latest-color.jpg")
    depth_path = os.path.join(OUTPUT_DIR, "aux-camera-latest-depth.png")
    preview_path = os.path.join(OUTPUT_DIR, "aux-camera-latest-depth-preview.pgm")
    metadata_path = os.path.join(OUTPUT_DIR, "aux-camera-latest.json")

    with open(color_path, "wb") as stream:
        stream.write(color_message.data)
    write_depth_png(depth_path, depth)
    write_preview_pgm(preview_path, preview)

    valid = depth > 0
    height, width = depth.shape
    center = depth[
        max(0, height // 2 - 5) : min(height, height // 2 + 6),
        max(0, width // 2 - 5) : min(width, width // 2 + 6),
    ]
    center_valid = center[center > 0]
    metadata = {
        "ok": True,
        "received_unix_s": time.time(),
        "receiver": socket.gethostname(),
        "ros_master_uri": os.environ.get("ROS_MASTER_URI", ""),
        "color_topic": COLOR_TOPIC,
        "depth_topic": DEPTH_TOPIC,
        "color_format": color_message.format,
        "color_bytes": len(color_message.data),
        "color_shape": [depth_message.height, depth_message.width, 3],
        "depth_encoding": depth_message.encoding,
        "depth_shape": list(depth.shape),
        "depth_frame_id": depth_message.header.frame_id,
        "valid_depth_pixels": int(np.count_nonzero(valid)),
        "valid_depth_ratio": float(np.count_nonzero(valid) / depth.size),
        "center_depth_mm_median": (
            float(np.median(center_valid)) if center_valid.size else None
        ),
        "color_path": color_path,
        "depth_path": depth_path,
        "depth_preview_path": preview_path,
    }
    with open(metadata_path, "w", encoding="utf-8") as stream:
        json.dump(metadata, stream, ensure_ascii=False, indent=2)
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
