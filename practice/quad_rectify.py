"""四边形检测 + 透视矫正（基础版）：从画面里找出字母牌，矫正成正面图。

对应升级方向①（借鉴 ArUco 检测管线）：先找牌（四边形）→ 透视矫正 →（后续再匹配）。
本脚本只做前两步，不接模板匹配——融合 Pro 版见 quad_match_pro.py。
实战要点：现场字母牌斜视/远距时，先做这一步把牌"摆正"，识别率会高得多。

用法：
    python quad_rectify.py            # 生成斜视字母牌合成场景 quad_scene.png 并自测
    python quad_rectify.py 某张图.jpg  # 处理真实图片（阈值参数需按现场调）
"""
import json
import sys

import cv2
import numpy as np


def make_letter_board(letter="A", w=200, h=280):
    """造一块'字母牌'：白底黑字。"""
    img = np.full((h, w), 255, np.uint8)
    cv2.putText(img, letter, (w // 4, int(h * 0.72)),
                cv2.FONT_HERSHEY_SIMPLEX, 5, 0, 18, cv2.LINE_AA)
    return img


def make_test_scene():
    """合成场景：字母牌经透视变换斜放在灰色背景里（模拟斜视角度的现场）。"""
    board = make_letter_board("A")
    src = np.float32([[0, 0], [200, 0], [200, 280], [0, 280]])
    dst = np.float32([[250, 70], [440, 170], [340, 420], [130, 310]])  # 强斜视四角（真值）
    M = cv2.getPerspectiveTransform(src, dst)
    scene = cv2.warpPerspective(board, M, (640, 480), borderValue=200)
    scene = cv2.GaussianBlur(scene, (3, 3), 0)
    cv2.imwrite("quad_scene.png", cv2.cvtColor(scene, cv2.COLOR_GRAY2BGR))
    return scene, dst


def order_points(pts):
    """四点排序为：左上、右上、右下、左下。"""
    pts = pts.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)],
                     pts[np.argmax(s)], pts[np.argmax(d)]], np.float32)


def find_quads(gray, min_area=3000, eps_ratio=0.03, thresh=220):
    """亮度阈值分离亮牌 → 轮廓 → approxPolyDP 筛四边形。

    现场适配提示：字母牌若是白底，thresh 按"背景与牌面的中间值"调；
    若牌面颜色特殊，可换颜色阈值或 Canny 边缘找轮廓。
    """
    _, mask = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    quads = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, eps_ratio * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quads.append((order_points(approx), area))
    return quads


def rectify(gray, quad, out_w=200, out_h=280):
    """按四边形四角做透视变换，输出正面图。"""
    dst = np.float32([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]])
    M = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(gray, M, (out_w, out_h))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        bgr = cv2.imread(sys.argv[1])
        assert bgr is not None, f"读不到图片: {sys.argv[1]}"
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        truth = None
    else:
        gray, truth = make_test_scene()
        print("已生成合成测试图 quad_scene.png")

    quads = find_quads(gray)
    print(f"quads found: {len(quads)}")
    ok = len(quads) >= 1
    for i, (quad, area) in enumerate(quads):
        cv2.imwrite(f"quad_rectified_{i}.png", rectify(gray, quad))
        print(json.dumps({"quad": i, "corners": quad.astype(int).tolist(), "area": int(area)}))
        if truth is not None:
            err = float(np.abs(quad - truth).max())
            print(f"corner error vs ground truth: {err:.1f}px (tolerance 12)")
            ok = ok and err <= 12
    print("SELF-TEST PASSED" if ok else "SELF-TEST FAILED")
    sys.exit(0 if ok else 1)
