from __future__ import annotations

import builtins
import importlib
import unittest
from unittest import mock

import support  # noqa: F401

from fake_ros import FakeRosFacade


class RosFacadeTests(unittest.TestCase):
    def test_module_import_does_not_resolve_ros_packages(self) -> None:
        real_import = builtins.__import__
        blocked = {"rospy", "rosgraph", "geometry_msgs", "sensor_msgs", "std_msgs"}

        def guarded_import(name: str, *args: object, **kwargs: object) -> object:
            if name.split(".", 1)[0] in blocked:
                raise AssertionError("ROS import escaped explicit loader: %s" % name)
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module("student_tasks.ros_facade")
            importlib.reload(module)

    def test_explicit_loader_reports_ros_packages_as_unavailable(self) -> None:
        from student_tasks.ros_facade import RosFacadeUnavailable, load_ros_facade

        real_import = builtins.__import__

        def unavailable(name: str, *args: object, **kwargs: object) -> object:
            if name == "rospy":
                raise ImportError("blocked for deterministic test")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=unavailable):
            with self.assertRaises(RosFacadeUnavailable) as raised:
                load_ros_facade()
        self.assertIn("ROS Python packages are unavailable", str(raised.exception))

    def test_fake_facade_covers_narrow_graph_message_time_and_log_surface(self) -> None:
        facade = FakeRosFacade(node_name="/jx_test")
        facade.publisher_nodes["/cmd_vel"] = ["/teleop"]
        facade.subscriber_nodes["/cmd_vel"] = ["/chassis"]
        facade.initialize("jx_control")
        publisher = facade.create_publisher("/cmd_vel")
        message = facade.make_twist(0.1, -0.1, 0.2)
        publisher.publish(message)
        facade.sleep(0.05)
        facade.log("info", "source verification pending HIL")

        self.assertTrue(facade.master_available())
        self.assertEqual("/jx_test", facade.current_node_name())
        self.assertEqual(("/teleop", "/jx_test"), facade.publishers("/cmd_vel"))
        self.assertEqual(("/chassis",), facade.subscribers("/cmd_vel"))
        self.assertEqual(0.05, facade.monotonic())
        self.assertEqual(1000.05, facade.source_time())
        self.assertEqual(0.1, publisher.messages[0].linear.x)
        self.assertEqual([("info", "source verification pending HIL")], facade.logs)
        with self.assertRaises(UnicodeEncodeError):
            facade.log("info", "non-English: 停止")


if __name__ == "__main__":
    unittest.main()
