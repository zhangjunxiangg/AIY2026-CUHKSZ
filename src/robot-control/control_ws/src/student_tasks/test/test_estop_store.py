from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401

from student_tasks.estop_store import EstopStore


class EstopStoreTests(unittest.TestCase):
    def test_missing_state_is_latched_and_persists_after_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "estop.json")
            store = EstopStore(path, pid=lambda: 101)
            missing = store.read()
            self.assertTrue(missing.latched)
            self.assertEqual("ESTOP_STATE_MISSING", missing.trigger_code)
            stored = store.latch("SECTOR_BLOCKED", "front below clearance", now=10.0, safety_digest="abc")
            self.assertTrue(stored.latched)
            reread = EstopStore(path, pid=lambda: 202).read()
            self.assertEqual("SECTOR_BLOCKED", reread.trigger_code)
            self.assertEqual("abc", reread.last_safety_digest)

    def test_write_uses_atomic_replace_and_mode_0600(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "estop.json")
            store = EstopStore(path)
            with mock.patch("student_tasks.estop_store.os.replace", wraps=os.replace) as replace_call:
                store.latch("SCAN_STALE", "scan expired", now=10.0)
            self.assertEqual(1, replace_call.call_count)
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
            leftovers = [item.name for item in Path(directory).iterdir() if item != path]
            self.assertEqual([], leftovers)

    def test_corrupt_unreadable_or_wrong_schema_state_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "estop.json")
            store = EstopStore(path)
            path.write_text("{bad", encoding="utf-8")
            self.assertEqual("ESTOP_STATE_INVALID", store.read().trigger_code)
            path.write_text(json.dumps({"schema": "wrong", "latched": False}), encoding="utf-8")
            self.assertEqual("ESTOP_STATE_INVALID", store.read().trigger_code)
            with mock.patch.object(Path, "read_text", side_effect=PermissionError("denied")):
                self.assertEqual("ESTOP_STATE_INVALID", store.read().trigger_code)

    def test_reset_request_and_consecutive_progress_persist_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "estop.json")
            first = EstopStore(path, pid=lambda: 101)
            first.latch("SECTOR_BLOCKED", "blocked", now=10.0)
            requested = first.request_reset(now=11.0)
            self.assertTrue(requested.reset_requested)
            self.assertEqual(0, requested.clear_frames)

            second = EstopStore(path, pid=lambda: 202)
            one = second.advance_reset(clear=True, required_frames=2, now=12.0)
            self.assertTrue(one.latched)
            self.assertEqual(1, one.clear_frames)
            cleared = first.advance_reset(clear=True, required_frames=2, now=13.0)
            self.assertFalse(cleared.latched)
            self.assertFalse(cleared.reset_requested)
            self.assertEqual(0, cleared.clear_frames)

    def test_blocked_reset_frame_resets_counter_and_no_request_cannot_clear(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "estop.json")
            store = EstopStore(path)
            store.latch("SECTOR_BLOCKED", "blocked", now=10.0)
            no_request = store.advance_reset(clear=True, required_frames=2, now=11.0)
            self.assertTrue(no_request.latched)
            self.assertEqual(0, no_request.clear_frames)
            store.request_reset(now=12.0)
            store.advance_reset(clear=True, required_frames=2, now=13.0)
            blocked = store.advance_reset(clear=False, required_frames=2, now=14.0)
            self.assertTrue(blocked.latched)
            self.assertTrue(blocked.reset_requested)
            self.assertEqual(0, blocked.clear_frames)


if __name__ == "__main__":
    unittest.main()
