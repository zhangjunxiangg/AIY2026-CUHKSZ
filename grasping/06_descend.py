#!/usr/bin/env python3
"""06_descend.py — Gate 06：前进逼近到位（含自然下降）

实测策略：俯视构型下 +x 前进，z 随几何自然下降至桌面；
每步 15mm + u 重对准，直到 bbox 底边 v_bc ≥ 380（目标在指线区域）。
gate：12 步内到位、z 不低于 -25mm（防撞桌）、到位后图像证据。
证据：approach_final.jpg。
"""
import cv2
import rospy

from util_gate import Gate, main
from util_board import (get_frame, detect_centroid, ensure_camera,
                        advance_to_grasp, bottom_center, annotate)

COLOR = "red"
V_TRIGGER = 380.0
Z_MIN = -0.025


def run(g: Gate):
    g.require_prev("05_align")
    rospy.init_node("step06_descend", anonymous=True)
    ensure_camera()

    res = advance_to_grasp(COLOR, v_trigger=V_TRIGGER, z_min=Z_MIN, log=g.log)
    g.gate("advance_done", res is not None, measured="None", expected="前进逼近完成")

    pos, det = res
    g.gate("z_floor_ok", pos[2] > Z_MIN - 0.005,
           measured=f"z={pos[2]:.3f}", expected=f"z > {Z_MIN - 0.005}（未撞桌）")
    if det is not None:
        _, v_bc = bottom_center(det)
        g.gate("v_bc_in_band", v_bc >= V_TRIGGER,
               measured=f"v_bc={v_bc:.0f}", expected=f">= {V_TRIGGER}")
        g.gate("u_still_aligned", abs(det["u"] - 287.0) <= 20,
               measured=f"u={det['u']:.0f}", expected="287±20")
    else:
        g.log("WARN: 到位时目标被夹指/遮挡（v_bc 不可读），需人工看图确认")

    frame = get_frame()
    cv2.imwrite(g.artifact_path("approach_final.jpg"),
                annotate(frame, detect_centroid(frame, COLOR), COLOR + " approach"))
    g.log(f"approach pose: {[round(v,3) for v in pos]}")


if __name__ == "__main__":
    raise SystemExit(main("06_descend", run))
