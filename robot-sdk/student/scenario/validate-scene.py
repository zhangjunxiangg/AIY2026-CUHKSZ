#!/usr/bin/env python3
"""Validate a student competition scene without moving the robot."""

import argparse
import json
import sys
from pathlib import Path

import yaml


REQUIRED = {
    "recognition_camera",
    "grasp_camera",
    "target_color",
    "rgb_topic",
    "depth_topic",
    "camera_info_topic",
    "astra_arm_calibration",
    "aux_ground_calibration",
    "aux_arm_calibration",
    "forward_speed",
    "lateral_speed_limit",
    "max_align_travel_m",
    "home_pulses",
    "grasp_pulses",
    "gripper_open_pulse",
    "gripper_close_pulse",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", type=Path)
    parser.add_argument("--check-files", action="store_true")
    args = parser.parse_args()
    data = yaml.safe_load(args.scene.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("scene root must be a YAML mapping")
    missing = sorted(REQUIRED - set(data))
    if missing:
        raise RuntimeError("missing scene fields: " + ", ".join(missing))
    forbidden = [
        key for key in data
        if key in {"target_xyz", "fixed_target", "object_base_xyz"}
    ]
    if forbidden:
        raise RuntimeError("fixed object coordinates are forbidden: " + ", ".join(forbidden))
    if data["recognition_camera"] not in {"astra", "d435i"}:
        raise RuntimeError("recognition_camera must be astra or d435i")
    if data["grasp_camera"] not in {"astra", "d435i"}:
        raise RuntimeError("grasp_camera must be astra or d435i")
    if not 0.0 < float(data["forward_speed"]) <= 0.08:
        raise RuntimeError("forward_speed must be in (0, 0.08]")
    if not 0.0 < float(data["lateral_speed_limit"]) <= 0.10:
        raise RuntimeError("lateral_speed_limit must be in (0, 0.10]")
    if not 0.0 < float(data["max_align_travel_m"]) <= 0.50:
        raise RuntimeError("max_align_travel_m must be in (0, 0.50]")
    for key in ("home_pulses", "grasp_pulses"):
        values = data[key]
        if not isinstance(values, list) or len(values) != 5:
            raise RuntimeError(key + " must be measured: provide five pulses in [0,1000]")
        if any(not 0 <= int(value) <= 1000 for value in values):
            raise RuntimeError(key + " must contain five pulses in [0,1000]")
    for key in ("gripper_open_pulse", "gripper_close_pulse"):
        if data[key] is None:
            raise RuntimeError(key + " must be measured on this vehicle")
        if not 0 <= int(data[key]) <= 1000:
            raise RuntimeError(key + " must be in [0,1000]")
    for key in ("recognition_goal", "grasp_goal", "place_goal", "return_goal"):
        values = data.get(key, [])
        if values and len(values) != 3:
            raise RuntimeError(key + " must be empty or [x,y,yaw]")
    checked = {}
    if args.check_files:
        for key in (
            "astra_arm_calibration",
            "aux_ground_calibration",
            "aux_arm_calibration",
        ):
            checked[key] = Path(data[key]).is_file()
            if not checked[key]:
                raise RuntimeError("calibration file is missing: " + data[key])
    print(
        json.dumps(
            {
                "ok": True,
                "scene": data.get("scenario_name", args.scene.stem),
                "dry_run": bool(data.get("dry_run", True)),
                "navigation_enabled": bool(data.get("navigation_enabled", False)),
                "calibration_files_checked": checked,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        sys.exit(1)
