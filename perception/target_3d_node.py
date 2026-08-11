#!/usr/bin/env python3
# 目标三维定位节点：把 perception_node 的像素+深度目标换算到 base_link / map，供角色D抓取。
"""Convert 2D perception targets into base_link / map coordinates for the grasping role.

Usage:
  ROS (on board):  python3 target_3d_node.py --ros --camera astra
  SIM (on PC):     python3 target_3d_node.py --sim --camera astra --targets <json> [--camera-info <json>]

The node reads camera extrinsics from the official calibration JSON
(e.g. astra-to-base.json) and camera intrinsics from the ROS camera_info topic
(or from config.json as a fallback). Depth is taken from the perception target
when valid; otherwise a monocular size-based estimate is used if configured.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from blind_spot import estimate_target_depth
from geometry3d import CameraExtrinsics, CameraIntrinsics, transform_point_with_tf

HERE = Path(__file__).resolve().parent


class TargetLocalizer:
    """Pure localization logic (no ROS)."""

    def __init__(self, config: dict, camera_name: str):
        self.config = config
        self.camera_name = camera_name
        cam_cfg = config.get("camera", {}).get(camera_name, {})

        self.intrinsics = None
        intr_cfg = cam_cfg.get("intrinsics")
        if intr_cfg:
            self.intrinsics = CameraIntrinsics.from_dict(intr_cfg)

        self.extrinsics = None
        extr_path = cam_cfg.get("extrinsics_json")
        if extr_path:
            p = Path(extr_path)
            if not p.is_absolute():
                p = HERE / p
            if p.exists():
                self.extrinsics = CameraExtrinsics.from_json_file(p)

        self.map_tf = None  # geometry_msgs/TransformStamped or None

    def update_intrinsics_from_msg(self, msg) -> None:
        self.intrinsics = CameraIntrinsics.from_camera_info(msg)

    def set_map_transform(self, tf_msg) -> None:
        """Set the latest map -> base_link transform."""
        self.map_tf = tf_msg

    def localize(self, targets_payload: dict) -> dict:
        """Convert a perception targets JSON dict into base_link/map coordinates."""
        now = round(time.time(), 3)
        if self.intrinsics is None:
            return {
                "ts": now,
                "stamp": now,
                "status": "no_intrinsics",
                "camera": self.camera_name,
                "targets": [],
            }

        mono_size = self.config.get("blind_spot", {}).get("mono_size", {})
        out_targets = []
        for t in targets_payload.get("targets", []):
            depth_m, depth_src = estimate_target_depth(t, self.intrinsics, self.config)
            result = dict(t)
            result["depth_m"] = depth_m
            result["depth_source"] = depth_src
            result["precision"] = "high" if depth_src == "camera" else ("low" if depth_src == "mono" else "none")

            category = t.get("category", "")
            if category in mono_size:
                result["object_size_m"] = mono_size[category]

            if depth_m is None:
                result.update({
                    "camera_point_m": None,
                    "base_center_m": None,
                    "map_center_m": None,
                })
            else:
                u, v = t["center"]
                cam_pt = self.intrinsics.pixel_to_camera(u, v, depth_m)
                result["camera_point_m"] = [round(float(x), 4) for x in cam_pt]

                if self.extrinsics is not None:
                    base_pt = self.extrinsics.camera_to_base(cam_pt)
                    result["base_center_m"] = [round(float(x), 4) for x in base_pt]
                    if self.map_tf is not None:
                        map_pt = transform_point_with_tf(self.map_tf, base_pt)
                        result["map_center_m"] = [round(float(x), 4) for x in map_pt]
                    else:
                        result["map_center_m"] = None
                else:
                    result["base_center_m"] = None
                    result["map_center_m"] = None

            out_targets.append(result)

        return {
            "ts": now,
            "stamp": now,
            "status": "ok",
            "camera": self.camera_name,
            "frame_id": "base_link",
            "targets": out_targets,
        }


def run_sim(args, config):
    """Offline mode: read a perception targets JSON and print the localized JSON."""
    localizer = TargetLocalizer(config, args.camera)

    if args.camera_info:
        info = json.loads(Path(args.camera_info).read_text(encoding="utf-8"))
        # Accept either a full CameraInfo dict or a plain intrinsics dict.
        if "K" in info:
            localizer.intrinsics = CameraIntrinsics(
                fx=info["K"][0], fy=info["K"][4], cx=info["K"][2], cy=info["K"][5],
                width=info.get("width", 0), height=info.get("height", 0),
            )
        else:
            localizer.intrinsics = CameraIntrinsics.from_dict(info)

    targets = json.loads(Path(args.targets).read_text(encoding="utf-8"))
    result = localizer.localize(targets)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def run_ros(args, config):
    """On-board ROS mode."""
    import rospy
    from std_msgs.msg import String

    localizer = TargetLocalizer(config, args.camera)
    loc_cfg = config.get("localization", {})
    pub_topic = loc_cfg.get("publish_topic", "/student/perception/targets_3d")
    out_file = Path(loc_cfg.get("output_file", "/tmp/perception_targets_3d.json"))

    cam_cfg = config.get("camera", {}).get(args.camera, {})
    camera_info_topic = cam_cfg.get("camera_info_topic")
    targets_topic = cam_cfg.get("targets_topic", "/student/perception/targets")

    # Optional TF for map -> base_link
    tf_buffer = None
    if loc_cfg.get("use_tf", True):
        try:
            import tf2_ros
            tf_buffer = tf2_ros.Buffer(cache_time=rospy.Duration(10.0))
            tf2_ros.TransformListener(tf_buffer)
            rospy.loginfo("[LOC3D] TF enabled for map frame")
        except Exception as exc:  # ImportError or ROS init issues
            rospy.logwarn("[LOC3D] TF unavailable, map_center_m will be null: %s", exc)

    rospy.init_node("student_target_3d", anonymous=False)
    pub = rospy.Publisher(pub_topic, String, queue_size=1, latch=False)

    if camera_info_topic:
        from sensor_msgs.msg import CameraInfo
        rospy.Subscriber(camera_info_topic, CameraInfo,
                         lambda msg: localizer.update_intrinsics_from_msg(msg))
        rospy.loginfo("[LOC3D] subscribing camera_info: %s", camera_info_topic)

    map_frame = loc_cfg.get("map_frame", "map")
    base_frame = loc_cfg.get("base_frame", "base_link")

    def on_targets(msg):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            rospy.logwarn_throttle(5.0, "[LOC3D] bad JSON on %s", targets_topic)
            return

        if tf_buffer is not None:
            try:
                tf = tf_buffer.lookup_transform(map_frame, base_frame, rospy.Time(0), rospy.Duration(0.5))
                localizer.set_map_transform(tf)
            except Exception as exc:
                rospy.logwarn_throttle(5.0, "[LOC3D] TF lookup failed: %s", exc)
                localizer.set_map_transform(None)

        result = localizer.localize(payload)
        out = json.dumps(result, ensure_ascii=False)
        pub.publish(String(data=out))
        try:
            out_file.write_text(out, encoding="utf-8")
        except OSError as exc:
            rospy.logwarn_throttle(10.0, "[LOC3D] cannot write %s: %s", out_file, exc)

    rospy.Subscriber(targets_topic, String, on_targets)
    rospy.loginfo("[LOC3D] node up: camera=%s targets=%s -> %s", args.camera, targets_topic, pub_topic)
    rospy.spin()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sim", action="store_true", help="offline mode on local JSON")
    mode.add_argument("--ros", action="store_true", help="on-board mode via rospy")
    parser.add_argument("--camera", required=True, choices=["astra", "aux"],
                        help="which camera the targets come from")
    parser.add_argument("--targets", help="perception targets JSON file (sim mode)")
    parser.add_argument("--camera-info", help="camera_info JSON or intrinsics dict (sim mode)")
    parser.add_argument("--config", default=None,
                        help="config json path (default: config.json next to this file)")
    args = parser.parse_args()

    from detectors import load_config
    config = load_config(args.config)

    if args.sim:
        if not args.targets:
            parser.error("--sim requires --targets <json>")
        return run_sim(args, config)
    return run_ros(args, config)


if __name__ == "__main__":
    sys.exit(main())
