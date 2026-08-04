from __future__ import annotations

import ast
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import support

from student_tasks.production_config import validate_production_config
from test_production_config import NOW, valid_document


PACKAGE_ROOT = support.PACKAGE_ROOT
REPOSITORY_ROOT = PACKAGE_ROOT.parents[3]
OFFICIAL_ROOT = REPOSITORY_ROOT / "AIY黑客松比赛资料 (深开鸿赛道)" / "source code" / "kaihong_adapter"
CHASSIS_SOURCE = OFFICIAL_ROOT / "robot-runtime" / "src" / "chassis_controller" / "scripts" / "chassis_controller_node.py"
LIDAR_SOURCE = OFFICIAL_ROOT / "robot-runtime" / "rplidar-raw-node.py"
TARGET_SOURCE = OFFICIAL_ROOT / "robot-runtime" / "student" / "interfaces" / "aux_target_relay.py"
SKILL_SOURCE = OFFICIAL_ROOT / "mclaw-skill" / "SKILL.md"


class OfficialSourceContractTests(unittest.TestCase):
    def test_chassis_source_confirms_twist_topic_limits_cadence_and_watchdog(self) -> None:
        source = CHASSIS_SOURCE.read_text(encoding="utf-8")
        self.assertIn("from geometry_msgs.msg import Twist", source)
        self.assertIn('rospy.get_param("~cmd_vel_topic", "/cmd_vel")', source)
        self.assertIn('rospy.get_param("~max_linear", 0.20)', source)
        self.assertIn('rospy.get_param("~max_angular", 0.50)', source)
        self.assertIn('rospy.get_param("~cmd_timeout", 0.50)', source)
        self.assertIn('rospy.get_param("~publish_rate", 20.0)', source)
        self.assertIn("msg.linear.x, msg.linear.y, msg.angular.z", source)

    def test_scan_and_target_topics_and_types_match_official_sources(self) -> None:
        lidar = LIDAR_SOURCE.read_text(encoding="utf-8")
        target = TARGET_SOURCE.read_text(encoding="utf-8")
        self.assertIn("from sensor_msgs.msg import LaserScan", lidar)
        self.assertIn('rospy.Publisher("/scan", LaserScan', lidar)
        self.assertIn("from std_msgs.msg import Bool, String", target)
        self.assertIn('"/competition/aux_target_json", String', target)
        self.assertIn('"/competition/aux_target_valid", Bool', target)
        self.assertIn('"/competition/aux_target", PointStamped', target)

    def test_official_operator_entry_requires_run_python(self) -> None:
        source = SKILL_SOURCE.read_text(encoding="utf-8")
        self.assertIn('/bin/run python3 "{{SKILL_DIR}}/scripts/ros_cmd_vel.py"', source)

    def test_production_cadence_must_remain_inside_official_watchdog(self) -> None:
        document = valid_document()
        document["motion"]["publish_rate_hz"] = 2.0
        document["motion"]["watchdog_timeout_s"] = 0.5
        findings = validate_production_config(document, now=NOW).findings
        self.assertIn("CADENCE_UNSAFE", {finding.code for finding in findings})


class ExecutableSourceContractTests(unittest.TestCase):
    def production_python(self) -> list[Path]:
        return sorted((PACKAGE_ROOT / "scripts").glob("*.py")) + sorted(
            (PACKAGE_ROOT / "src" / "student_tasks").glob("*.py")
        )

    def test_executable_python_has_no_forbidden_low_level_interface(self) -> None:
        forbidden_service = "/ros_robot_controller/" + "set_motor"
        forbidden_field = "motor_" + "type"
        for path in self.production_python():
            source = path.read_text(encoding="utf-8")
            self.assertNotIn(forbidden_service, source, path.name)
            self.assertNotIn(forbidden_field, source, path.name)

    def test_runtime_diagnostics_and_string_literals_are_ascii(self) -> None:
        for path in self.production_python():
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    node.value.encode("ascii")

    def test_catkin_metadata_declares_lazy_ros_runtime_and_installs_entries(self) -> None:
        package = ET.parse(PACKAGE_ROOT / "package.xml").getroot()
        dependencies = {element.text for element in package.findall("exec_depend")}
        self.assertTrue({"rospy", "rosgraph", "geometry_msgs", "sensor_msgs", "std_msgs"}.issubset(dependencies))
        cmake = (PACKAGE_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        for dependency in ("rospy", "rosgraph", "geometry_msgs", "sensor_msgs", "std_msgs"):
            self.assertRegex(cmake, r"find_package\(catkin REQUIRED COMPONENTS[\s\S]*\b%s\b" % dependency)
        self.assertIn("scripts/robot_control_cli.py", cmake)
        self.assertIn("scripts/board_smoke_test.py", cmake)
        self.assertIn("config/robot.measured.template.json", cmake)
        self.assertIn("deploy/robot-control", cmake)

    def test_package_contains_no_autostart_or_network_operation(self) -> None:
        paths = [PACKAGE_ROOT / "CMakeLists.txt", PACKAGE_ROOT / "package.xml"]
        paths.extend((PACKAGE_ROOT / "deploy").glob("*"))
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file()).lower()
        self.assertNotIn("init.cfg", text)
        self.assertIsNone(re.search(r"\b(?:ssh|scp|hdc|rsync)\b", text))


if __name__ == "__main__":
    unittest.main()
