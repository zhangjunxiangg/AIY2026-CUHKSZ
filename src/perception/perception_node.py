#!/usr/bin/env python3
# 感知主节点：sim 模式本机跑图片（不依赖 ROS）；ros 模式在板端 rk3588s-vision 容器内
# 用 rospy 订阅 Astra 相机话题跑检测（Python 3.11 + ROS1 Noetic）。日志一律英文。
"""Student perception node: sim mode (local images) / ros mode (on-board Astra camera).

sim: python perception_node.py --sim --images <file|dir> [--config config.json] [--loop N]
ros: python perception_node.py --ros [--config config.json] [--depth]

Output JSON (both modes):
  {"ts": <float sec>, "frame": [w, h],
   "targets": [{"category", "center", "confidence", "bbox", "depth_mm": null|int}]}
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from detectors import imread_safe, load_config, run_pipeline

HERE = Path(__file__).resolve().parent
IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp")


def attach_depth(targets, depth, cfg):
    """给每个目标附 depth_mm：bbox 中心区域深度中位数。

    采样区 = 以目标中心为中心、bbox 宽高的 sample_fraction 倍；
    过滤 0 值与 <min_valid_mm / >max_valid_mm 的无效值；有效像素太少则保持 None。
    """
    h_img, w_img = depth.shape[:2]
    lo = float(cfg.get("min_valid_mm", 600))
    hi = float(cfg.get("max_valid_mm", 8000))
    frac = float(cfg.get("sample_fraction", 0.5))
    min_pixels = int(cfg.get("min_valid_pixels", 5))
    for t in targets:
        t["depth_mm"] = None
        cx, cy = t["center"]
        bw, bh = t["bbox"][2], t["bbox"][3]
        hw = max(1, int(bw * frac / 2))
        hh = max(1, int(bh * frac / 2))
        x0, x1 = max(0, cx - hw), min(w_img, cx + hw + 1)
        y0, y1 = max(0, cy - hh), min(h_img, cy + hh + 1)
        if x1 <= x0 or y1 <= y0:
            continue
        region = depth[y0:y1, x0:x1]
        valid = region[(region >= lo) & (region <= hi)]  # 0 值自然被 lo 过滤
        if valid.size < min_pixels:
            continue
        t["depth_mm"] = int(np.median(valid))
    return targets


def make_result(bgr, targets):
    """组装顶层输出 JSON（两种模式格式一致）。status=ok 表示本帧正常检测。"""
    h, w = bgr.shape[:2]
    return {
        "ts": round(time.time(), 3),
        "status": "ok",
        "frame": [w, h],
        "targets": [
            {
                "category": t["category"],
                "center": t["center"],
                "confidence": t["confidence"],
                "bbox": t["bbox"],
                "depth_mm": t.get("depth_mm"),
            }
            for t in targets
        ],
    }


def run_sim(args, config):
    """sim 模式：对每张图跑 run_pipeline，打印英文摘要 + 最后一行输出纯 JSON。"""
    src = Path(args.images)
    if src.is_dir():
        files = sorted(p for p in src.iterdir() if p.suffix.lower() in IMG_EXTS)
    else:
        files = [src]
    if not files:
        print(f"[SIM] ERROR no images found: {src}", file=sys.stderr)
        return 2
    print(f"[SIM] {len(files)} image(s), loop x{args.loop}")
    for it in range(args.loop):
        if args.loop > 1:
            print(f"[SIM] --- loop {it + 1}/{args.loop} ---")
        for f in files:
            bgr = imread_safe(f)
            if bgr is None:
                print(f"[SIM] WARN cannot read image: {f}")
                continue
            t0 = time.time()
            targets = run_pipeline(bgr, config)
            for t in targets:
                t["depth_mm"] = None  # sim 模式无深度源
            elapsed_ms = (time.time() - t0) * 1000.0
            print(f"[SIM] {f.name}: {len(targets)} target(s) in {elapsed_ms:.1f} ms")
            for t in targets:
                print(
                    f"[SIM]   - {t['category']} conf={t['confidence']} "
                    f"center={t['center']} bbox={t['bbox']}"
                )
            print(json.dumps(make_result(bgr, targets), ensure_ascii=False))
    return 0


def run_ros(args, config):
    """ros 模式（板端容器内）：wait_for_message 循环 + 新鲜度检查，发布 String(JSON)。"""
    import rospy  # lazy import：仅板端容器内有 ROS
    from sensor_msgs.msg import Image
    from std_msgs.msg import String

    from decode import (
        ros_compressed_image_to_bgr,
        ros_image_to_bgr,
        ros_image_to_depth,
    )

    ros_cfg = config.get("ros", {})
    pub_topic = ros_cfg.get("publish_topic", "/student/perception/targets")
    rate_hz = float(ros_cfg.get("rate_hz", 2.0))
    timeout = float(ros_cfg.get("msg_timeout_s", 5.0))
    fresh_s = float(ros_cfg.get("freshness_s", 1.0))
    out_file = Path(ros_cfg.get("output_file", "/tmp/perception_targets.json"))
    depth_on = bool(config.get("depth", {}).get("enable", False)) or bool(args.depth)

    # 主相机（Astra）或辅助相机（Gemini335）二选一
    aux_cfg = config.get("aux_camera", {})
    use_aux = bool(aux_cfg.get("enable", False))
    if use_aux:
        from sensor_msgs.msg import CompressedImage
        rgb_topic = aux_cfg.get("compressed_color_topic", "/aux_camera/color/image_raw/compressed")
        depth_topic = aux_cfg.get("depth_topic", "/aux_camera/depth/image_raw")
        rgb_msg_type = CompressedImage
        rgb_decoder = ros_compressed_image_to_bgr
    else:
        rgb_topic = ros_cfg.get("rgb_topic", "/astra_camera/rgb/image_raw")
        depth_topic = ros_cfg.get("depth_topic", "/astra_camera/depth/image_raw")
        rgb_msg_type = Image
        rgb_decoder = ros_image_to_bgr

    rospy.init_node("student_perception", anonymous=False)
    pub = rospy.Publisher(pub_topic, String, queue_size=1, latch=False)
    rate = rospy.Rate(rate_hz)
    rospy.loginfo(
        "[PERCEPTION] node up: aux=%s rgb=%s depth=%s rate=%.1fHz depth_on=%s",
        use_aux, rgb_topic, depth_topic, rate_hz, depth_on,
    )
    depth_resize_warned = False

    def publish_status(status):
        """故障心跳：让下游永远能区分'没目标'（ok+空数组）和'链路故障'（status!=ok）。"""
        payload = json.dumps(
            {"ts": round(time.time(), 3), "status": status, "targets": []},
            ensure_ascii=False,
        )
        pub.publish(String(data=payload))
        try:
            out_file.write_text(payload, encoding="utf-8")
        except OSError:
            pass
        rate.sleep()

    while not rospy.is_shutdown():
        try:
            rgb_msg = rospy.wait_for_message(rgb_topic, rgb_msg_type, timeout=timeout)
        except rospy.ROSException:
            rospy.logwarn_throttle(5.0, "[PERCEPTION] timeout waiting for %s", rgb_topic)
            publish_status("no_frame")
            continue
        # 新鲜度检查：stamp 为 0 表示驱动没打时间戳，无法判断则放行
        stamp = rgb_msg.header.stamp.to_sec()
        if stamp > 0 and time.time() - stamp > fresh_s:
            rospy.logwarn_throttle(5.0, "[PERCEPTION] stale rgb frame, age=%.2fs", time.time() - stamp)
            publish_status("stale_frame")
            continue
        try:
            bgr = rgb_decoder(rgb_msg)
        except RuntimeError as exc:
            rospy.logwarn_throttle(5.0, "[PERCEPTION] rgb decode failed: %s", exc)
            publish_status("decode_error")
            continue

        depth = None
        if depth_on:
            try:
                depth_msg = rospy.wait_for_message(depth_topic, Image, timeout=timeout)
                depth = ros_image_to_depth(depth_msg)
            except rospy.ROSException:
                rospy.logwarn_throttle(5.0, "[PERCEPTION] timeout waiting for %s", depth_topic)
            except RuntimeError as exc:
                rospy.logwarn_throttle(5.0, "[PERCEPTION] depth decode failed: %s", exc)

        targets = run_pipeline(bgr, config)
        if depth is not None:
            if depth.shape[:2] != bgr.shape[:2]:
                if not depth_resize_warned:
                    rospy.logwarn(
                        "[PERCEPTION] depth size %s != rgb size %s, resizing depth (nearest)",
                        depth.shape[:2], bgr.shape[:2],
                    )
                    depth_resize_warned = True
                depth = cv2.resize(
                    depth, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_NEAREST
                )
            attach_depth(targets, depth, config.get("depth", {}))
        else:
            for t in targets:
                t["depth_mm"] = None

        payload = json.dumps(make_result(bgr, targets), ensure_ascii=False)
        pub.publish(String(data=payload))
        try:
            out_file.write_text(payload, encoding="utf-8")
        except OSError as exc:
            rospy.logwarn_throttle(10.0, "[PERCEPTION] cannot write %s: %s", out_file, exc)
        rospy.loginfo_throttle(2.0, "[PERCEPTION] %d target(s) published", len(targets))
        rate.sleep()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sim", action="store_true", help="offline mode on local images")
    mode.add_argument("--ros", action="store_true", help="on-board mode via rospy")
    parser.add_argument("--images", help="image file or directory (required in --sim mode)")
    parser.add_argument("--config", default=None,
                        help="config json path (default: config.json next to this file)")
    parser.add_argument("--loop", type=int, default=1, help="sim mode repeat count")
    parser.add_argument("--depth", action="store_true",
                        help="force-enable depth attach (overrides config depth.enable)")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.depth:
        config.setdefault("depth", {})["enable"] = True

    if args.sim:
        if not args.images:
            parser.error("--sim requires --images <file|dir>")
        return run_sim(args, config)
    return run_ros(args, config)


if __name__ == "__main__":
    sys.exit(main())
