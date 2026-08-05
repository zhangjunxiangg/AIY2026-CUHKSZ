#!/usr/bin/env python3
"""05_align.py — Gate 05：观察位姿 + u 通道对准

策略（2026-08-05 实战标定）：
- 观察位姿：pitch≈87°（俯视）、z≈0.06、J4 偏大 J2 偏小的"平夹"构型
- u 通道用 dy 伺服（du/dy≈+2.5px/mm，全场稳定）
- v 通道不在此步处理（俯视下 v-x 响应弱且非线性），由 06 前进逼近处理
gate：到观察位姿、目标可见、u 收敛到 287±12 且 3 帧保持。
"""
import cv2
import rospy

from util_gate import Gate, main
from util_board import (get_frame, detect_centroid, ensure_camera,
                        u_align, get_current_pose, goto_pose, annotate)

COLOR = "red"
OBS_POSE = [0.18, 0.0, 0.06]
OBS_PITCH = 87.0
U_TARGET = 287.0


def run(g: Gate):
    g.require_prev("04_jog_probe")
    rospy.init_node("step05_align", anonymous=True)
    ensure_camera()

    res = goto_pose(OBS_POSE, OBS_PITCH, tol=0.015, max_iter=20, log=g.log)
    g.gate("reach_obs_pose", res is not None,
           measured=str(None if res is None else [round(v, 3) for v in res[0]]),
           expected=f"{OBS_POSE} ±15mm pitch≈{OBS_PITCH}")

    det0 = detect_centroid(get_frame(), COLOR)
    g.gate("target_visible_start", det0 is not None, measured=str(det0), expected="目标可见")

    result = u_align(COLOR, u_target=U_TARGET, pitch_deg=OBS_PITCH, log=g.log)
    g.gate("u_align_converged", result is not None,
           measured=str(None if result is None else round(result["u"])),
           expected=f"u={U_TARGET}±12")

    for i in range(3):
        det = detect_centroid(get_frame(), COLOR)
        g.gate(f"align_hold_{i}", det is not None and abs(det["u"] - U_TARGET) <= 12,
               measured=f"u={det['u']:.0f}" if det else "丢失", expected="保持")

    frame = get_frame()
    cv2.imwrite(g.artifact_path("aligned.jpg"), annotate(frame, detect_centroid(frame, COLOR), COLOR))
    pos, rpy = get_current_pose()
    g.log(f"end: pose={[round(v,3) for v in pos]} pitch={rpy[1]:.1f}")


if __name__ == "__main__":
    raise SystemExit(main("05_align", run))
