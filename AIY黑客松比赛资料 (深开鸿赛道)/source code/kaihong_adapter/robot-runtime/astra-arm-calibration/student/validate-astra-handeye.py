#!/usr/bin/env python3
"""Validate one held-out Astra eye-to-hand sample against a candidate result."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


def load_solver(path: Path):
    spec = importlib.util.spec_from_file_location("astra_arm_handeye", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load hand-eye solver")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solver", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--translation-limit-m", type=float, default=0.020)
    parser.add_argument("--rotation-limit-deg", type=float, default=5.0)
    args = parser.parse_args()

    module = load_solver(args.solver)
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    samples = dataset.get("samples", [])
    if len(samples) != 1:
        raise RuntimeError("validation dataset must contain exactly one held-out sample")
    if calibration.get("quality") != "PASS":
        raise RuntimeError("candidate training quality is not PASS")

    base_to_camera = module.transform(
        calibration["base_to_camera"]["rotation_matrix"],
        calibration["base_to_camera"]["translation_m"],
    )
    gripper_to_marker = module.transform(
        calibration["estimated_gripper_to_marker"]["rotation_matrix"],
        calibration["estimated_gripper_to_marker"]["translation_m"],
    )
    base_to_gripper = module.sample_transform(samples[0], "base_to_gripper")
    camera_to_marker = module.sample_transform(samples[0], "camera_to_target")

    marker_from_camera = base_to_camera.dot(camera_to_marker)
    marker_from_arm = base_to_gripper.dot(gripper_to_marker)
    translation_error = float(
        np.linalg.norm(marker_from_camera[:3, 3] - marker_from_arm[:3, 3])
    )
    rotation_error = float(
        module.rotation_angle_degrees(
            marker_from_camera[:3, :3].T.dot(marker_from_arm[:3, :3])
        )
    )
    passed = (
        translation_error <= args.translation_limit_m
        and rotation_error <= args.rotation_limit_deg
    )
    result = {
        "ok": passed,
        "validation_type": "held_out_marker_pose",
        "translation_error_m": translation_error,
        "rotation_error_deg": rotation_error,
        "limits": {
            "translation_error_m": args.translation_limit_m,
            "rotation_error_deg": args.rotation_limit_deg,
        },
        "candidate_sha256": hashlib.sha256(args.calibration.read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
