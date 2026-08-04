from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

import support


class CliContractTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        environment = dict(os.environ)
        environment.pop("ROS_MASTER_URI", None)
        completed = subprocess.run(
            [sys.executable, str(support.SCRIPT_PATH), *arguments],
            cwd=support.PACKAGE_ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        lines = completed.stdout.strip().splitlines()
        self.assertEqual(1, len(lines), completed)
        payload = json.loads(lines[0])
        self.assertEqual("robot-control/v1", payload["schema"])
        self.assertEqual(set(payload), {
            "schema",
            "operation",
            "operation_id",
            "ok",
            "backend",
            "verification",
            "zero_velocity_attempted",
            "zero_velocity_confirmed",
            "elapsed_s",
            "data",
            "error",
        })
        return completed, payload

    def test_fake_status_is_one_success_object(self) -> None:
        completed, payload = self.run_cli("--backend", "fake", "status")
        self.assertEqual(0, completed.returncode)
        self.assertTrue(payload["ok"])
        self.assertEqual("fake", payload["backend"])
        self.assertEqual("OFFLINE_VERIFIED", payload["verification"])
        self.assertFalse(payload["zero_velocity_attempted"])

    def test_fake_move_and_stop_are_one_success_object_each(self) -> None:
        move_process, move = self.run_cli(
            "--backend",
            "fake",
            "move",
            "--linear-x",
            "0.10",
            "--linear-y",
            "0",
            "--angular-z",
            "0",
            "--duration",
            "0.10",
            "--operation-id",
            "cli-test",
        )
        self.assertEqual(0, move_process.returncode)
        self.assertTrue(move["ok"])
        self.assertEqual("cli-test", move["operation_id"])
        self.assertTrue(move["zero_velocity_confirmed"])

        stop_process, stop = self.run_cli("--backend", "fake", "stop")
        self.assertEqual(0, stop_process.returncode)
        self.assertTrue(stop["zero_velocity_confirmed"])

    def test_safety_validation_failure_uses_exit_two(self) -> None:
        completed, payload = self.run_cli(
            "--backend",
            "fake",
            "move",
            "--linear-x",
            "0.20",
            "--linear-y",
            "0.20",
            "--angular-z",
            "0",
            "--duration",
            "1",
        )
        self.assertEqual(2, completed.returncode)
        self.assertFalse(payload["ok"])
        self.assertEqual("LIMIT_EXCEEDED", payload["error"]["code"])
        self.assertFalse(payload["zero_velocity_attempted"])

    def test_malformed_syntax_still_produces_one_result(self) -> None:
        completed, payload = self.run_cli("--backend", "fake", "move", "--linear-x", "not-a-number")
        self.assertEqual(2, completed.returncode)
        self.assertEqual("INVALID_INPUT", payload["error"]["code"])
        self.assertIn("error", completed.stderr.lower())

    def test_missing_command_still_produces_one_result(self) -> None:
        completed, payload = self.run_cli("--backend", "fake")
        self.assertEqual(2, completed.returncode)
        self.assertEqual("INVALID_INPUT", payload["error"]["code"])

    def test_ros_selection_fails_closed_without_import_or_fallback(self) -> None:
        completed, payload = self.run_cli("--backend", "ros", "--config", "missing.json", "status")
        self.assertEqual(3, completed.returncode)
        self.assertFalse(payload["ok"])
        self.assertEqual("ros", payload["backend"])
        self.assertEqual("BACKEND_UNAVAILABLE", payload["error"]["code"])
        self.assertNotEqual("fake", payload["backend"])


if __name__ == "__main__":
    unittest.main()
