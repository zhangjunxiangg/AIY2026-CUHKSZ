"""融合 Pro 版：四边形检测 + 透视矫正 + 模板匹配（抗斜视点位识别）。

在 quad_rectify 基础上接 template_match.match_template：
对每块找到的四边形先矫正成正面图，再做模板匹配。
卖点（本脚本自带对比验证）：斜视的字母牌，裸多尺度模板匹配会失败，
矫正后匹配成功——这就是现场对付斜视/远距点位牌的组合拳。

前置：先跑通基础版 quad_rectify.py，理解"找牌→矫正"再玩这个。

用法：
    python quad_match_pro.py    # 合成斜视场景，对比裸匹配 vs 矫正匹配
"""
import json
import sys

import cv2
import numpy as np

from quad_rectify import make_letter_board, make_test_scene, find_quads, rectify
from template_match import match_template

THRESH = 0.75


def detect_letters_pro(gray, tpl, letter="letter_A"):
    """Pro 管线：找四边形 → 逐个矫正 → 矫正图上做模板匹配。"""
    results = []
    for quad, area in find_quads(gray):
        front = rectify(gray, quad)  # 关键两步：找牌 + 摆正
        hits = match_template(front, tpl, scales=(0.8, 1.0, 1.2),
                              thresh=THRESH, max_targets=1)
        for h in hits:
            cx, cy = quad.mean(axis=0).astype(int)
            results.append({
                "category": letter,
                "center": [int(cx), int(cy)],
                "confidence": h["confidence"],
            })
    return results


if __name__ == "__main__":
    gray, truth = make_test_scene()
    tpl = make_letter_board("A")

    # 对比 1：裸多尺度模板匹配（对透视斜视无能为力）
    plain = match_template(gray, tpl, thresh=0.0)
    plain_best = max((h["confidence"] for h in plain), default=0.0)
    print(f"[plain] best score on skewed scene: {plain_best:.2f} (thresh {THRESH})")

    # 对比 2：矫正后匹配（Pro 管线）
    pro = detect_letters_pro(gray, tpl)
    for r in pro:
        print(json.dumps(r, ensure_ascii=False))

    ok = (len(pro) >= 1
          and max(r["confidence"] for r in pro) >= THRESH
          and plain_best < THRESH)
    print("SELF-TEST PASSED" if ok else "SELF-TEST FAILED")
    sys.exit(0 if ok else 1)
