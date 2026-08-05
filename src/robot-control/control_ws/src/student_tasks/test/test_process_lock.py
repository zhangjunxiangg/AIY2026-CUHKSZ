from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401

from student_tasks.process_lock import MotionLock


class MotionLockTests(unittest.TestCase):
    def test_lock_is_nonblocking_and_reports_bounded_owner_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "motion.lock")
            first = MotionLock(path, wall_clock=lambda: 100.0, pid=lambda: 101, identity="first")
            second = MotionLock(path, wall_clock=lambda: 101.0, pid=lambda: 202, identity="second")
            acquired = first.try_acquire("first-operation")
            contended = second.try_acquire("second-operation")
            self.assertTrue(acquired.acquired)
            self.assertTrue(first.held)
            self.assertFalse(contended.acquired)
            self.assertEqual("MOTION_BUSY", contended.code)
            self.assertEqual(101, contended.owner_metadata["pid"])
            self.assertEqual("first-operation", contended.owner_metadata["operation_id"])
            first.release()
            self.assertTrue(second.try_acquire("second-operation").acquired)
            second.release()

    def test_descriptor_is_held_for_lifetime_and_release_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = MotionLock(Path(directory, "motion.lock"), identity="owner")
            lock.try_acquire("operation")
            self.assertTrue(lock.held)
            self.assertTrue(lock.assert_held())
            self.assertIsNotNone(lock.descriptor)
            lock.release()
            lock.release()
            self.assertFalse(lock.held)
            self.assertIsNone(lock.descriptor)

    def test_unlocked_stale_record_does_not_block_new_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "motion.lock")
            path.write_text(json.dumps({"pid": 999, "operation_id": "stale"}), encoding="utf-8")
            lock = MotionLock(path, pid=lambda: 303, identity="new")
            result = lock.try_acquire("new-operation")
            self.assertTrue(result.acquired)
            self.assertEqual(303, json.loads(path.read_text(encoding="utf-8"))["pid"])
            lock.release()

    def test_release_never_unlinks_replaced_foreign_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "motion.lock")
            replacement = Path(directory, "replacement.lock")
            lock = MotionLock(path, identity="original")
            lock.try_acquire("operation")
            replacement.write_text(json.dumps({"identity": "foreign"}), encoding="utf-8")
            os.replace(replacement, path)
            lock.release()
            self.assertTrue(path.exists())
            self.assertEqual("foreign", json.loads(path.read_text(encoding="utf-8"))["identity"])

    def test_operation_metadata_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "motion.lock")
            lock = MotionLock(path, identity="bounded")
            with self.assertRaises(ValueError):
                lock.try_acquire("x" * 129)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
