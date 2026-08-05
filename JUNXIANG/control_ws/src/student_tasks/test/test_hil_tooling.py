from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

import support


PACKAGE_ROOT = support.PACKAGE_ROOT


def load_script(name: str) -> object:
    path = PACKAGE_ROOT / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError("script could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HilToolingTests(unittest.TestCase):
    def test_manifest_validator_is_complete_and_local_staging_is_explicit(self) -> None:
        module = load_script("package_manifest")
        manifest_path = PACKAGE_ROOT / "deploy" / "board-manifest.json"
        manifest, findings = module.validate_manifest(manifest_path)
        self.assertEqual([], findings)
        assert manifest is not None
        with tempfile.TemporaryDirectory() as directory:
            staged = module.stage_manifest(manifest, directory)
            self.assertEqual(len(manifest["entries"]), len(staged))
            self.assertTrue((Path(directory) / "src/student_tasks/deploy/robot-control").is_file())

    def test_session_record_requires_explicit_identity_and_digests_files(self) -> None:
        module = load_script("hil_session")
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            configuration = Path(directory) / "config.json"
            manifest.write_text("manifest", encoding="utf-8")
            configuration.write_text("config", encoding="utf-8")
            record = module.build_record(
                Namespace(
                    session_id="session-20260805-a",
                    operator="junxiang",
                    robot_id="robot-a",
                    board_id="board-a",
                    source_revision="abc123",
                    manifest=str(manifest),
                    configuration=str(configuration),
                    environment="clear lab floor",
                ),
                created_at=1000.0,
            )
            self.assertEqual("HIL_PENDING", record["status"])
            self.assertEqual(0, record["nonzero_motion_count"])
            self.assertEqual(64, len(record["manifest"]["sha256"]))
        with self.assertRaises(ValueError):
            module.build_record(
                Namespace(
                    session_id="",
                    operator="junxiang",
                    robot_id="robot-a",
                    board_id="board-a",
                    source_revision="abc123",
                    manifest="missing",
                    configuration="missing",
                    environment="floor",
                ),
                created_at=1000.0,
            )

    def test_observer_rejects_invalid_topic_without_ros_import(self) -> None:
        module = load_script("cmd_vel_observer")
        with self.assertRaises(ValueError):
            module.observe("cmd_vel", 1.0)


if __name__ == "__main__":
    unittest.main()
