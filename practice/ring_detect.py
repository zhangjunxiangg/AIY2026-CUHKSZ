"""套环识别练习：颜色 + RETR_CCOMP 孔洞检测。

对应搬运任务的 EVA 套环。环 vs 实心球/方块最可靠的区别不是填充率，
而是**空心结构**：外轮廓内有子轮廓（内孔）。
cv2.findContours 用 RETR_CCOMP 取出两级轮廓（外边界 + 内孔），
"有子轮廓的外轮廓" = 环。

用法：
    python ring_detect.py            # 生成合成场景 ring_scene.png 并自测
    python ring_detect.py 某张图.jpg  # 检测真实图片
"""
import json
import sys

import cv2
import numpy as np

COLOR_RANGES = {
    "red": [((0, 120, 70), (10, 255, 255)), ((170, 120, 70), (180, 255, 255))],
    "green": [((35, 80, 60), (85, 255, 255))],
    "blue": [((90, 80, 60), (130, 255, 255))],
    "yellow": [((20, 100, 100), (35, 255, 255))],
}


def detect_rings(bgr, min_area=300):
    """输入 BGR 图像，输出套环列表（统一接口格式）。"""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    results = []
    for name, ranges in COLOR_RANGES.items():
        mask = np.zeros(hsv.shape[:2], np.uint8)
        for lo, hi in ranges:
            mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:
            continue
        hierarchy = hierarchy[0]  # 每条: [Next, Previous, First_Child, Parent]
        for i, c in enumerate(contours):
            has_child = hierarchy[i][2] >= 0   # 有子轮廓 = 有内孔
            is_outer = hierarchy[i][3] < 0     # 本身是外轮廓
            if not (has_child and is_outer):
                continue
            area = cv2.contourArea(c)
            if area < min_area:
                continue
            m = cv2.moments(c)
            cx, cy = int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"])
            results.append({
                "category": f"{name}_ring",
                "center": [cx, cy],
                "confidence": 1.0,
            })
    return results


def make_test_scene():
    """合成场景：红环、绿环 + 实心黄球、实心蓝方块干扰项。"""
    img = np.full((480, 640, 3), 240, np.uint8)
    cv2.circle(img, (150, 150), 55, (0, 0, 220), -1)     # 红环外圆
    cv2.circle(img, (150, 150), 25, (240, 240, 240), -1)  # 红环内孔
    cv2.circle(img, (450, 300), 50, (0, 200, 0), -1)     # 绿环外圆
    cv2.circle(img, (450, 300), 22, (240, 240, 240), -1)  # 绿环内孔
    cv2.circle(img, (480, 120), 40, (0, 220, 230), -1)   # 干扰：实心黄球
    cv2.rectangle(img, (80, 300), (180, 400), (230, 120, 0), -1)  # 干扰：蓝方块
    return cv2.GaussianBlur(img, (5, 5), 0)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        bgr = cv2.imread(sys.argv[1])
        assert bgr is not None, f"读不到图片: {sys.argv[1]}"
    else:
        bgr = make_test_scene()
        cv2.imwrite("ring_scene.png", bgr)
        print("已生成合成测试图 ring_scene.png")
    results = detect_rings(bgr)
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    ok = len(results) == 2
    print("SELF-TEST PASSED" if ok else f"SELF-TEST FAILED: expected 2 rings, got {len(results)}")
    sys.exit(0 if ok else 1)
