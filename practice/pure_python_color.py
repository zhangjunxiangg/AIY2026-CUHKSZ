"""纯 Python 兜底颜色检测：零依赖，只用标准库。

为什么要有这个（《踩坑与参考库》§1 的硬约束）：
- 板上 pip 只能装纯 Python 包，**numpy / opencv 这类带 C 扩展的现场装不上**
- 如果明天确认板端没有预装 cv2/numpy，感知算法就得靠这个兜底思路跑
- 输入是 RGB 原始像素（比如从相机帧或 ROS 消息手工解出的数组），不依赖任何图像库

已知局限（兜底方案，够用就行）：
- 同色多个目标会合并成一个区域（没有连通域分析）
- 阈值是 RGB 简单规则，现场要按物料实际颜色重新标定

用法：
    python pure_python_color.py    # 自测：合成 80x60 场景，找红/绿/蓝/黄
"""
import json
import sys

# RGB 判定规则：现场按物料实际颜色标定（此处对应合成场景的 EVA 方块/小球）
COLOR_RULES = {
    "red": lambda r, g, b: r > 150 and g < 110 and b < 110,
    "green": lambda r, g, b: g > 120 and r < 110 and b < 110,
    "blue": lambda r, g, b: b > 150 and r < 130 and g < 150,
    "yellow": lambda r, g, b: r > 150 and g > 130 and b < 110,
}


def detect_colors_stdlib(pixels, width, height, min_area=20):
    """pixels: 一维 list[(r,g,b)]，按行展开。返回统一格式检测结果。"""
    results = []
    for name, hit in COLOR_RULES.items():
        xs, ys = [], []
        for y in range(height):
            base = y * width
            for x in range(width):
                r, g, b = pixels[base + x]
                if hit(r, g, b):
                    xs.append(x)
                    ys.append(y)
        if len(xs) >= min_area:
            results.append({
                "category": name,
                "center": [sum(xs) // len(xs), sum(ys) // len(ys)],
                "confidence": 1.0,  # 无形状信息，兜底方案只保证"有/无 + 大概位置"
            })
    return results


def make_test_pixels(width=80, height=60):
    """合成场景：红方块(10,10)-(25,25)、绿圆心(60,15)r=8、
    蓝方块(40,35)-(55,50)、黄圆心(15,45)r=7。"""
    px = [(240, 240, 240)] * (width * height)

    def fill_rect(x0, y0, x1, y1, color):
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[y * width + x] = color

    def fill_circle(cx, cy, rad, color):
        for y in range(max(0, cy - rad), min(height, cy + rad + 1)):
            for x in range(max(0, cx - rad), min(width, cx + rad + 1)):
                if (x - cx) ** 2 + (y - cy) ** 2 <= rad ** 2:
                    px[y * width + x] = color

    fill_rect(10, 10, 25, 25, (220, 30, 30))
    fill_circle(60, 15, 8, (30, 200, 30))
    fill_rect(40, 35, 55, 50, (30, 60, 230))
    fill_circle(15, 45, 7, (230, 220, 30))
    return px, width, height


if __name__ == "__main__":
    pixels, w, h = make_test_pixels()
    results = detect_colors_stdlib(pixels, w, h)
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    # 自测校验：四类颜色都应检出，且质心落在目标附近（±5 像素）
    expected = {"red": (17, 17), "green": (60, 15), "blue": (47, 42), "yellow": (15, 45)}
    found = {r["category"]: r["center"] for r in results}
    ok = True
    for name, (ex, ey) in expected.items():
        if name not in found:
            print(f"FAIL: {name} not detected")
            ok = False
            continue
        ax, ay = found[name]
        if abs(ax - ex) > 5 or abs(ay - ey) > 5:
            print(f"FAIL: {name} center ({ax},{ay}) too far from ({ex},{ey})")
            ok = False
    print("SELF-TEST PASSED" if ok else "SELF-TEST FAILED")
    sys.exit(0 if ok else 1)
