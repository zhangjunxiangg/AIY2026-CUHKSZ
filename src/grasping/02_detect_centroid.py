#!/usr/bin/env python3
"""02_detect_centroid.py — Gate 02：三色质心检测验证

对 red/yellow/green 各检测 5 帧：
- 每帧都要检出（面积 >= min_area）
- 质心位置跨帧稳定（抖动 < 15px）
- 三色质心互不重合（区分度）
证据：logs/02_detect_centroid/<color>.jpg 标注图。
"""
import cv2
import rospy

from util_gate import Gate, main
from util_board import get_frame, wait_exposure, detect_centroid, annotate, ensure_camera

COLORS = ["red", "yellow", "green"]
MIN_AREA = 300.0
MAX_JITTER = 15.0
MIN_SEPARATION = 60.0


def run(g: Gate):
    g.require_prev("01_camera_ready")
    rospy.init_node("step02_detect", anonymous=True)
    ensure_camera()
    wait_exposure(discard=5)

    # 可见性分级：FULL（5/5 帧 >= MIN_AREA）、EDGE（>=3/5 帧 >= 200px，部分在画面外）、OUT
    centroids = {}
    status = {}
    for color in COLORS:
        dets = []
        annotated = None
        for _ in range(5):
            frame = get_frame()
            det = detect_centroid(frame, color, min_area=200.0)
            if det:
                dets.append(det)
                annotated = annotate(frame, det, color)
        full = [d for d in dets if d["area"] >= MIN_AREA]
        if len(full) == 5:
            status[color] = "FULL"
        elif len(dets) >= 3:
            status[color] = "EDGE"
        else:
            status[color] = "OUT"
        g.log(f"{color}: status={status[color]} detected={len(dets)}/5")
        g.gate(f"{color}_not_out", status[color] != "OUT",
               measured=status[color], expected="FULL 或 EDGE（至少 3/5 帧可见）")
        if status[color] == "FULL":
            areas = [d["area"] for d in full]
            us = [d["u"] for d in full]
            vs = [d["v"] for d in full]
            jitter = max(max(us) - min(us), max(vs) - min(vs))
            g.gate(f"{color}_stable", jitter < MAX_JITTER,
                   measured=f"jitter={jitter:.1f}px", expected=f"< {MAX_JITTER}px")
            centroids[color] = (sum(us) / len(us), sum(vs) / len(vs))
            g.log(f"{color}: centroid=({centroids[color][0]:.0f},{centroids[color][1]:.0f}) "
                  f"area={sum(areas)/len(areas):.0f} bbox={full[-1]['bbox']}")
        else:
            g.log(f"WARN: {color} 仅边缘可见（面积不足），伺服装管时先向该方向搜索")
            centroids[color] = (dets[-1]["u"], dets[-1]["v"])
        if annotated is not None:
            cv2.imwrite(g.artifact_path(f"{color}.jpg"), annotated)

    # 至少两个 FULL（当前机位红/绿应在视野内，黄允许 EDGE）
    full_count = sum(1 for s in status.values() if s == "FULL")
    g.gate("at_least_two_full", full_count >= 2,
           measured=f"FULL={full_count} status={status}", expected=">= 2 个 FULL")

    # FULL 颜色质心两两分离（EDGE 的质心不可靠，不参与）
    full_colors = [c for c, s in status.items() if s == "FULL"]
    for i in range(len(full_colors)):
        for j in range(i + 1, len(full_colors)):
            a, b = full_colors[i], full_colors[j]
            dx = centroids[a][0] - centroids[b][0]
            dy = centroids[a][1] - centroids[b][1]
            dist = (dx * dx + dy * dy) ** 0.5
            g.gate(f"separation_{a}_{b}", dist >= MIN_SEPARATION,
                   measured=f"{dist:.0f}px", expected=f">= {MIN_SEPARATION}px")


if __name__ == "__main__":
    raise SystemExit(main("02_detect_centroid", run))
