"""Thread-safe ROS scan and versioned target observation adapters."""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass, replace
from typing import Any

from .perception import BaseTargetObservation, PixelDepthObservation
from .ros_facade import RosFacade
from .safety import LaserScanSnapshot


TargetObservation = BaseTargetObservation | PixelDepthObservation


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    return normalized if math.isfinite(normalized) else None


def _stamp_seconds(message: object) -> float | None:
    try:
        return _finite(message.header.stamp.to_sec())
    except (AttributeError, TypeError, ValueError):
        return None


@dataclass(frozen=True)
class RosScanEnvelope:
    topic: str
    scan: LaserScanSnapshot | None
    source_time: float | None
    received_monotonic: float | None
    frame_id: str | None
    sequence: int
    error_code: str | None = None
    error_detail: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "topic": self.topic,
            "source_time": self.source_time,
            "received_monotonic": self.received_monotonic,
            "frame_id": self.frame_id,
            "sequence": self.sequence,
            "available": self.scan is not None and self.error_code is None,
            "error_code": self.error_code,
            "error_detail": self.error_detail,
        }


@dataclass(frozen=True)
class RosTargetEnvelope:
    json_topic: str
    valid_topic: str
    raw_json: str | None
    observation: TargetObservation | None
    source_time: float | None
    received_monotonic: float | None
    valid_signal: bool | None
    valid_received_monotonic: float | None
    source: str | None
    calibration_source: str | None
    sequence: int
    error_code: str | None = None
    error_detail: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "json_topic": self.json_topic,
            "valid_topic": self.valid_topic,
            "source_time": self.source_time,
            "received_monotonic": self.received_monotonic,
            "valid_signal": self.valid_signal,
            "valid_received_monotonic": self.valid_received_monotonic,
            "source": self.source,
            "calibration_source": self.calibration_source,
            "sequence": self.sequence,
            "available": self.observation is not None and self.error_code is None,
            "error_code": self.error_code,
            "error_detail": self.error_detail,
        }


class RosScanProvider:
    def __init__(
        self,
        facade: RosFacade,
        topic: str,
        *,
        max_source_age_s: float,
        max_receive_age_s: float,
        future_tolerance_s: float,
    ) -> None:
        self.facade = facade
        self.topic = topic
        self.max_source_age_s = self._positive(max_source_age_s, "max_source_age_s")
        self.max_receive_age_s = self._positive(max_receive_age_s, "max_receive_age_s")
        self.future_tolerance_s = self._nonnegative(future_tolerance_s, "future_tolerance_s")
        self._lock = threading.Lock()
        self._envelope = RosScanEnvelope(topic, None, None, None, None, 0, "SCAN_UNAVAILABLE", "no scan received")
        self.subscription = facade.subscribe(topic, self._receive, "laser_scan")

    def _receive(self, message: object) -> None:
        received = self.facade.monotonic()
        with self._lock:
            sequence = self._envelope.sequence + 1
        source_time = _stamp_seconds(message)
        try:
            frame_id = str(message.header.frame_id)
            ranges = tuple(message.ranges)
            scan = LaserScanSnapshot(
                source_time,
                message.angle_min,
                message.angle_increment,
                message.range_min,
                message.range_max,
                ranges,
            )
            if source_time is None or source_time <= 0.0:
                raise ValueError("scan source timestamp must be finite and positive")
            envelope = RosScanEnvelope(self.topic, scan, source_time, received, frame_id, sequence)
        except (AttributeError, TypeError, ValueError) as exc:
            envelope = RosScanEnvelope(
                self.topic,
                None,
                source_time,
                received,
                None,
                sequence,
                "SCAN_MESSAGE_INVALID",
                str(exc),
            )
        with self._lock:
            self._envelope = envelope

    def envelope(self) -> RosScanEnvelope:
        with self._lock:
            return self._envelope

    def snapshot(self) -> LaserScanSnapshot | None:
        envelope = self.envelope()
        code, _ = self._freshness(envelope, self.facade.monotonic())
        return envelope.scan if code == "SCAN_READY" else None

    def latest(self, now: float) -> LaserScanSnapshot | None:
        envelope = self.envelope()
        code, _ = self._freshness(envelope, now)
        if code != "SCAN_READY" or envelope.scan is None or envelope.received_monotonic is None:
            return None
        return replace(envelope.scan, observed_at=envelope.received_monotonic)

    def diagnostics(self, now: float | None = None) -> dict[str, object]:
        envelope = self.envelope()
        current = self.facade.monotonic() if now is None else now
        code, ages = self._freshness(envelope, current)
        return envelope.to_dict() | {"code": code, **ages}

    def _freshness(self, envelope: RosScanEnvelope, now: object) -> tuple[str, dict[str, float | None]]:
        if envelope.error_code is not None or envelope.scan is None:
            return envelope.error_code or "SCAN_UNAVAILABLE", {"source_age_s": None, "receive_age_s": None}
        current_monotonic = _finite(now)
        received = _finite(envelope.received_monotonic)
        try:
            current_source = _finite(self.facade.source_time())
        except Exception:
            current_source = None
        source = _finite(envelope.source_time)
        if None in (current_monotonic, received, current_source, source):
            return "SCAN_TIME_INVALID", {"source_age_s": None, "receive_age_s": None}
        assert current_monotonic is not None and received is not None
        assert current_source is not None and source is not None
        source_age = current_source - source
        receive_age = current_monotonic - received
        ages = {"source_age_s": source_age, "receive_age_s": receive_age}
        if source_age < -self.future_tolerance_s:
            return "SCAN_SOURCE_FUTURE", ages
        if source_age > self.max_source_age_s:
            return "SCAN_SOURCE_STALE", ages
        if receive_age < -self.future_tolerance_s:
            return "SCAN_RECEIVE_FUTURE", ages
        if receive_age > self.max_receive_age_s:
            return "SCAN_RECEIVE_STALE", ages
        return "SCAN_READY", ages

    @staticmethod
    def _positive(value: object, name: str) -> float:
        result = _finite(value)
        if result is None or result <= 0.0:
            raise ValueError("%s must be finite and positive" % name)
        return result

    @staticmethod
    def _nonnegative(value: object, name: str) -> float:
        result = _finite(value)
        if result is None or result < 0.0:
            raise ValueError("%s must be finite and non-negative" % name)
        return result


class RosTargetProvider:
    def __init__(
        self,
        facade: RosFacade,
        json_topic: str,
        valid_topic: str,
        *,
        expected_schema: str,
        max_source_age_s: float,
        max_receive_age_s: float,
        future_tolerance_s: float,
        min_confidence: float,
        expected_camera_frame: str,
        calibration_source: str | None,
    ) -> None:
        self.facade = facade
        self.json_topic = json_topic
        self.valid_topic = valid_topic
        self.expected_schema = expected_schema
        self.max_source_age_s = RosScanProvider._positive(max_source_age_s, "max_source_age_s")
        self.max_receive_age_s = RosScanProvider._positive(max_receive_age_s, "max_receive_age_s")
        self.future_tolerance_s = RosScanProvider._nonnegative(future_tolerance_s, "future_tolerance_s")
        confidence = _finite(min_confidence)
        if confidence is None or not 0.0 <= confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        self.min_confidence = confidence
        self.expected_camera_frame = expected_camera_frame
        self.calibration_source = calibration_source
        self._lock = threading.Lock()
        self._valid_signal: bool | None = None
        self._valid_received: float | None = None
        self._envelope = RosTargetEnvelope(
            json_topic,
            valid_topic,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            calibration_source,
            0,
            "TARGET_UNAVAILABLE",
            "no target received",
        )
        self.valid_subscription = facade.subscribe(valid_topic, self._receive_valid, "bool")
        self.json_subscription = facade.subscribe(json_topic, self._receive_json, "string")

    def _receive_valid(self, message: object) -> None:
        received = self.facade.monotonic()
        value = getattr(message, "data", None)
        with self._lock:
            self._valid_signal = value if isinstance(value, bool) else None
            self._valid_received = received
            self._envelope = replace(
                self._envelope,
                valid_signal=self._valid_signal,
                valid_received_monotonic=received,
            )

    def _receive_json(self, message: object) -> None:
        received = self.facade.monotonic()
        raw = getattr(message, "data", None)
        with self._lock:
            sequence = self._envelope.sequence + 1
            valid_signal = self._valid_signal
            valid_received = self._valid_received
        try:
            if not isinstance(raw, str):
                raise _TargetContractError("TARGET_JSON_INVALID", "target message data must be a string")
            try:
                document = json.loads(raw)
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                raise _TargetContractError("TARGET_JSON_INVALID", "target JSON is invalid: %s" % exc) from exc
            observation = self._decode(document)
            source_time = float(observation.observed_at)
            source = str(observation.source)
            envelope = RosTargetEnvelope(
                self.json_topic,
                self.valid_topic,
                raw,
                observation,
                source_time,
                received,
                valid_signal,
                valid_received,
                source,
                self.calibration_source,
                sequence,
            )
        except _TargetContractError as exc:
            envelope = RosTargetEnvelope(
                self.json_topic,
                self.valid_topic,
                raw if isinstance(raw, str) else None,
                None,
                None,
                received,
                valid_signal,
                valid_received,
                None,
                self.calibration_source,
                sequence,
                exc.code,
                str(exc),
            )
        with self._lock:
            self._envelope = envelope

    def envelope(self) -> RosTargetEnvelope:
        with self._lock:
            return self._envelope

    def latest(self, now: float) -> TargetObservation | None:
        envelope = self.envelope()
        code, _ = self._freshness(envelope, now)
        if code != "TARGET_READY" or envelope.observation is None or envelope.received_monotonic is None:
            return None
        return replace(envelope.observation, observed_at=envelope.received_monotonic)

    def diagnostics(self, now: float | None = None) -> dict[str, object]:
        envelope = self.envelope()
        current = self.facade.monotonic() if now is None else now
        code, ages = self._freshness(envelope, current)
        return envelope.to_dict() | {"code": code, **ages}

    def _freshness(self, envelope: RosTargetEnvelope, now: object) -> tuple[str, dict[str, float | None]]:
        empty_ages = {"source_age_s": None, "receive_age_s": None, "valid_receive_age_s": None}
        if envelope.error_code is not None or envelope.observation is None:
            return envelope.error_code or "TARGET_UNAVAILABLE", empty_ages
        if envelope.valid_signal is not True:
            return "TARGET_VALID_SIGNAL_FALSE", empty_ages
        current_monotonic = _finite(now)
        received = _finite(envelope.received_monotonic)
        valid_received = _finite(envelope.valid_received_monotonic)
        source = _finite(envelope.source_time)
        try:
            current_source = _finite(self.facade.source_time())
        except Exception:
            current_source = None
        if None in (current_monotonic, received, valid_received, source, current_source):
            return "TARGET_TIME_INVALID", empty_ages
        assert current_monotonic is not None and received is not None and valid_received is not None
        assert source is not None and current_source is not None
        source_age = current_source - source
        receive_age = current_monotonic - received
        valid_age = current_monotonic - valid_received
        ages = {
            "source_age_s": source_age,
            "receive_age_s": receive_age,
            "valid_receive_age_s": valid_age,
        }
        if source_age < -self.future_tolerance_s:
            return "TARGET_SOURCE_FUTURE", ages
        if source_age > self.max_source_age_s:
            return "TARGET_SOURCE_STALE", ages
        if receive_age < -self.future_tolerance_s or valid_age < -self.future_tolerance_s:
            return "TARGET_RECEIVE_FUTURE", ages
        if receive_age > self.max_receive_age_s or valid_age > self.max_receive_age_s:
            return "TARGET_RECEIVE_STALE", ages
        return "TARGET_READY", ages

    def _decode(self, document: object) -> TargetObservation:
        if not isinstance(document, dict):
            raise _TargetContractError("TARGET_CONTRACT_INVALID", "target root must be an object")
        if document.get("schema") != self.expected_schema:
            raise _TargetContractError("TARGET_SCHEMA_INVALID", "target schema does not match configuration")
        kind = document.get("kind")
        common = {"schema", "kind", "observed_at", "frame_id", "valid", "confidence", "source"}
        fields_by_kind = {
            "base_point": {"x", "y", "z"},
            "pixel_depth": {"u", "v", "depth_m"},
        }
        if kind not in fields_by_kind:
            raise _TargetContractError("TARGET_CONTRACT_INVALID", "target kind is unsupported")
        expected_fields = common | fields_by_kind[kind]
        if set(document) != expected_fields:
            raise _TargetContractError("TARGET_CONTRACT_INVALID", "target fields do not match the versioned contract")

        observed_at = self._number(document.get("observed_at"), "TARGET_TIME_INVALID")
        if observed_at <= 0.0:
            raise _TargetContractError("TARGET_TIME_INVALID", "target source time must be positive")
        if document.get("valid") is not True:
            raise _TargetContractError("TARGET_VALIDITY_INVALID", "target validity must be exactly true")
        confidence = self._number(document.get("confidence"), "TARGET_CONFIDENCE_INVALID")
        if not 0.0 <= confidence <= 1.0 or confidence < self.min_confidence:
            raise _TargetContractError("TARGET_CONFIDENCE_INVALID", "target confidence is outside the accepted range")
        source = document.get("source")
        if not isinstance(source, str) or not source.strip():
            raise _TargetContractError("TARGET_PROVENANCE_INVALID", "target source provenance is required")
        frame_id = document.get("frame_id")

        if kind == "base_point":
            if frame_id != "base_link":
                raise _TargetContractError("TARGET_FRAME_INVALID", "base target frame must be base_link")
            return BaseTargetObservation(
                observed_at,
                frame_id,
                self._number(document.get("x"), "TARGET_CONTRACT_INVALID"),
                self._number(document.get("y"), "TARGET_CONTRACT_INVALID"),
                self._number(document.get("z"), "TARGET_CONTRACT_INVALID"),
                True,
                confidence,
                source.strip(),
            )

        if not isinstance(frame_id, str) or not frame_id or frame_id != self.expected_camera_frame:
            raise _TargetContractError("TARGET_FRAME_INVALID", "pixel target frame does not match calibration")
        depth = self._number(document.get("depth_m"), "TARGET_CONTRACT_INVALID")
        if depth <= 0.0:
            raise _TargetContractError("TARGET_CONTRACT_INVALID", "target depth must be positive")
        return PixelDepthObservation(
            observed_at,
            frame_id,
            self._number(document.get("u"), "TARGET_CONTRACT_INVALID"),
            self._number(document.get("v"), "TARGET_CONTRACT_INVALID"),
            depth,
            True,
            confidence,
            source.strip(),
        )

    @staticmethod
    def _number(value: object, code: str) -> float:
        result = _finite(value)
        if result is None:
            raise _TargetContractError(code, "target numeric field must be finite")
        return result


class _TargetContractError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
