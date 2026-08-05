"""二维码 / 点位识别练习：对应赛场字母点位标识。

检测+解码用 OpenCV 自带 cv2.QRCodeDetector —— 不依赖 pyzbar/zbar DLL。
生成二维码用 cv2.QRCodeEncoder（练习自测用，同样不需要第三方库）。

用法：
    python qr_detect.py            # 生成合成场景 qr_scene.png（含 A/B 两个点位码）并自测
    python qr_detect.py 某张图.jpg  # 识别真实图片
"""
import json
import sys

import cv2
import numpy as np


def detect_qr(bgr, scales=(1.0, 2.0, 3.0)):
    """输入 BGR 图像，输出点位列表。

    注意：小二维码在大图里直接检测经常定位失败，多尺度放大重试
    是现场实用技巧（远处点位码 = 小目标）。
    """
    det = cv2.QRCodeDetector()
    for s in scales:
        img = bgr if s == 1.0 else cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
        ok, decoded_info, points, _ = det.detectAndDecodeMulti(img)
        if not ok or points is None:
            continue
        results = []
        for text, pts in zip(decoded_info, points):
            if not text:  # 检测到但没解码成功
                continue
            cx, cy = (pts.mean(axis=0) / s).astype(int)  # 坐标换算回原图
            results.append({
                "category": f"point_{text}",
                "center": [int(cx), int(cy)],
                "confidence": 1.0,
            })
        if results:
            return results
    return []


def make_qr_image(text, size=160):
    qr = cv2.QRCodeEncoder_create().encode(text)  # 单通道 0/255 小图
    return cv2.resize(qr, (size, size), interpolation=cv2.INTER_NEAREST)


def make_test_scene():
    img = np.full((480, 640), 245, np.uint8)
    for x, y, label in [(80, 90, "A"), (360, 240, "B")]:
        qr = make_qr_image(label)
        # 二维码四周要有安静区（空白边），否则检测不到
        img[y - 40:y + 200, x - 40:x + 200] = 245
        img[y:y + 160, x:x + 160] = qr
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        bgr = cv2.imread(sys.argv[1])
        assert bgr is not None, f"读不到图片: {sys.argv[1]}"
    else:
        bgr = make_test_scene()
        cv2.imwrite("qr_scene.png", bgr)
        print("已生成合成测试图 qr_scene.png")
    for r in detect_qr(bgr):
        print(json.dumps(r, ensure_ascii=False))
