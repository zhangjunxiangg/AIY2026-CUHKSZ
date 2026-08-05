from __future__ import annotations

import builtins
import socket
import unittest
from unittest import mock

import support  # noqa: F401

from student_tasks.errors import ControlFailure
from student_tasks.fake_backend import FakeBackend
from student_tasks.models import Velocity


class FakeBackendTests(unittest.TestCase):
    def test_virtual_clock_and_ordered_events_are_deterministic(self) -> None:
        backend = FakeBackend()
        self.assertEqual(0.0, backend.monotonic())
        backend.status()
        backend.acquire("op-1")
        backend.publish_velocity(Velocity(0.1, 0.0, 0.0))
        backend.sleep(0.25)
        backend.publish_velocity(Velocity(0.0, 0.0, 0.0))
        backend.release()

        self.assertEqual(0.25, backend.monotonic())
        self.assertEqual(list(range(1, 7)), [event.sequence for event in backend.events])
        self.assertEqual(
            ["status", "acquire", "velocity", "sleep", "velocity", "release"],
            [event.kind for event in backend.events],
        )

    def test_ownership_is_exclusive_and_release_is_idempotent(self) -> None:
        backend = FakeBackend()
        backend.acquire("first")
        with self.assertRaises(ControlFailure) as caught:
            backend.acquire("second")
        self.assertEqual("MOTION_BUSY", caught.exception.error.code)
        backend.release()
        backend.release()
        self.assertFalse(backend.owned)

    def test_injected_publish_failures_are_recorded_as_attempts(self) -> None:
        backend = FakeBackend(fail_nonzero_at=1, fail_zero=True)
        backend.acquire("op")
        with self.assertRaises(ControlFailure):
            backend.publish_velocity(Velocity(0.1, 0.0, 0.0))
        with self.assertRaises(ControlFailure):
            backend.publish_velocity(Velocity(0.0, 0.0, 0.0))
        velocity_events = [event for event in backend.events if event.kind == "velocity"]
        self.assertEqual([False, False], [event.metadata["accepted"] for event in velocity_events])

    def test_fake_operations_perform_no_file_or_network_io(self) -> None:
        backend = FakeBackend()
        with mock.patch.object(builtins, "open", side_effect=AssertionError("file I/O")), mock.patch.object(
            socket, "socket", side_effect=AssertionError("network I/O")
        ):
            backend.status()
            backend.acquire("op")
            backend.publish_velocity(Velocity(0.0, 0.0, 0.0))
            backend.sleep(0.1)
            backend.release()


if __name__ == "__main__":
    unittest.main()
