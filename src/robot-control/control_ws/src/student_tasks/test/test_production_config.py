from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401

from student_tasks.production_config import (
    load_production_config,
    validate_production_config,
    validate_stop_configuration,
)


NOW = 1_000.0


def valid_document() -> dict[str, object]:
    return {
        "schema": "robot-control/production-config/v1",
        "provenance": {
            "kind": "measured",
            "source": "field-record-001",
            "measured_at": 900.0,
            "robot_id": "robot-a",
        },
        "ros": {
            "node_name_prefix": "jx_control",
            "cmd_vel_topic": "/cmd_vel",
            "scan_topic": "/scan",
            "target_json_topic": "/competition/aux_target_json",
            "target_valid_topic": "/competition/aux_target_valid",
            "target_schema": "robot-control/target-observation/v1",
        },
        "motion": {
            "linear_x_sign": 1,
            "linear_y_sign": 1,
            "angular_z_sign": 1,
            "publish_rate_hz": 20.0,
            "zero_message_count": 3,
            "zero_interval_s": 0.02,
            "subscriber_timeout_s": 0.5,
            "watchdog_timeout_s": 0.5,
        },
        "ownership": {
            "lock_path": "/data/local/robot/jx/control_ws/run/motion.lock",
            "estop_path": "/data/local/robot/jx/control_ws/run/estop.json",
            "publisher_allowlist": [],
            "allowlist_evidence": None,
        },
        "safety": {
            "max_scan_age_s": 0.20,
            "future_tolerance_s": 0.02,
            "reset_clear_frames": 3,
            "sectors": [
                {"name": "front", "center_rad": 0.0, "half_width_rad": 0.35, "min_clearance_m": 0.4, "min_samples": 3},
                {"name": "rear", "center_rad": 3.141592653589793, "half_width_rad": 0.35, "min_clearance_m": 0.35, "min_samples": 3},
                {"name": "left", "center_rad": 1.5707963267948966, "half_width_rad": 0.35, "min_clearance_m": 0.35, "min_samples": 3},
                {"name": "right", "center_rad": -1.5707963267948966, "half_width_rad": 0.35, "min_clearance_m": 0.35, "min_samples": 3},
            ],
        },
        "target": {
            "max_source_age_s": 0.25,
            "max_receive_age_s": 0.25,
            "future_tolerance_s": 0.02,
            "min_confidence": 0.6,
            "require_calibration": True,
        },
        "approach": {
            "linear_speed_mps": 0.1,
            "angular_speed_radps": 0.2,
            "correction_duration_s": 0.1,
            "bearing_tolerance_rad": 0.08,
            "stand_off_m": 0.45,
            "stand_off_tolerance_m": 0.03,
            "stable_frames": 2,
            "target_loss_limit": 1,
            "timeout_s": 5.0,
            "max_iterations": 20,
            "observation_interval_s": 0.01,
        },
        "calibration": {
            "mode": "base_point",
            "source": "hand-eye-record-001",
            "measured_at": 900.0,
            "max_age_s": 200.0,
            "camera_frame": "camera_optical_frame",
            "base_frame": "base_link",
            "intrinsics": None,
            "rotation": None,
            "translation": None,
        },
    }


def codes(result: object) -> set[str]:
    return {finding.code for finding in result.findings}


def paths(result: object) -> set[str]:
    return {finding.path for finding in result.findings}


class ProductionConfigurationTests(unittest.TestCase):
    def test_valid_measured_document_converts_to_typed_immutable_configuration(self) -> None:
        result = validate_production_config(valid_document(), now=NOW)
        self.assertTrue(result.valid, result.findings)
        config = result.configuration
        assert config is not None
        self.assertEqual("measured", config.provenance.kind)
        self.assertEqual("/cmd_vel", config.ros.cmd_vel_topic)
        self.assertEqual(20.0, config.motion.publish_rate_hz)
        self.assertEqual((), config.ownership.publisher_allowlist)
        self.assertEqual("front", config.safety.sectors[0].name)

    def test_null_template_is_loadable_but_cannot_pass(self) -> None:
        template = Path(support.PACKAGE_ROOT, "config", "robot.measured.template.json")
        result = load_production_config(template, now=NOW)
        self.assertFalse(result.valid)
        self.assertIsNone(result.configuration)
        self.assertGreaterEqual(len(result.findings), 20)
        self.assertIn("NULL_OR_MISSING", codes(result))

    def test_schema_and_synthetic_provenance_are_rejected(self) -> None:
        document = valid_document()
        document["schema"] = "wrong/v1"
        document["provenance"]["kind"] = "synthetic"
        result = validate_production_config(document, now=NOW)
        self.assertIn("SCHEMA_INVALID", codes(result))
        self.assertIn("PRODUCTION_CONFIG_REQUIRED", codes(result))

    def test_future_measurement_and_stale_calibration_are_rejected(self) -> None:
        document = valid_document()
        document["provenance"]["measured_at"] = NOW + 1.0
        document["calibration"]["measured_at"] = 100.0
        document["calibration"]["max_age_s"] = 10.0
        result = validate_production_config(document, now=NOW)
        self.assertIn("TIMESTAMP_INVALID", codes(result))
        self.assertIn("CALIBRATION_STALE", codes(result))

    def test_topics_must_be_absolute_unique_and_source_schema_exact(self) -> None:
        document = valid_document()
        document["ros"]["cmd_vel_topic"] = "cmd_vel"
        document["ros"]["scan_topic"] = "/cmd_vel"
        document["ros"]["target_schema"] = "unversioned"
        result = validate_production_config(document, now=NOW)
        self.assertIn("TOPIC_INVALID", codes(result))
        self.assertIn("TOPIC_CONFLICT", codes(result))
        self.assertIn("TARGET_SCHEMA_INVALID", codes(result))

    def test_runtime_paths_must_be_absolute_distinct_and_inside_project_root(self) -> None:
        document = valid_document()
        document["ownership"]["lock_path"] = "run/motion.lock"
        document["ownership"]["estop_path"] = "/tmp/motion.lock"
        result = validate_production_config(document, now=NOW)
        self.assertIn("PATH_INVALID", codes(result))
        self.assertIn("ownership.lock_path", paths(result))
        self.assertIn("ownership.estop_path", paths(result))

    def test_direction_signs_are_exact_units_and_hard_limits_are_aggregated(self) -> None:
        document = valid_document()
        document["motion"]["linear_x_sign"] = 0
        document["motion"]["linear_y_sign"] = True
        document["motion"]["angular_z_sign"] = 2
        document["approach"]["linear_speed_mps"] = 0.21
        document["approach"]["angular_speed_radps"] = 0.51
        document["approach"]["correction_duration_s"] = 0.09
        result = validate_production_config(document, now=NOW)
        self.assertEqual(3, sum(finding.code == "DIRECTION_SIGN_INVALID" for finding in result.findings))
        self.assertIn("HARD_LIMIT_EXCEEDED", codes(result))
        self.assertGreaterEqual(len(result.findings), 6)

    def test_nonempty_allowlist_requires_dated_measured_evidence(self) -> None:
        document = valid_document()
        document["ownership"]["publisher_allowlist"] = ["/approved_teleop"]
        result = validate_production_config(document, now=NOW)
        self.assertIn("ALLOWLIST_EVIDENCE_REQUIRED", codes(result))
        document["ownership"]["allowlist_evidence"] = {
            "source": "dated graph capture",
            "measured_at": 950.0,
        }
        accepted = validate_production_config(document, now=NOW)
        self.assertTrue(accepted.valid, accepted.findings)

    def test_cross_field_watchdog_and_timeout_constraints_fail_closed(self) -> None:
        document = valid_document()
        document["motion"]["publish_rate_hz"] = 2.0
        document["motion"]["watchdog_timeout_s"] = 0.2
        document["motion"]["zero_interval_s"] = 0.25
        document["approach"]["timeout_s"] = 0.05
        result = validate_production_config(document, now=NOW)
        self.assertIn("CADENCE_UNSAFE", codes(result))
        self.assertIn("CROSS_FIELD_INVALID", codes(result))

    def test_loader_aggregates_json_and_io_failures(self) -> None:
        missing = load_production_config("/definitely/not/a/config.json", now=NOW)
        self.assertIn("CONFIG_UNREADABLE", codes(missing))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "bad.json")
            path.write_text("{bad", encoding="utf-8")
            malformed = load_production_config(path, now=NOW)
        self.assertIn("CONFIG_JSON_INVALID", codes(malformed))

    def test_zero_only_configuration_ignores_unrelated_invalid_motion_fields(self) -> None:
        document = valid_document()
        document["calibration"]["source"] = None
        document["safety"]["sectors"] = []
        document["motion"]["linear_x_sign"] = None
        full = validate_production_config(document, now=NOW)
        stop = validate_stop_configuration(document)
        self.assertFalse(full.valid)
        self.assertTrue(stop.valid, stop.findings)
        assert stop.configuration is not None
        self.assertEqual("/cmd_vel", stop.configuration.cmd_vel_topic)
        self.assertEqual(3, stop.configuration.zero_message_count)
        self.assertEqual(0.02, stop.configuration.zero_interval_s)

    def test_zero_only_configuration_never_guesses_critical_fields(self) -> None:
        document = valid_document()
        document["ros"]["cmd_vel_topic"] = None
        document["motion"]["zero_message_count"] = None
        document["motion"]["zero_interval_s"] = 0.5
        document["motion"]["watchdog_timeout_s"] = 0.5
        result = validate_stop_configuration(document)
        self.assertFalse(result.valid)
        self.assertIsNone(result.configuration)
        self.assertTrue(
            {"NULL_OR_MISSING", "CROSS_FIELD_INVALID"}.issubset(codes(result)),
            result.findings,
        )

    def test_v2_motion_only_configuration_omits_visual_contract(self) -> None:
        document = valid_document()
        document["schema"] = "robot-control/production-config/v2"
        document["capabilities"] = {"motion": True, "approach": False}
        for group in ("target", "approach", "calibration"):
            document.pop(group)
        document["ros"] = {
            "node_name_prefix": "jx_control",
            "cmd_vel_topic": "/cmd_vel",
            "scan_topic": "/scan",
        }
        result = validate_production_config(document, now=NOW)
        self.assertTrue(result.valid, result.findings)
        assert result.configuration is not None
        self.assertTrue(result.configuration.capabilities.motion)
        self.assertFalse(result.configuration.capabilities.approach)
        self.assertIsNone(result.configuration.target)
        self.assertIsNone(result.configuration.approach)
        self.assertIsNone(result.configuration.calibration)
        self.assertIsNone(result.configuration.ros.target_json_topic)

    def test_v2_motion_only_does_not_accept_visual_fields_or_missing_motion_measurements(self) -> None:
        document = valid_document()
        document["schema"] = "robot-control/production-config/v2"
        document["capabilities"] = {"motion": True, "approach": False}
        document.pop("target")
        document.pop("approach")
        document.pop("calibration")
        document["ros"].pop("target_json_topic")
        document["ros"].pop("target_valid_topic")
        document["ros"].pop("target_schema")
        document["motion"]["linear_x_sign"] = None
        document["target"] = {"unexpected": True}
        result = validate_production_config(document, now=NOW)
        self.assertIn("CAPABILITY_FIELD_CONFLICT", codes(result))
        self.assertIn("DIRECTION_SIGN_INVALID", codes(result))

    def test_v2_motion_only_stop_is_zero_only(self) -> None:
        document = valid_document()
        document["schema"] = "robot-control/production-config/v2"
        document["capabilities"] = {"motion": True, "approach": False}
        for group in ("target", "approach", "calibration"):
            document.pop(group)
        document["ros"] = {
            "node_name_prefix": "jx_control",
            "cmd_vel_topic": "/cmd_vel",
            "scan_topic": "/scan",
        }
        result = validate_stop_configuration(document)
        self.assertTrue(result.valid, result.findings)


if __name__ == "__main__":
    unittest.main()
