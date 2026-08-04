"""Directional lidar gating and deliberately reset emergency-stop state."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

from .configuration import ConfigurationProvenance
from .models import Velocity


SECTOR_ORDER = ("front", "rear", "left", "right")


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    return normalized if math.isfinite(normalized) else None


def _required_sectors(velocity: Velocity) -> tuple[str, ...]:
    if velocity.angular_z != 0.0:
        return SECTOR_ORDER
    requested: set[str] = set()
    if velocity.linear_x > 0.0:
        requested.add("front")
    elif velocity.linear_x < 0.0:
        requested.add("rear")
    if velocity.linear_y > 0.0:
        requested.add("left")
    elif velocity.linear_y < 0.0:
        requested.add("right")
    return tuple(name for name in SECTOR_ORDER if name in requested)


def _angular_distance(first: float, second: float) -> float:
    return abs((first - second + math.pi) % (2.0 * math.pi) - math.pi)


@dataclass(frozen=True)
class LaserScanSnapshot:
    """ROS-independent snapshot; evaluator validates metadata before use."""

    observed_at: object
    angle_min: object
    angle_increment: object
    range_min: object
    range_max: object
    ranges: tuple[object, ...]

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "ranges", tuple(self.ranges))
        except TypeError:
            object.__setattr__(self, "ranges", ())


@dataclass(frozen=True)
class SectorRule:
    name: str
    center_rad: float
    half_width_rad: float
    min_clearance_m: float
    min_samples: int

    def __post_init__(self) -> None:
        if self.name not in SECTOR_ORDER:
            raise ValueError("Unknown lidar sector")
        for field in ("center_rad", "half_width_rad", "min_clearance_m"):
            value = _finite(getattr(self, field))
            if value is None:
                raise ValueError("%s must be finite" % field)
            object.__setattr__(self, field, value)
        object.__setattr__(
            self,
            "center_rad",
            math.atan2(math.sin(self.center_rad), math.cos(self.center_rad)),
        )
        if not 0.0 < self.half_width_rad <= math.pi / 2.0:
            raise ValueError("Sector half width must be in (0, pi/2]")
        if self.min_clearance_m <= 0.0:
            raise ValueError("Sector clearance must be positive")
        if isinstance(self.min_samples, bool) or not isinstance(self.min_samples, int) or self.min_samples < 1:
            raise ValueError("Sector minimum samples must be a positive integer")


@dataclass(frozen=True)
class SafetyConfiguration:
    sectors: tuple[SectorRule, ...]
    max_scan_age_s: float
    future_tolerance_s: float
    reset_clear_frames: int
    provenance: ConfigurationProvenance

    def __post_init__(self) -> None:
        sectors = tuple(self.sectors)
        if any(not isinstance(rule, SectorRule) for rule in sectors):
            raise ValueError("Safety sectors must be SectorRule values")
        names = tuple(rule.name for rule in sectors)
        if len(sectors) != 4 or set(names) != set(SECTOR_ORDER):
            raise ValueError("Safety configuration requires exactly four unique sectors")
        object.__setattr__(self, "sectors", sectors)
        for field in ("max_scan_age_s", "future_tolerance_s"):
            value = _finite(getattr(self, field))
            if value is None or value < 0.0:
                raise ValueError("%s must be finite and non-negative" % field)
            object.__setattr__(self, field, value)
        if self.max_scan_age_s <= 0.0:
            raise ValueError("max_scan_age_s must be positive")
        if (
            isinstance(self.reset_clear_frames, bool)
            or not isinstance(self.reset_clear_frames, int)
            or self.reset_clear_frames < 1
        ):
            raise ValueError("reset_clear_frames must be a positive integer")
        if not isinstance(self.provenance, ConfigurationProvenance):
            raise ValueError("Safety configuration requires provenance")

    def sector(self, name: str) -> SectorRule:
        return next(rule for rule in self.sectors if rule.name == name)


@dataclass(frozen=True)
class SectorEvidence:
    name: str
    sample_count: int
    minimum_m: float | None
    threshold_m: float
    clear: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sample_count": self.sample_count,
            "minimum_m": self.minimum_m,
            "threshold_m": self.threshold_m,
            "clear": self.clear,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    code: str
    requested_velocity: Velocity
    required_sectors: tuple[str, ...]
    sectors: tuple[SectorEvidence, ...]
    latched: bool
    latch_reason: str | None
    scan_age_s: float | None
    clear_frames: int = 0
    schema: str = "robot-control/safety-decision/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "allowed": self.allowed,
            "code": self.code,
            "velocity": self.requested_velocity.to_dict(),
            "required_sectors": list(self.required_sectors),
            "sectors": [sector.to_dict() for sector in self.sectors],
            "latched": self.latched,
            "latch_reason": self.latch_reason,
            "scan_age_s": self.scan_age_s,
            "clear_frames": self.clear_frames,
        }


class SafetyMonitor:
    """Stateful fail-closed gate; one instance owns one global estop latch."""

    def __init__(self, configuration: SafetyConfiguration) -> None:
        if not isinstance(configuration, SafetyConfiguration):
            raise ValueError("configuration must be SafetyConfiguration")
        self.configuration = configuration
        self._rules = {rule.name: rule for rule in configuration.sectors}
        self._latched = False
        self._latch_reason: str | None = None
        self._latched_at: float | None = None
        self._reset_pending = False
        self._clear_frames = 0

    @property
    def latched(self) -> bool:
        return self._latched

    @property
    def latch_reason(self) -> str | None:
        return self._latch_reason

    @property
    def clear_frames(self) -> int:
        return self._clear_frames

    def evaluate(
        self,
        velocity: Velocity,
        scan: LaserScanSnapshot | None,
        *,
        now: object,
    ) -> SafetyDecision:
        if not isinstance(velocity, Velocity):
            raise ValueError("velocity must be Velocity")
        required = _required_sectors(velocity)
        if velocity.is_zero:
            return self._decision(True, "ZERO_VELOCITY", velocity, (), (), None)
        if self._latched:
            return self._decision(False, "ESTOP_LATCHED", velocity, required, (), None)

        code, evidence, age = self._evaluate_scan(scan, required, now)
        allowed = code == "CLEAR"
        if not allowed:
            self._trigger(code, now)
        return self._decision(allowed, code, velocity, required, evidence, age)

    def request_reset(self) -> bool:
        if not self._latched:
            return False
        self._reset_pending = True
        self._clear_frames = 0
        return True

    def observe_reset(self, scan: LaserScanSnapshot | None, *, now: object) -> SafetyDecision:
        zero = Velocity(0.0, 0.0, 0.0)
        if not self._latched:
            return self._decision(False, "ALREADY_CLEAR", zero, SECTOR_ORDER, (), None)

        code, evidence, age = self._evaluate_scan(scan, SECTOR_ORDER, now)
        if not self._reset_pending:
            return self._decision(False, "RESET_NOT_REQUESTED", zero, SECTOR_ORDER, evidence, age)

        if code != "CLEAR":
            self._clear_frames = 0
            reset_code = "RESET_BLOCKED" if code == "SECTOR_BLOCKED" else code
            return self._decision(False, reset_code, zero, SECTOR_ORDER, evidence, age)

        self._clear_frames += 1
        if self._clear_frames < self.configuration.reset_clear_frames:
            return self._decision(False, "RESET_PENDING", zero, SECTOR_ORDER, evidence, age)

        completed_frames = self._clear_frames
        self._latched = False
        self._latch_reason = None
        self._latched_at = None
        self._reset_pending = False
        self._clear_frames = 0
        return SafetyDecision(
            allowed=False,
            code="RESET_COMPLETE",
            requested_velocity=zero,
            required_sectors=SECTOR_ORDER,
            sectors=evidence,
            latched=False,
            latch_reason=None,
            scan_age_s=age,
            clear_frames=completed_frames,
        )

    def _trigger(self, reason: str, now: object) -> None:
        if self._latched:
            return
        self._latched = True
        self._latch_reason = reason
        self._latched_at = _finite(now)
        self._reset_pending = False
        self._clear_frames = 0

    def _decision(
        self,
        allowed: bool,
        code: str,
        velocity: Velocity,
        required: tuple[str, ...],
        evidence: tuple[SectorEvidence, ...],
        age: float | None,
    ) -> SafetyDecision:
        return SafetyDecision(
            allowed=allowed,
            code=code,
            requested_velocity=velocity,
            required_sectors=required,
            sectors=evidence,
            latched=self._latched,
            latch_reason=self._latch_reason,
            scan_age_s=age,
            clear_frames=self._clear_frames,
        )

    def _evaluate_scan(
        self,
        scan: LaserScanSnapshot | None,
        required: tuple[str, ...],
        now: object,
    ) -> tuple[str, tuple[SectorEvidence, ...], float | None]:
        if not isinstance(scan, LaserScanSnapshot):
            return "SCAN_UNAVAILABLE", (), None
        current = _finite(now)
        observed = _finite(scan.observed_at)
        angle_min = _finite(scan.angle_min)
        increment = _finite(scan.angle_increment)
        range_min = _finite(scan.range_min)
        range_max = _finite(scan.range_max)
        if None in (current, observed, angle_min, increment, range_min, range_max):
            return "SCAN_INVALID", (), None
        assert current is not None and observed is not None
        assert angle_min is not None and increment is not None
        assert range_min is not None and range_max is not None
        age = current - observed
        if age < -self.configuration.future_tolerance_s:
            return "SCAN_FUTURE", (), age
        if age > self.configuration.max_scan_age_s:
            return "SCAN_STALE", (), age
        if increment == 0.0 or range_min <= 0.0 or range_max <= range_min or not scan.ranges:
            return "SCAN_INVALID", (), age
        if abs(increment) * (len(scan.ranges) - 1) > 2.0 * math.pi + 1e-6:
            return "SCAN_INVALID", (), age

        selected = [
            (name, self._rules[name].center_rad, self._rules[name].half_width_rad, [])
            for name in required
        ]
        for index, raw_range in enumerate(scan.ranges):
            distance = _finite(raw_range)
            if distance is None or distance <= 0.0 or not range_min <= distance <= range_max:
                continue
            angle = angle_min + index * increment
            for _, center, half_width, sector_samples in selected:
                if _angular_distance(angle, center) <= half_width + 1e-12:
                    sector_samples.append(distance)

        evidence: list[SectorEvidence] = []
        insufficient = False
        blocked = False
        for name, _, _, distances in selected:
            rule = self._rules[name]
            minimum = min(distances) if distances else None
            if len(distances) < rule.min_samples:
                insufficient = True
                evidence.append(
                    SectorEvidence(name, len(distances), minimum, rule.min_clearance_m, False, "insufficient_samples")
                )
                continue
            clear = minimum is not None and minimum >= rule.min_clearance_m
            blocked = blocked or not clear
            evidence.append(
                SectorEvidence(
                    name,
                    len(distances),
                    minimum,
                    rule.min_clearance_m,
                    clear,
                    None if clear else "below_clearance",
                )
            )
        if insufficient:
            return "SCAN_INSUFFICIENT", tuple(evidence), age
        if blocked:
            return "SECTOR_BLOCKED", tuple(evidence), age
        return "CLEAR", tuple(evidence), age
