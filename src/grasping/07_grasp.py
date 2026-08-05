#!/usr/bin/env python3
"""07_grasp.py — Gate 07：夹取 + 抬升 + 持有验证

流程：闭合（540，3s）→ 阻力 gate（error ≤ -8 = 夹到东西）→ 抬升 3×20mm →
侧移 20mm → 图像验证目标跟随（仍在画面中且面积够大）。
gate：阻力、抬升后可见、侧移后可见。证据：post_grasp.jpg / verify_hold.jpg。
"""
import cv2
import rospy

from util_gate import Gate, main
from util_board import (get_frame, detect_centroid, ensure_camera,
                        gripper_set, get_servo_states, cartesian_jog,
                        get_current_pose, annotate)

COLOR = "red"
CLOSE_POS = 540
MIN_HOLD_AREA = 12000.0


def run(g: Gate):
    g.require_prev("06_descend")
    rospy.init_node("step07_grasp", anonymous=True)
    ensure_camera()

    g0 = get_servo_states()[10]["position"]
    g.log(f"gripper before: {g0}")
    gripper_set(CLOSE_POS, duration=3.0)
    rospy.sleep(1.0)
    g1 = get_servo_states()[10]
    g.log(f"gripper after close: {g1}")
    g.gate("grip_resistance", g1["error"] <= -8,
           measured=f"goal={g1['goal']} pos={g1['position']} err={g1['error']}",
           expected="error ≤ -8（受阻=夹到物体）")

    for _ in range(3):
        cartesian_jog(dz=0.02, duration=2.5, pitch_deg=87.0)
    pos, _ = get_current_pose()
    g.log(f"lifted pose: {[round(v,3) for v in pos]}")
    g.gate("lifted", pos[2] > 0.0, measured=f"z={pos[2]:.3f}", expected="抬离桌面")

    det = detect_centroid(get_frame(), COLOR)
    g.gate("held_after_lift", det is not None and det["area"] >= MIN_HOLD_AREA,
           measured=str(None if det is None else (round(det["u"]), round(det["v"]), int(det["area"]))),
           expected="目标仍可见且面积 ≥ 12000")
    frame = get_frame()
    cv2.imwrite(g.artifact_path("post_grasp.jpg"),
                annotate(frame, detect_centroid(frame, COLOR), COLOR + " held"))

    cartesian_jog(dy=0.02, duration=2.5, pitch_deg=87.0)
    det2 = detect_centroid(get_frame(), COLOR)
    g.gate("held_after_lateral", det2 is not None and det2["area"] >= MIN_HOLD_AREA,
           measured=str(None if det2 is None else (round(det2["u"]), round(det2["v"]), int(det2["area"]))),
           expected="侧移后目标仍跟随")
    cv2.imwrite(g.artifact_path("verify_hold.jpg"),
                annotate(get_frame(), detect_centroid(get_frame(), COLOR), COLOR + " verified"))


if __name__ == "__main__":
    raise SystemExit(main("07_grasp", run))
