from __future__ import annotations

import math
import unittest

import support  # noqa: F401

from student_tasks.errors import ControlFailure
from student_tasks.limits import (
    MAX_ANGULAR_SPEED_RAD_S,
    MAX_DURATION_S,
    MAX_LINEAR_SPEED_M_S,
    MIN_DURATION_S,
    validate_duration,
    validate_operation_id,
    validate_publish_rate,
    validate_velocity_components,
)


class LimitTests(unittest.TestCase):
    def test_accepts_exact_hard_boundaries(self) -> None:
        validate_velocity_components(MAX_LINEAR_SPEED_M_S, 0.0, MAX_ANGULAR_SPEED_RAD_S)
        validate_velocity_components(0.12, 0.16, -MAX_ANGULAR_SPEED_RAD_S)
        self.assertEqual(MIN_DURATION_S, validate_duration(MIN_DURATION_S))
        self.assertEqual(MAX_DURATION_S, validate_duration(MAX_DURATION_S))

    def test_rejects_diagonal_planar_magnitude_above_limit(self) -> None:
        with self.assertRaisesRegex(ControlFailure, "planar") as caught:
            validate_velocity_components(0.20, 0.20, 0.0)
        self.assertEqual("LIMIT_EXCEEDED", caught.exception.error.code)

    def test_rejects_angular_and_duration_limits(self) -> None:
        for angular_z in (-0.50001, 0.50001):
            with self.subTest(angular_z=angular_z), self.assertRaises(ControlFailure):
                validate_velocity_components(0.0, 0.0, angular_z)
        for duration in (0.09999, 10.00001):
            with self.subTest(duration=duration), self.assertRaises(ControlFailure):
                validate_duration(duration)

    def test_rejects_non_finite_and_boolean_numbers(self) -> None:
        for value in (math.nan, math.inf, -math.inf, True, False):
            with self.subTest(value=value), self.assertRaises(ControlFailure) as caught:
                validate_velocity_components(value, 0.0, 0.0)
            self.assertEqual("INVALID_INPUT", caught.exception.error.code)

    def test_operation_id_is_nonempty_and_bounded(self) -> None:
        self.assertEqual("move-1", validate_operation_id("move-1"))
        for value in ("", "   ", "x" * 129, None, 4):
            with self.subTest(value=value), self.assertRaises(ControlFailure):
                validate_operation_id(value)

    def test_publish_rate_is_bounded(self) -> None:
        self.assertEqual(20.0, validate_publish_rate(20))
        for value in (1.99, 50.01, math.nan, True):
            with self.subTest(value=value), self.assertRaises(ControlFailure):
                validate_publish_rate(value)

    def test_domain_source_has_no_forbidden_interfaces(self) -> None:
        source_root = support.SOURCE_ROOT / "student_tasks"
        forbidden_parts = ("motor" + "_type", "set_" + "motor")
        for path in source_root.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for forbidden in forbidden_parts:
                self.assertNotIn(forbidden, text, path)


if __name__ == "__main__":
    unittest.main()
