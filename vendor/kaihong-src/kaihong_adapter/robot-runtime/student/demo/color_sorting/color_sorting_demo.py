#!/usr/bin/env python3
"""One-shot, perception-only four-color sorting decision demo.

This node never publishes chassis, arm, servo, or gripper commands.  It reuses
the adapted RGB-D color detector and publishes a latched JSON recommendation on
a std_msgs/String topic for downstream student code.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from pathlib import Path
from typing import Any, Optional, Tuple

import cv2
import rospy
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String

from color_detect_demo import depth_preview, detect, image_depth16, image_rgb8


def stamp_seconds(message: Any) -> Optional[float]:
    stamp = message.header.stamp
    value = float(stamp.to_sec())
    return value if value > 0.0 else None


def wait_for_rgbd_pair(
    color_topic: str,
    depth_topic: str,
    timeout_s: float,
    max_skew_s: float,
) -> Tuple[Image, Image, Optional[float]]:
    condition = threading.Condition()
    latest: dict[str, Image] = {}

    def color_callback(message: Image) -> None:
        with condition:
            latest["color"] = message
            condition.notify_all()

    def depth_callback(message: Image) -> None:
        with condition:
            latest["depth"] = message
            condition.notify_all()

    color_subscriber = rospy.Subscriber(
        color_topic, Image, color_callback, queue_size=1
    )
    depth_subscriber = rospy.Subscriber(
        depth_topic, Image, depth_callback, queue_size=1
    )
    deadline = time.monotonic() + timeout_s
    last_skew: Optional[float] = None
    try:
        with condition:
            while time.monotonic() < deadline:
                color = latest.get("color")
                depth = latest.get("depth")
                if color is not None and depth is not None:
                    color_stamp = stamp_seconds(color)
                    depth_stamp = stamp_seconds(depth)
                    if color_stamp is None or depth_stamp is None:
                        return color, depth, None
                    last_skew = abs(color_stamp - depth_stamp)
                    if last_skew <= max_skew_s:
                        return color, depth, last_skew
                condition.wait(timeout=min(0.1, max(0.0, deadline - time.monotonic())))
        raise RuntimeError(
            f"no RGB-D pair within {max_skew_s:.3f}s skew; last skew={last_skew}"
        )
    finally:
        color_subscriber.unregister()
        depth_subscriber.unregister()


def confidence(detection: dict[str, Any], min_area_px: float) -> float:
    area_score = min(1.0, float(detection["area_px"]) / max(1.0, min_area_px * 4.0))
    shape_score = min(1.0, max(0.0, float(detection["circularity"]) / 0.85))
    return round(0.6 * area_score + 0.4 * shape_score, 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--detector-config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--public-output-dir")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--color-topic", default="/astra_camera/rgb/image_raw")
    parser.add_argument("--depth-topic", default="/astra_camera/depth/image_raw")
    parser.add_argument("--camera-info-topic", default="/astra_camera/depth/camera_info")
    parser.add_argument("--decision-topic", default="/student/color_sorting/decision")
    parser.add_argument("--publish-hold-sec", type=float, default=2.0)
    args = parser.parse_args()

    sorting_config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    detector_config = json.loads(
        Path(args.detector_config).read_text(encoding="utf-8")
    )
    max_skew_s = float(sorting_config.get("max_frame_skew_s", 0.25))
    max_age_s = float(sorting_config.get("max_frame_age_s", 2.0))
    min_confidence = float(sorting_config.get("min_confidence", 0.55))
    min_depth_ratio = float(sorting_config.get("min_depth_valid_ratio", 0.02))
    placement_zones = sorting_config["placement_zones"]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    public_output_dir = Path(args.public_output_dir or args.output_dir)

    rospy.init_node("student_color_sorting_once", anonymous=True, disable_signals=True)
    color_message, depth_message, frame_skew_s = wait_for_rgbd_pair(
        args.color_topic, args.depth_topic, args.timeout, max_skew_s
    )
    pair_received_ros_s = rospy.Time.now().to_sec()
    camera_info = rospy.wait_for_message(
        args.camera_info_topic, CameraInfo, timeout=args.timeout
    )

    color = image_rgb8(color_message)
    depth = image_depth16(depth_message)
    annotated, detections = detect(color, depth, camera_info, detector_config)

    color_stamp_s = stamp_seconds(color_message)
    depth_stamp_s = stamp_seconds(depth_message)
    newest_input_stamp = max(
        (value for value in (color_stamp_s, depth_stamp_s) if value is not None),
        default=None,
    )
    captured_ros_s = newest_input_stamp or pair_received_ros_s
    frame_age_s = (
        max(0.0, pair_received_ros_s - newest_input_stamp)
        if newest_input_stamp is not None
        else None
    )
    input_fresh = (
        (frame_skew_s is None or frame_skew_s <= max_skew_s)
        and (frame_age_s is None or frame_age_s <= max_age_s)
    )

    decisions = []
    depth_quality_count = 0
    for detection in detections:
        item_confidence = confidence(
            detection, float(detector_config.get("min_area_px", 350))
        )
        depth_quality_ok = (
            detection["camera_point_m"] is not None
            and float(detection["depth_valid_ratio"]) >= min_depth_ratio
        )
        if depth_quality_ok:
            depth_quality_count += 1
        recommendation_ready = input_fresh and item_confidence >= min_confidence
        decision = {
            "color": detection["color"],
            "center_px": detection["center_px"],
            "center_depth_mm": detection["center_depth_mm"],
            "camera_point_m": detection["camera_point_m"],
            "frame_id": detection["frame_id"],
            "captured_ros_s": captured_ros_s,
            "confidence": item_confidence,
            "suggested_placement_zone": placement_zones[detection["color"]],
            "recommendation_ready": recommendation_ready,
            "depth_quality_ok": depth_quality_ok,
            "pick_ready": False,
            "pick_block_reason": "camera_frame_only_no_calibrated_base_link_transform",
        }
        decisions.append(decision)

    if decisions:
        panel_height = 14 + 21 * len(decisions)
        overlay = annotated.copy()
        cv2.rectangle(overlay, (6, 6), (250, panel_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.68, annotated, 0.32, 0.0, annotated)
    for index, decision in enumerate(decisions):
        label = (
            f"{decision['color']} -> {decision['suggested_placement_zone']} "
            f"({decision['confidence']:.2f})"
        )
        cv2.putText(
            annotated,
            label,
            (13, 23 + index * 21),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    image_path = output_dir / "latest-color-sorting.jpg"
    depth_preview_path = output_dir / "latest-color-sorting-depth-preview.jpg"
    json_path = output_dir / "latest-color-sorting.json"
    if not cv2.imwrite(str(image_path), annotated):
        raise RuntimeError(f"failed to write {image_path}")
    if not cv2.imwrite(str(depth_preview_path), depth_preview(depth)):
        raise RuntimeError(f"failed to write {depth_preview_path}")

    result = {
        "ok": True,
        "mode": "perception_only_no_motion",
        "captured_unix_s": time.time(),
        "captured_ros_s": captured_ros_s,
        "color_header_stamp_s": color_stamp_s,
        "depth_header_stamp_s": depth_stamp_s,
        "frame_skew_s": frame_skew_s,
        "frame_age_s": frame_age_s,
        "input_fresh": input_fresh,
        "color_topic": args.color_topic,
        "depth_topic": args.depth_topic,
        "camera_info_topic": args.camera_info_topic,
        "decision_topic": args.decision_topic,
        "frame_id": camera_info.header.frame_id,
        "detection_count": len(detections),
        "recommendation_count": sum(
            1 for item in decisions if item["recommendation_ready"]
        ),
        "depth_quality_count": depth_quality_count,
        "rgbd_complete": bool(detections) and depth_quality_count == len(detections),
        "decisions": decisions,
        "annotated_image": str(public_output_dir / image_path.name),
        "depth_preview": str(public_output_dir / depth_preview_path.name),
        "result_json": str(public_output_dir / json_path.name),
        "safety": {
            "motion_commands_published": False,
            "camera_points_are_base_link_points": False,
            "note": "Placement zones are recommendations only. Run hand-eye calibration and transform fresh targets to base_link before implementing any pick action.",
        },
    }
    if detections and not result["rgbd_complete"]:
        result["warning"] = (
            "One or more candidates lack reliable depth. Color sorting recommendations "
            "remain available, but those camera points must not be used for picking."
        )

    payload = json.dumps(result, ensure_ascii=False)
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    publisher = rospy.Publisher(args.decision_topic, String, queue_size=1, latch=True)
    deadline = time.monotonic() + max(0.0, args.publish_hold_sec)
    while publisher.get_num_connections() == 0 and time.monotonic() < deadline:
        rospy.sleep(0.05)
    publisher.publish(String(data=payload))
    rospy.sleep(min(0.25, max(0.0, args.publish_hold_sec)))
    print(payload)


if __name__ == "__main__":
    main()
