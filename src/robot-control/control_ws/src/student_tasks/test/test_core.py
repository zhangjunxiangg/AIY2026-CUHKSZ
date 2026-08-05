from __future__ import annotations

import unittest

import support  # noqa: F401

from student_tasks.backend import Cancellation
from student_tasks.core import MotionController
from student_tasks.fake_backend import FakeBackend
from student_tasks.models import MotionRequest, Velocity


class TimedCancellation(Cancellation):
    def __init__(self, backend: FakeBackend, at_s: float) -> None:
        self.backend = backend
        self.at_s = at_s

    def is_cancelled(self) -> bool:
        return self.backend.monotonic() >= self.at_s


def request(duration_s: float = 0.20, rate_hz: float = 20.0) -> MotionRequest:
    return MotionRequest("move-1", Velocity(0.10, 0.0, 0.0), duration_s, rate_hz)


class MotionControllerMoveTests(unittest.TestCase):
    def test_success_publishes_bounded_velocity_then_zero_before_release(self) -> None:
        backend = FakeBackend()
        result = MotionController(backend).move(request(duration_s=0.10))

        self.assertTrue(result.ok)
        self.assertTrue(result.zero_velocity_attempted)
        self.assertTrue(result.zero_velocity_confirmed)
        velocity_events = [event for event in backend.events if event.kind == "velocity"]
        self.assertGreaterEqual(sum(not event.velocity.is_zero for event in velocity_events), 1)
        self.assertEqual(3, sum(event.velocity.is_zero for event in velocity_events))
        self.assertTrue(velocity_events[-1].velocity.is_zero)
        self.assertLess(
            max(event.sequence for event in velocity_events),
            next(event.sequence for event in backend.events if event.kind == "release"),
        )

    def test_unavailable_backend_rejects_before_ownership_and_nonzero_output(self) -> None:
        backend = FakeBackend(ready=False, blocking_reasons=("scan unavailable",))
        result = MotionController(backend).move(request())
        self.assertFalse(result.ok)
        self.assertEqual("BACKEND_UNAVAILABLE", result.error.code)
        self.assertFalse(result.zero_velocity_attempted)
        self.assertFalse(any(event.kind == "acquire" for event in backend.events))
        self.assertFalse(backend.nonzero_events)

    def test_production_requires_measured_configuration(self) -> None:
        backend = FakeBackend(production=True, configuration_kind="synthetic")
        result = MotionController(backend).move(request())
        self.assertEqual("PRODUCTION_CONFIG_REQUIRED", result.error.code)
        self.assertFalse(backend.nonzero_events)

    def test_cancellation_after_ownership_stops_and_releases(self) -> None:
        backend = FakeBackend()
        result = MotionController(backend).move(request(), TimedCancellation(backend, 0.05))
        self.assertEqual("CANCELLED", result.error.code)
        self.assertTrue(result.zero_velocity_confirmed)
        self.assertFalse(backend.owned)
        self.assertTrue([event for event in backend.events if event.kind == "velocity"][-1].velocity.is_zero)

    def test_timeout_stops_and_releases(self) -> None:
        backend = FakeBackend()
        result = MotionController(backend).move(request(duration_s=1.0), timeout_s=0.11)
        self.assertEqual("TIMEOUT", result.error.code)
        self.assertTrue(result.zero_velocity_confirmed)
        self.assertFalse(backend.owned)

    def test_backend_exception_still_stops(self) -> None:
        backend = FakeBackend(fail_nonzero_at=2)
        result = MotionController(backend).move(request())
        self.assertEqual("BACKEND_FAILURE", result.error.code)
        self.assertTrue(result.zero_velocity_attempted)
        self.assertTrue(result.zero_velocity_confirmed)
        self.assertFalse(backend.owned)

    def test_stop_failure_takes_precedence_and_retains_original_error(self) -> None:
        backend = FakeBackend(fail_nonzero_at=2, fail_zero=True)
        result = MotionController(backend).move(request())
        self.assertEqual("STOP_FAILED", result.error.code)
        self.assertTrue(result.zero_velocity_attempted)
        self.assertFalse(result.zero_velocity_confirmed)
        self.assertEqual("BACKEND_FAILURE", result.data["original_error"]["code"])
        self.assertEqual(3, result.data["stop_attempts"])
        self.assertFalse(backend.owned)

    def test_zero_velocity_move_still_runs_duration_and_final_stop(self) -> None:
        backend = FakeBackend()
        zero_request = MotionRequest("zero-move", Velocity(0.0, 0.0, 0.0), 0.1)
        result = MotionController(backend).move(zero_request)
        self.assertTrue(result.ok)
        self.assertTrue(result.zero_velocity_confirmed)
        self.assertTrue(all(event.velocity.is_zero for event in backend.velocity_events))


class MotionControllerStatusStopTests(unittest.TestCase):
    def test_status_is_read_only_and_reports_not_ready_without_moving(self) -> None:
        backend = FakeBackend(ready=False, blocking_reasons=("not calibrated",))
        result = MotionController(backend).status()
        self.assertTrue(result.ok)
        self.assertFalse(result.data["status"]["ready"])
        self.assertEqual(["status"], [event.kind for event in backend.events])
        self.assertFalse(backend.velocity_events)

    def test_status_backend_failure_is_structured(self) -> None:
        backend = FakeBackend(fail_status=True)
        result = MotionController(backend).status()
        self.assertFalse(result.ok)
        self.assertEqual("BACKEND_FAILURE", result.error.code)
        self.assertFalse(result.zero_velocity_attempted)

    def test_repeated_stop_is_zero_only_even_when_backend_not_ready(self) -> None:
        backend = FakeBackend(ready=False)
        controller = MotionController(backend)
        first = controller.stop()
        second = controller.stop()
        self.assertTrue(first.ok)
        self.assertTrue(second.ok)
        self.assertEqual(6, len(backend.zero_events))
        self.assertFalse(backend.nonzero_events)
        self.assertFalse(any(event.kind in {"status", "acquire"} for event in backend.events))

    def test_stop_failure_is_reported(self) -> None:
        backend = FakeBackend(fail_zero=True)
        result = MotionController(backend).stop()
        self.assertFalse(result.ok)
        self.assertEqual("STOP_FAILED", result.error.code)
        self.assertTrue(result.zero_velocity_attempted)
        self.assertFalse(result.zero_velocity_confirmed)
        self.assertEqual(3, result.data["stop_attempts"])


if __name__ == "__main__":
    unittest.main()
