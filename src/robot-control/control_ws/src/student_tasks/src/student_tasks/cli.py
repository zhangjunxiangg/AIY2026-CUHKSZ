"""Synchronous one-result CLI for fake and explicitly selected ROS backends."""

from __future__ import annotations

import argparse
import math
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TextIO

from .approach import ApproachController, ApproachResult
from .backend import Cancellation
from .configuration import ConfigurationProvenance
from .core import MotionController
from .errors import ControlError, ControlFailure, ErrorCategory, control_error
from .estop_store import EstopStore
from .fake_backend import FakeBackend
from .geometry import CameraIntrinsics, RigidTransform, Vector3
from .models import MotionRequest, MotionResult, Velocity, VerificationLevel
from .perception import CameraCalibration, TargetPolicy
from .production_config import ProductionConfiguration, load_production_config, load_stop_configuration
from .ros_backend import RosMotionBackend, RosStopBackend
from .ros_facade import RosFacadeUnavailable, load_ros_facade
from .ros_providers import RosScanProvider, RosTargetProvider
from .safety import SafetyDecision, SafetyMonitor


EXIT_BY_CATEGORY = {
    ErrorCategory.USAGE: 2,
    ErrorCategory.VALIDATION: 2,
    ErrorCategory.UNAVAILABLE: 3,
    ErrorCategory.RUNTIME: 4,
    ErrorCategory.STOP_SAFETY: 5,
}


class _UsageFailure(Exception):
    pass


class _ContractParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _UsageFailure(message)


@dataclass(frozen=True)
class _RosRuntime:
    configuration: ProductionConfiguration
    backend: RosMotionBackend
    controller: MotionController
    scans: RosScanProvider
    targets: RosTargetProvider | None


def build_parser() -> argparse.ArgumentParser:
    parser = _ContractParser(prog="robot-control", add_help=True)
    parser.add_argument("--backend", choices=("fake", "ros"), default="fake")
    parser.add_argument("--config")
    parser.add_argument("--operator-confirmed", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_ContractParser)
    commands.add_parser("status", help="Report backend readiness without motion")
    commands.add_parser("stop", help="Attempt the explicit zero sequence")
    move = commands.add_parser("move", help="Execute one bounded motion request")
    move.add_argument("--linear-x", required=True, type=float)
    move.add_argument("--linear-y", required=True, type=float)
    move.add_argument("--angular-z", required=True, type=float)
    move.add_argument("--duration", required=True, type=float)
    move.add_argument("--publish-rate", type=float)
    move.add_argument("--operation-id")
    approach = commands.add_parser("approach", help="Run one in-process visual approach")
    approach.add_argument("--operation-id")
    commands.add_parser("estop-reset", help="Request reset using consecutive clear scans")
    return parser


def _failure_result(
    operation: str,
    backend: str,
    error: ControlError,
    *,
    operation_id: str | None = None,
    data: dict[str, object] | None = None,
) -> MotionResult:
    verification = (
        VerificationLevel.SOURCE_VERIFIED_HIL_PENDING
        if backend == "ros"
        else VerificationLevel.OFFLINE_VERIFIED
    )
    return MotionResult(
        operation=operation,
        operation_id=operation_id,
        ok=False,
        backend=backend,
        verification=verification,
        zero_velocity_attempted=False,
        zero_velocity_confirmed=False,
        elapsed_s=0.0,
        data=data or {},
        error=error,
    )


def _infer_operation(arguments: Sequence[str]) -> str:
    for value in arguments:
        if value in {"status", "move", "stop", "approach", "estop-reset"}:
            return value
    return "status"


def _infer_backend(arguments: Sequence[str]) -> str:
    try:
        index = arguments.index("--backend")
        return arguments[index + 1]
    except (ValueError, IndexError):
        return "fake"


def _run_fake(arguments: argparse.Namespace, cancellation: Cancellation | None) -> MotionResult:
    backend = FakeBackend()
    controller = MotionController(backend)
    if arguments.command == "status":
        return controller.status()
    if arguments.command == "stop":
        return controller.stop()
    if arguments.command == "move":
        operation_id = arguments.operation_id or "move-%s" % uuid.uuid4().hex
        request = MotionRequest(
            operation_id=operation_id,
            velocity=Velocity(arguments.linear_x, arguments.linear_y, arguments.angular_z),
            duration_s=arguments.duration,
            publish_rate_hz=arguments.publish_rate or 20.0,
        )
        return controller.move(request, cancellation)
    return _failure_result(
        arguments.command,
        "fake",
        control_error("INVALID_INPUT", "%s requires --backend ros" % arguments.command),
        operation_id=getattr(arguments, "operation_id", None),
    )


def _build_ros_runtime(
    arguments: argparse.Namespace,
    *,
    wall_clock: Callable[[], float],
) -> _RosRuntime | MotionResult:
    if not arguments.config:
        return _failure_result(
            arguments.command,
            "ros",
            control_error("PRODUCTION_CONFIG_REQUIRED", "--config is required for ROS selection"),
            operation_id=getattr(arguments, "operation_id", None),
            data={"fallback_used": False, "configuration_findings": []},
        )
    validation = load_production_config(arguments.config, now=wall_clock())
    if not validation.valid or validation.configuration is None:
        return _failure_result(
            arguments.command,
            "ros",
            control_error("PRODUCTION_CONFIG_REQUIRED", "measured production configuration is invalid"),
            operation_id=getattr(arguments, "operation_id", None),
            data={
                "fallback_used": False,
                "config": arguments.config,
                "configuration_findings": [finding.to_dict() for finding in validation.findings],
            },
        )
    config = validation.configuration
    if arguments.command == "approach" and not config.capabilities.approach:
        return _failure_result(
            "approach",
            "ros",
            control_error("CAPABILITY_DISABLED", "visual approach capability is disabled by production configuration"),
            operation_id=getattr(arguments, "operation_id", None),
            data={
                "fallback_used": False,
                "config": arguments.config,
                "capabilities": {
                    "motion": config.capabilities.motion,
                    "approach": config.capabilities.approach,
                },
            },
        )
    try:
        facade = load_ros_facade()
    except RosFacadeUnavailable as exc:
        return _failure_result(
            arguments.command,
            "ros",
            control_error("BACKEND_UNAVAILABLE", str(exc)),
            operation_id=getattr(arguments, "operation_id", None),
            data={"fallback_used": False, "config": arguments.config},
        )

    backend = RosMotionBackend(
        facade,
        config,
        operator_confirmed=arguments.operator_confirmed,
    )
    scans = RosScanProvider(
        facade,
        config.ros.scan_topic,
        max_source_age_s=config.safety.max_scan_age_s,
        max_receive_age_s=config.safety.max_scan_age_s,
        future_tolerance_s=config.safety.future_tolerance_s,
    )
    scans.wait_for_first_message(config.motion.subscriber_timeout_s)
    targets: RosTargetProvider | None = None
    if config.capabilities.approach:
        if config.target is None or config.calibration is None:
            return _failure_result(
                arguments.command,
                "ros",
                control_error("PRODUCTION_CONFIG_REQUIRED", "approach configuration is incomplete"),
                operation_id=getattr(arguments, "operation_id", None),
                data={"fallback_used": False, "config": arguments.config},
            )
        assert config.ros.target_json_topic is not None
        assert config.ros.target_valid_topic is not None
        assert config.ros.target_schema is not None
        targets = RosTargetProvider(
            facade,
            config.ros.target_json_topic,
            config.ros.target_valid_topic,
            expected_schema=config.ros.target_schema,
            max_source_age_s=config.target.max_source_age_s,
            max_receive_age_s=config.target.max_receive_age_s,
            future_tolerance_s=config.target.future_tolerance_s,
            min_confidence=config.target.min_confidence,
            expected_camera_frame=config.calibration.camera_frame,
            calibration_source=config.calibration.source,
        )
    backend.scan_provider = scans
    backend.target_provider = targets
    controller = MotionController(
        backend,
        zero_message_count=config.motion.zero_message_count,
        zero_interval_s=config.motion.zero_interval_s,
    )
    return _RosRuntime(config, backend, controller, scans, targets)


def _run_ros(
    arguments: argparse.Namespace,
    cancellation: Cancellation | None,
    *,
    wall_clock: Callable[[], float],
) -> MotionResult:
    if arguments.command == "stop":
        return _run_ros_stop(arguments)
    selected = _build_ros_runtime(arguments, wall_clock=wall_clock)
    if isinstance(selected, MotionResult):
        return selected
    runtime = selected
    if arguments.command == "status":
        return runtime.controller.status()
    if arguments.command == "move":
        if arguments.publish_rate is not None and not math.isclose(
            arguments.publish_rate,
            runtime.configuration.motion.publish_rate_hz,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            return _failure_result(
                "move",
                "ros",
                control_error("INVALID_INPUT", "ROS publish rate must match measured configuration"),
                operation_id=arguments.operation_id,
            )
        operation_id = arguments.operation_id or "move-%s" % uuid.uuid4().hex
        request = MotionRequest(
            operation_id,
            Velocity(arguments.linear_x, arguments.linear_y, arguments.angular_z),
            arguments.duration,
            runtime.configuration.motion.publish_rate_hz,
        )
        return runtime.controller.move(request, cancellation)
    if arguments.command == "approach":
        return _run_approach(runtime, arguments.operation_id, cancellation)
    if arguments.command == "estop-reset":
        return _run_estop_reset(runtime, cancellation)
    return _failure_result("status", "ros", control_error("INVALID_INPUT", "unknown ROS command"))


def _run_ros_stop(arguments: argparse.Namespace) -> MotionResult:
    if not arguments.config:
        return _failure_result(
            "stop",
            "ros",
            control_error("PRODUCTION_CONFIG_REQUIRED", "--config is required for ROS selection"),
            data={"fallback_used": False, "configuration_findings": []},
        )
    validation = load_stop_configuration(arguments.config)
    if not validation.valid or validation.configuration is None:
        return _failure_result(
            "stop",
            "ros",
            control_error("PRODUCTION_CONFIG_REQUIRED", "explicit zero-delivery configuration is invalid"),
            data={
                "fallback_used": False,
                "config": arguments.config,
                "configuration_scope": "zero_only",
                "configuration_findings": [finding.to_dict() for finding in validation.findings],
            },
        )
    try:
        facade = load_ros_facade()
    except RosFacadeUnavailable as exc:
        return _failure_result(
            "stop",
            "ros",
            control_error("BACKEND_UNAVAILABLE", str(exc)),
            data={"fallback_used": False, "config": arguments.config},
        )
    configuration = validation.configuration
    backend = RosStopBackend(facade, configuration)
    controller = MotionController(
        backend,
        zero_message_count=configuration.zero_message_count,
        zero_interval_s=configuration.zero_interval_s,
    )
    return controller.stop()


def _run_approach(
    runtime: _RosRuntime,
    operation_id: str | None,
    cancellation: Cancellation | None,
) -> MotionResult:
    operation = operation_id or "approach-%s" % uuid.uuid4().hex
    if not runtime.configuration.capabilities.approach or runtime.targets is None:
        return _failure_result(
            "approach",
            "ros",
            control_error("CAPABILITY_DISABLED", "visual approach capability is disabled by production configuration"),
            operation_id=operation,
            data={"fallback_used": False},
        )
    if runtime.configuration.approach is None or runtime.configuration.target is None or runtime.configuration.calibration is None:
        return _failure_result(
            "approach",
            "ros",
            control_error("PRODUCTION_CONFIG_REQUIRED", "approach configuration is incomplete"),
            operation_id=operation,
            data={"fallback_used": False},
        )
    if not runtime.backend.operator_confirmed:
        return _failure_result(
            "approach",
            "ros",
            control_error("BACKEND_UNAVAILABLE", "operator confirmation is required for approach"),
            operation_id=operation,
            data={"fallback_used": False},
        )
    if cancellation is not None and cancellation.is_cancelled():
        return _failure_result(
            "approach",
            "ros",
            control_error("CANCELLED", "approach was cancelled before ownership"),
            operation_id=operation,
        )
    backend_status = runtime.backend.status()
    if not backend_status.ready:
        return _failure_result(
            "approach",
            "ros",
            control_error("BACKEND_UNAVAILABLE", "; ".join(backend_status.blocking_reasons)),
            operation_id=operation,
            data={"status": backend_status.to_dict(), "fallback_used": False},
        )
    target_diagnostics = runtime.targets.diagnostics(runtime.backend.monotonic())
    if target_diagnostics["code"] != "TARGET_READY":
        return _failure_result(
            "approach",
            "ros",
            control_error("BACKEND_UNAVAILABLE", "target provider is not ready: %s" % target_diagnostics["code"]),
            operation_id=operation,
            data={"target": target_diagnostics, "fallback_used": False},
        )

    calibration = _camera_calibration(runtime.configuration)
    approach = ApproachController(
        motion=runtime.controller,
        safety=SafetyMonitor(runtime.configuration.safety),
        targets=runtime.targets,
        scans=runtime.scans,
        configuration=runtime.configuration.approach,
        target_policy=TargetPolicy(
            runtime.configuration.target.max_receive_age_s,
            runtime.configuration.target.future_tolerance_s,
            runtime.configuration.target.min_confidence,
        ),
        calibration=calibration,
        production=True,
    )
    started = runtime.backend.monotonic()
    runtime.backend.begin_session(operation)
    try:
        result = approach.run(operation, cancellation)
        if result.last_safety is not None and not result.last_safety.allowed:
            runtime.backend.latch_safety(result.last_safety)
    except Exception as exc:
        stop = runtime.controller.stop()
        error = (
            control_error("STOP_FAILED", "approach exception stop could not be confirmed")
            if not stop.ok
            else control_error("BACKEND_FAILURE", "approach execution failed: %s" % exc)
        )
        return MotionResult(
            operation="approach",
            operation_id=operation,
            ok=False,
            backend="ros",
            verification=runtime.backend.verification_level,
            zero_velocity_attempted=stop.zero_velocity_attempted,
            zero_velocity_confirmed=stop.zero_velocity_confirmed,
            elapsed_s=max(0.0, runtime.backend.monotonic() - started),
            data={"stop_result": stop.to_dict(), "fallback_used": False},
            error=error,
        )
    finally:
        runtime.backend.end_session()
    return _approach_result(operation, result, runtime)


def _approach_result(operation: str, result: ApproachResult, runtime: _RosRuntime) -> MotionResult:
    error: ControlError | None = None
    if not result.ok:
        if result.error_code == "CANCELLED":
            error = control_error("CANCELLED", result.error_detail or "approach was cancelled")
        elif result.error_code == "STOP_FAILED":
            error = control_error("STOP_FAILED", result.error_detail or "approach stop failed")
        else:
            error = control_error("BACKEND_FAILURE", result.error_detail or "approach failed")
    return MotionResult(
        operation="approach",
        operation_id=operation,
        ok=error is None,
        backend="ros",
        verification=runtime.backend.verification_level,
        zero_velocity_attempted=result.stop_result.zero_velocity_attempted,
        zero_velocity_confirmed=result.stop_result.zero_velocity_confirmed,
        elapsed_s=result.elapsed_s,
        data={
            "approach_result": result.to_dict(),
            "target": runtime.targets.diagnostics(runtime.backend.monotonic()),
            "scan": runtime.scans.diagnostics(runtime.backend.monotonic()),
            "fallback_used": False,
        },
        error=error,
    )


def _run_estop_reset(runtime: _RosRuntime, cancellation: Cancellation | None) -> MotionResult:
    config = runtime.configuration
    store = EstopStore(config.ownership.estop_path)
    started = runtime.backend.monotonic()
    current = store.request_reset(now=runtime.backend.facade.source_time())
    if not current.latched:
        return _estop_reset_result(runtime, current, started, None, None)

    deadline = started + max(
        1.0,
        config.motion.subscriber_timeout_s * (config.safety.reset_clear_frames + 1),
    )
    last_sequence = 0
    last_decision: SafetyDecision | None = None
    while runtime.backend.monotonic() < deadline:
        if cancellation is not None and cancellation.is_cancelled():
            return _estop_reset_result(
                runtime,
                store.read(),
                started,
                last_decision,
                control_error("CANCELLED", "emergency-stop reset was cancelled"),
            )
        envelope = runtime.scans.envelope()
        if envelope.sequence > last_sequence:
            last_sequence = envelope.sequence
            scan = runtime.scans.snapshot()
            last_decision = SafetyMonitor(config.safety).evaluate(
                Velocity(0.0, 0.0, 0.001),
                scan,
                now=runtime.backend.facade.source_time(),
            )
            current = store.advance_reset(
                clear=last_decision.allowed,
                required_frames=config.safety.reset_clear_frames,
                now=runtime.backend.facade.source_time(),
            )
            if not current.latched:
                return _estop_reset_result(runtime, current, started, last_decision, None)
        runtime.backend.sleep(min(0.05, 1.0 / config.motion.publish_rate_hz))
    return _estop_reset_result(
        runtime,
        store.read(),
        started,
        last_decision,
        control_error("BACKEND_UNAVAILABLE", "fresh all-direction clear scans did not complete reset"),
    )


def _estop_reset_result(
    runtime: _RosRuntime,
    record: object,
    started: float,
    decision: SafetyDecision | None,
    error: ControlError | None,
) -> MotionResult:
    return MotionResult(
        operation="estop-reset",
        operation_id=None,
        ok=error is None,
        backend="ros",
        verification=runtime.backend.verification_level,
        zero_velocity_attempted=False,
        zero_velocity_confirmed=False,
        elapsed_s=max(0.0, runtime.backend.monotonic() - started),
        data={
            "estop": record.to_dict(),
            "safety": None if decision is None else decision.to_dict(),
            "scan": runtime.scans.diagnostics(runtime.backend.monotonic()),
            "fallback_used": False,
        },
        error=error,
    )


def _camera_calibration(config: ProductionConfiguration) -> CameraCalibration | None:
    if config.calibration is None:
        return None
    calibration = config.calibration
    if calibration.mode != "pixel_depth":
        return None
    if calibration.intrinsics is None or calibration.rotation is None or calibration.translation is None:
        raise ValueError("pixel-depth calibration is incomplete")
    values = calibration.intrinsics
    width = int(values["width"])
    height = int(values["height"])
    if float(width) != values["width"] or float(height) != values["height"]:
        raise ValueError("calibration image dimensions must be integers")
    intrinsics = CameraIntrinsics(
        values["fx"], values["fy"], values["cx"], values["cy"], width, height
    )
    transform = RigidTransform(calibration.rotation, Vector3(*calibration.translation))
    provenance = ConfigurationProvenance("measured", calibration.source, calibration.measured_at)
    return CameraCalibration(
        calibration.camera_frame,
        calibration.base_frame,
        intrinsics,
        transform,
        calibration.measured_at,
        calibration.max_age_s,
        provenance,
    )


def _run_parsed(
    arguments: argparse.Namespace,
    cancellation: Cancellation | None,
    *,
    wall_clock: Callable[[], float],
) -> MotionResult:
    if arguments.backend == "ros":
        return _run_ros(arguments, cancellation, wall_clock=wall_clock)
    return _run_fake(arguments, cancellation)


def exit_code_for(result: MotionResult) -> int:
    if result.ok:
        return 0
    if result.error is None:
        return 4
    return EXIT_BY_CATEGORY[result.error.category]


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    cancellation: Cancellation | None = None,
    wall_clock: Callable[[], float] = time.time,
) -> int:
    """Parse, execute once, and write exactly one JSON object to stdout."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    output = sys.stdout if stdout is None else stdout
    diagnostics = sys.stderr if stderr is None else stderr
    operation = _infer_operation(arguments)
    backend = _infer_backend(arguments)

    try:
        parsed = build_parser().parse_args(arguments)
        operation = parsed.command
        backend = parsed.backend
        result = _run_parsed(parsed, cancellation, wall_clock=wall_clock)
    except _UsageFailure as exc:
        diagnostics.write("error: %s\n" % exc)
        result = _failure_result(operation, backend, control_error("INVALID_INPUT", str(exc)))
    except ControlFailure as exc:
        result = _failure_result(operation, backend, exc.error, data=dict(exc.context))
    except KeyboardInterrupt:
        result = _failure_result(operation, backend, control_error("CANCELLED", "command was interrupted"))
    except Exception as exc:
        diagnostics.write("error: internal command failure\n")
        result = _failure_result(
            operation,
            backend,
            control_error("BACKEND_FAILURE", "command failed: %s" % exc),
        )

    output.write(result.to_json())
    output.write("\n")
    output.flush()
    return exit_code_for(result)
