#!/usr/bin/env python3
"""07_robot_localization: locate the robot on the field.

Hard-won design (see run1 logs for the evidence trail):
  - The robot is a weak structured-light target (dark plastic / metal /
    glossy screen): only ~2-15% of its pixels return valid depth per frame,
    so depth-only foreground detection cannot find it reliably.
  - The mat is uniformly WHITE. The robot is the darkest object on it.
  -> Detection in the COLOR image: largest dark connected blob on the
     floor surface (floor-plane inlier ROI). Mat-seam phantoms are the same
     white as the floor and are rejected by the darkness test.
  -> Position: the blob's base-band pixels (contact with the floor) are
     back-projected through the fitted floor plane (ray-plane
     intersection). Depth values of the robot body are NOT needed, which
     also avoids the ray-overshoot problem of elevated bodies.

Field frame: origin = camera nadir on the floor, x = camera-right
projected, y = cross(n, x), millimetres.

Gates: plane inliers >= 25%, detection rate >= 80%, static-window position
std <= 60mm (repeatability floor, ~2% of range), overlay artifact.
Usage: 07_robot_localization.py <out_root> <intrinsics.json>
"""

import csv
import json
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from util_gate import Step
from util_filter import colorize

DARK_MAX = 110.0      # mean-intensity ceiling for "dark" pixels on the mat
AREA_ROBOT = (1500, 30000)   # robot blob area range, px
STATIC_WINDOW = 20


def deproject_grids(h, w, fx, fy, cx, cy):
    u, v = np.meshgrid(np.arange(w, dtype=np.float32),
                       np.arange(h, dtype=np.float32))
    return (u - cx) / fx, (v - cy) / fy


def fit_plane(dx, dy, zmed, valid, iterations=400, thresh_mm=60.0, seed=7):
    """RANSAC plane fit: the floor is a large plane but may not be the
    majority of valid pixels (walls, people, background)."""
    pts = np.stack([dx[valid] * zmed[valid], dy[valid] * zmed[valid],
                    zmed[valid]], axis=1)
    rng = np.random.default_rng(seed)
    best_inliers = None
    best_count = 0
    for _ in range(iterations):
        sample = pts[rng.choice(len(pts), 3, replace=False)]
        v1, v2 = sample[1] - sample[0], sample[2] - sample[0]
        n = np.cross(v1, v2)
        norm = np.linalg.norm(n)
        if norm < 1e-6:
            continue
        n /= norm
        if n[2] > 0:  # normal must point toward the camera (-Z side)
            n = -n
        dist = pts @ n - (sample[0] @ n)
        inliers = np.abs(dist) < thresh_mm
        count = int(inliers.sum())
        if count > best_count:
            best_count = count
            best_inliers = inliers
    mask = best_inliers
    for _ in range(2):
        sel = pts[mask]
        A = np.stack([sel[:, 0], sel[:, 1], np.ones(len(sel))], axis=1)
        sol, *_ = np.linalg.lstsq(A, sel[:, 2], rcond=None)
        a, b, c = sol
        n = np.array([a, b, -1.0])
        norm = np.linalg.norm(n)
        n /= norm
        d = c / norm
        if d > 0:  # camera center must be on the positive side
            n, d = -n, -d
        mask = np.abs(pts @ n + d) < thresh_mm
    return n, d, float(mask.mean())


def main(out_root, intr_path):
    step = Step(out_root, "07_robot_localization")
    step.require_predecessor(out_root, "01_capture_baseline")

    intr = json.load(open(intr_path))
    fx, fy, cx, cy = intr["fx"], intr["fy"], intr["cx"], intr["cy"]
    step.gate(fx > 0 and fy > 0, "intrinsics valid", f"fx={fx} fy={fy}", ">0")

    seq = np.load(os.path.join(out_root, "depth_seq.npy"))
    T, h, w = seq.shape
    step.log(f"seq {seq.shape}, intrinsics fx={fx:.1f} fy={fy:.1f}")

    color_path = os.path.join(out_root, "color.mp4")
    cap = cv2.VideoCapture(color_path)
    color_frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        color_frames.append(fr)
    cap.release()
    step.gate(len(color_frames) >= 0.8 * T, "color frames >= 80% of depth",
              len(color_frames), f">={int(0.8 * T)}")

    dx, dy = deproject_grids(h, w, fx, fy, cx, cy)
    zmed = np.median(seq, axis=0)
    valid = zmed > 0
    sub = np.zeros_like(valid)
    sub[::4, ::4] = True
    n, d_off, inlier = fit_plane(dx, dy, zmed, valid & sub)
    step.log(f"plane n={np.round(n, 4).tolist()} d={d_off:.1f} "
             f"inlier={inlier:.3f}")
    inl_mask = (np.abs((np.stack([dx * zmed, dy * zmed, zmed],
                                 axis=-1) @ n) + d_off) < 60.0) & valid
    vis = colorize(zmed.astype(np.uint16))
    vis[inl_mask] = (0.5 * vis[inl_mask] + np.array([127, 0, 0])).astype(np.uint8)
    cv2.imwrite(os.path.join(out_root, "floor_inliers.jpg"), vis)
    step.gate(inlier >= 0.25, "dominant plane inlier ratio >= 0.25",
              round(inlier, 3), ">=0.25")

    origin = -d_off * n
    x_f = np.array([1.0, 0, 0]) - n[0] * n
    x_f /= np.linalg.norm(x_f)
    y_f = np.cross(n, x_f)
    step.log(f"camera height above floor: {abs(d_off):.0f} mm")

    # robot must sit on the floor surface (dilated inlier mask)
    roi = cv2.dilate(inl_mask.astype(np.uint8),
                     np.ones((25, 25), np.uint8)).astype(bool)

    k3 = np.ones((3, 3), np.uint8)
    k15 = np.ones((15, 15), np.uint8)

    t0 = time.perf_counter()
    positions = []
    track = None
    overlay = cv2.VideoWriter(os.path.join(out_root, "robot_overlay.mp4"),
                              cv2.VideoWriter_fourcc(*"mp4v"), 10, (w, h))
    font = cv2.FONT_HERSHEY_SIMPLEX
    for t in range(T):
        img = color_frames[min(t, len(color_frames) - 1)].copy()
        gray = img.mean(axis=2)
        dark = ((gray < DARK_MAX) & roi).astype(np.uint8)
        dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, k3)
        dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, k15)
        nlab, labels, stats, cents = cv2.connectedComponentsWithStats(dark, 8)
        best = None
        for i in range(1, nlab):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if not (AREA_ROBOT[0] <= area <= AREA_ROBOT[1]):
                continue
            st = stats[i]
            # reject blobs cut off by the image border (near-edge bezel,
            # furniture) -- the robot is fully inside the frame
            if st[cv2.CC_STAT_LEFT] <= 2 or st[cv2.CC_STAT_TOP] <= 2 \
                    or st[cv2.CC_STAT_LEFT] + st[cv2.CC_STAT_WIDTH] >= w - 2 \
                    or st[cv2.CC_STAT_TOP] + st[cv2.CC_STAT_HEIGHT] >= h - 2:
                continue
            if best is None or area > best[0]:
                best = (area, i)
        if best is not None:
            i = best[1]
            blob = labels == i
            # footprint = blob base band (bottom 5% rows) -> ray x floor
            ys, xs = np.nonzero(blob)
            y_cut = np.percentile(ys, 95)
            base = ys >= y_cut
            bx, by = float(xs[base].mean()), float(ys[base].mean())
            dirv = np.array([(bx - cx) / fx, (by - cy) / fy, 1.0])
            p = (-d_off / float(n @ dirv)) * dirv
            fx_mm = float((p - origin) @ x_f)
            fy_mm = float((p - origin) @ y_f)
            if track is None:
                track = [fx_mm, fy_mm]
            else:
                track[0] += 0.3 * (fx_mm - track[0])
                track[1] += 0.3 * (fy_mm - track[1])
            positions.append((t, track[0], track[1], 0.0, best[0]))
            st = stats[i]
            x0, y0 = st[cv2.CC_STAT_LEFT], st[cv2.CC_STAT_TOP]
            bw, bh = st[cv2.CC_STAT_WIDTH], st[cv2.CC_STAT_HEIGHT]
            cv2.rectangle(img, (x0, y0), (x0 + bw, y0 + bh),
                          (0, 255, 0), 2)
            cv2.drawMarker(img, (int(bx), int(by)), (0, 0, 255),
                           cv2.MARKER_CROSS, 16, 2)
            cv2.putText(img, f"robot x={track[0]:.0f} y={track[1]:.0f} mm",
                        (x0, max(20, y0 - 8)), font, 0.6, (0, 255, 0), 2)
        overlay.write(img)
    overlay.release()
    ms = (time.perf_counter() - t0) * 1000.0 / T
    step.log(f"localization time mean={ms:.2f}ms/frame, "
             f"detected={len(positions)}/{T}")

    det_rate = len(positions) / T
    step.gate(det_rate >= 0.8, "detection rate >= 80%",
              f"{det_rate * 100:.1f}%", ">=80%")

    arr = np.array([(p[1], p[2]) for p in positions])
    disp = np.linalg.norm(np.diff(arr, axis=0), axis=1)
    idx = int(np.argmin([disp[i:i + STATIC_WINDOW - 1].sum()
                         for i in range(max(1, len(disp) - STATIC_WINDOW + 2))]))
    win = arr[idx:idx + STATIC_WINDOW]
    std_xy = float(np.std(win, axis=0).max()) if len(win) > 1 else 0.0
    mean_x, mean_y = arr.mean(axis=0)
    step.log(f"static window std={std_xy:.1f}mm "
             f"mean_pos=({mean_x:.0f},{mean_y:.0f})")
    # Repeatability floor: blob-edge jitter on 16UC1 depth at ~2-3m is
    # ~2% of range; 60mm is ~15% of the robot body length.
    step.gate(std_xy <= 60.0, "static position std <= 60mm",
              f"{std_xy:.1f}mm", "<=60mm")

    with open(os.path.join(out_root, "robot_positions.csv"), "w",
              newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["frame", "field_x_mm", "field_y_mm", "reserved",
                     "area_px"])
        wr.writerows(positions)
    metrics = {"detection_rate": det_rate, "static_std_mm": std_xy,
               "mean_pos_mm": [float(mean_x), float(mean_y)],
               "camera_height_mm": abs(d_off),
               "plane_normal": n.tolist(), "ms_per_frame": ms,
               "method": "color dark-blob on white mat + ray-plane footprint",
               "field_frame": "origin=camera nadir on floor, "
                              "x=camera-right projected, y=cross(n,x), mm"}
    with open(os.path.join(out_root, "robot_metrics.json"), "w") as fh:
        json.dump(metrics, fh, indent=2)
    for name in ("robot_overlay.mp4", "robot_positions.csv"):
        ok = os.path.getsize(os.path.join(out_root, name)) > 1000
        step.gate(ok, f"artifact {name}", name, ">1KB")
    step.finish("PASS")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/df/out",
         sys.argv[2] if len(sys.argv) > 2 else "/tmp/df/src/intrinsics.json")
