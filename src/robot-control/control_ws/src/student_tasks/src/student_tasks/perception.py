"""Fail-closed visual target normalization into base_link coordinates."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .configuration import ConfigurationProvenance
from .geometry import CameraIntrinsics, RigidTransform, Vector3, base_planar_geometry, unproject_pixel


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    return normalized if math.isfinite(normalized) else None


@dataclass(frozen=True)
class TargetPolicy:
    max_target_age_s: float
    future_tolerance_s: float
    min_confidence: float
    max_coordinate_abs_m: float = 100.0

    def __post_init__(self) -> None:
        for name in ("max_target_age_s", "future_tolerance_s", "min_confidence", "max_coordinate_abs_m"):
            value = _finite(getattr(self, name))
            if value is None:
                raise ValueError("%s must be finite" % name)
            object.__setattr__(self, name, value)
        if self.max_target_age_s <= 0.0 or self.future_tolerance_s < 0.0:
            raise ValueError("Target age limits are invalid")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        if self.max_coordinate_abs_m <= 0.0:
            raise ValueError("max_coordinate_abs_m must be positive")


@dataclass(frozen=True)
class BaseTargetObservation:
    observed_at: object
    frame_id: object
    x: object
    y: object
    z: object
    valid: object
    confidence: object
    source: object


@dataclass(frozen=True)
class PixelDepthObservation:
    observed_at: object
    frame_id: object
    u: object
    v: object
    depth_m: object
    valid: object
    confidence: object
    source: object


@dataclass(frozen=True)
class CameraCalibration:
    camera_frame: str
    base_frame: str
    intrinsics: CameraIntrinsics
    camera_to_base: RigidTransform
    calibrated_at: float
    max_age_s: float
    provenance: ConfigurationProvenance

    def __post_init__(self) -> None:
        if not isinstance(self.camera_frame, str) or not self.camera_frame.strip():
            raise ValueError("Calibration camera frame must be non-empty")
        if self.base_frame != "base_link":
            raise ValueError("Calibration target frame must be base_link")
        if not isinstance(self.intrinsics, CameraIntrinsics):
            raise ValueError("Calibration requires CameraIntrinsics")
        if not isinstance(self.camera_to_base, RigidTransform):
            raise ValueError("Calibration requires RigidTransform")
        calibrated_at = _finite(self.calibrated_at)
        max_age = _finite(self.max_age_s)
        if calibrated_at is None or calibrated_at <= 0.0:
            raise ValueError("Calibration timestamp must be finite and positive")
        if max_age is None or max_age <= 0.0:
            raise ValueError("Calibration max age must be finite and positive")
        object.__setattr__(self, "calibrated_at", calibrated_at)
        object.__setattr__(self, "max_age_s", max_age)
        if not isinstance(self.provenance, ConfigurationProvenance):
            raise ValueError("Calibration requires provenance")


@dataclass(frozen=True)
class NormalizedTarget:
    observed_at: float
    x: float
    y: float
    z: float
    planar_distance_m: float
    bearing_rad: float
    confidence: float
    source: str
    calibration_provenance: ConfigurationProvenance | None = None
    frame_id: str = "base_link"

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_at": self.observed_at,
            "frame_id": self.frame_id,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "planar_distance_m": self.planar_distance_m,
            "bearing_rad": self.bearing_rad,
            "confidence": self.confidence,
            "source": self.source,
            "calibration_provenance": (
                None if self.calibration_provenance is None else self.calibration_provenance.to_dict()
            ),
        }


@dataclass(frozen=True)
class TargetNormalization:
    ok: bool
    code: str
    target: NormalizedTarget | None
    detail: str

    def __post_init__(self) -> None:
        if self.ok != (self.target is not None):
            raise ValueError("Successful normalization requires exactly one target")
        if not self.code or not self.detail:
            raise ValueError("Normalization code and detail must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "target": None if self.target is None else self.target.to_dict(),
            "detail": self.detail,
        }


def _reject(code: str, detail: str) -> TargetNormalization:
    return TargetNormalization(False, code, None, detail)


def _validate_common(
    observation: BaseTargetObservation | PixelDepthObservation,
    *,
    now: object,
    policy: TargetPolicy,
) -> tuple[float, float, str] | TargetNormalization:
    current = _finite(now)
    observed = _finite(observation.observed_at)
    if current is None or observed is None:
        return _reject("TARGET_INVALID", "Target timestamp must be finite")
    age = current - observed
    if age > policy.max_target_age_s or age < -policy.future_tolerance_s:
        return _reject("TARGET_STALE", "Target timestamp is outside the accepted freshness window")
    if observation.valid is not True:
        return _reject("TARGET_INVALID", "Target validity flag is not true")
    confidence = _finite(observation.confidence)
    if confidence is None or not 0.0 <= confidence <= 1.0 or confidence < policy.min_confidence:
        return _reject("TARGET_INVALID", "Target confidence is invalid or below threshold")
    if not isinstance(observation.source, str) or not observation.source.strip():
        return _reject("TARGET_INVALID", "Target source must be non-empty")
    return observed, confidence, observation.source.strip()


def _normalized(
    point: Vector3,
    observed_at: float,
    confidence: float,
    source: str,
    policy: TargetPolicy,
    provenance: ConfigurationProvenance | None,
) -> TargetNormalization:
    if any(abs(value) > policy.max_coordinate_abs_m for value in point.to_tuple()):
        return _reject("TARGET_INVALID", "Target coordinate exceeds the configured bound")
    distance, bearing = base_planar_geometry(point)
    target = NormalizedTarget(
        observed_at=observed_at,
        x=point.x,
        y=point.y,
        z=point.z,
        planar_distance_m=distance,
        bearing_rad=bearing,
        confidence=confidence,
        source=source,
        calibration_provenance=provenance,
    )
    return TargetNormalization(True, "TARGET_OK", target, "Target normalized into base_link")


def normalize_target(
    observation: BaseTargetObservation | PixelDepthObservation | None,
    *,
    now: object,
    policy: TargetPolicy,
    calibration: CameraCalibration | None = None,
    production: bool = False,
) -> TargetNormalization:
    """Validate and normalize one observation without fallback or frame guessing."""

    if not isinstance(policy, TargetPolicy):
        raise ValueError("policy must be TargetPolicy")
    if observation is None:
        return _reject("TARGET_UNAVAILABLE", "No target observation is available")
    if not isinstance(observation, (BaseTargetObservation, PixelDepthObservation)):
        return _reject("TARGET_INVALID", "Unsupported target observation type")

    common = _validate_common(observation, now=now, policy=policy)
    if isinstance(common, TargetNormalization):
        return common
    observed_at, confidence, source = common

    if isinstance(observation, BaseTargetObservation):
        if observation.frame_id != "base_link":
            return _reject("TARGET_FRAME_INVALID", "Base target frame must be base_link")
        coordinates = tuple(_finite(value) for value in (observation.x, observation.y, observation.z))
        if any(value is None for value in coordinates):
            return _reject("TARGET_INVALID", "Base target coordinates must be finite")
        x, y, z = coordinates
        assert x is not None and y is not None and z is not None
        return _normalized(Vector3(x, y, z), observed_at, confidence, source, policy, None)

    if not isinstance(calibration, CameraCalibration):
        return _reject("CALIBRATION_REQUIRED", "Pixel-depth target requires camera calibration")
    if observation.frame_id != calibration.camera_frame:
        return _reject("TARGET_FRAME_INVALID", "Pixel target frame does not match calibration")
    current = _finite(now)
    if current is None:
        return _reject("TARGET_INVALID", "Current timestamp must be finite")
    calibration_age = current - calibration.calibrated_at
    if calibration_age > calibration.max_age_s or calibration_age < -policy.future_tolerance_s:
        return _reject("CALIBRATION_REQUIRED", "Camera calibration is stale or future-dated")
    if production and calibration.provenance.kind != "measured":
        return _reject("CALIBRATION_REQUIRED", "Production target requires measured calibration")

    try:
        optical_point = unproject_pixel(
            observation.u,
            observation.v,
            observation.depth_m,
            calibration.intrinsics,
        )
        base_point = calibration.camera_to_base.apply(optical_point)
    except ValueError:
        return _reject("TARGET_INVALID", "Pixel, depth, or camera geometry is invalid")
    return _normalized(
        base_point,
        observed_at,
        confidence,
        source,
        policy,
        calibration.provenance,
    )
