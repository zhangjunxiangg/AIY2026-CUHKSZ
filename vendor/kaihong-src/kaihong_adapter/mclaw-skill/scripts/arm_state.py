#!/usr/bin/env python3
"""Read three arm servo-state frames and return stable JSON."""

from __future__ import annotations

import json
import statistics

import rospy
from servo_msgs.msg import ServoStateList


TOPIC = "/servo_controllers/port_id_1/servo_states"
EXPECTED_IDS = (1, 2, 3, 4, 5, 10)


def read_frames(count: int = 3) -> list[dict[int, dict[str, int]]]:
    frames: list[dict[int, dict[str, int]]] = []
    for _ in range(count):
        message = rospy.wait_for_message(TOPIC, ServoStateList, timeout=5.0)
        frames.append(
            {
                int(state.id): {
                    "position": int(state.position),
                    "goal": int(state.goal),
                    "error": int(state.error),
                    "voltage": int(state.voltage),
                }
                for state in message.servo_states
            }
        )
    return frames


def summarize(frames: list[dict[int, dict[str, int]]]) -> dict[str, object]:
    servos: dict[str, object] = {}
    all_stable = True
    for servo_id in EXPECTED_IDS:
        samples = [frame[servo_id] for frame in frames if servo_id in frame]
        if len(samples) != len(frames):
            servos[str(servo_id)] = {"present": False}
            all_stable = False
            continue
        positions = [sample["position"] for sample in samples]
        stable = max(positions) - min(positions) <= 3
        all_stable = all_stable and stable
        servos[str(servo_id)] = {
            "present": True,
            "position": int(statistics.median(positions)),
            "goal": int(statistics.median(sample["goal"] for sample in samples)),
            "error": int(statistics.median(sample["error"] for sample in samples)),
            "voltage_mv": int(statistics.median(sample["voltage"] for sample in samples)),
            "samples": positions,
            "stable": stable,
        }
    return {
        "ok": all_stable,
        "source": TOPIC,
        "frame_count": len(frames),
        "servos": servos,
    }


def main() -> int:
    rospy.init_node("mclaw_arm_state", anonymous=True, disable_signals=True)
    try:
        payload = summarize(read_frames())
    except Exception as error:
        payload = {"ok": False, "source": TOPIC, "error": f"{type(error).__name__}: {error}"}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
