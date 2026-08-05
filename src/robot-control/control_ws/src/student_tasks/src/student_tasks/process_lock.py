"""Non-blocking advisory ownership for project motion processes."""

from __future__ import annotations

import errno
import fcntl
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping


LOCK_SCHEMA = "robot-control/motion-lock/v1"
MAX_METADATA_BYTES = 4096


@dataclass(frozen=True)
class LockResult:
    acquired: bool
    code: str
    owner_metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_metadata", MappingProxyType(dict(self.owner_metadata)))


class MotionLock:
    """Hold one flock descriptor and remove only the record it created."""

    def __init__(
        self,
        path: str | Path,
        *,
        wall_clock: Callable[[], float] = time.time,
        pid: Callable[[], int] = os.getpid,
        identity: str | None = None,
    ) -> None:
        self.path = Path(path)
        self._wall_clock = wall_clock
        self._pid = pid
        self._identity = identity or uuid.uuid4().hex
        self._descriptor: int | None = None
        self._inode: tuple[int, int] | None = None
        self._operation_id: str | None = None

    @property
    def descriptor(self) -> int | None:
        return self._descriptor

    @property
    def held(self) -> bool:
        return self.assert_held()

    def probe(self) -> LockResult:
        """Inspect an existing record without creating or changing lock metadata."""

        if self._descriptor is not None:
            return LockResult(self.assert_held(), "LOCK_AVAILABLE", {"state": "owned_by_current_process"})
        try:
            descriptor = os.open(self.path, os.O_RDWR)
        except FileNotFoundError:
            return LockResult(True, "LOCK_AVAILABLE", {"state": "no_record"})
        except OSError:
            return LockResult(False, "LOCK_STATE_UNAVAILABLE", {"state": "record_unreadable"})
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                    return LockResult(False, "LOCK_STATE_UNAVAILABLE", {"state": "probe_failed"})
                return LockResult(False, "MOTION_BUSY", self._read_descriptor(descriptor))
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            return LockResult(True, "LOCK_AVAILABLE", self._read_descriptor(descriptor))
        finally:
            os.close(descriptor)

    def try_acquire(self, operation_id: str) -> LockResult:
        if not isinstance(operation_id, str) or not operation_id.strip() or len(operation_id.strip()) > 128:
            raise ValueError("operation_id must be a non-empty string of at most 128 characters")
        if self._descriptor is not None:
            raise RuntimeError("lock instance already owns a descriptor")
        operation = operation_id.strip()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                os.close(descriptor)
                raise
            owner = self._read_descriptor(descriptor)
            os.close(descriptor)
            return LockResult(False, "MOTION_BUSY", owner)

        metadata = {
            "schema": LOCK_SCHEMA,
            "identity": self._identity,
            "pid": int(self._pid()),
            "operation_id": operation,
            "acquired_at": float(self._wall_clock()),
        }
        payload = (json.dumps(metadata, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n").encode("ascii")
        if len(payload) > MAX_METADATA_BYTES:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
            raise ValueError("lock metadata exceeds bounded record size")
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, payload)
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o600)
        stat_result = os.fstat(descriptor)
        self._descriptor = descriptor
        self._inode = (stat_result.st_dev, stat_result.st_ino)
        self._operation_id = operation
        return LockResult(True, "LOCK_ACQUIRED", metadata)

    def assert_held(self) -> bool:
        descriptor = self._descriptor
        inode = self._inode
        if descriptor is None or inode is None:
            return False
        try:
            descriptor_stat = os.fstat(descriptor)
            path_stat = self.path.stat()
            if (descriptor_stat.st_dev, descriptor_stat.st_ino) != inode:
                return False
            if (path_stat.st_dev, path_stat.st_ino) != inode:
                return False
            record = json.loads(self.path.read_text(encoding="ascii")[:MAX_METADATA_BYTES])
            return isinstance(record, dict) and record.get("identity") == self._identity
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return False

    def release(self) -> None:
        descriptor = self._descriptor
        if descriptor is None:
            return
        owns_path = self.assert_held()
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
            self._descriptor = None
            self._inode = None
            self._operation_id = None
        if owns_path:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

    def _read_descriptor(self, descriptor: int) -> Mapping[str, object]:
        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            raw = os.read(descriptor, MAX_METADATA_BYTES)
            decoded = json.loads(raw.decode("ascii"))
            if isinstance(decoded, dict):
                return {str(key): value for key, value in decoded.items()}
        except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
            pass
        return {"state": "owner_metadata_unavailable"}

    def __enter__(self) -> "MotionLock":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()
