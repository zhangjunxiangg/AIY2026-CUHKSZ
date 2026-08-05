#!/usr/bin/env python3
"""Observe a ROS cmd_vel topic without creating a publisher or sending motion."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any


SCHEMA = "robot-control/cmd-vel-observer/v1"


def observe(topic: str, duration_s: float) -> dict[str, Any]:
    if not topic.startswith("/") or topic == "/":
        raise ValueError("topic must be an absolute ROS topic")
    if duration_s <= 0:
        raise ValueError("duration must be positive")
    import rospy
    from geometry_msgs.msg import Twist

    rospy.init_node("jx_cmd_vel_observer", anonymous=True, disable_signals=True)
    started = time.monotonic()
    messages: list[dict[str, float]] = []

    def callback(message: Twist) -> None:
        messages.append({
            "linear_x": float(message.linear.x),
            "linear_y": float(message.linear.y),
            "angular_z": float(message.angular.z),
            "received_at": time.time(),
        })

    subscriber = rospy.Subscriber(topic, Twist, callback, queue_size=50)
    try:
        while not rospy.is_shutdown() and time.monotonic() - started < duration_s:
            rospy.sleep(0.05)
    finally:
        subscriber.unregister()
    nonzero = [message for message in messages if any(message[key] != 0.0 for key in ("linear_x", "linear_y", "angular_z"))]
    return {
        "schema": SCHEMA,
        "ok": True,
        "read_only": True,
        "topic": topic,
        "topic_type": "geometry_msgs/Twist",
        "observation_duration_s": duration_s,
        "message_count": len(messages),
        "nonzero_message_count": len(nonzero),
        "last_message": messages[-1] if messages else None,
        "first_received_at": messages[0]["received_at"] if messages else None,
        "last_received_at": messages[-1]["received_at"] if messages else None,
    }


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cmd-vel-observer")
    parser.add_argument("--topic", default="/cmd_vel")
    parser.add_argument("--duration", type=float, default=2.0)
    parsed = parser.parse_args(arguments)
    try:
        result = observe(parsed.topic, parsed.duration)
    except Exception as exc:
        result = {"schema": SCHEMA, "ok": False, "read_only": True, "error": {"code": "OBSERVER_FAILED", "detail": str(exc)}}
        sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
        return 3
    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
