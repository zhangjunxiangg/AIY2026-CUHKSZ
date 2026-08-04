from __future__ import annotations

import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import support  # noqa: F401

from fake_ros import FakeRosFacade
from student_tasks.core import MotionController
from student_tasks.estop_store import EstopStore
from student_tasks.models import MotionRequest, Velocity, VerificationLevel
from student_tasks.process_lock import MotionLock
from student_tasks.production_config import ProductionConfiguration, validate_production_config
from student_tasks.ros_backend import RosMotionBackend
from student_tasks.safety import LaserScanSnapshot
from test_production_config import NOW, valid_document


class StaticScanProvider:
    def __init__(self, scan: LaserScanSnapshot | None) -> None:
        self.scan = scan

    def snapshot(self) -> LaserScanSnapshot | None:
        return self.scan


def full_scan(*, observed_at: float = NOW, distance: float = 1.0) -> LaserScanSnapshot:
    return LaserScanSnapshot(
        observed_at=observed_at,
        angle_min=-math.pi,
        angle_increment=math.pi / 36.0,
        range_min=0.05,
        range_max=5.0,
        ranges=(distance,) * 73,
    )


def measured_config(directory: str, **signs: int) -> ProductionConfiguration:
    result = validate_production_config(valid_document(), now=NOW)
    assert result.configuration is not None
    config = result.configuration
    ownership = replace(
        config.ownership,
        lock_path=str(Path(directory, "motion.lock")),
        estop_path=str(Path(directory, "estop.json")),
    )
    motion = replace(
        config.motion,
        linear_x_sign=signs.get("linear_x_sign", 1),
        linear_y_sign=signs.get("linear_y_sign", 1),
        angular_z_sign=signs.get("angular_z_sign", 1),
    )
    return replace(config, ownership=ownership, motion=motion)


def clear_estop(config: ProductionConfiguration) -> EstopStore:
    store = EstopStore(config.ownership.estop_path, pid=lambda: 101)
    store.latch("TEST_SETUP", "initialize persistent test state", now=NOW - 2.0)
    store.request_reset(now=NOW - 1.0)
    for index in range(config.safety.reset_clear_frames):
        store.advance_reset(
            clear=True,
            required_frames=config.safety.reset_clear_frames,
            now=NOW - 0.5 + index * 0.01,
        )
    self_check = store.read()
    assert not self_check.latched
    return store


def ready_backend(
    directory: str,
    *,
    facade: FakeRosFacade | None = None,
    config: ProductionConfiguration | None = None,
    scan: LaserScanSnapshot | None = None,
    operator_confirmed: bool = True,
) -> tuple[RosMotionBackend, FakeRosFacade, ProductionConfiguration]:
    facade = facade or FakeRosFacade(wall_time=NOW)
    config = config or measured_config(directory)
    facade.subscriber_nodes[config.ros.cmd_vel_topic] = ["/chassis_controller"]
    clear_estop(config)
    backend = RosMotionBackend(
        facade,
        config,
        scan_provider=StaticScanProvider(scan or full_scan()),
        operator_confirmed=operator_confirmed,
    )
    return backend, facade, config


class RosBackendStatusTests(unittest.TestCase):
    def test_ready_status_is_read_only_and_source_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backend, facade, _ = ready_backend(directory)
            status = backend.status()
            self.assertTrue(status.ready, status.blocking_reasons)
            self.assertEqual(VerificationLevel.SOURCE_VERIFIED_HIL_PENDING, backend.verification_level)
            self.assertEqual("SOURCE_VERIFIED_HIL_PENDING", status.details["verification"])
            self.assertEqual([], facade.created_publishers)
            self.assertEqual(0, facade.publish_attempts)

    def test_status_aggregates_master_subscriber_authorization_lock_estop_and_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = measured_config(directory)
            facade = FakeRosFacade(master_up=False, wall_time=NOW)
            store = EstopStore(config.ownership.estop_path)
            store.latch("TEST_LATCH", "latched for status", now=NOW)
            held = MotionLock(config.ownership.lock_path, identity="other")
            held.try_acquire("other-operation")
            try:
                backend = RosMotionBackend(
                    facade,
                    config,
                    scan_provider=StaticScanProvider(None),
                    operator_confirmed=False,
                )
                reasons = set(backend.status().blocking_reasons)
            finally:
                held.release()
            self.assertTrue(
                {
                    "ROS_MASTER_UNAVAILABLE",
                    "CMD_VEL_SUBSCRIBER_MISSING",
                    "OPERATOR_CONFIRMATION_REQUIRED",
                    "MOTION_LOCK_UNAVAILABLE",
                    "ESTOP_LATCHED",
                    "SCAN_UNAVAILABLE",
                }.issubset(reasons),
                reasons,
            )
            self.assertEqual([], facade.created_publishers)

    def test_invalid_configuration_fails_closed_without_initializing_ros(self) -> None:
        facade = FakeRosFacade(wall_time=NOW)
        backend = RosMotionBackend(
            facade,
            None,
            configuration_findings=("ros.cmd_vel_topic: NULL_OR_MISSING",),
            operator_confirmed=True,
        )
        status = backend.status()
        self.assertFalse(status.ready)
        self.assertIn("CONFIGURATION_INVALID", status.blocking_reasons)
        self.assertEqual([], facade.initialized_names)
        self.assertEqual([], facade.created_publishers)

    def test_self_publisher_is_excluded_but_external_or_graph_failure_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backend, facade, config = ready_backend(directory)
            facade.publisher_nodes[config.ros.cmd_vel_topic] = [facade.node_name]
            self.assertTrue(backend.status().ready)
            facade.publisher_nodes[config.ros.cmd_vel_topic].append("/teleop")
            status = backend.status()
            self.assertIn("CMD_VEL_PUBLISHER_CONFLICT", status.blocking_reasons)
            self.assertEqual(["/teleop"], status.details["publishers"]["conflicts"])
            facade.fail_graph = True
            self.assertIn("ROS_GRAPH_UNAVAILABLE", backend.status().blocking_reasons)


class RosBackendMotionTests(unittest.TestCase):
    def test_move_maps_measured_signs_repeats_and_ends_in_zeros(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = measured_config(directory, linear_x_sign=-1, linear_y_sign=1, angular_z_sign=-1)
            backend, facade, config = ready_backend(directory, config=config)
            controller = MotionController(
                backend,
                zero_message_count=config.motion.zero_message_count,
                zero_interval_s=config.motion.zero_interval_s,
            )
            result = controller.move(
                MotionRequest("signed-move", Velocity(0.1, -0.05, 0.2), 0.1, publish_rate_hz=20.0)
            )
            self.assertTrue(result.ok, result.to_dict())
            messages = facade.created_publishers[0].messages
            nonzero = [message for message in messages if (message.linear.x, message.linear.y, message.angular.z) != (0.0, 0.0, 0.0)]
            self.assertEqual(2, len(nonzero))
            self.assertEqual((-0.1, -0.05, -0.2), (nonzero[0].linear.x, nonzero[0].linear.y, nonzero[0].angular.z))
            self.assertEqual(3, len(messages) - len(nonzero))
            self.assertTrue(result.zero_velocity_confirmed)

    def test_each_readiness_gate_blocks_all_nonzero_output(self) -> None:
        cases = ("authorization", "subscriber", "lock", "publisher", "estop", "scan")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                backend, facade, config = ready_backend(directory)
                held: MotionLock | None = None
                if case == "authorization":
                    backend.operator_confirmed = False
                elif case == "subscriber":
                    facade.subscriber_nodes[config.ros.cmd_vel_topic] = []
                elif case == "lock":
                    held = MotionLock(config.ownership.lock_path, identity="other")
                    held.try_acquire("other")
                elif case == "publisher":
                    facade.publisher_nodes[config.ros.cmd_vel_topic] = ["/teleop"]
                elif case == "estop":
                    EstopStore(config.ownership.estop_path).latch("TEST", "blocked", now=NOW)
                elif case == "scan":
                    backend.scan_provider = StaticScanProvider(full_scan(distance=0.1))
                try:
                    result = MotionController(backend).move(
                        MotionRequest("blocked-%s" % case, Velocity(0.1, 0.0, 0.0), 0.1)
                    )
                finally:
                    if held is not None:
                        held.release()
                messages = [message for publisher in facade.created_publishers for message in publisher.messages]
                self.assertFalse(result.ok)
                self.assertFalse(any((message.linear.x, message.linear.y, message.angular.z) != (0.0, 0.0, 0.0) for message in messages))

    def test_runtime_publisher_conflict_is_rechecked_before_next_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backend, facade, config = ready_backend(directory)
            backend.acquire("runtime-conflict")
            try:
                backend.publish_velocity(Velocity(0.1, 0.0, 0.0))
                facade.publisher_nodes[config.ros.cmd_vel_topic].append("/late_teleop")
                with self.assertRaisesRegex(Exception, "publisher conflict"):
                    backend.publish_velocity(Velocity(0.1, 0.0, 0.0))
            finally:
                backend.publish_velocity(Velocity(0.0, 0.0, 0.0))
                backend.release()
            messages = facade.created_publishers[0].messages
            self.assertEqual(1, sum((message.linear.x, message.linear.y, message.angular.z) != (0.0, 0.0, 0.0) for message in messages))

    def test_stop_attempts_zeros_during_degraded_nonzero_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backend, facade, config = ready_backend(directory)
            facade.master_up = False
            EstopStore(config.ownership.estop_path).latch("TEST", "latched", now=NOW)
            result = MotionController(backend, zero_message_count=2).stop()
            self.assertTrue(result.ok, result.to_dict())
            messages = facade.created_publishers[0].messages
            self.assertEqual(2, len(messages))
            self.assertTrue(all((message.linear.x, message.linear.y, message.angular.z) == (0.0, 0.0, 0.0) for message in messages))

    def test_stop_distinguishes_missing_subscriber_from_publish_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backend, facade, config = ready_backend(directory)
            facade.subscriber_nodes[config.ros.cmd_vel_topic] = []
            missing = MotionController(backend, zero_message_count=1).stop()
            self.assertFalse(missing.ok)
            self.assertIn("CMD_VEL_SUBSCRIBER_MISSING", missing.data["stop_failures"][0])

        with tempfile.TemporaryDirectory() as directory:
            backend, facade, _ = ready_backend(directory)
            facade.fail_publish_at = 1
            failed = MotionController(backend, zero_message_count=1).stop()
            self.assertFalse(failed.ok)
            self.assertIn("publish failure", failed.data["stop_failures"][0])


if __name__ == "__main__":
    unittest.main()
