"""Bounded in-process visual approach state machine."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from .backend import Cancellation
from .configuration import ConfigurationProvenance
from .core import MotionController
from .limits import (
    MAX_ANGULAR_SPEED_RAD_S,
    MAX_DURATION_S,
    MAX_LINEAR_SPEED_M_S,
    MAX_PUBLISH_RATE_HZ,
    MIN_DURATION_S,
    MIN_PUBLISH_RATE_HZ,
    validate_operation_id,
)
from .models import MotionRequest, MotionResult, Velocity, VerificationLevel
from .perception import (
    BaseTargetObservation,
    CameraCalibration,
    NormalizedTarget,
    PixelDepthObservation,
    TargetPolicy,
    normalize_target,
)
from .safety import LaserScanSnapshot, SafetyDecision, SafetyMonitor


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("%s must be finite" % name)
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError("%s must be finite" % name)
    return normalized


class ApproachState(str, Enum):
    IDLE = "IDLE"
    PRECHECK = "PRECHECK"
    ROTATE = "ROTATE"
    TRANSLATE = "TRANSLATE"
    VERIFY = "VERIFY"
    STOPPING = "STOPPING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ESTOPPED = "ESTOPPED"


@runtime_checkable
class TargetProvider(Protocol):
    def latest(self, now: float) -> BaseTargetObservation | PixelDepthObservation | None:
        ...


@runtime_checkable
class ScanProvider(Protocol):
    def latest(self, now: float) -> LaserScanSnapshot | None:
        ...


@dataclass(frozen=True)
class ApproachConfiguration:
    linear_speed_mps: float
    angular_speed_radps: float
    correction_duration_s: float
    bearing_tolerance_rad: float
    stand_off_m: float
    stand_off_tolerance_m: float
    stable_frames: int
    target_loss_limit: int
    timeout_s: float
    max_iterations: int
    observation_interval_s: float
    publish_rate_hz: float
    provenance: ConfigurationProvenance

    def __post_init__(self) -> None:
        numeric_fields = (
            "linear_speed_mps",
            "angular_speed_radps",
            "correction_duration_s",
            "bearing_tolerance_rad",
            "stand_off_m",
            "stand_off_tolerance_m",
            "timeout_s",
            "observation_interval_s",
            "publish_rate_hz",
        )
        for name in numeric_fields:
            object.__setattr__(self, name, _finite(getattr(self, name), name))
        if not 0.0 < self.linear_speed_mps <= MAX_LINEAR_SPEED_M_S:
            raise ValueError("linear_speed_mps exceeds the hard limit")
        if not 0.0 < self.angular_speed_radps <= MAX_ANGULAR_SPEED_RAD_S:
            raise ValueError("angular_speed_radps exceeds the hard limit")
        if not MIN_DURATION_S <= self.correction_duration_s <= MAX_DURATION_S:
            raise ValueError("correction_duration_s is outside the hard duration limits")
        if not 0.0 < self.bearing_tolerance_rad <= math.pi:
            raise ValueError("bearing_tolerance_rad must be in (0, pi]")
        if self.stand_off_m <= 0.0 or not 0.0 < self.stand_off_tolerance_m < self.stand_off_m:
            raise ValueError("stand-off values are invalid")
        if self.timeout_s <= 0.0 or self.observation_interval_s <= 0.0:
            raise ValueError("Approach timing values must be positive")
        if not MIN_PUBLISH_RATE_HZ <= self.publish_rate_hz <= MAX_PUBLISH_RATE_HZ:
            raise ValueError("publish_rate_hz is outside the hard limits")
        for name, minimum in (("stable_frames", 1), ("target_loss_limit", 0), ("max_iterations", 1)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValueError("%s must be an integer >= %d" % (name, minimum))
        if not isinstance(self.provenance, ConfigurationProvenance):
            raise ValueError("Approach configuration requires provenance")


@dataclass(frozen=True)
class ApproachResult:
    terminal_state: ApproachState
    state_history: tuple[ApproachState, ...]
    corrections: tuple[MotionResult, ...]
    last_target: NormalizedTarget | None
    last_safety: SafetyDecision | None
    stop_result: MotionResult
    elapsed_s: float
    stable_frames: int
    verification: VerificationLevel
    error_code: str | None = None
    error_detail: str | None = None
    original_error_code: str | None = None
    schema: str = "robot-control/approach-result/v1"

    @property
    def ok(self) -> bool:
        return self.terminal_state == ApproachState.SUCCEEDED and self.error_code is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "ok": self.ok,
            "terminal_state": self.terminal_state.value,
            "state_history": [state.value for state in self.state_history],
            "corrections": [correction.to_dict() for correction in self.corrections],
            "last_target": None if self.last_target is None else self.last_target.to_dict(),
            "last_safety": None if self.last_safety is None else self.last_safety.to_dict(),
            "stop_result": self.stop_result.to_dict(),
            "elapsed_s": self.elapsed_s,
            "stable_frames": self.stable_frames,
            "verification": self.verification.value,
            "error_code": self.error_code,
            "error_detail": self.error_detail,
            "original_error_code": self.original_error_code,
        }


class ApproachController:
    """Re-observe, authorize, correct, and verify using one shared core."""

    def __init__(
        self,
        *,
        motion: MotionController,
        safety: SafetyMonitor,
        targets: TargetProvider,
        scans: ScanProvider,
        configuration: ApproachConfiguration,
        target_policy: TargetPolicy,
        calibration: CameraCalibration | None = None,
        production: bool = False,
    ) -> None:
        if not isinstance(motion, MotionController):
            raise ValueError("motion must be MotionController")
        if not isinstance(safety, SafetyMonitor):
            raise ValueError("safety must be SafetyMonitor")
        if not isinstance(targets, TargetProvider) or not isinstance(scans, ScanProvider):
            raise ValueError("Approach providers do not satisfy their contracts")
        if not isinstance(configuration, ApproachConfiguration):
            raise ValueError("configuration must be ApproachConfiguration")
        if not isinstance(target_policy, TargetPolicy):
            raise ValueError("target_policy must be TargetPolicy")
        self.motion = motion
        self.safety = safety
        self.targets = targets
        self.scans = scans
        self.configuration = configuration
        self.target_policy = target_policy
        self.calibration = calibration
        self.production = bool(production)

    def run(self, operation_id: str, cancellation: Cancellation | None = None) -> ApproachResult:
        operation = validate_operation_id(operation_id)
        start = self.motion.backend.monotonic()
        states: list[ApproachState] = []
        corrections: list[MotionResult] = []
        last_target: NormalizedTarget | None = None
        last_safety: SafetyDecision | None = None
        stable_frames = 0
        losses = 0
        iterations = 0

        terminal = ApproachState.FAILED
        error_code: str | None = None
        error_detail: str | None = None
        original_error_code: str | None = None

        while True:
            states.append(ApproachState.PRECHECK)
            now = self.motion.backend.monotonic()
            if cancellation is not None and cancellation.is_cancelled():
                terminal = ApproachState.CANCELLED
                error_code = "CANCELLED"
                error_detail = "Approach was cancelled"
                break
            if now - start >= self.configuration.timeout_s:
                error_code = "APPROACH_TIMEOUT"
                error_detail = "Approach timeout reached"
                break
            if iterations >= self.configuration.max_iterations:
                error_code = "ITERATION_LIMIT"
                error_detail = "Approach iteration limit reached"
                break
            iterations += 1

            try:
                observation = self.targets.latest(now)
            except Exception:
                observation = None
            normalized = normalize_target(
                observation,
                now=now,
                policy=self.target_policy,
                calibration=self.calibration,
                production=self.production,
            )
            if not normalized.ok:
                losses += 1
                stable_frames = 0
                if losses > self.configuration.target_loss_limit:
                    error_code = normalized.code
                    error_detail = normalized.detail
                    break
                self.motion.backend.sleep(self.configuration.observation_interval_s)
                continue

            losses = 0
            target = normalized.target
            assert target is not None
            last_target = target
            too_close_boundary = self.configuration.stand_off_m - self.configuration.stand_off_tolerance_m
            if target.planar_distance_m < too_close_boundary:
                error_code = "TARGET_TOO_CLOSE"
                error_detail = "Target is closer than the allowed stand-off; automatic reverse is disabled"
                break

            velocity: Velocity | None = None
            correction_state: ApproachState | None = None
            if abs(target.bearing_rad) > self.configuration.bearing_tolerance_rad:
                stable_frames = 0
                correction_state = ApproachState.ROTATE
                angular = math.copysign(self.configuration.angular_speed_radps, target.bearing_rad)
                velocity = Velocity(0.0, 0.0, angular)
            elif (
                target.planar_distance_m
                > self.configuration.stand_off_m + self.configuration.stand_off_tolerance_m
            ):
                stable_frames = 0
                correction_state = ApproachState.TRANSLATE
                velocity = Velocity(self.configuration.linear_speed_mps, 0.0, 0.0)

            if velocity is None or correction_state is None:
                states.append(ApproachState.VERIFY)
                stable_frames += 1
                if stable_frames >= self.configuration.stable_frames:
                    terminal = ApproachState.SUCCEEDED
                    break
                self.motion.backend.sleep(self.configuration.observation_interval_s)
                continue

            states.append(correction_state)
            try:
                scan = self.scans.latest(self.motion.backend.monotonic())
            except Exception:
                scan = None
            last_safety = self.safety.evaluate(
                velocity,
                scan,
                now=self.motion.backend.monotonic(),
            )
            if not last_safety.allowed:
                terminal = ApproachState.ESTOPPED
                error_code = "ESTOP_LATCHED" if last_safety.code == "ESTOP_LATCHED" else "SAFETY_REJECTED"
                error_detail = "Safety gate rejected correction: %s" % last_safety.code
                break

            request = MotionRequest(
                self._correction_id(operation, iterations, correction_state),
                velocity,
                self.configuration.correction_duration_s,
                self.configuration.publish_rate_hz,
            )
            correction = self.motion.move(request, cancellation)
            corrections.append(correction)
            if not correction.ok:
                if correction.error is not None and correction.error.code == "CANCELLED":
                    terminal = ApproachState.CANCELLED
                    error_code = "CANCELLED"
                    error_detail = "Approach correction was cancelled"
                elif correction.error is not None and correction.error.code == "STOP_FAILED":
                    error_code = "STOP_FAILED"
                    error_detail = "Correction could not confirm zero velocity"
                elif correction.error is not None and correction.error.code == "TIMEOUT":
                    error_code = "APPROACH_TIMEOUT"
                    error_detail = "Approach correction exceeded the remaining deadline"
                else:
                    error_code = "MOTION_FAILED"
                    error_detail = "Shared motion core rejected or failed the correction"
                original_error_code = None if correction.error is None else correction.error.code
                break

        return self._finish(
            start=start,
            states=states,
            corrections=corrections,
            last_target=last_target,
            last_safety=last_safety,
            stable_frames=stable_frames,
            terminal=terminal,
            error_code=error_code,
            error_detail=error_detail,
            original_error_code=original_error_code,
        )

    def _finish(
        self,
        *,
        start: float,
        states: list[ApproachState],
        corrections: list[MotionResult],
        last_target: NormalizedTarget | None,
        last_safety: SafetyDecision | None,
        stable_frames: int,
        terminal: ApproachState,
        error_code: str | None,
        error_detail: str | None,
        original_error_code: str | None,
    ) -> ApproachResult:
        states.append(ApproachState.STOPPING)
        stop_result = self.motion.stop()
        if not stop_result.ok:
            original_error_code = error_code or original_error_code
            error_code = "STOP_FAILED"
            error_detail = "Final approach stop could not confirm zero velocity"
            terminal = ApproachState.FAILED
        states.append(terminal)
        elapsed = max(0.0, self.motion.backend.monotonic() - start)
        return ApproachResult(
            terminal_state=terminal,
            state_history=tuple(states),
            corrections=tuple(corrections),
            last_target=last_target,
            last_safety=last_safety,
            stop_result=stop_result,
            elapsed_s=elapsed,
            stable_frames=stable_frames,
            verification=self.motion.backend.verification_level,
            error_code=error_code,
            error_detail=error_detail,
            original_error_code=original_error_code,
        )

    @staticmethod
    def _correction_id(operation: str, iteration: int, state: ApproachState) -> str:
        suffix = "-%d-%s" % (iteration, state.value.lower())
        return operation[: 128 - len(suffix)] + suffix
