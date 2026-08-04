#!/usr/bin/env python3
"""Install or update the unified Kaihong 4.1 M-Claw skill."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mclaw.tools.skill_tools.manage_tool import skill_manage


SKILL_NAME = "kaihong-robot-operations"
SHORT_DESCRIPTION = "统一操作Kaihong 4.1底盘、机械臂、相机、雷达、辅助相机和颜色分类。"
SCRIPT_NAMES = (
    "robot_ops.py",
    "ros_cmd_vel.py",
    "arm_state.py",
    "arm_set_one.py",
    "camera_snapshot.py",
    "latest_photo_server.py",
)
LEGACY_SKILL_NAMES = (
    "kaihong-mecanum-chassis",
    "kaihong-robot-competition",
    "kaihong-color-sorting",
)


def call(action: str, name: str = SKILL_NAME, **kwargs: Any) -> dict[str, Any]:
    result = json.loads(skill_manage(action=action, name=name, **kwargs))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    root = Path(__file__).resolve().parent
    skill_md = (root / "SKILL.md").read_text(encoding="utf-8")
    evolution = {
        "adaptation_summary": [
            "Combines chassis, arm, lidar, Astra, competition interfaces, and color sorting in one skill.",
            "Uses host ROS for chassis/arm/lidar and the vision Docker only for Astra RGB-D.",
            "Runs M-Claw only on the car and verifies Gemini publishers against the user-provided auxiliary-board IP.",
            "Overwrites fixed latest camera files to avoid storage growth.",
        ],
        "known_failures": [
            "Never infer missing lidar or depth values from model knowledge.",
            "Large arm deltas require explicit clearance confirmation.",
            "Color sorting is perception-only and never triggers robot motion.",
        ],
    }
    created = call(
        "create",
        skill_md=skill_md,
        short_description=SHORT_DESCRIPTION,
        initial_evolution=evolution,
    )
    if not created.get("success"):
        error = str(created.get("error") or "")
        if "already exists" not in error:
            return 1
        edited = call("edit", skill_md=skill_md)
        if not edited.get("success"):
            return 1
        inspected = call("validate")
        current_description = (
            inspected.get("mclaw_skill", {}).get("short_description")
        )
        if current_description != SHORT_DESCRIPTION:
            if not call("delete").get("success"):
                return 1
            recreated = call(
                "create",
                skill_md=skill_md,
                short_description=SHORT_DESCRIPTION,
                initial_evolution=evolution,
            )
            if not recreated.get("success"):
                return 1

    for name in SCRIPT_NAMES:
        written = call(
            "write_file",
            file_path=f"scripts/{name}",
            content=(root / "scripts" / name).read_text(encoding="utf-8"),
            encoding="text",
            overwrite=True,
        )
        if not written.get("success"):
            return 1
    for legacy_name in LEGACY_SKILL_NAMES:
        legacy = call("delete", name=legacy_name)
        if not legacy.get("success") and "not found" not in str(
            legacy.get("error", "")
        ).lower():
            return 1
    validated = call("validate")
    return 0 if validated.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
