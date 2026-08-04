from __future__ import annotations

import json
import unittest

import support  # noqa: F401

from student_tasks.errors import ErrorCategory, control_error
from student_tasks.models import (
    BackendStatus,
    MotionRequest,
    MotionResult,
    Velocity,
    VerificationLevel,
)


class ModelTests(unittest.TestCase):
    def test_velocity_and_request_are_immutable_and_normalized(self) -> None:
        velocity = Velocity(0, -0.0, 0)
        request = MotionRequest("move-1", velocity, 0.1, 20)
        self.assertTrue(velocity.is_zero)
        self.assertEqual(0.0, velocity.linear_y)
        self.assertEqual(20.0, request.publish_rate_hz)
        with self.assertRaises((AttributeError, TypeError)):
            velocity.linear_x = 0.1  # type: ignore[misc]

    def test_backend_status_has_deterministic_serialization(self) -> None:
        status = BackendStatus(
            ready=False,
            backend="fake",
            production=False,
            configuration_kind="synthetic",
            blocking_reasons=("second", "first", "second"),
            details={"clock": "virtual"},
        )
        self.assertEqual(["second", "first"], status.to_dict()["blocking_reasons"])

    def test_result_serializes_to_stable_versioned_object(self) -> None:
        result = MotionResult(
            operation="move",
            operation_id="move-1",
            ok=False,
            backend="fake",
            verification=VerificationLevel.OFFLINE_VERIFIED,
            zero_velocity_attempted=True,
            zero_velocity_confirmed=True,
            elapsed_s=0.25,
            data={"events": 3},
            error=control_error("TIMEOUT", "deadline reached"),
        )
        payload = result.to_dict()
        self.assertEqual("robot-control/v1", payload["schema"])
        self.assertEqual("TIMEOUT", payload["error"]["code"])
        self.assertEqual(payload, json.loads(result.to_json()))

    def test_error_taxonomy_is_stable(self) -> None:
        expected = {
            "INVALID_INPUT": ErrorCategory.VALIDATION,
            "LIMIT_EXCEEDED": ErrorCategory.VALIDATION,
            "BACKEND_UNAVAILABLE": ErrorCategory.UNAVAILABLE,
            "PRODUCTION_CONFIG_REQUIRED": ErrorCategory.UNAVAILABLE,
            "MOTION_BUSY": ErrorCategory.UNAVAILABLE,
            "CANCELLED": ErrorCategory.RUNTIME,
            "TIMEOUT": ErrorCategory.RUNTIME,
            "BACKEND_FAILURE": ErrorCategory.RUNTIME,
            "STOP_FAILED": ErrorCategory.STOP_SAFETY,
        }
        for code, category in expected.items():
            with self.subTest(code=code):
                error = control_error(code, "detail")
                self.assertEqual(category, error.category)
                self.assertEqual(code, error.to_dict()["code"])


if __name__ == "__main__":
    unittest.main()
