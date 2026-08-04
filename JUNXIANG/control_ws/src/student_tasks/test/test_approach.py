from __future__ import annotations

import math
import subprocess
import unittest
from unittest import mock

import support  # noqa: F401

from student_tasks.approach import ApproachConfiguration, ApproachController, ApproachState
from student_tasks.configuration import ConfigurationProvenance
from student_tasks.core import MotionController
from student_tasks.fake_backend import FakeBackend
from student_tasks.perception import BaseTargetObservation, TargetPolicy
from student_tasks.safety import LaserScanSnapshot, SafetyConfiguration, SafetyMonitor, SectorRule


def fresh_target(now: float, x: float, y: float, z: float = 0.2) -> BaseTargetObservation:
    return BaseTargetObservation(now, "base_link", x, y, z, True, 0.9, "scripted-vision")


def fresh_scan(now: float, *, blocked: bool = False) -> LaserScanSnapshot:
    ranges = [2.0] * 37
    if blocked:
        ranges[18] = 0.2
    return LaserScanSnapshot(
        now,
        -math.pi,
        math.pi / 18.0,
        0.05,
        8.0,
        tuple(ranges),
    )


class ScriptedTargets:
    def __init__(self, values: list[tuple[float, float] | BaseTargetObservation | None]) -> None:
        self.values = list(values)
        self.calls = 0

    def latest(self, now: float) -> BaseTargetObservation | None:
        self.calls += 1
        if not self.values:
            return None
        value = self.values.pop(0)
        if value is None or isinstance(value, BaseTargetObservation):
            return value
        return fresh_target(now, value[0], value[1])


class ScriptedScans:
    def __init__(self, blocked: list[bool] | None = None) -> None:
        self.blocked = list(blocked or [])
        self.calls = 0

    def latest(self, now: float) -> LaserScanSnapshot:
        self.calls += 1
        is_blocked = self.blocked.pop(0) if self.blocked else False
        return fresh_scan(now, blocked=is_blocked)


class AlwaysCancelled:
    def is_cancelled(self) -> bool:
        return True


def safety_configuration() -> SafetyConfiguration:
    return SafetyConfiguration(
        sectors=(
            SectorRule("front", 0.0, 0.35, 0.4, 3),
            SectorRule("rear", math.pi, 0.35, 0.35, 3),
            SectorRule("left", math.pi / 2.0, 0.35, 0.35, 3),
            SectorRule("right", -math.pi / 2.0, 0.35, 0.35, 3),
        ),
        max_scan_age_s=0.25,
        future_tolerance_s=0.02,
        reset_clear_frames=3,
        provenance=ConfigurationProvenance("synthetic", "approach test safety"),
    )


def approach_configuration(**changes: object) -> ApproachConfiguration:
    values: dict[str, object] = {
        "linear_speed_mps": 0.10,
        "angular_speed_radps": 0.20,
        "correction_duration_s": 0.10,
        "bearing_tolerance_rad": 0.08,
        "stand_off_m": 0.45,
        "stand_off_tolerance_m": 0.03,
        "stable_frames": 2,
        "target_loss_limit": 1,
        "timeout_s": 5.0,
        "max_iterations": 20,
        "observation_interval_s": 0.01,
        "publish_rate_hz": 20.0,
        "provenance": ConfigurationProvenance("synthetic", "approach test configuration"),
    }
    values.update(changes)
    return ApproachConfiguration(**values)


def build(
    targets: ScriptedTargets,
    scans: ScriptedScans,
    *,
    backend: FakeBackend | None = None,
    configuration: ApproachConfiguration | None = None,
) -> tuple[ApproachController, FakeBackend, SafetyMonitor]:
    selected_backend = backend or FakeBackend()
    safety = SafetyMonitor(safety_configuration())
    controller = ApproachController(
        motion=MotionController(selected_backend),
        safety=safety,
        targets=targets,
        scans=scans,
        configuration=configuration or approach_configuration(),
        target_policy=TargetPolicy(0.25, 0.02, 0.6),
    )
    return controller, selected_backend, safety


class ApproachSuccessAndOrderingTests(unittest.TestCase):
    def test_convergent_approach_rotates_translates_and_requires_two_visual_confirmations(self) -> None:
        targets = ScriptedTargets([(0.8, 0.2), (0.7, 0.01), (0.46, 0.01), (0.45, 0.0)])
        scans = ScriptedScans()
        controller, backend, _ = build(targets, scans)

        with mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess motion")):
            result = controller.run("approach-success")

        self.assertTrue(result.ok)
        self.assertEqual(ApproachState.SUCCEEDED, result.terminal_state)
        self.assertEqual(
            (
                ApproachState.PRECHECK,
                ApproachState.ROTATE,
                ApproachState.PRECHECK,
                ApproachState.TRANSLATE,
                ApproachState.PRECHECK,
                ApproachState.VERIFY,
                ApproachState.PRECHECK,
                ApproachState.VERIFY,
                ApproachState.STOPPING,
                ApproachState.SUCCEEDED,
            ),
            result.state_history,
        )
        self.assertEqual(2, len(result.corrections))
        first_velocity = result.corrections[0].data["request"]["velocity"]
        second_velocity = result.corrections[1].data["request"]["velocity"]
        self.assertGreater(first_velocity["angular_z"], 0.0)
        self.assertEqual(0.0, first_velocity["linear_x"])
        self.assertGreater(second_velocity["linear_x"], 0.0)
        self.assertEqual(0.0, second_velocity["linear_y"])
        self.assertEqual(4, targets.calls)
        self.assertEqual(2, scans.calls)
        self.assertTrue(result.stop_result.zero_velocity_confirmed)
        self.assertTrue(backend.zero_events)

    def test_negative_bearing_rotates_clockwise_and_never_translates_backward(self) -> None:
        targets = ScriptedTargets([(0.8, -0.2), (0.45, 0.0), (0.45, 0.0)])
        controller, backend, _ = build(targets, ScriptedScans())
        result = controller.run("negative-bearing")
        self.assertTrue(result.ok)
        requested = [correction.data["request"]["velocity"] for correction in result.corrections]
        self.assertLess(requested[0]["angular_z"], 0.0)
        self.assertTrue(all(velocity["linear_x"] >= 0.0 for velocity in requested))
        self.assertTrue(all(event.velocity.linear_x >= 0.0 for event in backend.nonzero_events))

    def test_too_close_target_is_refused_without_nonzero_output(self) -> None:
        targets = ScriptedTargets([(0.30, 0.0)])
        controller, backend, _ = build(targets, ScriptedScans())
        result = controller.run("too-close")
        self.assertFalse(result.ok)
        self.assertEqual("TARGET_TOO_CLOSE", result.error_code)
        self.assertEqual(ApproachState.FAILED, result.terminal_state)
        self.assertFalse(backend.nonzero_events)
        self.assertTrue(result.stop_result.zero_velocity_attempted)


class ApproachTerminalFailureTests(unittest.TestCase):
    def test_target_loss_uses_bounded_grace_then_stops(self) -> None:
        targets = ScriptedTargets([None, None, (0.45, 0.0)])
        controller, backend, _ = build(targets, ScriptedScans())
        result = controller.run("target-loss")
        self.assertEqual("TARGET_UNAVAILABLE", result.error_code)
        self.assertEqual(2, targets.calls)
        self.assertFalse(backend.nonzero_events)
        self.assertTrue(result.stop_result.zero_velocity_confirmed)

    def test_odometry_or_elapsed_commands_cannot_replace_visual_confirmations(self) -> None:
        targets = ScriptedTargets([(0.45, 0.0), None, None])
        controller, _, _ = build(targets, ScriptedScans())
        result = controller.run("vision-only-arrival")
        self.assertFalse(result.ok)
        self.assertEqual("TARGET_UNAVAILABLE", result.error_code)
        self.assertIn(ApproachState.VERIFY, result.state_history)
        self.assertLess(result.stable_frames, 2)

    def test_blocked_safety_latches_estop_before_motion(self) -> None:
        targets = ScriptedTargets([(0.8, 0.0)])
        controller, backend, safety = build(targets, ScriptedScans([True]))
        result = controller.run("blocked")
        self.assertEqual(ApproachState.ESTOPPED, result.terminal_state)
        self.assertEqual("SAFETY_REJECTED", result.error_code)
        self.assertTrue(safety.latched)
        self.assertEqual("SECTOR_BLOCKED", result.last_safety.code)
        self.assertFalse(backend.nonzero_events)
        self.assertTrue(result.stop_result.zero_velocity_confirmed)

    def test_cancellation_stops_before_reading_providers(self) -> None:
        targets = ScriptedTargets([(0.8, 0.0)])
        controller, backend, _ = build(targets, ScriptedScans())
        result = controller.run("cancelled", AlwaysCancelled())
        self.assertEqual(ApproachState.CANCELLED, result.terminal_state)
        self.assertEqual("CANCELLED", result.error_code)
        self.assertEqual(0, targets.calls)
        self.assertFalse(backend.nonzero_events)
        self.assertTrue(result.stop_result.zero_velocity_confirmed)

    def test_total_timeout_and_iteration_limit_are_deterministic(self) -> None:
        many_targets = [(0.45, 0.0)] * 20
        timeout_controller, _, _ = build(
            ScriptedTargets(list(many_targets)),
            ScriptedScans(),
            configuration=approach_configuration(stable_frames=100, timeout_s=0.025),
        )
        timeout = timeout_controller.run("timeout")
        self.assertEqual("APPROACH_TIMEOUT", timeout.error_code)

        iteration_controller, _, _ = build(
            ScriptedTargets(list(many_targets)),
            ScriptedScans(),
            configuration=approach_configuration(stable_frames=100, max_iterations=2),
        )
        iteration = iteration_controller.run("iteration")
        self.assertEqual("ITERATION_LIMIT", iteration.error_code)

    def test_motion_backend_failure_is_retained_and_final_stop_runs(self) -> None:
        backend = FakeBackend(fail_nonzero_at=1)
        controller, _, _ = build(ScriptedTargets([(0.8, 0.0)]), ScriptedScans(), backend=backend)
        result = controller.run("motion-failure")
        self.assertEqual("MOTION_FAILED", result.error_code)
        self.assertEqual("BACKEND_FAILURE", result.original_error_code)
        self.assertEqual(1, len(result.corrections))
        self.assertTrue(result.stop_result.zero_velocity_confirmed)

    def test_final_stop_failure_takes_precedence_and_retains_original_error(self) -> None:
        backend = FakeBackend(fail_zero=True)
        controller, _, _ = build(ScriptedTargets([(0.30, 0.0)]), ScriptedScans(), backend=backend)
        result = controller.run("stop-failure")
        self.assertEqual(ApproachState.FAILED, result.terminal_state)
        self.assertEqual("STOP_FAILED", result.error_code)
        self.assertEqual("TARGET_TOO_CLOSE", result.original_error_code)
        self.assertTrue(result.stop_result.zero_velocity_attempted)
        self.assertFalse(result.stop_result.zero_velocity_confirmed)


if __name__ == "__main__":
    unittest.main()
