#!/usr/bin/env python3
"""Bounded low-level ROS /cmd_vel publisher for unified robot operations."""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import sys
import time
from typing import Any


MAX_LINEAR_MPS = 0.20
MAX_ANGULAR_RAD_S = 0.50
MIN_DURATION_S = 0.10
MAX_DURATION_S = 10.0
PUBLISH_RATE_HZ = 20.0
CONNECTION_TIMEOUT_S = 3.0

os.environ.setdefault("ROS_MASTER_URI", "http://127.0.0.1:11311")
os.environ.setdefault("ROS_IP", "127.0.0.1")
os.environ.pop("ROS_HOSTNAME", None)

try:
    import rosgraph
    import rospy
    from geometry_msgs.msg import Twist
    from std_msgs.msg import UInt16
except ImportError as exc:
    raise SystemExit(
        "ROS Python modules are unavailable. Run this script with /bin/run python3. "
        f"Details: {exc}"
    )


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise argparse.ArgumentTypeError("value must be finite")
    return number


def init_node() -> None:
    if not rospy.core.is_initialized():
        rospy.init_node("mclaw_chassis_control", anonymous=True, disable_signals=True)


def zero_twist() -> Twist:
    return Twist()


def publish_zero(publisher: rospy.Publisher, seconds: float = 0.6) -> None:
    deadline = time.monotonic() + seconds
    rate = rospy.Rate(PUBLISH_RATE_HZ)
    message = zero_twist()
    while time.monotonic() < deadline and not rospy.is_shutdown():
        publisher.publish(message)
        rate.sleep()


def wait_for_subscriber(publisher: rospy.Publisher) -> int:
    deadline = time.monotonic() + CONNECTION_TIMEOUT_S
    while time.monotonic() < deadline and not rospy.is_shutdown():
        count = publisher.get_num_connections()
        if count > 0:
            return count
        time.sleep(0.05)
    return publisher.get_num_connections()


def master_state() -> tuple[list[Any], list[Any], list[Any]]:
    master = rosgraph.Master("/mclaw_chassis_status")
    return master.getSystemState()


def status() -> int:
    try:
        _publishers, subscribers, _services = master_state()
    except Exception as exc:
        print_json(
            {
                "ok": False,
                "master_ready": False,
                "error": str(exc),
                "ros_master_uri": os.environ["ROS_MASTER_URI"],
            }
        )
        return 2

    subscriber_nodes: list[str] = []
    for topic, nodes in subscribers:
        if topic == "/cmd_vel":
            subscriber_nodes = list(nodes)
            break

    battery: int | None = None
    battery_error: str | None = None
    try:
        init_node()
        battery = int(
            rospy.wait_for_message(
                "/ros_robot_controller/battery", UInt16, timeout=1.5
            ).data
        )
    except Exception as exc:
        battery_error = str(exc)

    payload: dict[str, Any] = {
        "ok": bool(subscriber_nodes),
        "master_ready": True,
        "cmd_vel_subscribers": len(subscriber_nodes),
        "subscriber_nodes": subscriber_nodes,
        "battery_raw": battery,
        "ros_master_uri": os.environ["ROS_MASTER_URI"],
    }
    if battery_error:
        payload["battery_warning"] = battery_error
    print_json(payload)
    return 0 if subscriber_nodes else 3


def validate_motion(
    linear_x: float, linear_y: float, angular_z: float, duration: float
) -> None:
    linear_magnitude = math.hypot(linear_x, linear_y)
    if linear_magnitude > MAX_LINEAR_MPS + 1e-9:
        raise ValueError(
            f"planar linear magnitude {linear_magnitude:.3f} exceeds {MAX_LINEAR_MPS:.2f} m/s"
        )
    if abs(angular_z) > MAX_ANGULAR_RAD_S + 1e-9:
        raise ValueError(
            f"absolute angular speed {abs(angular_z):.3f} exceeds {MAX_ANGULAR_RAD_S:.2f} rad/s"
        )
    if not MIN_DURATION_S <= duration <= MAX_DURATION_S:
        raise ValueError(
            f"duration must be between {MIN_DURATION_S:.1f} and {MAX_DURATION_S:.1f} seconds"
        )


def make_twist(linear_x: float, linear_y: float, angular_z: float) -> Twist:
    message = Twist()
    message.linear.x = linear_x
    message.linear.y = linear_y
    message.angular.z = angular_z
    return message


def run_publish(
    linear_x: float, linear_y: float, angular_z: float, duration: float
) -> int:
    try:
        validate_motion(linear_x, linear_y, angular_z, duration)
    except ValueError as exc:
        print_json({"ok": False, "error": str(exc)})
        return 2

    init_node()
    publisher = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
    connections = wait_for_subscriber(publisher)
    if connections < 1:
        print_json({"ok": False, "error": "no /cmd_vel subscriber found"})
        return 3

    interrupted = False

    def request_stop(_signum: int, _frame: Any) -> None:
        nonlocal interrupted
        interrupted = True

    previous_handlers = {
        signum: signal.signal(signum, request_stop)
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    }
    message = make_twist(linear_x, linear_y, angular_z)
    deadline = time.monotonic() + duration
    rate = rospy.Rate(PUBLISH_RATE_HZ)
    started = time.monotonic()
    error: str | None = None
    try:
        while time.monotonic() < deadline and not interrupted and not rospy.is_shutdown():
            publisher.publish(message)
            rate.sleep()
    except Exception as exc:
        error = str(exc)
    finally:
        try:
            publish_zero(publisher)
        finally:
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)

    elapsed = time.monotonic() - started
    payload = {
        "ok": error is None and not interrupted,
        "topic": "/cmd_vel",
        "message_type": "geometry_msgs/Twist",
        "linear_x": linear_x,
        "linear_y": linear_y,
        "angular_z": angular_z,
        "requested_duration": duration,
        "elapsed": round(elapsed, 3),
        "subscribers": connections,
        "zero_velocity_sent": True,
    }
    if interrupted:
        payload["error"] = "movement interrupted"
    elif error:
        payload["error"] = error
    print_json(payload)
    return 0 if payload["ok"] else 4


def stop() -> int:
    init_node()
    publisher = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
    connections = wait_for_subscriber(publisher)
    publish_zero(publisher, seconds=1.0)
    print_json(
        {
            "ok": connections > 0,
            "topic": "/cmd_vel",
            "subscribers": connections,
            "zero_velocity_sent": True,
        }
    )
    return 0 if connections > 0 else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish a bounded geometry_msgs/Twist command to /cmd_vel"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("stop")
    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("--linear-x", type=finite_float, default=0.0)
    publish_parser.add_argument("--linear-y", type=finite_float, default=0.0)
    publish_parser.add_argument("--angular-z", type=finite_float, default=0.0)
    publish_parser.add_argument("--duration", type=finite_float, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "status":
        return status()
    if args.command == "stop":
        return stop()
    return run_publish(args.linear_x, args.linear_y, args.angular_z, args.duration)


if __name__ == "__main__":
    sys.exit(main())
