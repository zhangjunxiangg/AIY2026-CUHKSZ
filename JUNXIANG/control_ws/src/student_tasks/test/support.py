"""Test bootstrap helpers for the catkin-style Python package."""

from __future__ import annotations

import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "src"
SCRIPT_PATH = PACKAGE_ROOT / "scripts" / "robot_control_cli.py"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
