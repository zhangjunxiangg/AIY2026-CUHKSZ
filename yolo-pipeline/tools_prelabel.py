"""tools_prelabel.py —— 锥桶自动预标注（人工验证前的提案生成）。

对 dataset_transformed/ 每张图用 HSV+形态学提出 blue_cone bbox，
写出 YOLO 标签 .txt 和标注预览图 prelabel_preview/。
标签必须经人工核对后才算数（02 门禁只负责格式，不负责对错）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util_paths

# 原图（手机）上的藏青锥范围（实测：锥 H147-153 S137-165 V111-142，放宽留余量）
# 注意：提案在原始手机图（缩放到 640x480）上做，颜色未受风格迁移影响；
# 标签是归一化坐标，几何不变，直接给转换后图像复用。
CONE_HSV = [((90, 80, 30), (130, 255, 175))]
MIN_AREA = 1500         # 640x480 下锥体最小面积
MIN_ASPECT = 1.0        # 立式：高 >= 宽
MAX_ASPECT = 4.0
MORPH_CLOSE = (21, 11)
MORPH_CLOSE_V = (200, 5)  # 竖向桥接：合并同一锥被白条纹分割的各段


def imread_safe(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)


def propose(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], np.uint8)
    for lo, hi in CONE_HSV:
        mask |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones(MORPH_CLOSE, np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 段级组件（锥的顶部/底座等藏青色部分）
    comps = []
    for c in contours:
        if cv2.contourArea(c) < MIN_AREA:
            continue
        comps.append(list(cv2.boundingRect(c)))

    # 聚类：x 重叠大 + 垂直间距小（白条纹间隙）的段属于同一锥；
    # 不用巨核 CLOSE，避免与锥上方背景（横幅/展位）合并
    clusters = []
    for x, y, w, h in sorted(comps, key=lambda b: b[1]):
        placed = False
        for cl in clusters:
            cx1 = max(cl[0], x)
            cx2 = min(cl[0] + cl[2], x + w)
            x_overlap = cx2 - cx1
            gap = y - (cl[1] + cl[3])  # cl 始终在当前段上方（按 y 排序）
            max_h = max(cl[3], h)
            if x_overlap > 0.5 * min(cl[2], w) and gap <= max(40, int(0.8 * max_h)):
                nx, ny = min(cl[0], x), min(cl[1], y)
                nx2 = max(cl[0] + cl[2], x + w)
                ny2 = max(cl[1] + cl[3], y + h)
                cl[:] = [nx, ny, nx2 - nx, ny2 - ny]
                placed = True
                break
        if not placed:
            clusters.append([x, y, w, h])

    boxes = []
    H, W = img.shape[:2]
    for x, y, w, h in clusters:
        aspect = h / float(w)
        if not (MIN_ASPECT <= aspect <= MAX_ASPECT):
            continue
        boxes.append([x / W + w / 2 / W, y / H + h / 2 / H, w / W, h / H])
    return boxes


def main():
    out_dir = util_paths.ROOT / "prelabel_preview"
    out_dir.mkdir(exist_ok=True)
    raw_imgs = {p.stem: p for p in util_paths.DATASET_RAW.glob("*.jpg")}
    raw_imgs.update({p.stem: p for p in util_paths.DATASET_RAW.glob("*.png")})
    imgs = sorted(util_paths.TRANSFORMED.glob("*.jpg"))
    n_boxes = 0
    misses = []
    for p in imgs:
        # 提案在原始手机图上做（色彩未被风格迁移改变），几何一致
        src = raw_imgs.get(p.stem)
        proposal_img = cv2.resize(imread_safe(src), (640, 480),
                                  interpolation=cv2.INTER_AREA) if src else imread_safe(p)
        boxes = propose(proposal_img)
        if not boxes:
            misses.append(p.name)
        img = imread_safe(p)
        H, W = img.shape[:2]
        vis = img.copy()
        for cx, cy, w, h in boxes:
            x1, y1 = int((cx - w / 2) * W), int((cy - h / 2) * H)
            x2, y2 = int((cx + w / 2) * W), int((cy + h / 2) * H)
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.imencode(".jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 85])[1] \
            .tofile(str(out_dir / p.name))
        (util_paths.TRANSFORMED / (p.stem + ".txt")).write_text(
            "\n".join("0 " + " ".join(f"{v:.6f}" for v in b) for b in boxes),
            encoding="utf-8")
        n_boxes += len(boxes)
    print(f"预标注完成: {len(imgs)} 张图, {n_boxes} 个框, 无框 {len(misses)} 张: {misses}")


if __name__ == "__main__":
    main()
