#!/usr/bin/env python3
"""One-shot ROS RGB-D demo for red/yellow/green/blue object candidates."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import rospy
from sensor_msgs.msg import CameraInfo, Image


DRAW_COLORS = {
    "red": (0, 0, 255),
    "yellow": (0, 255, 255),
    "green": (0, 255, 0),
    "blue": (255, 0, 0),
}


def image_rgb8(message: Image) -> np.ndarray:
    if message.encoding.lower() not in {"rgb8", "bgr8"}:
        raise RuntimeError(f"unsupported color encoding: {message.encoding}")
    row_width = int(message.step)
    raw = np.frombuffer(message.data, dtype=np.uint8).reshape(message.height, row_width)
    image = raw[:, : message.width * 3].reshape(message.height, message.width, 3)
    if message.encoding.lower() == "rgb8":
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    return image.copy()


def image_depth16(message: Image) -> np.ndarray:
    if message.encoding.upper() not in {"16UC1", "MONO16"}:
        raise RuntimeError(f"unsupported depth encoding: {message.encoding}")
    byte_order = ">u2" if message.is_bigendian else "<u2"
    values_per_row = int(message.step) // 2
    raw = np.frombuffer(message.data, dtype=np.dtype(byte_order)).reshape(
        message.height, values_per_row
    )
    return raw[:, : message.width].astype(np.uint16, copy=False)


def largest_contour(mask: np.ndarray, min_area: float):
    contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
    if not contours:
        return None, 0.0
    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    return (contour, area) if area >= min_area else (None, area)


def contour_depth_stats(depth: np.ndarray, contour: np.ndarray) -> dict[str, Any]:
    mask = np.zeros(depth.shape, dtype=np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, -1)
    total = int(np.count_nonzero(mask))
    valid = depth[(mask > 0) & (depth > 0)]
    valid_count = int(valid.size)
    return {
        "depth_mm": float(np.median(valid)) if valid_count >= 8 else None,
        "valid_pixels": valid_count,
        "valid_ratio": float(valid_count / total) if total else 0.0,
        "sample_pixels": total,
    }


def depth_preview(depth: np.ndarray) -> np.ndarray:
    valid = depth > 0
    gray = np.zeros(depth.shape, dtype=np.uint8)
    if np.any(valid):
        lo, hi = np.percentile(depth[valid], [2, 98])
        if hi <= lo:
            hi = lo + 1
        gray[valid] = np.clip((depth[valid] - lo) * 255.0 / (hi - lo), 0, 255)
    preview = cv2.applyColorMap(255 - gray, cv2.COLORMAP_TURBO)
    preview[~valid] = 0
    return preview


def detect(
    color: np.ndarray,
    depth: np.ndarray,
    camera_info: CameraInfo,
    config: dict[str, Any],
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    if color.shape[:2] != depth.shape[:2]:
        raise RuntimeError(
            f"RGB/depth size mismatch: {color.shape[:2]} versus {depth.shape[:2]}"
        )
    hsv = cv2.cvtColor(cv2.GaussianBlur(color, (5, 5), 0), cv2.COLOR_BGR2HSV)
    kernel_size = max(3, int(config.get("morph_kernel_px", 5)))
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    min_area = float(config.get("min_area_px", 350))
    fx, fy = float(camera_info.K[0]), float(camera_info.K[4])
    cx, cy = float(camera_info.K[2]), float(camera_info.K[5])
    annotated = color.copy()
    detections: list[dict[str, Any]] = []

    for name in ("red", "yellow", "green", "blue"):
        ranges = config["colors"].get(name, [])
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for hsv_range in ranges:
            mask = cv2.bitwise_or(
                mask,
                cv2.inRange(
                    hsv,
                    np.array(hsv_range["min"], dtype=np.uint8),
                    np.array(hsv_range["max"], dtype=np.uint8),
                ),
            )
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contour, area = largest_contour(mask, min_area)
        if contour is None:
            continue

        moments = cv2.moments(contour)
        if moments["m00"] <= 0:
            continue
        u = int(round(moments["m10"] / moments["m00"]))
        v = int(round(moments["m01"] / moments["m00"]))
        x, y, w, h = cv2.boundingRect(contour)
        perimeter = float(cv2.arcLength(contour, True))
        circularity = float(4.0 * np.pi * area / (perimeter * perimeter)) if perimeter else 0.0
        depth_stats = contour_depth_stats(depth, contour)
        distance_mm = depth_stats["depth_mm"]
        point_m = None
        if distance_mm is not None and fx > 0 and fy > 0:
            z_m = distance_mm / 1000.0
            point_m = {
                "x": (u - cx) * z_m / fx,
                "y": (v - cy) * z_m / fy,
                "z": z_m,
            }

        detection = {
            "color": name,
            "center_px": [u, v],
            "bbox_px": [x, y, w, h],
            "area_px": area,
            "circularity": circularity,
            "center_depth_mm": distance_mm,
            "depth_valid_pixels": depth_stats["valid_pixels"],
            "depth_valid_ratio": depth_stats["valid_ratio"],
            "depth_sample_pixels": depth_stats["sample_pixels"],
            "depth_method": "contour_valid_median" if distance_mm is not None else None,
            "camera_point_m": point_m,
            "frame_id": camera_info.header.frame_id,
        }
        detections.append(detection)
        draw = DRAW_COLORS[name]
        cv2.drawContours(annotated, [contour], -1, draw, 2)
        cv2.rectangle(annotated, (x, y), (x + w, y + h), draw, 2)
        label = f"{name}:{distance_mm:.0f}mm" if distance_mm is not None else name
        cv2.putText(
            annotated,
            label,
            (max(0, x + 2), min(annotated.shape[0] - 5, y + 18)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            draw,
            2,
            cv2.LINE_AA,
        )
        cv2.circle(annotated, (u, v), 4, draw, -1)
    return annotated, detections


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--color-topic", default="/astra_camera/rgb/image_raw")
    parser.add_argument("--depth-topic", default="/astra_camera/depth/image_raw")
    parser.add_argument("--camera-info-topic", default="/astra_camera/depth/camera_info")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rospy.init_node("student_color_detect_once", anonymous=True, disable_signals=True)
    color_message = rospy.wait_for_message(args.color_topic, Image, timeout=args.timeout)
    depth_message = rospy.wait_for_message(args.depth_topic, Image, timeout=args.timeout)
    camera_info = rospy.wait_for_message(
        args.camera_info_topic, CameraInfo, timeout=args.timeout
    )

    color = image_rgb8(color_message)
    depth = image_depth16(depth_message)
    annotated, detections = detect(color, depth, camera_info, config)
    image_path = output_dir / "latest-color-detect.jpg"
    depth_preview_path = output_dir / "latest-color-detect-depth-preview.jpg"
    json_path = output_dir / "latest-color-detect.json"
    if not cv2.imwrite(str(image_path), annotated):
        raise RuntimeError(f"failed to write {image_path}")
    if not cv2.imwrite(str(depth_preview_path), depth_preview(depth)):
        raise RuntimeError(f"failed to write {depth_preview_path}")
    depth_detection_count = sum(
        1 for item in detections if item["center_depth_mm"] is not None
    )
    rgbd_complete = bool(detections) and depth_detection_count == len(detections)
    result = {
        "ok": True,
        "captured_unix_s": time.time(),
        "color_topic": args.color_topic,
        "depth_topic": args.depth_topic,
        "camera_info_topic": args.camera_info_topic,
        "image_shape": list(color.shape),
        "depth_encoding": depth_message.encoding,
        "frame_id": camera_info.header.frame_id,
        "detection_count": len(detections),
        "depth_detection_count": depth_detection_count,
        "rgbd_complete": rgbd_complete,
        "detections": detections,
        "annotated_image": str(image_path),
        "depth_preview": str(depth_preview_path),
        "result_json": str(json_path),
        "note": "Color contours are object candidates, not semantic proof of a cylinder. Camera coordinates are not base_link coordinates.",
    }
    if detections and not rgbd_complete:
        result["warning"] = (
            "One or more color candidates have no valid Astra depth. Keep null values; "
            "move the object beyond the camera minimum range and capture again."
        )
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
