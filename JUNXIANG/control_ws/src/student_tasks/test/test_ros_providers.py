from __future__ import annotations

import json
import math
import unittest

import support  # noqa: F401

from fake_ros import FakeBool, FakeHeader, FakeLaserScan, FakeRosFacade, FakeStamp, FakeString
from student_tasks.perception import BaseTargetObservation, PixelDepthObservation
from student_tasks.ros_providers import RosScanProvider, RosTargetProvider


NOW = 1_000.0


def scan_message(*, source_time: float = NOW) -> FakeLaserScan:
    return FakeLaserScan(
        FakeHeader(FakeStamp(source_time), "laser"),
        -math.pi,
        math.pi / 18.0,
        0.05,
        8.0,
        (1.0, float("nan"), 2.0),
    )


def base_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": "robot-control/target-observation/v1",
        "kind": "base_point",
        "observed_at": NOW,
        "frame_id": "base_link",
        "x": 0.7,
        "y": 0.1,
        "z": 0.2,
        "valid": True,
        "confidence": 0.9,
        "source": "vision-localizer-v1",
    }
    payload.update(changes)
    return payload


class RosScanProviderTests(unittest.TestCase):
    def test_preserves_raw_fields_source_time_and_receive_time(self) -> None:
        facade = FakeRosFacade(wall_time=NOW)
        facade.monotonic_seconds = 20.0
        provider = RosScanProvider(facade, "/scan", max_source_age_s=0.25, max_receive_age_s=0.20, future_tolerance_s=0.02)
        facade.emit("/scan", scan_message())

        envelope = provider.envelope()
        self.assertEqual(NOW, envelope.source_time)
        self.assertEqual(20.0, envelope.received_monotonic)
        self.assertEqual("laser", envelope.frame_id)
        self.assertEqual((1.0, float("nan"), 2.0)[::2], envelope.scan.ranges[::2])
        self.assertTrue(math.isnan(envelope.scan.ranges[1]))
        self.assertEqual(-math.pi, envelope.scan.angle_min)
        self.assertEqual(1, envelope.sequence)
        self.assertIsNone(envelope.error_code)

        domain = provider.latest(20.0)
        self.assertIsNotNone(domain)
        self.assertEqual(20.0, domain.observed_at)
        backend = provider.snapshot()
        self.assertIsNotNone(backend)
        self.assertEqual(NOW, backend.observed_at)

    def test_source_receive_future_and_malformed_messages_fail_closed(self) -> None:
        facade = FakeRosFacade(wall_time=NOW)
        provider = RosScanProvider(facade, "/scan", max_source_age_s=0.25, max_receive_age_s=0.20, future_tolerance_s=0.02)
        self.assertIsNone(provider.latest(0.0))
        self.assertEqual("SCAN_UNAVAILABLE", provider.diagnostics(0.0)["code"])

        facade.emit("/scan", scan_message(source_time=NOW - 1.0))
        self.assertIsNone(provider.latest(0.0))
        self.assertEqual("SCAN_SOURCE_STALE", provider.diagnostics(0.0)["code"])

        facade.emit("/scan", scan_message(source_time=NOW + 1.0))
        self.assertEqual("SCAN_SOURCE_FUTURE", provider.diagnostics(0.0)["code"])

        facade.emit("/scan", scan_message())
        facade.monotonic_seconds = 0.3
        self.assertEqual("SCAN_RECEIVE_STALE", provider.diagnostics(0.3)["code"])

        facade.emit("/scan", object())
        self.assertEqual("SCAN_MESSAGE_INVALID", provider.envelope().error_code)
        self.assertIsNone(provider.snapshot())


class RosTargetProviderTests(unittest.TestCase):
    def build(self) -> tuple[FakeRosFacade, RosTargetProvider]:
        facade = FakeRosFacade(wall_time=NOW)
        provider = RosTargetProvider(
            facade,
            "/competition/aux_target_json",
            "/competition/aux_target_valid",
            expected_schema="robot-control/target-observation/v1",
            max_source_age_s=0.25,
            max_receive_age_s=0.20,
            future_tolerance_s=0.02,
            min_confidence=0.6,
            expected_camera_frame="camera_optical_frame",
            calibration_source="hand-eye-record-001",
        )
        return facade, provider

    def emit(self, facade: FakeRosFacade, payload: object, *, valid: object = True) -> None:
        facade.emit("/competition/aux_target_valid", FakeBool(valid))
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        facade.emit("/competition/aux_target_json", FakeString(raw))

    def test_base_target_preserves_contract_validity_confidence_and_provenance(self) -> None:
        facade, provider = self.build()
        facade.monotonic_seconds = 12.0
        self.emit(facade, base_payload())
        envelope = provider.envelope()
        self.assertEqual(NOW, envelope.source_time)
        self.assertEqual(12.0, envelope.received_monotonic)
        self.assertEqual("vision-localizer-v1", envelope.source)
        self.assertEqual("hand-eye-record-001", envelope.calibration_source)
        self.assertTrue(envelope.valid_signal)
        self.assertEqual(1, envelope.sequence)
        observation = provider.latest(12.0)
        self.assertIsInstance(observation, BaseTargetObservation)
        self.assertEqual(12.0, observation.observed_at)
        self.assertEqual("base_link", observation.frame_id)
        self.assertEqual(0.9, observation.confidence)

    def test_pixel_depth_contract_is_converted_without_geometry_guessing(self) -> None:
        facade, provider = self.build()
        payload = {
            "schema": "robot-control/target-observation/v1",
            "kind": "pixel_depth",
            "observed_at": NOW,
            "frame_id": "camera_optical_frame",
            "u": 320.0,
            "v": 240.0,
            "depth_m": 0.8,
            "valid": True,
            "confidence": 0.95,
            "source": "depth-localizer-v1",
        }
        self.emit(facade, payload)
        observation = provider.latest(0.0)
        self.assertIsInstance(observation, PixelDepthObservation)
        self.assertEqual(0.8, observation.depth_m)

    def test_invalid_json_schema_fields_frame_confidence_and_validity_are_structured(self) -> None:
        cases = (
            ("{bad", True, "TARGET_JSON_INVALID"),
            (base_payload(schema="wrong/v1"), True, "TARGET_SCHEMA_INVALID"),
            (base_payload(frame_id="camera"), True, "TARGET_FRAME_INVALID"),
            (base_payload(confidence=None), True, "TARGET_CONFIDENCE_INVALID"),
            (base_payload(valid=False), True, "TARGET_VALIDITY_INVALID"),
            (base_payload(extra="not allowed"), True, "TARGET_CONTRACT_INVALID"),
            (base_payload(), False, "TARGET_VALID_SIGNAL_FALSE"),
        )
        for payload, valid, code in cases:
            with self.subTest(code=code):
                facade, provider = self.build()
                self.emit(facade, payload, valid=valid)
                self.assertIsNone(provider.latest(0.0))
                self.assertEqual(code, provider.diagnostics(0.0)["code"])

    def test_source_and_receive_staleness_fail_independently(self) -> None:
        facade, provider = self.build()
        self.emit(facade, base_payload(observed_at=NOW - 1.0))
        self.assertEqual("TARGET_SOURCE_STALE", provider.diagnostics(0.0)["code"])

        facade, provider = self.build()
        self.emit(facade, base_payload())
        facade.monotonic_seconds = 0.3
        self.assertEqual("TARGET_RECEIVE_STALE", provider.diagnostics(0.3)["code"])


if __name__ == "__main__":
    unittest.main()
