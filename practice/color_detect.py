"""颜色块检测练习：对应赛事物料 EVA 方块 / 小球。

输出统一格式（感知节点接口草案，给角色D用）：
    {"category": "red_block" | "green_ball" | ..., "center": [cx, cy], "confidence": 0.0~1.0}

用法：
    python color_detect.py            # 生成合成场景 color_scene.png 并自测
    python color_detect.py 某张图.jpg  # 检测真实图片
"""
import json
import sys

import cv2
import numpy as np

# HSV 阈值表（OpenCV 的 H 范围 0~180）；现场按实际物料颜色重新标定
COLOR_RANGES = {
    "red": [((0, 120, 70), (10, 255, 255)), ((170, 120, 70), (180, 255, 255))],  # 红色跨 0 度，两段
    "green": [((35, 80, 60), (85, 255, 255))],
    "blue": [((90, 80, 60), (130, 255, 255))],
    "yellow": [((20, 100, 100), (35, 255, 255))],
}


def detect_colors(bgr, min_area=400):
    """输入 BGR 图像，输出检测列表。"""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    results = []
    for name, ranges in COLOR_RANGES.items():
        mask = np.zeros(hsv.shape[:2], np.uint8)
        for lo, hi in ranges:
            mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area:
                continue
            m = cv2.moments(c)
            cx, cy = int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"])
            x, y, w, h = cv2.boundingRect(c)
            fill = area / (w * h)  # 轮廓面积/外接矩形面积：圆≈0.79，方块≈1.0
            is_square_aspect = abs(w - h) < 0.15 * max(w, h)
            shape = "ball" if is_square_aspect and fill < 0.9 else "block"
            results.append({
                "category": f"{name}_{shape}",
                "center": [cx, cy],
                "confidence": round(float(fill), 2),
            })
    return results


def make_test_scene():
    """合成场景：红方块、绿球、蓝方块、黄球（对应 EVA 方块/小球物料）。"""
    img = np.full((480, 640, 3), 240, np.uint8)
    cv2.rectangle(img, (60, 80), (160, 180), (0, 0, 220), -1)      # 红方块
    cv2.circle(img, (420, 140), 45, (0, 200, 0), -1)               # 绿球
    cv2.rectangle(img, (300, 300), (420, 420), (230, 120, 0), -1)  # 蓝方块（BGR）
    cv2.circle(img, (120, 360), 40, (0, 220, 230), -1)             # 黄球
    return cv2.GaussianBlur(img, (5, 5), 0)  # 模糊一点模拟真实画质


if __name__ == "__main__":
    if len(sys.argv) > 1:
        bgr = cv2.imread(sys.argv[1])
        assert bgr is not None, f"读不到图片: {sys.argv[1]}"
    else:
        bgr = make_test_scene()
        cv2.imwrite("color_scene.png", bgr)
        print("已生成合成测试图 color_scene.png")
    for r in detect_colors(bgr):
        print(json.dumps(r, ensure_ascii=False))
