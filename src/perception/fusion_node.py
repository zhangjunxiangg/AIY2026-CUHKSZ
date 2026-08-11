#!/usr/bin/env python3
# 双相机融合节点：合并 Astra 与 Gemini335 的 3D 目标，盲区目标优先用辅助相机。
"""Fuse localized 3D targets from the main Astra camera and the auxiliary camera.

The node subscribes to two `target_3d_node` outputs (e.g. astra and aux), merges
them in base_link, and publishes a single fused list. When an Astra target was
estimated with monocular size (no real depth) or is flagged as blind_spot, an
aux target of the same category within `radius_m` replaces it.

Usage:
  ROS (on board):  python3 fusion_node.py --ros
  SIM (on PC):     python3 fusion_node.py --sim --astra <json> --aux <json>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _distance(a: list | None, b: list | None) -> float | None:
    if a is None or b is None:
        return None
    return float(sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5)


class TargetFuser:
    """Pure fusion logic (no ROS)."""

    def __init__(self, config: dict):
        cfg = config.get("fusion", {})
        self.radius_m = float(cfg.get("radius_m", 0.12))
        self.prefer_aux_blind = bool(cfg.get("prefer_aux_for_blind_spot", True))

    def fuse(self, astra_payload: dict, aux_payload: dict) -> dict:
        astra_targets = astra_payload.get("targets", [])
        aux_targets = aux_payload.get("targets", [])

        fused = []
        used_aux = set()

        for at in astra_targets:
            # Find a matching aux target of the same category within radius.
            best_idx = None
            best_dist = None
            for i, xt in enumerate(aux_targets):
                if i in used_aux or xt.get("category") != at.get("category"):
                    continue
                d = _distance(at.get("base_center_m"), xt.get("base_center_m"))
                if d is None or d > self.radius_m:
                    continue
                if best_dist is None or d < best_dist:
                    best_dist = d
                    best_idx = i

            should_replace = False
            if best_idx is not None and self.prefer_aux_blind:
                # Replace Astra with aux when Astra had no real depth.
                if at.get("depth_source") in ("mono", "none") or at.get("blind_spot"):
                    should_replace = True

            if should_replace:
                fused.append(aux_targets[best_idx])
                used_aux.add(best_idx)
            else:
                fused.append(at)
                if best_idx is not None:
                    used_aux.add(best_idx)  # duplicate suppressed

        # Add remaining aux targets (objects visible only to the aux camera).
        for i, xt in enumerate(aux_targets):
            if i not in used_aux:
                fused.append(xt)

        return {
            "ts": round(time.time(), 3),
            "status": "ok",
            "frame_id": "base_link",
            "targets": fused,
        }


def run_sim(args, config):
    fuser = TargetFuser(config)
    astra = json.loads(Path(args.astra).read_text(encoding="utf-8"))
    aux = json.loads(Path(args.aux).read_text(encoding="utf-8"))
    result = fuser.fuse(astra, aux)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def run_ros(args, config):
    import rospy
    from std_msgs.msg import String

    fuser = TargetFuser(config)
    cfg = config.get("fusion", {})
    pub_topic = cfg.get("publish_topic", "/student/perception/targets_3d_fused")
    out_file = Path(cfg.get("output_file", "/tmp/perception_targets_3d_fused.json"))

    astra_topic = config.get("camera", {}).get("astra", {}).get(
        "localized_topic", "/student/perception/targets_3d")
    aux_topic = config.get("camera", {}).get("aux", {}).get(
        "localized_topic", "/student/perception/targets_3d_aux")

    rospy.init_node("student_target_fusion", anonymous=False)
    pub = rospy.Publisher(pub_topic, String, queue_size=1, latch=False)

    latest = {"astra": None, "aux": None}

    def on_astra(msg):
        latest["astra"] = msg
        try_fuse()

    def on_aux(msg):
        latest["aux"] = msg
        try_fuse()

    def try_fuse():
        if latest["astra"] is None and latest["aux"] is None:
            return
        try:
            astra = json.loads(latest["astra"].data) if latest["astra"] else {"targets": []}
            aux = json.loads(latest["aux"].data) if latest["aux"] else {"targets": []}
        except json.JSONDecodeError:
            return
        result = fuser.fuse(astra, aux)
        out = json.dumps(result, ensure_ascii=False)
        pub.publish(String(data=out))
        try:
            out_file.write_text(out, encoding="utf-8")
        except OSError as exc:
            rospy.logwarn_throttle(10.0, "[FUSION] cannot write %s: %s", out_file, exc)

    rospy.Subscriber(astra_topic, String, on_astra)
    rospy.Subscriber(aux_topic, String, on_aux)
    rospy.loginfo("[FUSION] node up: %s + %s -> %s", astra_topic, aux_topic, pub_topic)
    rospy.spin()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sim", action="store_true", help="offline mode on local JSON")
    mode.add_argument("--ros", action="store_true", help="on-board mode via rospy")
    parser.add_argument("--astra", help="astra targets_3d JSON (sim mode)")
    parser.add_argument("--aux", help="aux targets_3d JSON (sim mode)")
    parser.add_argument("--config", default=None,
                        help="config json path (default: config.json next to this file)")
    args = parser.parse_args()

    from detectors import load_config
    config = load_config(args.config)

    if args.sim:
        if not args.astra or not args.aux:
            parser.error("--sim requires --astra and --aux")
        return run_sim(args, config)
    return run_ros(args, config)


if __name__ == "__main__":
    sys.exit(main())
