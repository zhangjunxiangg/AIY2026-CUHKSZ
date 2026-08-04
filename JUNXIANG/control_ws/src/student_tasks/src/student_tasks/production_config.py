"""Aggregated fail-closed validation for measured board configuration."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .approach import ApproachConfiguration
from .configuration import ConfigurationProvenance
from .limits import (
    MAX_ANGULAR_SPEED_RAD_S,
    MAX_DURATION_S,
    MAX_LINEAR_SPEED_M_S,
    MAX_PUBLISH_RATE_HZ,
    MIN_DURATION_S,
    MIN_PUBLISH_RATE_HZ,
)
from .safety import SafetyConfiguration, SectorRule


CONFIG_SCHEMA = "robot-control/production-config/v1"
TARGET_SCHEMA = "robot-control/target-observation/v1"
BOARD_ROOT = "/data/local/robot/jx/control_ws/"


@dataclass(frozen=True)
class ConfigurationFinding:
    path: str
    code: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class RosConfiguration:
    node_name_prefix: str
    cmd_vel_topic: str
    scan_topic: str
    target_json_topic: str
    target_valid_topic: str
    target_schema: str


@dataclass(frozen=True)
class MotionConfiguration:
    linear_x_sign: int
    linear_y_sign: int
    angular_z_sign: int
    publish_rate_hz: float
    zero_message_count: int
    zero_interval_s: float
    subscriber_timeout_s: float
    watchdog_timeout_s: float


@dataclass(frozen=True)
class OwnershipConfiguration:
    lock_path: str
    estop_path: str
    publisher_allowlist: tuple[str, ...]
    allowlist_evidence_source: str | None
    allowlist_evidence_at: float | None


@dataclass(frozen=True)
class TargetConfiguration:
    max_source_age_s: float
    max_receive_age_s: float
    future_tolerance_s: float
    min_confidence: float
    require_calibration: bool


@dataclass(frozen=True)
class CalibrationConfiguration:
    mode: str
    source: str
    measured_at: float
    max_age_s: float
    camera_frame: str
    base_frame: str
    intrinsics: Mapping[str, float] | None
    rotation: tuple[float, ...] | None
    translation: tuple[float, ...] | None


@dataclass(frozen=True)
class ProductionConfiguration:
    provenance: ConfigurationProvenance
    robot_id: str
    ros: RosConfiguration
    motion: MotionConfiguration
    ownership: OwnershipConfiguration
    safety: SafetyConfiguration
    target: TargetConfiguration
    approach: ApproachConfiguration
    calibration: CalibrationConfiguration
    schema: str = CONFIG_SCHEMA


@dataclass(frozen=True)
class ConfigurationValidation:
    findings: tuple[ConfigurationFinding, ...]
    configuration: ProductionConfiguration | None = None

    @property
    def valid(self) -> bool:
        return not self.findings and self.configuration is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "configuration_kind": (
                "missing" if self.configuration is None else self.configuration.provenance.kind
            ),
            "findings": [finding.to_dict() for finding in self.findings],
        }


class _Validator:
    def __init__(self, now: float) -> None:
        self.now = now
        self.findings: list[ConfigurationFinding] = []

    def add(self, path: str, code: str, detail: str) -> None:
        self.findings.append(ConfigurationFinding(path, code, detail))

    def group(self, parent: Mapping[str, Any], name: str) -> Mapping[str, Any]:
        value = parent.get(name)
        if not isinstance(value, dict):
            self.add(name, "NULL_OR_MISSING", "%s must be an object" % name)
            return {}
        return value

    def string(self, parent: Mapping[str, Any], key: str, path: str) -> str | None:
        value = parent.get(key)
        if not isinstance(value, str) or not value.strip():
            self.add(path, "NULL_OR_MISSING", "%s must be a non-empty string" % path)
            return None
        return value.strip()

    def number(
        self,
        parent: Mapping[str, Any],
        key: str,
        path: str,
        *,
        minimum: float | None = None,
        strict_minimum: bool = False,
    ) -> float | None:
        value = parent.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            self.add(path, "NULL_OR_MISSING", "%s must be a finite number" % path)
            return None
        normalized = float(value)
        if minimum is not None:
            invalid = normalized <= minimum if strict_minimum else normalized < minimum
            if invalid:
                self.add(path, "VALUE_INVALID", "%s is below its allowed minimum" % path)
                return None
        return normalized

    def integer(self, parent: Mapping[str, Any], key: str, path: str, *, minimum: int) -> int | None:
        value = parent.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            self.add(path, "NULL_OR_MISSING", "%s must be an integer >= %d" % (path, minimum))
            return None
        return value

    def boolean(self, parent: Mapping[str, Any], key: str, path: str) -> bool | None:
        value = parent.get(key)
        if not isinstance(value, bool):
            self.add(path, "NULL_OR_MISSING", "%s must be boolean" % path)
            return None
        return value

    def timestamp(self, parent: Mapping[str, Any], key: str, path: str) -> float | None:
        value = self.number(parent, key, path, minimum=0.0, strict_minimum=True)
        if value is not None and value > self.now:
            self.add(path, "TIMESTAMP_INVALID", "%s cannot be in the future" % path)
            return None
        return value


def _topic(validator: _Validator, group: Mapping[str, Any], key: str) -> str | None:
    path = "ros.%s" % key
    value = validator.string(group, key, path)
    if value is not None and (not value.startswith("/") or " " in value or value == "/"):
        validator.add(path, "TOPIC_INVALID", "%s must be an absolute ROS topic" % path)
    return value


def _runtime_path(validator: _Validator, group: Mapping[str, Any], key: str) -> str | None:
    path = "ownership.%s" % key
    value = validator.string(group, key, path)
    if value is not None and (not value.startswith(BOARD_ROOT) or value.endswith("/")):
        validator.add(path, "PATH_INVALID", "%s must be a file below %s" % (path, BOARD_ROOT))
    return value


def _sequence_of_numbers(value: object, size: int) -> tuple[float, ...] | None:
    if not isinstance(value, list) or len(value) != size:
        return None
    result: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
            return None
        result.append(float(item))
    return tuple(result)


def validate_production_config(document: object, *, now: float) -> ConfigurationValidation:
    """Validate one decoded document and aggregate all independently detectable issues."""

    if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(float(now)):
        raise ValueError("now must be finite")
    validator = _Validator(float(now))
    if not isinstance(document, dict):
        return ConfigurationValidation((ConfigurationFinding("$", "CONFIG_INVALID", "root must be an object"),))

    expected_groups = {"schema", "provenance", "ros", "motion", "ownership", "safety", "target", "approach", "calibration"}
    for key in document:
        if key not in expected_groups:
            validator.add(key, "UNKNOWN_FIELD", "unknown top-level configuration field")
    if document.get("schema") != CONFIG_SCHEMA:
        validator.add("schema", "SCHEMA_INVALID", "production configuration schema is not supported")

    provenance_data = validator.group(document, "provenance")
    kind = provenance_data.get("kind")
    if kind != "measured":
        validator.add("provenance.kind", "PRODUCTION_CONFIG_REQUIRED", "production provenance must be measured")
    source = validator.string(provenance_data, "source", "provenance.source")
    measured_at = validator.timestamp(provenance_data, "measured_at", "provenance.measured_at")
    robot_id = validator.string(provenance_data, "robot_id", "provenance.robot_id")

    ros_data = validator.group(document, "ros")
    node_prefix = validator.string(ros_data, "node_name_prefix", "ros.node_name_prefix")
    if node_prefix is not None and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", node_prefix) is None:
        validator.add("ros.node_name_prefix", "NODE_NAME_INVALID", "node prefix must be a ROS-safe basename")
    cmd_vel_topic = _topic(validator, ros_data, "cmd_vel_topic")
    scan_topic = _topic(validator, ros_data, "scan_topic")
    target_json_topic = _topic(validator, ros_data, "target_json_topic")
    target_valid_topic = _topic(validator, ros_data, "target_valid_topic")
    target_schema = validator.string(ros_data, "target_schema", "ros.target_schema")
    if target_schema is not None and target_schema != TARGET_SCHEMA:
        validator.add("ros.target_schema", "TARGET_SCHEMA_INVALID", "target schema must match the versioned contract")
    topics = [topic for topic in (cmd_vel_topic, scan_topic, target_json_topic, target_valid_topic) if topic]
    normalized_topics = [topic if topic.startswith("/") else "/" + topic for topic in topics]
    if len(normalized_topics) != len(set(normalized_topics)):
        validator.add("ros", "TOPIC_CONFLICT", "configured ROS topics must be distinct")

    motion_data = validator.group(document, "motion")
    signs: dict[str, int | None] = {}
    for name in ("linear_x_sign", "linear_y_sign", "angular_z_sign"):
        value = motion_data.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value not in {-1, 1}:
            validator.add("motion.%s" % name, "DIRECTION_SIGN_INVALID", "direction sign must be exactly -1 or +1")
            signs[name] = None
        else:
            signs[name] = value
    publish_rate = validator.number(motion_data, "publish_rate_hz", "motion.publish_rate_hz", minimum=0.0, strict_minimum=True)
    zero_count = validator.integer(motion_data, "zero_message_count", "motion.zero_message_count", minimum=1)
    zero_interval = validator.number(motion_data, "zero_interval_s", "motion.zero_interval_s", minimum=0.0)
    subscriber_timeout = validator.number(motion_data, "subscriber_timeout_s", "motion.subscriber_timeout_s", minimum=0.0, strict_minimum=True)
    watchdog_timeout = validator.number(motion_data, "watchdog_timeout_s", "motion.watchdog_timeout_s", minimum=0.0, strict_minimum=True)
    if publish_rate is not None and not MIN_PUBLISH_RATE_HZ <= publish_rate <= MAX_PUBLISH_RATE_HZ:
        validator.add("motion.publish_rate_hz", "HARD_LIMIT_EXCEEDED", "publish rate is outside shared-core limits")
    if publish_rate is not None and watchdog_timeout is not None and 1.0 / publish_rate >= watchdog_timeout:
        validator.add("motion.publish_rate_hz", "CADENCE_UNSAFE", "publish period must be shorter than watchdog timeout")
    if zero_interval is not None and watchdog_timeout is not None and zero_interval >= watchdog_timeout:
        validator.add("motion.zero_interval_s", "CROSS_FIELD_INVALID", "zero interval must be shorter than watchdog timeout")

    ownership_data = validator.group(document, "ownership")
    lock_path = _runtime_path(validator, ownership_data, "lock_path")
    estop_path = _runtime_path(validator, ownership_data, "estop_path")
    if lock_path is not None and lock_path == estop_path:
        validator.add("ownership", "PATH_CONFLICT", "lock and estop paths must be distinct")
    raw_allowlist = ownership_data.get("publisher_allowlist")
    allowlist: tuple[str, ...] | None = None
    if not isinstance(raw_allowlist, list):
        validator.add("ownership.publisher_allowlist", "NULL_OR_MISSING", "publisher allowlist must be an array")
    elif any(not isinstance(node, str) or not node.startswith("/") or not node.strip() for node in raw_allowlist):
        validator.add("ownership.publisher_allowlist", "ALLOWLIST_INVALID", "allowlist entries must be absolute ROS node names")
    elif len(raw_allowlist) != len(set(raw_allowlist)):
        validator.add("ownership.publisher_allowlist", "ALLOWLIST_INVALID", "allowlist entries must be unique")
    else:
        allowlist = tuple(raw_allowlist)
    evidence_source: str | None = None
    evidence_at: float | None = None
    evidence = ownership_data.get("allowlist_evidence")
    if allowlist:
        if not isinstance(evidence, dict):
            validator.add("ownership.allowlist_evidence", "ALLOWLIST_EVIDENCE_REQUIRED", "non-empty allowlist requires dated evidence")
        else:
            evidence_source = validator.string(evidence, "source", "ownership.allowlist_evidence.source")
            evidence_at = validator.timestamp(evidence, "measured_at", "ownership.allowlist_evidence.measured_at")
    elif evidence is not None:
        validator.add("ownership.allowlist_evidence", "ALLOWLIST_EVIDENCE_UNUSED", "empty allowlist must not carry approval evidence")

    safety_data = validator.group(document, "safety")
    max_scan_age = validator.number(safety_data, "max_scan_age_s", "safety.max_scan_age_s", minimum=0.0, strict_minimum=True)
    safety_future = validator.number(safety_data, "future_tolerance_s", "safety.future_tolerance_s", minimum=0.0)
    reset_frames = validator.integer(safety_data, "reset_clear_frames", "safety.reset_clear_frames", minimum=1)
    sector_rules: list[SectorRule] = []
    raw_sectors = safety_data.get("sectors")
    if not isinstance(raw_sectors, list):
        validator.add("safety.sectors", "NULL_OR_MISSING", "safety sectors must be an array")
    else:
        for index, item in enumerate(raw_sectors):
            prefix = "safety.sectors[%d]" % index
            if not isinstance(item, dict):
                validator.add(prefix, "NULL_OR_MISSING", "sector must be an object")
                continue
            name = validator.string(item, "name", prefix + ".name")
            center = validator.number(item, "center_rad", prefix + ".center_rad")
            half = validator.number(item, "half_width_rad", prefix + ".half_width_rad", minimum=0.0, strict_minimum=True)
            clearance = validator.number(item, "min_clearance_m", prefix + ".min_clearance_m", minimum=0.0, strict_minimum=True)
            samples = validator.integer(item, "min_samples", prefix + ".min_samples", minimum=1)
            if None not in (name, center, half, clearance, samples):
                try:
                    sector_rules.append(SectorRule(name, center, half, clearance, samples))
                except ValueError as exc:
                    validator.add(prefix, "SECTOR_INVALID", str(exc))

    target_data = validator.group(document, "target")
    max_source_age = validator.number(target_data, "max_source_age_s", "target.max_source_age_s", minimum=0.0, strict_minimum=True)
    max_receive_age = validator.number(target_data, "max_receive_age_s", "target.max_receive_age_s", minimum=0.0, strict_minimum=True)
    target_future = validator.number(target_data, "future_tolerance_s", "target.future_tolerance_s", minimum=0.0)
    min_confidence = validator.number(target_data, "min_confidence", "target.min_confidence", minimum=0.0)
    if min_confidence is not None and min_confidence > 1.0:
        validator.add("target.min_confidence", "VALUE_INVALID", "minimum confidence must be in [0, 1]")
    require_calibration = validator.boolean(target_data, "require_calibration", "target.require_calibration")

    approach_data = validator.group(document, "approach")
    approach_numbers: dict[str, float | None] = {}
    for name, minimum, strict in (
        ("linear_speed_mps", 0.0, True),
        ("angular_speed_radps", 0.0, True),
        ("correction_duration_s", 0.0, True),
        ("bearing_tolerance_rad", 0.0, True),
        ("stand_off_m", 0.0, True),
        ("stand_off_tolerance_m", 0.0, True),
        ("timeout_s", 0.0, True),
        ("observation_interval_s", 0.0, True),
    ):
        approach_numbers[name] = validator.number(approach_data, name, "approach.%s" % name, minimum=minimum, strict_minimum=strict)
    stable_frames = validator.integer(approach_data, "stable_frames", "approach.stable_frames", minimum=1)
    target_loss_limit = validator.integer(approach_data, "target_loss_limit", "approach.target_loss_limit", minimum=0)
    max_iterations = validator.integer(approach_data, "max_iterations", "approach.max_iterations", minimum=1)
    if approach_numbers["linear_speed_mps"] is not None and approach_numbers["linear_speed_mps"] > MAX_LINEAR_SPEED_M_S:
        validator.add("approach.linear_speed_mps", "HARD_LIMIT_EXCEEDED", "linear speed exceeds shared-core limit")
    if approach_numbers["angular_speed_radps"] is not None and approach_numbers["angular_speed_radps"] > MAX_ANGULAR_SPEED_RAD_S:
        validator.add("approach.angular_speed_radps", "HARD_LIMIT_EXCEEDED", "angular speed exceeds shared-core limit")
    duration = approach_numbers["correction_duration_s"]
    if duration is not None and not MIN_DURATION_S <= duration <= MAX_DURATION_S:
        validator.add("approach.correction_duration_s", "HARD_LIMIT_EXCEEDED", "duration is outside shared-core limits")
    timeout = approach_numbers["timeout_s"]
    if duration is not None and timeout is not None and timeout < duration:
        validator.add("approach.timeout_s", "CROSS_FIELD_INVALID", "approach timeout cannot be shorter than one correction")

    calibration_data = validator.group(document, "calibration")
    mode = validator.string(calibration_data, "mode", "calibration.mode")
    if mode is not None and mode not in {"base_point", "pixel_depth"}:
        validator.add("calibration.mode", "CALIBRATION_INVALID", "calibration mode is unsupported")
    calibration_source = validator.string(calibration_data, "source", "calibration.source")
    calibration_at = validator.timestamp(calibration_data, "measured_at", "calibration.measured_at")
    calibration_max_age = validator.number(calibration_data, "max_age_s", "calibration.max_age_s", minimum=0.0, strict_minimum=True)
    camera_frame = validator.string(calibration_data, "camera_frame", "calibration.camera_frame")
    base_frame = validator.string(calibration_data, "base_frame", "calibration.base_frame")
    if base_frame is not None and base_frame != "base_link":
        validator.add("calibration.base_frame", "CALIBRATION_INVALID", "calibration base frame must be base_link")
    if calibration_at is not None and calibration_max_age is not None and validator.now - calibration_at > calibration_max_age:
        validator.add("calibration.measured_at", "CALIBRATION_STALE", "calibration is older than its measured validity window")
    intrinsics: Mapping[str, float] | None = None
    rotation: tuple[float, ...] | None = None
    translation: tuple[float, ...] | None = None
    if mode == "pixel_depth":
        raw_intrinsics = calibration_data.get("intrinsics")
        if not isinstance(raw_intrinsics, dict) or set(raw_intrinsics) != {"fx", "fy", "cx", "cy", "width", "height"}:
            validator.add("calibration.intrinsics", "CALIBRATION_INVALID", "pixel-depth mode requires complete intrinsics")
        else:
            try:
                intrinsics = {key: float(value) for key, value in raw_intrinsics.items()}
                if not all(math.isfinite(value) for value in intrinsics.values()):
                    raise ValueError
            except (TypeError, ValueError):
                validator.add("calibration.intrinsics", "CALIBRATION_INVALID", "intrinsics must contain finite numbers")
                intrinsics = None
        rotation = _sequence_of_numbers(calibration_data.get("rotation"), 9)
        translation = _sequence_of_numbers(calibration_data.get("translation"), 3)
        if rotation is None:
            validator.add("calibration.rotation", "CALIBRATION_INVALID", "pixel-depth mode requires nine rotation values")
        if translation is None:
            validator.add("calibration.translation", "CALIBRATION_INVALID", "pixel-depth mode requires three translation values")
    elif mode == "base_point" and any(calibration_data.get(name) is not None for name in ("intrinsics", "rotation", "translation")):
        validator.add("calibration", "CALIBRATION_INVALID", "base-point mode must not carry an unused camera transform")

    if validator.findings:
        return ConfigurationValidation(tuple(validator.findings))

    assert source is not None and measured_at is not None and robot_id is not None
    provenance = ConfigurationProvenance("measured", source, measured_at)
    try:
        safety = SafetyConfiguration(
            tuple(sector_rules), max_scan_age, safety_future, reset_frames, provenance  # type: ignore[arg-type]
        )
        approach = ApproachConfiguration(
            approach_numbers["linear_speed_mps"],
            approach_numbers["angular_speed_radps"],
            approach_numbers["correction_duration_s"],
            approach_numbers["bearing_tolerance_rad"],
            approach_numbers["stand_off_m"],
            approach_numbers["stand_off_tolerance_m"],
            stable_frames,
            target_loss_limit,
            approach_numbers["timeout_s"],
            max_iterations,
            approach_numbers["observation_interval_s"],
            publish_rate,
            provenance,
        )  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        return ConfigurationValidation((ConfigurationFinding("$", "CONFIG_INVALID", str(exc)),))

    configuration = ProductionConfiguration(
        provenance=provenance,
        robot_id=robot_id,
        ros=RosConfiguration(node_prefix, cmd_vel_topic, scan_topic, target_json_topic, target_valid_topic, target_schema),  # type: ignore[arg-type]
        motion=MotionConfiguration(
            signs["linear_x_sign"], signs["linear_y_sign"], signs["angular_z_sign"], publish_rate,
            zero_count, zero_interval, subscriber_timeout, watchdog_timeout,
        ),  # type: ignore[arg-type]
        ownership=OwnershipConfiguration(lock_path, estop_path, allowlist, evidence_source, evidence_at),  # type: ignore[arg-type]
        safety=safety,
        target=TargetConfiguration(max_source_age, max_receive_age, target_future, min_confidence, require_calibration),  # type: ignore[arg-type]
        approach=approach,
        calibration=CalibrationConfiguration(
            mode, calibration_source, calibration_at, calibration_max_age, camera_frame, base_frame,
            intrinsics, rotation, translation,
        ),  # type: ignore[arg-type]
    )
    return ConfigurationValidation((), configuration)


def load_production_config(path: str | Path, *, now: float) -> ConfigurationValidation:
    """Load UTF-8 JSON without defaults, fallback, or environment expansion."""

    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return ConfigurationValidation(
            (ConfigurationFinding("$", "CONFIG_JSON_INVALID", "configuration JSON is invalid: %s" % exc),)
        )
    except OSError as exc:
        return ConfigurationValidation(
            (ConfigurationFinding("$", "CONFIG_UNREADABLE", "configuration cannot be read: %s" % exc),)
        )
    return validate_production_config(document, now=now)
