from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from io import StringIO
from unittest import mock

import support

from fake_ros import FakeBool, FakeRosFacade, FakeString
from student_tasks.estop_store import EstopStore
from student_tasks.process_lock import MotionLock
from student_tasks.production_config import ConfigurationValidation
from student_tasks.ros_facade import RosFacadeUnavailable
from student_tasks.signals import SignalCancellationGuard
from test_production_config import NOW
from test_ros_backend import clear_estop, measured_config
from test_ros_providers import base_payload, scan_message


class SeededRosFacade(FakeRosFacade):
    def __init__(self, *, scan_messages: list[object] | None = None, target: bool = False) -> None:
        super().__init__(wall_time=NOW)
        self.scan_messages = list(scan_messages or [clear_scan_message()])
        self.target = target
        self.lock_observations: list[bool] = []
        self.observed_lock_path: str | None = None

    def subscribe(self, topic: str, callback: object, message_kind: str = "string") -> object:
        subscription = super().subscribe(topic, callback, message_kind)
        if message_kind == "laser_scan" and self.scan_messages:
            callback(self.scan_messages.pop(0))
        elif message_kind == "bool" and self.target:
            callback(FakeBool(True))
        elif message_kind == "string" and self.target:
            callback(FakeString(json.dumps(base_payload(x=0.45, y=0.0))))
        return subscription

    def sleep(self, duration_s: float) -> None:
        super().sleep(duration_s)
        if self.observed_lock_path is not None:
            self.lock_observations.append(MotionLock(self.observed_lock_path).probe().acquired)
        if self.scan_messages:
            self.emit("/scan", self.scan_messages.pop(0))


def clear_scan_message(*, source_time: float = NOW) -> object:
    return replace(
        scan_message(source_time=source_time),
        angle_increment=math.pi / 36.0,
        ranges=(1.0,) * 73,
    )


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
        self.assertEqual("PRODUCTION_CONFIG_REQUIRED", payload["error"]["code"])
        self.assertNotEqual("fake", payload["backend"])

    def run_ros_main(
        self,
        arguments: list[str],
        *,
        config: object,
        facade: FakeRosFacade | None,
        cancellation: object | None = None,
        loader_error: Exception | None = None,
    ) -> tuple[int, dict[str, object], str]:
        from student_tasks import cli

        output = StringIO()
        diagnostics = StringIO()
        validation = ConfigurationValidation((), config)
        if loader_error is None:
            facade_loader = mock.Mock(return_value=facade)
        else:
            facade_loader = mock.Mock(side_effect=loader_error)
        with mock.patch.object(cli, "load_production_config", return_value=validation), mock.patch.object(
            cli, "load_ros_facade", facade_loader
        ):
            exit_code = cli.main(
                arguments,
                stdout=output,
                stderr=diagnostics,
                cancellation=cancellation,
                wall_clock=lambda: NOW,
            )
        lines = output.getvalue().strip().splitlines()
        self.assertEqual(1, len(lines), output.getvalue())
        return exit_code, json.loads(lines[0]), diagnostics.getvalue()

    def test_ros_status_uses_injected_facade_and_source_verification_without_motion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = measured_config(directory)
            clear_estop(config)
            facade = SeededRosFacade()
            facade.subscriber_nodes[config.ros.cmd_vel_topic] = ["/chassis_controller"]
            exit_code, payload, _ = self.run_ros_main(
                ["--backend", "ros", "--config", "measured.json", "status"],
                config=config,
                facade=facade,
            )
            self.assertEqual(0, exit_code)
            self.assertEqual("SOURCE_VERIFIED_HIL_PENDING", payload["verification"])
            self.assertFalse(payload["zero_velocity_attempted"])
            self.assertEqual([], facade.created_publishers)

    def test_valid_ros_selection_never_falls_back_when_explicit_loader_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = measured_config(directory)
            exit_code, payload, _ = self.run_ros_main(
                ["--backend", "ros", "--config", "measured.json", "status"],
                config=config,
                facade=None,
                loader_error=RosFacadeUnavailable("ROS unavailable for test"),
            )
            self.assertEqual(3, exit_code)
            self.assertEqual("ros", payload["backend"])
            self.assertFalse(payload["data"]["fallback_used"])

    def test_motion_only_configuration_disables_approach_before_ros_side_effects(self) -> None:
        from dataclasses import replace
        from student_tasks.production_config import CapabilitiesConfiguration

        with tempfile.TemporaryDirectory() as directory:
            full = measured_config(directory)
            motion_only = replace(
                full,
                schema="robot-control/production-config/v2",
                capabilities=CapabilitiesConfiguration(motion=True, approach=False),
                ros=replace(
                    full.ros,
                    target_json_topic=None,
                    target_valid_topic=None,
                    target_schema=None,
                ),
                target=None,
                approach=None,
                calibration=None,
            )
            facade = mock.Mock(side_effect=AssertionError("approach must not load ROS"))
            code, payload, _ = self.run_ros_main(
                ["--backend", "ros", "--config", "motion.json", "approach"],
                config=motion_only,
                facade=facade,
            )
            self.assertEqual(3, code)
            self.assertFalse(payload["ok"])
            self.assertEqual("CAPABILITY_DISABLED", payload["error"]["code"])
            facade.assert_not_called()

    def test_ros_move_requires_authorization_and_authorized_move_uses_shared_core(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = measured_config(directory)
            clear_estop(config)
            facade = SeededRosFacade()
            facade.subscriber_nodes[config.ros.cmd_vel_topic] = ["/chassis_controller"]
            arguments = [
                "--backend", "ros", "--config", "measured.json", "move",
                "--linear-x", "0.1", "--linear-y", "0", "--angular-z", "0", "--duration", "0.1",
            ]
            denied_code, denied, _ = self.run_ros_main(arguments, config=config, facade=facade)
            self.assertEqual(3, denied_code)
            self.assertFalse(denied["ok"])
            self.assertEqual([], facade.created_publishers)

        with tempfile.TemporaryDirectory() as directory:
            config = measured_config(directory)
            clear_estop(config)
            facade = SeededRosFacade()
            facade.subscriber_nodes[config.ros.cmd_vel_topic] = ["/chassis_controller"]
            # The confirmation flag is global and therefore precedes the command.
            authorized = [
                "--backend", "ros", "--config", "measured.json", "--operator-confirmed", "move", *arguments[5:]
            ]
            ok_code, result, _ = self.run_ros_main(authorized, config=config, facade=facade)
            self.assertEqual(0, ok_code)
            self.assertTrue(result["ok"])
            self.assertTrue(result["zero_velocity_confirmed"])

    def test_ros_approach_is_in_process_and_holds_lock_through_final_stop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = measured_config(directory)
            clear_estop(config)
            facade = SeededRosFacade(target=True)
            facade.observed_lock_path = config.ownership.lock_path
            facade.subscriber_nodes[config.ros.cmd_vel_topic] = ["/chassis_controller"]
            guard = SignalCancellationGuard()
            with mock.patch.object(subprocess, "run", side_effect=AssertionError("approach subprocess")):
                code, payload, _ = self.run_ros_main(
                    [
                        "--backend", "ros", "--config", "measured.json", "--operator-confirmed",
                        "approach", "--operation-id", "cli-approach",
                    ],
                    config=config,
                    facade=facade,
                    cancellation=guard,
                )
            self.assertEqual(0, code)
            self.assertTrue(payload["data"]["approach_result"]["ok"])
            self.assertTrue(facade.lock_observations)
            self.assertTrue(all(available is False for available in facade.lock_observations))
            self.assertTrue(MotionLock(config.ownership.lock_path).probe().acquired)

    def test_ros_approach_safety_rejection_persists_estop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = measured_config(directory)
            clear_estop(config)
            blocked = replace(clear_scan_message(), ranges=(0.1,) * 73)
            facade = SeededRosFacade(scan_messages=[blocked], target=True)
            facade.subscriber_nodes[config.ros.cmd_vel_topic] = ["/chassis_controller"]
            # Force a forward correction rather than an already-arrived target.
            facade.target = False
            original_subscribe = facade.subscribe

            def subscribe(topic: str, callback: object, message_kind: str = "string") -> object:
                subscription = original_subscribe(topic, callback, message_kind)
                if message_kind == "bool":
                    callback(FakeBool(True))
                elif message_kind == "string":
                    callback(FakeString(json.dumps(base_payload(x=0.8, y=0.0))))
                return subscription

            facade.subscribe = subscribe
            code, payload, _ = self.run_ros_main(
                [
                    "--backend", "ros", "--config", "measured.json", "--operator-confirmed",
                    "approach", "--operation-id", "blocked-approach",
                ],
                config=config,
                facade=facade,
            )
            self.assertEqual(4, code)
            self.assertEqual("SAFETY_REJECTED", payload["data"]["approach_result"]["error_code"])
            self.assertTrue(EstopStore(config.ownership.estop_path).read().latched)
            self.assertFalse(any(message.linear.x != 0.0 for publisher in facade.created_publishers for message in publisher.messages))

    def test_estop_reset_requires_distinct_consecutive_clear_scan_messages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = measured_config(directory)
            config = replace(config, safety=replace(config.safety, reset_clear_frames=2))
            store = EstopStore(config.ownership.estop_path)
            store.latch("TEST", "reset through CLI", now=NOW - 1.0)
            facade = SeededRosFacade(
                scan_messages=[clear_scan_message(), clear_scan_message(source_time=NOW + 0.01)]
            )
            facade.subscriber_nodes[config.ros.cmd_vel_topic] = ["/chassis_controller"]
            code, payload, _ = self.run_ros_main(
                ["--backend", "ros", "--config", "measured.json", "estop-reset"],
                config=config,
                facade=facade,
            )
            self.assertEqual(0, code)
            self.assertTrue(payload["ok"])
            self.assertFalse(store.read().latched)
            self.assertEqual([], facade.created_publishers)

    def test_cancelled_ros_move_returns_one_interrupted_result_and_zero_stop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = measured_config(directory)
            clear_estop(config)
            facade = SeededRosFacade()
            facade.subscriber_nodes[config.ros.cmd_vel_topic] = ["/chassis_controller"]
            guard = SignalCancellationGuard()
            original_sleep = facade.sleep

            def cancel_after_publish(duration_s: float) -> None:
                original_sleep(duration_s)
                guard.handle_signal(signal.SIGTERM, None)

            facade.sleep = cancel_after_publish
            code, payload, _ = self.run_ros_main(
                [
                    "--backend", "ros", "--config", "measured.json", "--operator-confirmed", "move",
                    "--linear-x", "0.1", "--linear-y", "0", "--angular-z", "0", "--duration", "0.2",
                ],
                config=config,
                facade=facade,
                cancellation=guard,
            )
            self.assertEqual(4, code)
            self.assertEqual("CANCELLED", payload["error"]["code"])
            self.assertTrue(payload["zero_velocity_confirmed"])

    def test_ros_stop_uses_explicit_zero_fields_when_full_configuration_is_invalid(self) -> None:
        from student_tasks import cli
        from student_tasks.production_config import StopConfiguration, StopConfigurationValidation

        facade = FakeRosFacade(wall_time=NOW)
        facade.subscriber_nodes["/measured_cmd"] = ["/chassis_controller"]
        zero_config = StopConfiguration("jx_stop", "/measured_cmd", 2, 0.01, 0.5)
        output = StringIO()
        with mock.patch.object(
            cli,
            "load_stop_configuration",
            return_value=StopConfigurationValidation((), zero_config),
        ), mock.patch.object(cli, "load_ros_facade", return_value=facade), mock.patch.object(
            cli,
            "load_production_config",
            side_effect=AssertionError("stop must not require the full configuration"),
        ):
            exit_code = cli.main(
                ["--backend", "ros", "--config", "partially-invalid.json", "stop"],
                stdout=output,
                wall_clock=lambda: NOW,
            )
        payload = json.loads(output.getvalue())
        self.assertEqual(0, exit_code)
        self.assertTrue(payload["zero_velocity_confirmed"])
        self.assertEqual(2, len(facade.created_publishers[0].messages))


if __name__ == "__main__":
    unittest.main()
