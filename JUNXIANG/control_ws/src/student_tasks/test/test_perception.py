from __future__ import annotations

import math
import unittest

import support  # noqa: F401

from student_tasks.configuration import ConfigurationProvenance
from student_tasks.geometry import CameraIntrinsics, RigidTransform, Vector3
from student_tasks.perception import (
    BaseTargetObservation,
    CameraCalibration,
    PixelDepthObservation,
    TargetPolicy,
    normalize_target,
)


def policy() -> TargetPolicy:
    return TargetPolicy(max_target_age_s=0.25, future_tolerance_s=0.02, min_confidence=0.60)


def base_observation(**changes: object) -> BaseTargetObservation:
    values: dict[str, object] = {
        "observed_at": 10.0,
        "frame_id": "base_link",
        "x": 0.8,
        "y": 0.1,
        "z": 3.0,
        "valid": True,
        "confidence": 0.9,
        "source": "synthetic-base",
    }
    values.update(changes)
    return BaseTargetObservation(**values)


def pixel_observation(**changes: object) -> PixelDepthObservation:
    values: dict[str, object] = {
        "observed_at": 10.0,
        "frame_id": "camera_optical_frame",
        "u": 60.0,
        "v": 30.0,
        "depth_m": 1.0,
        "valid": True,
        "confidence": 0.9,
        "source": "synthetic-pixel",
    }
    values.update(changes)
    return PixelDepthObservation(**values)


def calibration(
    *,
    provenance: ConfigurationProvenance | None = None,
    calibrated_at: float = 10.0,
    max_age_s: float = 1.0,
) -> CameraCalibration:
    return CameraCalibration(
        camera_frame="camera_optical_frame",
        base_frame="base_link",
        intrinsics=CameraIntrinsics(100, 100, 50, 40, 100, 80),
        camera_to_base=RigidTransform(
            (0, 0, 1, -1, 0, 0, 0, -1, 0),
            Vector3(0.1, 0.0, 0.2),
        ),
        calibrated_at=calibrated_at,
        max_age_s=max_age_s,
        provenance=provenance or ConfigurationProvenance("synthetic", "test calibration"),
    )


class BaseTargetAdapterTests(unittest.TestCase):
    def test_base_point_normalizes_planar_geometry_and_keeps_z_as_height(self) -> None:
        result = normalize_target(base_observation(), now=10.1, policy=policy())
        self.assertTrue(result.ok)
        self.assertIsNotNone(result.target)
        target = result.target
        assert target is not None
        self.assertAlmostEqual(math.hypot(0.8, 0.1), target.planar_distance_m)
        self.assertAlmostEqual(math.atan2(0.1, 0.8), target.bearing_rad)
        self.assertEqual(3.0, target.z)
        self.assertNotEqual(target.z, target.planar_distance_m)
        self.assertIsNone(target.calibration_provenance)

    def test_base_point_rejects_stale_future_invalid_confidence_frame_and_coordinates(self) -> None:
        cases = (
            (base_observation(observed_at=9.0), "TARGET_STALE"),
            (base_observation(observed_at=10.2), "TARGET_STALE"),
            (base_observation(valid=False), "TARGET_INVALID"),
            (base_observation(confidence=0.5), "TARGET_INVALID"),
            (base_observation(confidence=1.1), "TARGET_INVALID"),
            (base_observation(frame_id="camera"), "TARGET_FRAME_INVALID"),
            (base_observation(x=math.nan), "TARGET_INVALID"),
            (base_observation(y=101.0), "TARGET_INVALID"),
            (base_observation(source=" "), "TARGET_INVALID"),
        )
        for observation, expected in cases:
            with self.subTest(expected=expected, observation=observation):
                result = normalize_target(observation, now=10.0, policy=policy())
                self.assertFalse(result.ok)
                self.assertIsNone(result.target)
                self.assertEqual(expected, result.code)


class PixelDepthAdapterTests(unittest.TestCase):
    def test_pixel_depth_unprojects_and_transforms_with_traceable_calibration(self) -> None:
        result = normalize_target(
            pixel_observation(), now=10.1, policy=policy(), calibration=calibration()
        )
        self.assertTrue(result.ok)
        target = result.target
        assert target is not None
        self.assertAlmostEqual(1.1, target.x, places=6)
        self.assertAlmostEqual(-0.1, target.y, places=6)
        self.assertAlmostEqual(0.3, target.z, places=6)
        self.assertAlmostEqual(math.hypot(1.1, -0.1), target.planar_distance_m, places=6)
        self.assertEqual("synthetic", target.calibration_provenance.kind)

    def test_pixel_depth_requires_calibration_and_matching_camera_frame(self) -> None:
        missing = normalize_target(pixel_observation(), now=10.0, policy=policy())
        self.assertEqual("CALIBRATION_REQUIRED", missing.code)
        wrong_frame = normalize_target(
            pixel_observation(frame_id="wrong_camera"),
            now=10.0,
            policy=policy(),
            calibration=calibration(),
        )
        self.assertEqual("TARGET_FRAME_INVALID", wrong_frame.code)

    def test_pixel_and_calibration_validity_failures_are_structured(self) -> None:
        invalid_pixels = (
            pixel_observation(depth_m=0.0),
            pixel_observation(depth_m=math.inf),
            pixel_observation(u=100.0),
            pixel_observation(v=-1.0),
            pixel_observation(valid=False),
        )
        for observation in invalid_pixels:
            with self.subTest(observation=observation):
                result = normalize_target(
                    observation, now=10.0, policy=policy(), calibration=calibration()
                )
                self.assertEqual("TARGET_INVALID", result.code)

        stale = normalize_target(
            pixel_observation(observed_at=20.0),
            now=20.0,
            policy=policy(),
            calibration=calibration(calibrated_at=10.0, max_age_s=1.0),
        )
        self.assertEqual("CALIBRATION_REQUIRED", stale.code)

    def test_synthetic_calibration_is_rejected_in_production_mode(self) -> None:
        result = normalize_target(
            pixel_observation(),
            now=10.0,
            policy=policy(),
            calibration=calibration(),
            production=True,
        )
        self.assertFalse(result.ok)
        self.assertEqual("CALIBRATION_REQUIRED", result.code)
        measured = calibration(
            provenance=ConfigurationProvenance("measured", "field calibration", 9.0)
        )
        accepted = normalize_target(
            pixel_observation(),
            now=10.0,
            policy=policy(),
            calibration=measured,
            production=True,
        )
        self.assertTrue(accepted.ok)


if __name__ == "__main__":
    unittest.main()
