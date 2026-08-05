from __future__ import annotations

import signal
import tempfile
import unittest

import support  # noqa: F401

from student_tasks.signals import SignalCancellationGuard


class SignalCancellationGuardTests(unittest.TestCase):
    def test_installs_three_handlers_and_restores_previous_handlers(self) -> None:
        watched = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
        before = {number: signal.getsignal(number) for number in watched}
        guard = SignalCancellationGuard()
        with guard:
            self.assertTrue(guard.state.installed)
            self.assertFalse(guard.state.restored)
            for number in watched:
                self.assertEqual(guard.handle_signal, signal.getsignal(number))
        self.assertTrue(guard.state.restored)
        for number in watched:
            self.assertEqual(before[number], signal.getsignal(number))

    def test_first_signal_wins_and_all_supported_signals_cancel(self) -> None:
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(number=number):
                guard = SignalCancellationGuard()
                guard.handle_signal(number, None)
                guard.handle_signal(signal.SIGTERM, None)
                self.assertTrue(guard.is_cancelled())
                self.assertEqual(number, guard.state.signal_number)
                self.assertEqual(signal.Signals(number).name, guard.state.signal_name)

    def test_handler_changes_cancellation_state_only(self) -> None:
        guard = SignalCancellationGuard()
        before = guard.state
        guard.handle_signal(signal.SIGINT, object())
        after = guard.state
        self.assertFalse(before.cancelled)
        self.assertTrue(after.cancelled)
        self.assertFalse(after.installed)
        self.assertFalse(after.restored)

    def test_scope_cannot_be_entered_twice(self) -> None:
        guard = SignalCancellationGuard()
        with guard:
            with self.assertRaises(RuntimeError):
                guard.__enter__()

    def test_owned_motion_cancellation_for_each_signal_runs_final_stop(self) -> None:
        from student_tasks.core import MotionController
        from student_tasks.models import MotionRequest, Velocity
        from test_ros_backend import ready_backend

        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(number=number), tempfile.TemporaryDirectory() as directory:
                backend, facade, _ = ready_backend(directory)
                guard = SignalCancellationGuard()
                original_sleep = facade.sleep

                def cancelling_sleep(duration_s: float) -> None:
                    original_sleep(duration_s)
                    guard.handle_signal(number, None)

                facade.sleep = cancelling_sleep
                with guard:
                    result = MotionController(backend, zero_message_count=2).move(
                        MotionRequest("signal-%d" % number, Velocity(0.1, 0.0, 0.0), 0.2),
                        guard,
                    )
                self.assertFalse(result.ok)
                self.assertEqual("CANCELLED", result.error.code)
                self.assertTrue(result.zero_velocity_confirmed)
                messages = facade.created_publishers[0].messages
                self.assertEqual(1, sum(not message.linear.x == 0.0 for message in messages))
                self.assertEqual(2, sum(message.linear.x == 0.0 for message in messages))


if __name__ == "__main__":
    unittest.main()
