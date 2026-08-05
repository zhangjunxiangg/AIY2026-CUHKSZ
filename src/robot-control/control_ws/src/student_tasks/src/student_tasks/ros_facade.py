"""Lazy, narrow ROS1 boundary for production adapters."""

from __future__ import annotations

import time
from typing import Callable, Protocol, runtime_checkable


class RosFacadeUnavailable(RuntimeError):
    """Raised only when explicit ROS loading cannot resolve board packages."""


@runtime_checkable
class RosFacade(Protocol):
    def initialize(self, node_name: str) -> None: ...

    def master_available(self) -> bool: ...

    def current_node_name(self) -> str: ...

    def publishers(self, topic: str) -> tuple[str, ...]: ...

    def subscribers(self, topic: str) -> tuple[str, ...]: ...

    def create_publisher(self, topic: str) -> object: ...

    def subscribe(self, topic: str, callback: Callable[[object], None], message_kind: str = "string") -> object: ...

    def make_twist(self, linear_x: float, linear_y: float, angular_z: float) -> object: ...

    def monotonic(self) -> float: ...

    def source_time(self) -> float: ...

    def sleep(self, duration_s: float) -> None: ...

    def is_shutdown(self) -> bool: ...

    def log(self, level: str, message: str) -> None: ...


class _RealRosFacade:
    def __init__(
        self,
        rospy: object,
        rosgraph: object,
        twist_type: type,
        scan_type: type,
        string_type: type,
        bool_type: type,
    ) -> None:
        self._rospy = rospy
        self._rosgraph = rosgraph
        self._twist_type = twist_type
        self._message_types = {
            "laser_scan": scan_type,
            "string": string_type,
            "bool": bool_type,
        }

    def initialize(self, node_name: str) -> None:
        core = getattr(self._rospy, "core")
        if not core.is_initialized():
            self._rospy.init_node(node_name, anonymous=True, disable_signals=True)

    def master_available(self) -> bool:
        try:
            return bool(self._rosgraph.is_master_online())
        except Exception:
            return False

    def current_node_name(self) -> str:
        return str(self._rospy.get_name())

    def publishers(self, topic: str) -> tuple[str, ...]:
        publishers, _, _ = self._system_state()
        return self._topic_nodes(publishers, topic)

    def subscribers(self, topic: str) -> tuple[str, ...]:
        _, subscribers, _ = self._system_state()
        return self._topic_nodes(subscribers, topic)

    def create_publisher(self, topic: str) -> object:
        return self._rospy.Publisher(topic, self._twist_type, queue_size=1)

    def subscribe(
        self,
        topic: str,
        callback: Callable[[object], None],
        message_kind: str = "string",
    ) -> object:
        try:
            message_type = self._message_types[message_kind]
        except KeyError as exc:
            raise ValueError("unsupported ROS message kind: %s" % message_kind) from exc
        return self._rospy.Subscriber(topic, message_type, callback, queue_size=1)

    def make_twist(self, linear_x: float, linear_y: float, angular_z: float) -> object:
        message = self._twist_type()
        message.linear.x = float(linear_x)
        message.linear.y = float(linear_y)
        message.angular.z = float(angular_z)
        return message

    def monotonic(self) -> float:
        return time.monotonic()

    def source_time(self) -> float:
        return float(self._rospy.Time.now().to_sec())

    def sleep(self, duration_s: float) -> None:
        self._rospy.sleep(float(duration_s))

    def is_shutdown(self) -> bool:
        return bool(self._rospy.is_shutdown())

    def log(self, level: str, message: str) -> None:
        message.encode("ascii")
        methods = {
            "debug": self._rospy.logdebug,
            "info": self._rospy.loginfo,
            "warning": self._rospy.logwarn,
            "error": self._rospy.logerr,
        }
        try:
            method = methods[level]
        except KeyError as exc:
            raise ValueError("unsupported log level: %s" % level) from exc
        method(message)

    def _system_state(self) -> tuple[object, object, object]:
        master = self._rosgraph.Master(self.current_node_name())
        return master.getSystemState()

    @staticmethod
    def _topic_nodes(entries: object, topic: str) -> tuple[str, ...]:
        for name, nodes in entries:
            if name == topic:
                return tuple(sorted(str(node) for node in nodes))
        return ()


def load_ros_facade() -> RosFacade:
    """Resolve board ROS packages only after explicit production selection."""

    try:
        import rosgraph
        import rospy
        from geometry_msgs.msg import Twist
        from sensor_msgs.msg import LaserScan
        from std_msgs.msg import Bool, String
    except (ImportError, ModuleNotFoundError) as exc:
        raise RosFacadeUnavailable("ROS Python packages are unavailable in the selected runtime") from exc
    return _RealRosFacade(rospy, rosgraph, Twist, LaserScan, String, Bool)
