"""路锥检测练习：HSV 颜色 + 立式形状过滤（高宽比 > 1.2）。

对应巡检任务的"障碍识别"（路锥×5）。
路锥 vs EVA 方块/小球：同色也能区分——路锥是立式（h > w），方块/球高宽比 ≈1。
实战技巧：路锥的白色条纹会把颜色掩码切成两段，用 MORPH_CLOSE 纵向桥接。

用法：
    python cone_detect.py            # 生成合成场景 cone_scene.png 并自测
    python cone_detect.py 某张图.jpg  # 检测真实图片
"""
import json
import sys

import cv2
import numpy as np

# 路锥颜色：图示是蓝白锥，这里以蓝色为例；现场按实物重新标定（橙白锥用 orange）
CONE_COLOR = "blue"
COLOR_RANGES = {
    "blue": [((90, 80, 60), (130, 255, 255))],
    "orange": [((5, 120, 70), (25, 255, 255))],
}


def detect_cones(bgr, color=CONE_COLOR, min_area=400, min_aspect=1.2):
    """输入 BGR 图像，输出路锥列表（统一接口格式）。"""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], np.uint8)
    for lo, hi in COLOR_RANGES[color]:
        mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    # 关键一步：纵向闭运算，把被白色条纹截断的锥体重新连成整体
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((25, 9), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    results = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(c)
        aspect = h / w
        if aspect < min_aspect:  # 立式过滤：方块/球（≈1.0）在此被滤掉
            continue
        m = cv2.moments(c)
        cx, cy = int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"])
        results.append({
            "category": "cone",
            "center": [cx, cy],
            "confidence": round(min(1.0, aspect / 2), 2),
        })
    return results


def make_test_scene():
    """合成场景：两个蓝白路锥（远景一近一）+ 同色方块和小球干扰项。"""
    img = np.full((480, 640, 3), 240, np.uint8)
    for cx, base_y, s in [(150, 350, 1.0), (450, 300, 0.8)]:
        bw, bh = int(90 * s), int(150 * s)
        pts = np.array([(cx - bw // 2, base_y), (cx + bw // 2, base_y),
                        (cx + int(20 * s), base_y - bh), (cx - int(20 * s), base_y - bh)], np.int32)
        cv2.fillPoly(img, [pts], (230, 120, 0))          # 蓝锥体（BGR）
        cv2.rectangle(img, (cx - bw // 3, base_y - bh // 2 - 10),
                      (cx + bw // 3, base_y - bh // 2 + 10), (245, 245, 245), -1)  # 白条纹
    cv2.rectangle(img, (60, 60), (150, 150), (230, 120, 0), -1)   # 干扰：蓝方块
    cv2.circle(img, (520, 120), 45, (230, 120, 0), -1)            # 干扰：蓝球
    return cv2.GaussianBlur(img, (5, 5), 0)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        bgr = cv2.imread(sys.argv[1])
        assert bgr is not None, f"读不到图片: {sys.argv[1]}"
    else:
        bgr = make_test_scene()
        cv2.imwrite("cone_scene.png", bgr)
        print("已生成合成测试图 cone_scene.png")
    results = detect_cones(bgr)
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    ok = len(results) == 2
    print("SELF-TEST PASSED" if ok else f"SELF-TEST FAILED: expected 2 cones, got {len(results)}")
    sys.exit(0 if ok else 1)
