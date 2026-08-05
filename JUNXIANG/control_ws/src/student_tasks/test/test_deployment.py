from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

import support

from fake_ros import FakeRosFacade
from student_tasks.production_config import ConfigurationValidation, load_production_config
from test_production_config import NOW
from test_ros_backend import measured_config


PACKAGE_ROOT = support.PACKAGE_ROOT
SMOKE_PATH = PACKAGE_ROOT / "scripts" / "board_smoke_test.py"
DEPLOY_ROOT = PACKAGE_ROOT / "deploy"
MANIFEST_PATH = DEPLOY_ROOT / "board-manifest.json"
WRAPPER_PATH = DEPLOY_ROOT / "robot-control"
TARGET_ROOT = "/data/local/robot/jx/control_ws/"


def load_smoke_module() -> object:
    spec = importlib.util.spec_from_file_location("board_smoke_test", SMOKE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("board smoke module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_manifest_sources() -> set[str]:
    sources = {
        "src/student_tasks/CMakeLists.txt",
        "src/student_tasks/README.md",
        "src/student_tasks/package.xml",
        "src/student_tasks/config/robot.measured.template.json",
        "src/student_tasks/config/robot.motion.measured.template.json",
        "src/student_tasks/deploy/README.md",
        "src/student_tasks/deploy/board-manifest.json",
        "src/student_tasks/deploy/robot-control",
        "src/student_tasks/scripts/board_smoke_test.py",
        "src/student_tasks/scripts/cmd_vel_observer.py",
        "src/student_tasks/scripts/hil_session.py",
        "src/student_tasks/scripts/package_manifest.py",
        "src/student_tasks/scripts/robot_control_cli.py",
    }
    sources.update(
        "src/student_tasks/src/student_tasks/%s" % path.name
        for path in (PACKAGE_ROOT / "src" / "student_tasks").glob("*.py")
    )
    return sources


class BoardSmokeTests(unittest.TestCase):
    def test_smoke_ast_cannot_construct_or_publish_motion(self) -> None:
        tree = ast.parse(SMOKE_PATH.read_text(encoding="utf-8"), filename=str(SMOKE_PATH))
        forbidden_names = {"MotionRequest", "Velocity"}
        forbidden_calls = {"create_publisher", "make_twist", "publish", "publish_velocity", "move", "stop"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imported = {
                    alias.asname or alias.name.rsplit(".", 1)[-1]
                    for alias in node.names
                }
                self.assertTrue(forbidden_names.isdisjoint(imported))
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
                self.assertNotIn(name, forbidden_names | forbidden_calls)

    def test_smoke_reports_config_graph_and_provider_state_without_publisher(self) -> None:
        smoke = load_smoke_module()
        with tempfile.TemporaryDirectory() as directory:
            configuration = measured_config(directory)
            facade = FakeRosFacade(wall_time=NOW)
            facade.subscriber_nodes[configuration.ros.cmd_vel_topic] = ["/chassis_controller"]
            validation = ConfigurationValidation((), configuration)
            with mock.patch.object(smoke, "load_production_config", return_value=validation):
                exit_code, payload = smoke.run_smoke(
                    "measured.json",
                    wall_clock=lambda: NOW,
                    facade_loader=lambda: facade,
                )
        self.assertEqual(0, exit_code)
        self.assertEqual("robot-control/board-smoke/v1", payload["schema"])
        self.assertEqual("SOURCE_VERIFIED_HIL_PENDING", payload["verification"])
        self.assertTrue(payload["read_only"])
        self.assertFalse(payload["nonzero_motion_constructed"])
        self.assertTrue(payload["configuration"]["valid"])
        self.assertIn("master", payload["graph"])
        self.assertIn("scan", payload["providers"])
        self.assertIn("target", payload["providers"])
        self.assertEqual([], facade.created_publishers)

    def test_invalid_config_fails_before_ros_loading(self) -> None:
        smoke = load_smoke_module()
        validation = ConfigurationValidation(())
        loader = mock.Mock(side_effect=AssertionError("ROS must not load for invalid config"))
        with mock.patch.object(smoke, "load_production_config", return_value=validation):
            exit_code, payload = smoke.run_smoke(
                "template.json",
                wall_clock=lambda: NOW,
                facade_loader=loader,
            )
        self.assertEqual(2, exit_code)
        self.assertFalse(payload["configuration"]["valid"])
        self.assertFalse(payload["ros"]["loaded"])
        loader.assert_not_called()

    def test_smoke_entry_emits_exactly_one_json_result(self) -> None:
        smoke = load_smoke_module()
        output = StringIO()
        validation = ConfigurationValidation(())
        with mock.patch.object(smoke, "load_production_config", return_value=validation):
            exit_code = smoke.main(
                ["--config", "template.json"],
                stdout=output,
                wall_clock=lambda: NOW,
                facade_loader=mock.Mock(side_effect=AssertionError("unexpected ROS load")),
            )
        lines = output.getvalue().splitlines()
        self.assertEqual(2, exit_code)
        self.assertEqual(1, len(lines))
        self.assertEqual("robot-control/board-smoke/v1", json.loads(lines[0])["schema"])


class DeploymentBundleTests(unittest.TestCase):
    def manifest(self) -> dict[str, object]:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_is_complete_unique_production_allowlist(self) -> None:
        manifest = self.manifest()
        self.assertEqual("robot-control/board-manifest/v1", manifest["schema"])
        self.assertEqual(TARGET_ROOT, manifest["target_root"])
        self.assertEqual("SOURCE_VERIFIED_HIL_PENDING", manifest["verification"])
        entries = manifest["entries"]
        sources = [entry["source"] for entry in entries]
        self.assertEqual(len(sources), len(set(sources)))
        self.assertEqual(expected_manifest_sources(), set(sources))
        self.assertTrue(all(entry["production_allowed"] is True for entry in entries))

    def test_manifest_targets_modes_and_source_files_are_exact(self) -> None:
        for entry in self.manifest()["entries"]:
            source = entry["source"]
            target = entry["target"]
            self.assertTrue((PACKAGE_ROOT.parents[1] / source).is_file(), source)
            self.assertEqual(TARGET_ROOT + source, target)
            expected_mode = "0755" if source.endswith(("/robot-control", ".py")) and "/scripts/" in source or source.endswith("/robot-control") else "0644"
            self.assertEqual(expected_mode, entry["mode"], source)
            self.assertTrue(entry["purpose"].strip())

    def test_manifest_excludes_synthetic_tests_secrets_network_and_autostart(self) -> None:
        text = MANIFEST_PATH.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in ("offline.synthetic", "/test/", "/fixtures/", "/specs/", "secrets/", "init.cfg", "ssh", "hdc"):
            self.assertNotIn(forbidden, lowered)
        self.assertIsNone(re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text))
        self.assertNotRegex(lowered, r"api[_-]?key|access[_-]?token|password")

    def test_wrapper_is_self_contained_run_python_and_shell_valid(self) -> None:
        wrapper = WRAPPER_PATH.read_text(encoding="ascii")
        self.assertTrue(wrapper.startswith("#!/bin/sh\nset -eu\n"))
        self.assertIn('CONTROL_ROOT="/data/local/robot/jx/control_ws"', wrapper)
        self.assertIn('PYTHONPATH="$CONTROL_ROOT/src/student_tasks/src', wrapper)
        self.assertIn('exec /bin/run python3 "$CONTROL_ROOT/src/student_tasks/scripts/robot_control_cli.py" "$@"', wrapper)
        for forbidden in ("ssh ", "scp ", "hdc ", "mount ", "init.cfg"):
            self.assertNotIn(forbidden, wrapper)
        completed = subprocess.run(
            ["sh", "-n", str(WRAPPER_PATH)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_unfilled_production_template_is_rejected(self) -> None:
        validation = load_production_config(
            PACKAGE_ROOT / "config" / "robot.measured.template.json",
            now=NOW,
        )
        self.assertFalse(validation.valid)
        self.assertIsNone(validation.configuration)
        self.assertGreaterEqual(len(validation.findings), 10)


if __name__ == "__main__":
    unittest.main()
