#!/usr/bin/env python3
"""01_camera_ready.py — Gate 01：夹爪相机就绪验证

验证链：话题在发布 → 丢 20 帧等自动曝光收敛 → 帧统计合理（不过曝/不黑屏/非均匀图）。
证据：logs/01_camera_ready/frame_ok.jpg + 统计写入 step.log。
"""
import cv2
import rospy

from util_gate import Gate, main
from util_board import get_frame, wait_exposure, frame_stats


def run(g: Gate):
    rospy.init_node("step01_camera_ready", anonymous=True)

    # gate 1：话题在发布（gripper_camera_node 已启动）
    t0 = __import__("time").time()
    try:
        first = get_frame(timeout=5.0)
        alive = True
    except Exception as e:
        alive = False
        g.log(f"get_frame exception: {e}")
    g.gate("topic_alive", alive, measured="frame received" if alive else "timeout/exception",
           expected="/gripper_camera/image_raw publishing")
    g.gate("frame_shape", first.shape == (480, 640, 3), measured=str(first.shape), expected="(480,640,3)")

    # gate 2：首帧允许过曝（icSpring 特性），记录但不卡
    s0 = frame_stats(first)
    g.log(f"first-frame stats: mean={s0['mean']:.1f} std={s0['std']:.1f}（允许过曝）")
    cv2.imwrite(g.artifact_path("frame_first.jpg"), first)

    # 丢 20 帧等曝光收敛
    wait_exposure(discard=20)
    g.time_it("exposure_discard", __import__("time").time() - t0)

    # gate 3：收敛后帧统计合理
    frame = get_frame()
    s = frame_stats(frame)
    g.gate("exposure_converged", 15.0 < s["mean"] < 240.0,
           measured=f"mean={s['mean']:.1f}", expected="15 < mean < 240（不过曝/不黑屏）")
    g.gate("frame_not_uniform", s["std"] > 10.0,
           measured=f"std={s['std']:.1f}", expected="std > 10（非纯色/异常帧）")

    # gate 4：连续 3 帧稳定（曝光不漂移）
    means = [frame_stats(get_frame())["mean"] for _ in range(3)]
    drift = max(means) - min(means)
    g.gate("exposure_stable", drift < 30.0,
           measured=f"means={[round(m,1) for m in means]} drift={drift:.1f}", expected="drift < 30")

    cv2.imwrite(g.artifact_path("frame_ok.jpg"), frame)
    g.log(f"settled stats: mean={s['mean']:.1f} std={s['std']:.1f}；证据 frame_ok.jpg")


if __name__ == "__main__":
    raise SystemExit(main("01_camera_ready", run))
