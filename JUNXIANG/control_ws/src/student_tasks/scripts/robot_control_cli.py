#!/usr/bin/env python3
"""Executable adapter for the student_tasks command contract."""

from __future__ import annotations

import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from student_tasks.cli import main  # noqa: E402
from student_tasks.signals import SignalCancellationGuard  # noqa: E402


if __name__ == "__main__":
    with SignalCancellationGuard() as cancellation:
        raise SystemExit(main(cancellation=cancellation))
