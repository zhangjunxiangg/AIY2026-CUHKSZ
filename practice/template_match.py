"""模板匹配练习：对应人形立牌 / 木制圆柱等形状固定的目标。

多尺度 cv2.matchTemplate + 简单非极大抑制，找多个目标。
真实场景的模板要从现场拍的照片里裁，这里用程序画的"人形立牌"演示流程。

用法：
    python template_match.py            # 生成模板 template.png + 合成场景 tpl_scene.png 并自测
    python template_match.py 某张图.jpg  # 在真实图片里找模板
"""
import json
import sys

import cv2
import numpy as np


def make_template():
    """画一个'人形立牌'模板：头（圆）+ 身（矩形）。"""
    t = np.full((120, 80), 255, np.uint8)
    cv2.circle(t, (40, 22), 16, 40, -1)
    cv2.rectangle(t, (18, 42), (62, 112), 40, -1)
    return t


def match_template(bgr, tpl, scales=(0.6, 0.8, 1.0, 1.2, 1.4), thresh=0.75, max_targets=3):
    """多尺度模板匹配，输出目标列表（最多 max_targets 个）。"""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    work = gray.copy()
    results = []
    for _ in range(max_targets):
        best = None
        for s in scales:
            resized = cv2.resize(tpl, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            if resized.shape[0] > work.shape[0] or resized.shape[1] > work.shape[1]:
                continue
            res = cv2.matchTemplate(work, resized, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(res)
            if best is None or score > best[0]:
                best = (score, loc, resized.shape[::-1])
        if best is None or best[0] < thresh:
            break
        score, (x, y), (w, h) = best
        results.append({
            "category": "human_board",
            "center": [x + w // 2, y + h // 2],
            "confidence": round(float(score), 2),
        })
        cv2.rectangle(work, (x, y), (x + w, y + h), 235, -1)  # 抹掉已找到的，继续找下一个
    return results


def make_test_scene(tpl):
    """合成场景：一大一小两个立牌，考多尺度匹配。"""
    img = np.full((480, 640), 235, np.uint8)
    big = cv2.resize(tpl, None, fx=1.3, fy=1.3)
    img[150:150 + big.shape[0], 380:380 + big.shape[1]] = big
    small = cv2.resize(tpl, None, fx=0.8, fy=0.8)
    img[60:60 + small.shape[0], 100:100 + small.shape[1]] = small
    img = cv2.GaussianBlur(img, (3, 3), 0)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


if __name__ == "__main__":
    tpl = make_template()
    cv2.imwrite("template.png", tpl)
    if len(sys.argv) > 1:
        bgr = cv2.imread(sys.argv[1])
        assert bgr is not None, f"读不到图片: {sys.argv[1]}"
    else:
        bgr = make_test_scene(tpl)
        cv2.imwrite("tpl_scene.png", bgr)
        print("已生成合成测试图 tpl_scene.png（模板 template.png）")
    for r in match_template(bgr, tpl):
        print(json.dumps(r, ensure_ascii=False))
