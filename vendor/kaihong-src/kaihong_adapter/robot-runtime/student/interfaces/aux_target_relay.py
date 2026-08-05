#!/usr/bin/env python3
"""Publish a fresh auxiliary-camera localization result through the student interface.

The auxiliary camera stays off the 4.1 board.  A small JSON handoff file is
copied into the vision container, and this node publishes only the validated
base-frame target, not a full image stream.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import rospy
from geometry_msgs.msg import PointStamped
from std_msgs.msg import Bool, String


def load_target(path: Path, max_age_s: float) -> tuple[dict[str, object] | None, str]:
    try:
        age = time.time() - path.stat().st_mtime
        if age < 0.0 or age > max_age_s:
            return None, "stale_file_age=%.3fs" % age
        data = json.loads(path.read_text(encoding="utf-8"))
        center = data.get("base_center_m")
        if not isinstance(center, list) or len(center) != 3:
            return None, "missing base_center_m"
        values = [float(value) for value in center]
        if not all(-2.0 <= value <= 2.0 for value in values):
            return None, "base_center_m_out_of_range"
        if not (0.05 <= values[2] <= 2.0):
            return None, "base_center_m_z_out_of_range"
        data["base_center_m"] = values
        data["file_age_s"] = age
        return data, "ok"
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return None, str(exc)


def main() -> int:
    rospy.init_node("aux_target_relay")
    target_file = Path(
        rospy.get_param(
            "~target_file",
            os.environ.get("AUX_TARGET_FILE", "/tmp/d435i-target.json"),
        )
    )
    max_age_s = float(rospy.get_param("~max_age_s", 5.0))
    rate = rospy.Rate(float(rospy.get_param("~rate_hz", 5.0)))
    point_pub = rospy.Publisher(
        "/competition/aux_target", PointStamped, queue_size=1, latch=True
    )
    json_pub = rospy.Publisher(
        "/competition/aux_target_json", String, queue_size=1, latch=True
    )
    valid_pub = rospy.Publisher(
        "/competition/aux_target_valid", Bool, queue_size=1, latch=True
    )
    last_signature = None
    last_valid = False
    while not rospy.is_shutdown():
        try:
            signature = (target_file.stat().st_mtime_ns, target_file.stat().st_size)
        except OSError:
            signature = None
        target, reason = load_target(target_file, max_age_s)
        current_valid = target is not None
        if signature != last_signature or current_valid != last_valid:
            if current_valid:
                x, y, z = target["base_center_m"]
                message = PointStamped()
                message.header.stamp = rospy.Time.now()
                message.header.frame_id = "base_link"
                message.point.x = x
                message.point.y = y
                message.point.z = z
                point_pub.publish(message)
                target["relay_frame"] = "base_link"
                target["relay_published_at"] = time.time()
                json_pub.publish(String(data=json.dumps(target, ensure_ascii=False)))
                valid_pub.publish(Bool(data=True))
                rospy.loginfo(
                    "AUX_TARGET_PASS xyz=(%.3f, %.3f, %.3f) age=%.3fs",
                    x,
                    y,
                    z,
                    target["file_age_s"],
                )
            else:
                valid_pub.publish(Bool(data=False))
                rospy.logwarn("AUX_TARGET_SKIP %s: %s", target_file, reason)
            last_signature = signature
            last_valid = current_valid
        rate.sleep()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
