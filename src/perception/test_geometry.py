#!/usr/bin/env python3
"""Offline sanity tests for geometry3d / blind_spot / target_3d_node."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from blind_spot import annotate_blind_spot, estimate_target_depth, is_depth_valid
from fusion_node import TargetFuser
from geometry3d import CameraExtrinsics, CameraIntrinsics
from target_3d_node import TargetLocalizer


def test_intrinsics():
    cam = CameraIntrinsics(fx=520.0, fy=520.0, cx=320.0, cy=240.0, width=640, height=480)
    pt = cam.pixel_to_camera(320, 240, 1.0)
    assert np.allclose(pt, [0.0, 0.0, 1.0]), f"center pixel failed: {pt}"
    pt2 = cam.pixel_to_camera(320 + 52, 240, 1.0)
    assert np.allclose(pt2, [0.1, 0.0, 1.0]), f"off-center failed: {pt2}"

    depth = cam.mono_depth_from_bbox([0, 0, 52, 52], real_width_m=0.05, real_height_m=0.05)
    assert depth is not None and abs(depth - 0.5) < 1e-6, f"mono depth failed: {depth}"
    print("[TEST] CameraIntrinsics OK")


def test_extrinsics():
    # base_link -> camera: translation [1, 0, 0], identity rotation.
    # Therefore camera -> base of point [0,0,1] should be [-1, 0, 1].
    extr = CameraExtrinsics(
        translation_m=np.array([1.0, 0.0, 0.0]),
        rotation_matrix=np.eye(3),
    )
    pt = extr.camera_to_base(np.array([0.0, 0.0, 1.0]))
    assert np.allclose(pt, [-1.0, 0.0, 1.0]), f"camera_to_base failed: {pt}"

    # Round-trip via the official JSON format.
    data = {
        "base_to_camera": {
            "translation_m": [1.0, 0.0, 0.0],
            "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        }
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        tmp = f.name
    extr2 = CameraExtrinsics.from_json_file(tmp)
    pt2 = extr2.camera_to_base(np.array([0.0, 0.0, 1.0]))
    assert np.allclose(pt2, [-1.0, 0.0, 1.0]), f"json load failed: {pt2}"
    Path(tmp).unlink(missing_ok=True)
    print("[TEST] CameraExtrinsics OK")


def test_blind_spot():
    config = {
        "blind_spot": {
            "enable": True,
            "min_valid_mm": 600,
            "max_valid_mm": 8000,
            "horizon_y": 320,
            "mono_size": {
                "red_block": {"width_m": 0.05, "height_m": 0.05},
            },
        }
    }
    cam = CameraIntrinsics(fx=520.0, fy=520.0, cx=320.0, cy=240.0)

    assert is_depth_valid(650, 600, 8000)
    assert not is_depth_valid(None, 600, 8000)
    assert not is_depth_valid(500, 600, 8000)

    target = {
        "category": "red_block",
        "center": [320, 400],
        "confidence": 0.9,
        "bbox": [294, 374, 52, 52],
        "depth_mm": None,
    }
    depth_m, src = estimate_target_depth(target, cam, config)
    assert src == "mono", f"expected mono, got {src}"
    assert depth_m is not None and abs(depth_m - 0.5) < 1e-6, f"mono depth wrong: {depth_m}"

    targets = annotate_blind_spot([dict(target)], config)
    assert targets[0]["blind_spot"] is True, "blind_spot flag not set"
    print("[TEST] blind_spot OK")


def test_localizer():
    config = {
        "camera": {
            "astra": {
                "intrinsics": {"fx": 520.0, "fy": 520.0, "cx": 320.0, "cy": 240.0},
                "extrinsics_json": "",
            }
        },
        "blind_spot": {
            "enable": True,
            "mono_size": {"red_block": {"width_m": 0.05, "height_m": 0.05}},
        },
    }
    localizer = TargetLocalizer(config, "astra")
    # No extrinsics configured -> base_center_m should be None, but camera_point_m present.
    targets = {
        "targets": [
            {
                "category": "red_block",
                "center": [320, 240],
                "confidence": 0.9,
                "bbox": [294, 214, 52, 52],
                "depth_mm": 650,
            }
        ]
    }
    result = localizer.localize(targets)
    assert result["status"] == "ok"
    assert "stamp" in result and "ts" in result
    t = result["targets"][0]
    assert t["depth_m"] == 0.65 and t["depth_source"] == "camera"
    assert t["precision"] == "high"
    assert t["object_size_m"] == {"width_m": 0.05, "height_m": 0.05}
    assert t["camera_point_m"] == [0.0, 0.0, 0.65]
    assert t["base_center_m"] is None
    print("[TEST] TargetLocalizer OK")


def test_fuser():
    config = {"fusion": {"radius_m": 0.12, "prefer_aux_for_blind_spot": True}}
    fuser = TargetFuser(config)

    astra = {
        "targets": [
            {
                "category": "red_block",
                "center": [320, 400],
                "confidence": 0.9,
                "bbox": [294, 374, 52, 52],
                "depth_mm": None,
                "depth_m": 0.5,
                "depth_source": "mono",
                "blind_spot": True,
                "base_center_m": [0.5, 0.0, 0.1],
            },
            {
                "category": "cone",
                "center": [100, 100],
                "confidence": 0.8,
                "bbox": [80, 60, 40, 80],
                "depth_mm": 700,
                "depth_m": 0.7,
                "depth_source": "camera",
                "base_center_m": [0.3, 0.2, 0.0],
            },
        ]
    }
    aux = {
        "targets": [
            {
                "category": "red_block",
                "center": [300, 350],
                "confidence": 0.95,
                "bbox": [280, 320, 40, 40],
                "depth_mm": 480,
                "depth_m": 0.48,
                "depth_source": "camera",
                "base_center_m": [0.51, 0.01, 0.1],
            },
            {
                "category": "green_ball",
                "center": [200, 200],
                "confidence": 0.9,
                "bbox": [180, 180, 40, 40],
                "depth_mm": 500,
                "depth_m": 0.5,
                "depth_source": "camera",
                "base_center_m": [0.4, -0.1, 0.05],
            },
        ]
    }

    result = fuser.fuse(astra, aux)
    cats = {t["category"] for t in result["targets"]}
    assert "red_block" in cats and "cone" in cats and "green_ball" in cats
    # The mono astra red_block should be replaced by the aux camera version.
    red = [t for t in result["targets"] if t["category"] == "red_block"][0]
    assert red["depth_source"] == "camera", f"expected aux camera depth, got {red}"
    print("[TEST] TargetFuser OK")


if __name__ == "__main__":
    test_intrinsics()
    test_extrinsics()
    test_blind_spot()
    test_localizer()
    test_fuser()
    print("[TEST] ALL PASSED")
