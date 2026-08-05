from __future__ import annotations

import math
import unittest
from dataclasses import replace

import support  # noqa: F401

from student_tasks.configuration import ConfigurationProvenance
from student_tasks.models import Velocity, ZERO_VELOCITY
from student_tasks.safety import (
    LaserScanSnapshot,
    SafetyConfiguration,
    SafetyMonitor,
    SectorRule,
)


DIRECTIONS = ("front", "rear", "left", "right")


def configuration(*, min_samples: int = 3, reset_frames: int = 3) -> SafetyConfiguration:
    return SafetyConfiguration(
        sectors=(
            SectorRule("front", 0.0, 0.35, 0.40, min_samples),
            SectorRule("rear", math.pi, 0.35, 0.35, min_samples),
            SectorRule("left", math.pi / 2.0, 0.35, 0.35, min_samples),
            SectorRule("right", -math.pi / 2.0, 0.35, 0.35, min_samples),
        ),
        max_scan_age_s=0.25,
        future_tolerance_s=0.02,
        reset_clear_frames=reset_frames,
        provenance=ConfigurationProvenance("synthetic", "test safety configuration"),
    )


def clear_scan(*, observed_at: float = 10.0, distance: float = 2.0) -> LaserScanSnapshot:
    return LaserScanSnapshot(
        observed_at=observed_at,
        angle_min=-math.pi,
        angle_increment=math.pi / 18.0,
        range_min=0.05,
        range_max=8.0,
        ranges=(distance,) * 37,
    )


def scan_with_obstacle(direction: str, *, observed_at: float = 10.0) -> LaserScanSnapshot:
    scan = clear_scan(observed_at=observed_at)
    ranges = list(scan.ranges)
    indices = {"rear": 0, "right": 9, "front": 18, "left": 27}
    ranges[indices[direction]] = 0.20
    return replace(scan, ranges=tuple(ranges))


class ScanAndDirectionalSafetyTests(unittest.TestCase):
    def test_all_translation_direction_combinations_select_union(self) -> None:
        cases = (
            (Velocity(0.1, 0.0, 0.0), ("front",)),
            (Velocity(-0.1, 0.0, 0.0), ("rear",)),
            (Velocity(0.0, 0.1, 0.0), ("left",)),
            (Velocity(0.0, -0.1, 0.0), ("right",)),
            (Velocity(0.1, 0.1, 0.0), ("front", "left")),
            (Velocity(0.1, -0.1, 0.0), ("front", "right")),
            (Velocity(-0.1, 0.1, 0.0), ("rear", "left")),
            (Velocity(-0.1, -0.1, 0.0), ("rear", "right")),
        )
        for velocity, expected in cases:
            with self.subTest(velocity=velocity):
                decision = SafetyMonitor(configuration()).evaluate(velocity, clear_scan(), now=10.1)
                self.assertTrue(decision.allowed)
                self.assertEqual(expected, decision.required_sectors)
                self.assertEqual(expected, tuple(evidence.name for evidence in decision.sectors))

    def test_any_rotation_requires_all_swept_sectors(self) -> None:
        for velocity in (Velocity(0.0, 0.0, 0.2), Velocity(0.1, 0.0, -0.2)):
            with self.subTest(velocity=velocity):
                decision = SafetyMonitor(configuration()).evaluate(velocity, clear_scan(), now=10.1)
                self.assertTrue(decision.allowed)
                self.assertEqual(DIRECTIONS, decision.required_sectors)

    def test_wraparound_rear_sector_and_boundary_samples_are_counted(self) -> None:
        decision = SafetyMonitor(configuration(min_samples=4)).evaluate(
            Velocity(-0.1, 0.0, 0.0), clear_scan(), now=10.0
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(6, decision.sectors[0].sample_count)
        self.assertAlmostEqual(2.0, decision.sectors[0].minimum_m)

    def test_invalid_ranges_are_filtered_and_sample_deficiency_fails_closed(self) -> None:
        scan = clear_scan()
        ranges = list(scan.ranges)
        ranges[17:20] = [math.nan, 0.0, 99.0]
        decision = SafetyMonitor(configuration()).evaluate(
            Velocity(0.1, 0.0, 0.0), replace(scan, ranges=tuple(ranges)), now=10.1
        )
        self.assertFalse(decision.allowed)
        self.assertEqual("SCAN_INSUFFICIENT", decision.code)
        self.assertEqual(2, decision.sectors[0].sample_count)
        self.assertTrue(decision.latched)

    def test_stale_future_and_malformed_scan_metadata_fail_closed(self) -> None:
        base = clear_scan()
        malformed = (
            (replace(base, observed_at=9.0), 10.0, "SCAN_STALE"),
            (replace(base, observed_at=10.1), 10.0, "SCAN_FUTURE"),
            (replace(base, angle_increment=0.0), 10.0, "SCAN_INVALID"),
            (replace(base, range_min=8.0, range_max=1.0), 10.0, "SCAN_INVALID"),
            (replace(base, angle_increment=1.0), 10.0, "SCAN_INVALID"),
            (replace(base, ranges=()), 10.0, "SCAN_INVALID"),
        )
        for scan, now, expected_code in malformed:
            with self.subTest(expected_code=expected_code):
                decision = SafetyMonitor(configuration()).evaluate(Velocity(0.1, 0, 0), scan, now=now)
                self.assertFalse(decision.allowed)
                self.assertEqual(expected_code, decision.code)
                self.assertTrue(decision.latched)
                self.assertFalse(decision.sectors)

    def test_obstacle_uses_conservative_minimum_and_returns_evidence(self) -> None:
        decision = SafetyMonitor(configuration()).evaluate(
            Velocity(0.1, 0.0, 0.0), scan_with_obstacle("front"), now=10.1
        )
        self.assertFalse(decision.allowed)
        self.assertEqual("SECTOR_BLOCKED", decision.code)
        self.assertEqual(0.20, decision.sectors[0].minimum_m)
        self.assertEqual(0.40, decision.sectors[0].threshold_m)
        self.assertFalse(decision.sectors[0].clear)
        self.assertTrue(decision.latched)

    def test_zero_velocity_is_allowed_without_scan_and_does_not_clear_latch(self) -> None:
        monitor = SafetyMonitor(configuration())
        monitor.evaluate(Velocity(0.1, 0, 0), None, now=10.0)
        decision = monitor.evaluate(ZERO_VELOCITY, None, now=100.0)
        self.assertTrue(decision.allowed)
        self.assertEqual("ZERO_VELOCITY", decision.code)
        self.assertTrue(decision.latched)
        self.assertEqual((), decision.required_sectors)


class EmergencyStopLatchTests(unittest.TestCase):
    def test_clear_scans_without_reset_never_clear_latch(self) -> None:
        monitor = SafetyMonitor(configuration(reset_frames=2))
        first = monitor.evaluate(Velocity(0.1, 0, 0), scan_with_obstacle("front"), now=10.0)
        original_reason = first.latch_reason
        for index in range(5):
            decision = monitor.evaluate(Velocity(0.1, 0, 0), clear_scan(observed_at=11 + index), now=11 + index)
            self.assertEqual("ESTOP_LATCHED", decision.code)
            self.assertEqual(original_reason, decision.latch_reason)
        self.assertTrue(monitor.latched)

    def test_reset_requires_explicit_request_and_exact_consecutive_clear_frames(self) -> None:
        monitor = SafetyMonitor(configuration(reset_frames=3))
        monitor.evaluate(Velocity(0.1, 0, 0), None, now=10.0)

        no_request = monitor.observe_reset(clear_scan(observed_at=11.0), now=11.0)
        self.assertEqual("RESET_NOT_REQUESTED", no_request.code)
        self.assertTrue(no_request.latched)

        self.assertTrue(monitor.request_reset())
        for count in (1, 2):
            decision = monitor.observe_reset(clear_scan(observed_at=11.0 + count), now=11.0 + count)
            self.assertEqual("RESET_PENDING", decision.code)
            self.assertEqual(count, decision.clear_frames)
            self.assertTrue(decision.latched)
        complete = monitor.observe_reset(clear_scan(observed_at=14.0), now=14.0)
        self.assertEqual("RESET_COMPLETE", complete.code)
        self.assertFalse(complete.latched)
        self.assertFalse(monitor.latched)

    def test_invalid_or_blocked_reset_frame_resets_counter(self) -> None:
        monitor = SafetyMonitor(configuration(reset_frames=2))
        monitor.evaluate(Velocity(0.1, 0, 0), None, now=10.0)
        monitor.request_reset()
        first = monitor.observe_reset(clear_scan(observed_at=11.0), now=11.0)
        self.assertEqual(1, first.clear_frames)
        blocked = monitor.observe_reset(scan_with_obstacle("right", observed_at=12.0), now=12.0)
        self.assertEqual("RESET_BLOCKED", blocked.code)
        self.assertEqual(0, blocked.clear_frames)
        stale = monitor.observe_reset(clear_scan(observed_at=1.0), now=13.0)
        self.assertEqual("SCAN_STALE", stale.code)
        self.assertEqual(0, stale.clear_frames)
        again = monitor.observe_reset(clear_scan(observed_at=14.0), now=14.0)
        self.assertEqual(1, again.clear_frames)
        self.assertTrue(again.latched)

    def test_reset_when_clear_is_idempotent_and_never_starts_motion(self) -> None:
        monitor = SafetyMonitor(configuration())
        self.assertFalse(monitor.request_reset())
        decision = monitor.observe_reset(clear_scan(), now=10.0)
        self.assertEqual("ALREADY_CLEAR", decision.code)
        self.assertFalse(decision.allowed)
        self.assertFalse(decision.latched)


if __name__ == "__main__":
    unittest.main()
