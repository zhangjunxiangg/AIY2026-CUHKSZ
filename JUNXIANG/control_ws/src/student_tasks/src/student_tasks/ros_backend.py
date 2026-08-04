"""Guarded ROS1 motion backend for the shared controller."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Protocol

from .errors import failure
from .estop_store import EstopRecord, EstopStore
from .models import BackendStatus, Velocity, VerificationLevel
from .process_lock import LockResult, MotionLock
from .production_config import ProductionConfiguration
from .ros_facade import RosFacade
from .safety import LaserScanSnapshot, SafetyDecision, SafetyMonitor


VERIFICATION_LABEL = VerificationLevel.SOURCE_VERIFIED_HIL_PENDING


class ScanSnapshotProvider(Protocol):
    def snapshot(self) -> LaserScanSnapshot | None: ...


@dataclass(frozen=True)
class PublisherSnapshot:
    topic: str
    current_node: str | None
    publishers: tuple[str, ...]
    allowlist: tuple[str, ...]
    conflicts: tuple[str, ...]
    graph_error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "topic": self.topic,
            "current_node": self.current_node,
            "publishers": list(self.publishers),
            "allowlist": list(self.allowlist),
            "conflicts": list(self.conflicts),
            "graph_error": self.graph_error,
        }


class RosMotionBackend:
    """Production adapter whose every non-zero publish rechecks volatile gates."""

    def __init__(
        self,
        facade: RosFacade,
        configuration: ProductionConfiguration | None,
        *,
        configuration_findings: tuple[str, ...] = (),
        scan_provider: ScanSnapshotProvider | None = None,
        operator_confirmed: bool = False,
        motion_lock: MotionLock | None = None,
        estop_store: EstopStore | None = None,
    ) -> None:
        self.facade = facade
        self.configuration = configuration
        self.configuration_findings = tuple(configuration_findings)
        self.scan_provider = scan_provider
        self.operator_confirmed = operator_confirmed
        self._publisher: object | None = None
        self._initialization_error: str | None = None
        self._motion_lock = motion_lock
        self._estop_store = estop_store
        if configuration is not None:
            self._motion_lock = motion_lock or MotionLock(configuration.ownership.lock_path)
            self._estop_store = estop_store or EstopStore(configuration.ownership.estop_path)
            try:
                facade.initialize(configuration.ros.node_name_prefix)
            except Exception as exc:
                self._initialization_error = "ROS node initialization failed: %s" % exc

    @property
    def backend_name(self) -> str:
        return "ros"

    @property
    def verification_level(self) -> VerificationLevel:
        return VERIFICATION_LABEL

    def monotonic(self) -> float:
        return float(self.facade.monotonic())

    def sleep(self, duration_s: float) -> None:
        self.facade.sleep(duration_s)

    def status(self) -> BackendStatus:
        reasons: list[str] = []
        details: dict[str, object] = {
            "verification": VERIFICATION_LABEL.value,
            "configuration_findings": list(self.configuration_findings),
            "authorization": {"operator_confirmed": bool(self.operator_confirmed)},
        }
        config = self.configuration
        if config is None:
            reasons.append("CONFIGURATION_INVALID")
            return BackendStatus(False, "ros", True, "missing", tuple(reasons), details)
        if self._initialization_error is not None:
            reasons.append("ROS_INITIALIZATION_FAILED")
            details["initialization_error"] = self._initialization_error

        master_available = self._master_available()
        details["master"] = {"available": master_available}
        if not master_available:
            reasons.append("ROS_MASTER_UNAVAILABLE")

        subscribers, subscriber_error = self._subscribers()
        details["subscribers"] = {
            "topic": config.ros.cmd_vel_topic,
            "nodes": list(subscribers),
            "count": len(subscribers),
            "error": subscriber_error,
        }
        if subscriber_error is not None:
            reasons.append("ROS_GRAPH_UNAVAILABLE")
        if not subscribers:
            reasons.append("CMD_VEL_SUBSCRIBER_MISSING")

        publisher_snapshot = self._publisher_snapshot()
        details["publishers"] = publisher_snapshot.to_dict()
        if publisher_snapshot.graph_error is not None:
            reasons.append("ROS_GRAPH_UNAVAILABLE")
        if publisher_snapshot.conflicts:
            reasons.append("CMD_VEL_PUBLISHER_CONFLICT")

        if not self.operator_confirmed:
            reasons.append("OPERATOR_CONFIRMATION_REQUIRED")

        lock_result = self._probe_lock()
        details["motion_lock"] = {
            "available": lock_result.acquired,
            "code": lock_result.code,
            "owner_metadata": dict(lock_result.owner_metadata),
        }
        if not lock_result.acquired:
            reasons.append("MOTION_LOCK_UNAVAILABLE")

        estop = self._read_estop()
        details["estop"] = estop.to_dict() | {"valid_state": estop.valid_state}
        if estop.latched:
            reasons.append("ESTOP_LATCHED")

        scan_code = self._scan_readiness_code()
        details["scan"] = {"code": scan_code}
        if scan_code != "SCAN_READY":
            reasons.append(scan_code)

        return BackendStatus(not reasons, "ros", True, "measured", tuple(reasons), details)

    def acquire(self, operation_id: str) -> None:
        if self.configuration is None or self._motion_lock is None:
            raise failure("PRODUCTION_CONFIG_REQUIRED", "production configuration is unavailable")
        if not self.operator_confirmed:
            raise failure("BACKEND_UNAVAILABLE", "operator confirmation is required for non-zero motion")
        result = self._motion_lock.try_acquire(operation_id)
        if not result.acquired:
            raise failure(
                "MOTION_BUSY",
                "motion ownership is held by another process",
                owner_metadata=dict(result.owner_metadata),
            )

    def release(self) -> None:
        if self._motion_lock is not None:
            self._motion_lock.release()

    def publish_velocity(self, velocity: Velocity) -> None:
        if not isinstance(velocity, Velocity):
            raise failure("INVALID_INPUT", "velocity must be a Velocity value")
        if velocity.is_zero:
            self._publish_zero()
            return
        self._publish_nonzero(velocity)

    def _publish_nonzero(self, velocity: Velocity) -> None:
        config = self.configuration
        if config is None:
            raise failure("PRODUCTION_CONFIG_REQUIRED", "production configuration is unavailable")
        if not self.operator_confirmed:
            raise failure("BACKEND_UNAVAILABLE", "operator confirmation is required for non-zero motion")
        if self._motion_lock is None or not self._motion_lock.assert_held():
            raise failure("MOTION_BUSY", "motion lock ownership was lost")
        if not self._master_available():
            raise failure("BACKEND_UNAVAILABLE", "ROS Master is unavailable")
        subscribers, subscriber_error = self._subscribers()
        if subscriber_error is not None:
            raise failure("BACKEND_UNAVAILABLE", "ROS graph inspection failed: %s" % subscriber_error)
        if not subscribers:
            raise failure("BACKEND_UNAVAILABLE", "CMD_VEL_SUBSCRIBER_MISSING: no chassis subscriber")
        snapshot = self._publisher_snapshot()
        if snapshot.graph_error is not None:
            raise failure("BACKEND_UNAVAILABLE", "ROS graph inspection failed: %s" % snapshot.graph_error)
        if snapshot.conflicts:
            raise failure(
                "BACKEND_UNAVAILABLE",
                "cmd_vel publisher conflict: %s" % ", ".join(snapshot.conflicts),
            )
        estop = self._read_estop()
        if estop.latched:
            raise failure("BACKEND_UNAVAILABLE", "persistent emergency stop is latched: %s" % estop.trigger_code)
        decision = self._directional_safety(velocity)
        if not decision.allowed:
            self._latch_safety(decision)
            raise failure("BACKEND_UNAVAILABLE", "directional scan rejected motion: %s" % decision.code)

        publisher = self._ensure_publisher()
        message = self.facade.make_twist(
            velocity.linear_x * config.motion.linear_x_sign,
            velocity.linear_y * config.motion.linear_y_sign,
            velocity.angular_z * config.motion.angular_z_sign,
        )
        self._publish(publisher, message)

    def _publish_zero(self) -> None:
        config = self.configuration
        if config is None:
            raise failure("PRODUCTION_CONFIG_REQUIRED", "cmd_vel topic is unavailable without production configuration")
        publisher = self._ensure_publisher()
        message = self.facade.make_twist(0.0, 0.0, 0.0)
        self._publish(publisher, message)
        subscribers, subscriber_error = self._subscribers()
        if subscriber_error is not None:
            raise failure("BACKEND_UNAVAILABLE", "ROS graph inspection failed after zero publish: %s" % subscriber_error)
        if not subscribers:
            raise failure(
                "BACKEND_UNAVAILABLE",
                "CMD_VEL_SUBSCRIBER_MISSING: zero velocity published without a subscriber",
            )

    def _ensure_publisher(self) -> object:
        config = self.configuration
        assert config is not None
        if self._publisher is None:
            try:
                self._publisher = self.facade.create_publisher(config.ros.cmd_vel_topic)
            except Exception as exc:
                raise failure("BACKEND_FAILURE", "cmd_vel publisher creation failed: %s" % exc) from exc
        return self._publisher

    def _publish(self, publisher: object, message: object) -> None:
        try:
            publisher.publish(message)
        except Exception as exc:
            raise failure("BACKEND_FAILURE", "cmd_vel publish failure: %s" % exc) from exc

    def _master_available(self) -> bool:
        try:
            return bool(self.facade.master_available())
        except Exception:
            return False

    def _subscribers(self) -> tuple[tuple[str, ...], str | None]:
        config = self.configuration
        assert config is not None
        try:
            return tuple(sorted(set(self.facade.subscribers(config.ros.cmd_vel_topic)))), None
        except Exception as exc:
            return (), str(exc)

    def _publisher_snapshot(self) -> PublisherSnapshot:
        config = self.configuration
        assert config is not None
        try:
            current = self.facade.current_node_name()
            publishers = tuple(sorted(set(self.facade.publishers(config.ros.cmd_vel_topic))))
            excluded = {current, *config.ownership.publisher_allowlist}
            conflicts = tuple(node for node in publishers if node not in excluded)
            return PublisherSnapshot(
                config.ros.cmd_vel_topic,
                current,
                publishers,
                config.ownership.publisher_allowlist,
                conflicts,
            )
        except Exception as exc:
            return PublisherSnapshot(
                config.ros.cmd_vel_topic,
                None,
                (),
                config.ownership.publisher_allowlist,
                (),
                str(exc),
            )

    def _probe_lock(self) -> LockResult:
        if self._motion_lock is None:
            return LockResult(False, "LOCK_STATE_UNAVAILABLE", {"state": "configuration_missing"})
        return self._motion_lock.probe()

    def _read_estop(self) -> EstopRecord:
        if self._estop_store is None:
            return EstopStore._invalid("ESTOP_STATE_MISSING", "persistent estop store is unavailable")
        return self._estop_store.read()

    def _scan_readiness_code(self) -> str:
        scan = self._scan_snapshot()
        config = self.configuration
        assert config is not None
        if scan is None:
            return "SCAN_UNAVAILABLE"
        values = (
            scan.observed_at,
            scan.angle_min,
            scan.angle_increment,
            scan.range_min,
            scan.range_max,
        )
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values):
            return "SCAN_INVALID"
        age = self.facade.source_time() - float(scan.observed_at)
        if age < -config.safety.future_tolerance_s:
            return "SCAN_FUTURE"
        if age > config.safety.max_scan_age_s:
            return "SCAN_STALE"
        if float(scan.angle_increment) == 0.0 or float(scan.range_min) <= 0.0 or float(scan.range_max) <= float(scan.range_min):
            return "SCAN_INVALID"
        if not scan.ranges:
            return "SCAN_INVALID"
        return "SCAN_READY"

    def _scan_snapshot(self) -> LaserScanSnapshot | None:
        if self.scan_provider is None:
            return None
        try:
            scan = self.scan_provider.snapshot()
        except Exception:
            return None
        return scan if isinstance(scan, LaserScanSnapshot) else None

    def _directional_safety(self, velocity: Velocity) -> SafetyDecision:
        config = self.configuration
        assert config is not None
        monitor = SafetyMonitor(config.safety)
        return monitor.evaluate(velocity, self._scan_snapshot(), now=self.facade.source_time())

    def _latch_safety(self, decision: SafetyDecision) -> None:
        if self._estop_store is None:
            return
        serialized = json.dumps(decision.to_dict(), ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        digest = hashlib.sha256(serialized.encode("ascii")).hexdigest()
        self._estop_store.latch(
            decision.code,
            "directional scan safety rejected non-zero motion",
            now=self.facade.source_time(),
            safety_digest=digest,
        )
