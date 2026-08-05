#!/usr/bin/env python3
"""Offline eye-to-hand calibration for an auxiliary camera and the arm base."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np


MIN_SAMPLES = 10


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def tf(rotation, translation):
    result = np.eye(4)
    result[:3, :3] = np.asarray(rotation, dtype=float).reshape(3, 3)
    result[:3, 3] = np.asarray(translation, dtype=float).reshape(3)
    return result


def tf_payload(value):
    return {
        "rotation_matrix": value[:3, :3].tolist(),
        "translation_m": value[:3, 3].tolist(),
    }


def tf_from(value):
    if "rotation_matrix" in value:
        return tf(value["rotation_matrix"], value["translation_m"])
    for key in ("base_to_gripper", "camera_to_marker", "transform"):
        if key in value:
            return tf_from(value[key])
    raise ValueError("transform JSON must contain rotation_matrix and translation_m")


def inv(value):
    result = np.eye(4)
    result[:3, :3] = value[:3, :3].T
    result[:3, 3] = -result[:3, :3].dot(value[:3, 3])
    return result


def angle_deg(rotation):
    cosine = max(-1.0, min(1.0, (float(np.trace(rotation)) - 1.0) * 0.5))
    return math.degrees(math.acos(cosine))


def average_rotation(values):
    u, _s, vt = np.linalg.svd(sum(values, np.zeros((3, 3))))
    result = u.dot(vt)
    if np.linalg.det(result) < 0:
        u[:, -1] *= -1
        result = u.dot(vt)
    return result


def empty():
    return {
        "schema_version": 1,
        "calibration_type": "aux_camera_eye_to_hand",
        "base_frame": "base_link",
        "camera_frame": "aux_camera_optical_frame",
        "marker_dictionary": "DICT_APRILTAG_36h11",
        "marker_id": 1,
        "marker_size_m": 0.035,
        "samples": [],
    }


def pose_span(samples):
    poses = [tf_from(item["base_to_gripper"]) for item in samples]
    translation = rotation = 0.0
    for index, left in enumerate(poses):
        for right in poses[index + 1:]:
            translation = max(
                translation, float(np.linalg.norm(left[:3, 3] - right[:3, 3]))
            )
            rotation = max(rotation, angle_deg(left[:3, :3].T.dot(right[:3, :3])))
    return translation, rotation


def residuals(samples, base_to_camera):
    implied = []
    for item in samples:
        base_to_gripper = tf_from(item["base_to_gripper"])
        camera_to_marker = tf_from(item["camera_to_marker"])
        implied.append(
            inv(base_to_gripper).dot(base_to_camera).dot(camera_to_marker)
        )
    mean_t = np.mean([value[:3, 3] for value in implied], axis=0)
    mean_r = average_rotation([value[:3, :3] for value in implied])
    translation = np.asarray(
        [np.linalg.norm(value[:3, 3] - mean_t) for value in implied]
    )
    rotation = np.asarray(
        [angle_deg(mean_r.T.dot(value[:3, :3])) for value in implied]
    )
    return {
        "translation_rmse_m": float(math.sqrt(np.mean(translation ** 2))),
        "translation_max_m": float(np.max(translation)),
        "rotation_rmse_deg": float(math.sqrt(np.mean(rotation ** 2))),
        "rotation_max_deg": float(np.max(rotation)),
        "estimated_gripper_to_marker": tf_payload(tf(mean_r, mean_t)),
    }


METHODS = [
    ("TSAI", cv2.CALIB_HAND_EYE_TSAI),
    ("PARK", cv2.CALIB_HAND_EYE_PARK),
    ("HORAUD", cv2.CALIB_HAND_EYE_HORAUD),
    ("ANDREFF", cv2.CALIB_HAND_EYE_ANDREFF),
    ("DANIILIDIS", cv2.CALIB_HAND_EYE_DANIILIDIS),
]


def solve_samples(samples):
    gripper_to_base = [inv(tf_from(item["base_to_gripper"])) for item in samples]
    camera_to_marker = [tf_from(item["camera_to_marker"]) for item in samples]
    candidates = []
    for name, method in METHODS:
        try:
            rotation, translation = cv2.calibrateHandEye(
                [value[:3, :3] for value in gripper_to_base],
                [value[:3, 3].reshape(3, 1) for value in gripper_to_base],
                [value[:3, :3] for value in camera_to_marker],
                [value[:3, 3].reshape(3, 1) for value in camera_to_marker],
                method=method,
            )
            solution = tf(rotation, np.asarray(translation).reshape(3))
            metrics = residuals(samples, solution)
            score = metrics["translation_rmse_m"] + math.radians(
                metrics["rotation_rmse_deg"]
            ) * 0.05
            if np.all(np.isfinite(solution)):
                candidates.append((score, name, solution, metrics))
        except Exception:
            pass
    if not candidates:
        raise RuntimeError("all hand-eye solvers failed")
    return min(candidates, key=lambda value: value[0])[1:]


def cmd_init(args):
    write(args.dataset, empty())
    print(json.dumps({"ok": True, "dataset": str(args.dataset)}))
    return 0


def cmd_detect(args):
    info = read(args.camera_info)
    matrix = np.asarray(info["K"], dtype=float).reshape(3, 3)
    distortion = np.asarray(info.get("D", []), dtype=float)
    image = cv2.imread(str(args.image))
    if image is None:
        raise RuntimeError("cannot read image")
    dictionary_id = getattr(cv2.aruco, args.dictionary)
    dictionary = cv2.aruco.Dictionary_get(dictionary_id)
    corners, ids, _ = cv2.aruco.detectMarkers(
        image, dictionary, parameters=cv2.aruco.DetectorParameters_create()
    )
    if ids is None or args.marker_id not in ids.flatten().tolist():
        raise RuntimeError("requested marker was not detected")
    selected = corners[ids.flatten().tolist().index(args.marker_id)]
    rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
        [selected], args.marker_size, matrix, distortion
    )
    rotation, _ = cv2.Rodrigues(rvecs[0, 0])
    result = {
        "camera_to_marker": tf_payload(tf(rotation, tvecs[0, 0])),
        "marker_dictionary": args.dictionary,
        "marker_id": args.marker_id,
        "marker_size_m": args.marker_size,
    }
    write(args.output, result)
    print(json.dumps({"ok": True, "output": str(args.output)}))
    return 0


def cmd_add(args):
    data = read(args.dataset) if args.dataset.exists() else empty()
    base_to_gripper = tf_from(read(args.arm_pose))
    camera_to_marker = tf_from(read(args.marker_pose))
    for item in data["samples"]:
        previous = tf_from(item["base_to_gripper"])
        if (
            np.linalg.norm(previous[:3, 3] - base_to_gripper[:3, 3]) < 0.02
            and angle_deg(previous[:3, :3].T.dot(base_to_gripper[:3, :3])) < 7.0
        ):
            raise RuntimeError("pose too similar; move >=2cm or rotate >=7deg")
    data["samples"].append(
        {
            "index": len(data["samples"]) + 1,
            "base_to_gripper": tf_payload(base_to_gripper),
            "camera_to_marker": tf_payload(camera_to_marker),
        }
    )
    write(args.dataset, data)
    print(json.dumps({"ok": True, "sample_count": len(data["samples"])}))
    return 0


def cmd_status(args):
    data = read(args.dataset) if args.dataset.exists() else empty()
    translation, rotation = (
        pose_span(data["samples"]) if len(data["samples"]) > 1 else (0.0, 0.0)
    )
    print(
        json.dumps(
            {
                "ok": True,
                "sample_count": len(data["samples"]),
                "minimum_samples": MIN_SAMPLES,
                "translation_span_m": translation,
                "rotation_span_deg": rotation,
                "ready_to_solve": (
                    len(data["samples"]) >= MIN_SAMPLES
                    and translation >= 0.08
                    and rotation >= 20.0
                ),
            }
        )
    )
    return 0


def cmd_solve(args):
    data = read(args.dataset)
    samples = data["samples"]
    translation, rotation = pose_span(samples)
    if len(samples) < MIN_SAMPLES or translation < 0.08 or rotation < 20.0:
        raise RuntimeError("need >=10 samples, >=0.08m translation and >=20deg rotation")
    method, solution, metrics = solve_samples(samples)
    passed = (
        metrics["translation_rmse_m"] <= 0.012
        and metrics["rotation_rmse_deg"] <= 3.0
    )
    result = {
        "schema_version": 1,
        "calibration_type": "aux_camera_eye_to_hand",
        "parent_frame": data["base_frame"],
        "child_frame": data["camera_frame"],
        "base_to_camera": tf_payload(solution),
        "solver": method,
        "sample_count": len(samples),
        "pose_translation_span_m": translation,
        "pose_rotation_span_deg": rotation,
        **metrics,
        "quality": "PASS" if passed else "REVIEW",
        "quality_limits": {
            "translation_rmse_m": 0.012,
            "rotation_rmse_deg": 3.0,
        },
    }
    write(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 2


def cmd_transform(args):
    calibration = read(args.calibration)
    point = tf_from(calibration["base_to_camera"]).dot(
        np.asarray([args.x, args.y, args.z, 1.0])
    )
    print(json.dumps({"ok": True, "base_point_m": point[:3].tolist()}))
    return 0


def random_tf(rng, scale):
    axis = rng.normal(size=3)
    axis /= np.linalg.norm(axis)
    rotation, _ = cv2.Rodrigues(axis * rng.uniform(-1.0, 1.0))
    return tf(rotation, rng.uniform(-scale, scale, size=3))


def cmd_self_test(_args):
    rng = np.random.RandomState(19)
    expected = random_tf(rng, 0.4)
    gripper_to_marker = random_tf(rng, 0.08)
    samples = []
    for index in range(18):
        base_to_gripper = random_tf(rng, 0.25)
        camera_to_marker = inv(expected).dot(base_to_gripper).dot(gripper_to_marker)
        samples.append(
            {
                "index": index + 1,
                "base_to_gripper": tf_payload(base_to_gripper),
                "camera_to_marker": tf_payload(camera_to_marker),
            }
        )
    _method, solved, _metrics = solve_samples(samples)
    t_error = float(np.linalg.norm(solved[:3, 3] - expected[:3, 3]))
    r_error = angle_deg(solved[:3, :3].T.dot(expected[:3, :3]))
    passed = t_error < 1e-5 and r_error < 1e-3
    print(json.dumps({"ok": passed, "translation_error_m": t_error,
                      "rotation_error_deg": r_error}))
    return 0 if passed else 1


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--dataset", type=Path, required=True)
    init.set_defaults(handler=cmd_init)
    detect = commands.add_parser("detect")
    detect.add_argument("--image", type=Path, required=True)
    detect.add_argument("--camera-info", type=Path, required=True)
    detect.add_argument("--output", type=Path, required=True)
    detect.add_argument("--dictionary", default="DICT_APRILTAG_36h11")
    detect.add_argument("--marker-id", type=int, default=1)
    detect.add_argument("--marker-size", type=float, default=0.035)
    detect.set_defaults(handler=cmd_detect)
    add = commands.add_parser("add")
    add.add_argument("--dataset", type=Path, required=True)
    add.add_argument("--arm-pose", type=Path, required=True)
    add.add_argument("--marker-pose", type=Path, required=True)
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
