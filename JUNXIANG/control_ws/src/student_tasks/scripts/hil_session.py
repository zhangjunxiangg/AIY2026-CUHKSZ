#!/usr/bin/env python3
"""Create and validate a local, explicit HIL session identity record."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA = "robot-control/hil-session/v1"
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$")


def _required(value: str, name: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("%s must be explicit and non-empty" % name)
    return value


def _digest(path: str | None) -> str | None:
    if path is None:
        return None
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_record(arguments: argparse.Namespace, *, created_at: float) -> dict[str, Any]:
    session_id = _required(arguments.session_id, "session_id")
    if SESSION_ID_RE.fullmatch(session_id) is None:
        raise ValueError("session_id contains unsupported characters")
    return {
        "schema": SCHEMA,
        "status": "HIL_PENDING",
        "created_at": created_at,
        "operator": _required(arguments.operator, "operator"),
        "robot_id": _required(arguments.robot_id, "robot_id"),
        "board_id": _required(arguments.board_id, "board_id"),
        "source_revision": _required(arguments.source_revision, "source_revision"),
        "manifest": {
            "path": _required(arguments.manifest, "manifest"),
            "sha256": _digest(arguments.manifest),
        },
        "configuration": {
            "path": _required(arguments.configuration, "configuration"),
            "sha256": _digest(arguments.configuration),
        },
        "environment": _required(arguments.environment, "environment"),
        "nonzero_motion_count": 0,
        "artifact_roots": {
            "cases": "cases/",
            "logs": "logs/",
            "snapshots": "snapshots/",
            "media": "media/",
        },
    }


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hil-session")
    parser.add_argument("--output", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--robot-id", required=True)
    parser.add_argument("--board-id", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--configuration", required=True)
    parser.add_argument("--environment", required=True)
    parsed = parser.parse_args(arguments)
    try:
        record = build_record(parsed, created_at=time.time())
        output = Path(parsed.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(record, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2
    sys.stdout.write(json.dumps({"ok": True, "path": str(Path(parsed.output))}, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
