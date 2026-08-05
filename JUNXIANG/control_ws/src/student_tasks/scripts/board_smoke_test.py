#!/usr/bin/env python3
"""Read-only board graph, configuration, and provider diagnostics."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from student_tasks.production_config import load_production_config  # noqa: E402
from student_tasks.ros_backend import RosMotionBackend  # noqa: E402
from student_tasks.ros_facade import RosFacadeUnavailable, load_ros_facade  # noqa: E402
from student_tasks.ros_providers import RosScanProvider, RosTargetProvider  # noqa: E402


SCHEMA = "robot-control/board-smoke/v1"
VERIFICATION = "SOURCE_VERIFIED_HIL_PENDING"


def _base_payload() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "ok": False,
        "verification": VERIFICATION,
        "read_only": True,
        "nonzero_motion_constructed": False,
        "configuration": {"valid": False, "schema": None, "configuration_kind": "missing", "capabilities": None, "findings": []},
        "ros": {"loaded": False},
        "graph": {},
        "providers": {
            "scan": {"code": "NOT_CHECKED"},
            "target": {"code": "NOT_CHECKED"},
        },
    }


def run_smoke(
    config_path: str,
    *,
    wall_clock: Callable[[], float] = time.time,
    facade_loader: Callable[[], object] = load_ros_facade,
) -> tuple[int, dict[str, object]]:
    """Collect diagnostics without constructing any command or publisher."""

    payload = _base_payload()
    validation = load_production_config(config_path, now=wall_clock())
    payload["configuration"] = validation.to_dict()
    if not validation.valid or validation.configuration is None:
        payload["error"] = {
            "code": "PRODUCTION_CONFIG_REQUIRED",
            "detail": "measured production configuration is invalid",
        }
        return 2, payload

    try:
        facade = facade_loader()
    except RosFacadeUnavailable as exc:
        payload["error"] = {"code": "ROS_UNAVAILABLE", "detail": str(exc)}
        return 3, payload
    except Exception as exc:
        payload["error"] = {"code": "ROS_LOAD_FAILED", "detail": str(exc)}
        return 3, payload

    payload["ros"] = {"loaded": True}
    configuration = validation.configuration
    backend = RosMotionBackend(facade, configuration, operator_confirmed=False)

    scan = None
    try:
        scan = RosScanProvider(
            facade,
            configuration.ros.scan_topic,
            max_source_age_s=configuration.safety.max_scan_age_s,
            max_receive_age_s=configuration.safety.max_scan_age_s,
            future_tolerance_s=configuration.safety.future_tolerance_s,
        )
        payload["providers"]["scan"] = scan.diagnostics()
        backend.scan_provider = scan
    except Exception as exc:
        payload["providers"]["scan"] = {
            "code": "SCAN_SUBSCRIPTION_FAILED",
            "detail": str(exc),
        }

    if not configuration.capabilities.approach:
        payload["providers"]["target"] = {
            "code": "CAPABILITY_DISABLED",
            "detail": "visual approach capability is disabled by production configuration",
        }
    else:
        try:
            assert configuration.target is not None
            assert configuration.calibration is not None
            assert configuration.ros.target_json_topic is not None
            assert configuration.ros.target_valid_topic is not None
            assert configuration.ros.target_schema is not None
            target = RosTargetProvider(
                facade,
                configuration.ros.target_json_topic,
                configuration.ros.target_valid_topic,
                expected_schema=configuration.ros.target_schema,
                max_source_age_s=configuration.target.max_source_age_s,
                max_receive_age_s=configuration.target.max_receive_age_s,
                future_tolerance_s=configuration.target.future_tolerance_s,
                min_confidence=configuration.target.min_confidence,
                expected_camera_frame=configuration.calibration.camera_frame,
                calibration_source=configuration.calibration.source,
            )
            payload["providers"]["target"] = target.diagnostics()
            backend.target_provider = target
        except Exception as exc:
            payload["providers"]["target"] = {
                "code": "TARGET_SUBSCRIPTION_FAILED",
                "detail": str(exc),
            }

    status = backend.status()
    payload["graph"] = status.details
    payload["motion_ready"] = status.ready
    payload["blocking_reasons"] = list(status.blocking_reasons)
    payload["ok"] = True
    return 0, payload


def main(
    arguments: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    wall_clock: Callable[[], float] = time.time,
    facade_loader: Callable[[], object] = load_ros_facade,
) -> int:
    parser = argparse.ArgumentParser(prog="board-smoke-test")
    parser.add_argument("--config", required=True)
    parsed = parser.parse_args(arguments)
    exit_code, payload = run_smoke(
        parsed.config,
        wall_clock=wall_clock,
        facade_loader=facade_loader,
    )
    stdout.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n")
    stdout.flush()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
