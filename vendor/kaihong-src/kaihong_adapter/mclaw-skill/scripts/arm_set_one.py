#!/usr/bin/env python3
"""Move one arm joint with three-frame feedback and bounded delta."""

from __future__ import annotations

import argparse
import json
import statistics
import time

import rospy
from servo_msgs.msg import RawIdPosDur, ServoStateList


STATE_TOPIC = "/servo_controllers/port_id_1/servo_states"
COMMAND_TOPIC = "/servo_controllers/port_id_1/id_pos_dur"
SOFT_DELTA = 120
HARD_DELTA = 250


def positions(servo_id: int) -> list[int]:
    values: list[int] = []
    for _ in range(3):
        message = rospy.wait_for_message(STATE_TOPIC, ServoStateList, timeout=5.0)
        matches = [state for state in message.servo_states if int(state.id) == servo_id]
        if len(matches) != 1:
            raise RuntimeError(f"servo {servo_id} missing from feedback")
        values.append(int(matches[0].position))
    if max(values) - min(values) > 3:
        raise RuntimeError(f"servo {servo_id} feedback is unstable: {values}")
    return values


def emit(payload: dict[str, object], code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--servo-id", type=int, required=True)
    parser.add_argument("--position", type=int, required=True)
    parser.add_argument("--allow-large-delta", action="store_true")
    args = parser.parse_args()

    if args.servo_id not in (1, 2, 3, 4, 5):
        return emit({"ok": False, "error": "servo-id must be 1..5; ID10 is the gripper"}, 2)
    if not 0 <= args.position <= 1000:
        return emit({"ok": False, "error": "position must be 0..1000"}, 2)

    rospy.init_node("mclaw_arm_set_one", anonymous=True, disable_signals=True)
    try:
        before_samples = positions(args.servo_id)
        before = int(statistics.median(before_samples))
        delta = args.position - before
        if abs(delta) > HARD_DELTA:
            return emit(
                {
                    "ok": False,
                    "servo_id": args.servo_id,
                    "before": before,
                    "target": args.position,
                    "delta": delta,
                    "error": f"absolute delta exceeds hard limit {HARD_DELTA}",
                },
                3,
            )
        if abs(delta) > SOFT_DELTA and not args.allow_large_delta:
            return emit(
                {
                    "ok": False,
                    "servo_id": args.servo_id,
                    "before": before,
                    "target": args.position,
                    "delta": delta,
                    "confirmation_required": True,
                    "error": f"absolute delta exceeds soft limit {SOFT_DELTA}",
                },
                4,
            )
        duration = max(2.0, min(5.0, abs(delta) / 50.0))
        publisher = rospy.Publisher(COMMAND_TOPIC, RawIdPosDur, queue_size=1)
        deadline = time.monotonic() + 5.0
        while publisher.get_num_connections() < 1 and time.monotonic() < deadline:
            time.sleep(0.1)
        if publisher.get_num_connections() < 1:
            raise RuntimeError("arm command subscriber unavailable")
        publisher.publish(
            RawIdPosDur(id=args.servo_id, position=args.position, duration=duration)
        )
        time.sleep(duration + 0.5)
        after_samples = positions(args.servo_id)
        after = int(statistics.median(after_samples))
        error = after - args.position
        ok = abs(error) <= 5
        return emit(
            {
                "ok": ok,
                "servo_id": args.servo_id,
                "before": before,
                "before_samples": before_samples,
                "target": args.position,
                "delta": delta,
                "duration": duration,
                "after": after,
                "after_samples": after_samples,
                "error": error,
                "topic": COMMAND_TOPIC,
            },
            0 if ok else 5,
        )
    except Exception as error:
        return emit({"ok": False, "error": f"{type(error).__name__}: {error}"}, 6)


if __name__ == "__main__":
    raise SystemExit(main())
