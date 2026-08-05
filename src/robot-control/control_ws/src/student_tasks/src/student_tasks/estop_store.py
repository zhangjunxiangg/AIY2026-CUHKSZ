"""Atomic persistent emergency-stop state shared by finite CLI processes."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable


ESTOP_SCHEMA = "robot-control/estop-state/v1"


@dataclass(frozen=True)
class EstopRecord:
    latched: bool
    trigger_code: str | None
    trigger_detail: str | None
    triggered_at: float | None
    last_safety_digest: str | None
    reset_requested: bool
    clear_frames: int
    updated_at: float | None
    writer_pid: int | None
    valid_state: bool = True
    schema: str = ESTOP_SCHEMA

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "latched": self.latched,
            "trigger_code": self.trigger_code,
            "trigger_detail": self.trigger_detail,
            "triggered_at": self.triggered_at,
            "last_safety_digest": self.last_safety_digest,
            "reset_requested": self.reset_requested,
            "clear_frames": self.clear_frames,
            "updated_at": self.updated_at,
            "writer_pid": self.writer_pid,
        }


class EstopStore:
    def __init__(self, path: str | Path, *, pid: Callable[[], int] = os.getpid) -> None:
        self.path = Path(path)
        self._pid = pid

    def read(self) -> EstopRecord:
        if not self.path.exists():
            return self._invalid("ESTOP_STATE_MISSING", "persistent estop state is missing")
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return self._decode(value)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return self._invalid("ESTOP_STATE_INVALID", "persistent estop state is unreadable or corrupt")

    def latch(
        self,
        code: str,
        detail: str,
        *,
        now: float,
        safety_digest: str | None = None,
    ) -> EstopRecord:
        if not code or not detail:
            raise ValueError("estop trigger code and detail must be non-empty")
        record = EstopRecord(
            latched=True,
            trigger_code=code,
            trigger_detail=detail,
            triggered_at=float(now),
            last_safety_digest=safety_digest,
            reset_requested=False,
            clear_frames=0,
            updated_at=float(now),
            writer_pid=int(self._pid()),
        )
        self._write(record)
        return record

    def request_reset(self, *, now: float) -> EstopRecord:
        current = self.read()
        if not current.latched:
            return current
        record = replace(
            current,
            reset_requested=True,
            clear_frames=0,
            updated_at=float(now),
            writer_pid=int(self._pid()),
            valid_state=True,
        )
        self._write(record)
        return record

    def advance_reset(self, *, clear: bool, required_frames: int, now: float) -> EstopRecord:
        if isinstance(required_frames, bool) or not isinstance(required_frames, int) or required_frames < 1:
            raise ValueError("required_frames must be a positive integer")
        current = self.read()
        if not current.latched or not current.reset_requested:
            return current
        next_count = current.clear_frames + 1 if clear else 0
        if next_count >= required_frames:
            record = EstopRecord(
                latched=False,
                trigger_code=None,
                trigger_detail=None,
                triggered_at=None,
                last_safety_digest=current.last_safety_digest,
                reset_requested=False,
                clear_frames=0,
                updated_at=float(now),
                writer_pid=int(self._pid()),
            )
        else:
            record = replace(
                current,
                clear_frames=next_count,
                updated_at=float(now),
                writer_pid=int(self._pid()),
                valid_state=True,
            )
        self._write(record)
        return record

    def _write(self, record: EstopRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=self.path.name + ".", dir=self.path.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(record.to_dict(), stream, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
            os.chmod(self.path, 0o600)
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    def _decode(self, value: object) -> EstopRecord:
        if not isinstance(value, dict) or value.get("schema") != ESTOP_SCHEMA:
            raise ValueError("invalid estop schema")
        latched = value.get("latched")
        reset_requested = value.get("reset_requested")
        clear_frames = value.get("clear_frames")
        if not isinstance(latched, bool) or not isinstance(reset_requested, bool):
            raise ValueError("invalid estop booleans")
        if isinstance(clear_frames, bool) or not isinstance(clear_frames, int) or clear_frames < 0:
            raise ValueError("invalid estop clear counter")
        code = value.get("trigger_code")
        detail = value.get("trigger_detail")
        if latched and (not isinstance(code, str) or not code or not isinstance(detail, str) or not detail):
            raise ValueError("latched estop requires trigger evidence")
        return EstopRecord(
            latched=latched,
            trigger_code=code if isinstance(code, str) else None,
            trigger_detail=detail if isinstance(detail, str) else None,
            triggered_at=_optional_number(value.get("triggered_at")),
            last_safety_digest=(
                value.get("last_safety_digest") if isinstance(value.get("last_safety_digest"), str) else None
            ),
            reset_requested=reset_requested,
            clear_frames=clear_frames,
            updated_at=_optional_number(value.get("updated_at")),
            writer_pid=(value.get("writer_pid") if isinstance(value.get("writer_pid"), int) else None),
        )

    @staticmethod
    def _invalid(code: str, detail: str) -> EstopRecord:
        return EstopRecord(
            latched=True,
            trigger_code=code,
            trigger_detail=detail,
            triggered_at=None,
            last_safety_digest=None,
            reset_requested=False,
            clear_frames=0,
            updated_at=None,
            writer_pid=None,
            valid_state=False,
        )


def _optional_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
