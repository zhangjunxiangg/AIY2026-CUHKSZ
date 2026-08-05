#!/usr/bin/env python3
"""Calibrate an auxiliary depth camera to the competition ground frame."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np


MIN_SAMPLES = 6


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def empty():
    return {
        "schema_version": 1,
        "calibration_type": "aux_camera_to_ground_3d",
        "camera_frame": "aux_camera_optical_frame",
        "ground_frame": "competition_ground",
        "samples": [],
    }


def transform_payload(rotation, translation):
    return {
        "rotation_matrix": np.asarray(rotation).tolist(),
        "translation_m": np.asarray(translation).reshape(3).tolist(),
    }


def matrix(value):
    result = np.eye(4)
    result[:3, :3] = np.asarray(value["rotation_matrix"], dtype=float)
    result[:3, 3] = np.asarray(value["translation_m"], dtype=float)
    return result


def solve_rigid(camera_points, ground_points):
    camera = np.asarray(camera_points, dtype=float)
    ground = np.asarray(ground_points, dtype=float)
    camera_center = camera.mean(axis=0)
    ground_center = ground.mean(axis=0)
    covariance = (camera - camera_center).T.dot(ground - ground_center)
    u, _singular, vt = np.linalg.svd(covariance)
    rotation = vt.T.dot(u.T)
    if np.linalg.det(rotation) < 0:
        vt[-1, :] *= -1
        rotation = vt.T.dot(u.T)
    translation = ground_center - rotation.dot(camera_center)
    predicted = (rotation.dot(camera.T)).T + translation
    errors = np.linalg.norm(predicted - ground, axis=1)
    return rotation, translation, errors


def geometry_ready(points):
    values = np.asarray(points, dtype=float)
    if len(values) < MIN_SAMPLES:
        return False, [0.0, 0.0, 0.0]
    span = np.ptp(values, axis=0)
    # Ground control points must cover both horizontal axes.
    return bool(sorted(span, reverse=True)[1] >= 0.20), span.tolist()


def cmd_init(args):
    write(args.dataset, empty())
    print(json.dumps({"ok": True, "dataset": str(args.dataset)}))
    return 0


def cmd_add(args):
    data = read(args.dataset) if args.dataset.exists() else empty()
    camera = [args.cx, args.cy, args.cz]
    ground = [args.gx, args.gy, args.gz]
    for sample in data["samples"]:
        if np.linalg.norm(np.asarray(sample["camera_xyz_m"]) - camera) < 0.02:
            raise RuntimeError("camera point is too close to an existing sample")
    data["samples"].append(
        {
            "index": len(data["samples"]) + 1,
            "camera_xyz_m": camera,
            "ground_xyz_m": ground,
        }
    )
    write(args.dataset, data)
    print(json.dumps({"ok": True, "sample_count": len(data["samples"])}))
    return 0


def cmd_status(args):
    data = read(args.dataset) if args.dataset.exists() else empty()
    ready, span = geometry_ready([s["ground_xyz_m"] for s in data["samples"]])
    print(
        json.dumps(
            {
                "ok": True,
                "sample_count": len(data["samples"]),
                "minimum_samples": MIN_SAMPLES,
                "ground_span_m": span,
                "ready_to_solve": ready,
            },
            ensure_ascii=False,
        )
    )
    return 0


def cmd_solve(args):
    data = read(args.dataset)
    samples = data["samples"]
    ready, span = geometry_ready([s["ground_xyz_m"] for s in samples])
    if not ready:
        raise RuntimeError("need >=6 non-collinear points spanning both ground axes")
    rotation, translation, errors = solve_rigid(
        [s["camera_xyz_m"] for s in samples],
        [s["ground_xyz_m"] for s in samples],
    )
    rmse = float(math.sqrt(np.mean(errors * errors)))
    maximum = float(np.max(errors))
    passed = rmse <= 0.020 and maximum <= 0.040
    result = {
        "schema_version": 1,
        "calibration_type": "aux_camera_to_ground_3d",
        "parent_frame": data.get("ground_frame", "competition_ground"),
        "child_frame": data.get("camera_frame", "aux_camera_optical_frame"),
        "ground_from_camera": transform_payload(rotation, translation),
        "sample_count": len(samples),
        "ground_span_m": span,
        "residual_rmse_m": rmse,
        "residual_max_m": maximum,
        "quality": "PASS" if passed else "REVIEW",
        "quality_limits": {"rmse_m": 0.020, "max_m": 0.040},
    }
    write(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 2


def transformed(calibration, point):
    value = matrix(calibration["ground_from_camera"]).dot(
        np.asarray([*point, 1.0], dtype=float)
    )
    return value[:3]


def cmd_transform(args):
    calibration = read(args.calibration)
    point = transformed(calibration, [args.x, args.y, args.z])
    print(
        json.dumps(
            {
                "ok": True,
                "ground_frame": calibration["parent_frame"],
                "ground_xyz_m": point.tolist(),
            }
        )
    )
    return 0


def cmd_chassis(args):
    calibration = read(args.calibration)
    front = transformed(calibration, [args.fx, args.fy, args.fz])
    rear = transformed(calibration, [args.rx, args.ry, args.rz])
    delta = front - rear
    if np.linalg.norm(delta[:2]) < 0.05:
        raise RuntimeError("front/rear marker separation is too small")
    center = (front + rear) * 0.5
    yaw = math.atan2(float(delta[1]), float(delta[0]))
    print(
        json.dumps(
            {
                "ok": True,
                "ground_frame": calibration["parent_frame"],
                "chassis_center_xy_m": center[:2].tolist(),
                "chassis_yaw_rad": yaw,
            }
        )
    )
    return 0


def cmd_self_test(_args):
    rng = np.random.RandomState(7)
    angle = 0.42
    rotation = np.array(
        [[math.cos(angle), -math.sin(angle), 0.0],
         [math.sin(angle), math.cos(angle), 0.0],
         [0.0, 0.0, 1.0]]
    )
    translation = np.array([1.2, -0.4, 0.08])
    camera = rng.uniform(-1.0, 1.0, size=(12, 3))
    ground = (rotation.dot(camera.T)).T + translation
    solved_r, solved_t, errors = solve_rigid(camera, ground)
    passed = (
        np.linalg.norm(solved_r - rotation) < 1e-9
        and np.linalg.norm(solved_t - translation) < 1e-9
        and float(np.max(errors)) < 1e-9
    )
    print(json.dumps({"ok": passed, "max_error_m": float(np.max(errors))}))
    return 0 if passed else 1


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--dataset", type=Path, required=True)
    init.set_defaults(handler=cmd_init)
    add = commands.add_parser("add")
    add.add_argument("--dataset", type=Path, required=True)
    for name in ("cx", "cy", "cz", "gx", "gy", "gz"):
        add.add_argument("--" + name, type=float, required=True)
    add.set_defaults(handler=cmd_add)
    status = commands.add_parser("status")
    status.add_argument("--dataset", type=Path, required=True)
    status.set_defaults(handler=cmd_status)
    solve = commands.add_parser("solve")
    solve.add_argument("--dataset", type=Path, required=True)
    solve.add_argument("--output", type=Path, required=True)
    solve.set_defaults(handler=cmd_solve)
    transform = commands.add_parser("transform")
    transform.add_argument("--calibration", type=Path, required=True)
    for name in ("x", "y", "z"):
        transform.add_argument("--" + name, type=float, required=True)
    transform.set_defaults(handler=cmd_transform)
    chassis = commands.add_parser("chassis")
    chassis.add_argument("--calibration", type=Path, required=True)
    for name in ("fx", "fy", "fz", "rx", "ry", "rz"):
        chassis.add_argument("--" + name, type=float, required=True)
    chassis.set_defaults(handler=cmd_chassis)
    commands.add_parser("self-test").set_defaults(handler=cmd_self_test)
    return result


def main():
    args = parser().parse_args()
    try:
        return int(args.handler(args))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
