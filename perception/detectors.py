# 纯算法库：颜色/形状、路锥、模板、QR 检测。不 import rospy，本机与板端通用（板端 Python 3.11 + cv2 + numpy）。
"""Pure perception algorithm library (no ROS dependency).

Every detector takes a BGR image plus the loaded config dict and returns a
list of target dicts:
    {"category": str, "center": [x, y], "confidence": 0~1, "bbox": [x, y, w, h]}
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent


def load_config(path=None):
    """加载 config.json；相对路径先按 cwd 解析，找不到再按 perception/ 目录解析。"""
    p = Path(path) if path else HERE / "config.json"
    if not p.is_absolute() and not p.exists():
        p = HERE / p
    return json.loads(p.read_text(encoding="utf-8"))


def imread_safe(path, flags=cv2.IMREAD_COLOR):
    """Unicode 路径兼容的 imread：Windows 中文路径下 cv2.imread 直接读会失败，
    改用 np.fromfile + imdecode；Linux/板端行为一致。"""
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)


def preprocess(bgr, config):
    """可选预处理：白平衡 + gamma 校正 + LAB 空间 CLAHE，用于抑制过曝/增强颜色对比。

    配置项（config["preprocess"]）：
      - enable: bool，默认 false（保持原有行为不变）
      - white_balance: bool，gray-world 白平衡，用于修正色偏
      - gamma: float，<1 压暗高光、>1 提亮暗部，默认 1.0
      - clahe_clip: float，CLAHE clip limit，默认 2.0；<=0 表示不做 CLAHE
      - clahe_grid: int，CLAHE tile grid size，默认 8
    """
    cfg = config.get("preprocess", {})
    if not cfg.get("enable", False):
        return bgr

    out = bgr.copy()

    if cfg.get("white_balance", False):
        # 简单 gray-world 白平衡：让 B/G/R 三通道均值趋于一致
        out_float = out.astype(np.float32)
        means = out_float.mean(axis=(0, 1))
        avg = means.mean()
        scale = avg / (means + 1e-6)
        out_float *= scale[None, None, :]
        out = np.clip(out_float, 0, 255).astype(np.uint8)

    gamma = float(cfg.get("gamma", 1.0))
    if gamma > 0 and gamma != 1.0:
        inv_gamma = 1.0 / gamma
        table = (np.arange(256, dtype=np.float32) / 255.0) ** inv_gamma * 255.0
        out = cv2.LUT(out, table.clip(0, 255).astype(np.uint8))

    clahe_clip = float(cfg.get("clahe_clip", 2.0))
    clahe_grid = int(cfg.get("clahe_grid", 8))
    if clahe_clip > 0 and clahe_grid > 0:
        lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(clahe_grid, clahe_grid))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        out = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # 场地多边形 mask：只保留场地中央，屏蔽两侧挡板/背景
    mask_cfg = config.get("field_mask", {})
    if mask_cfg.get("enable", False):
        points = np.array(mask_cfg.get("points", []), dtype=np.int32)
        if points.size > 0:
            h, w = out.shape[:2]
            # 支持相对坐标 (0~1) 或绝对像素坐标
            pts = points.copy().astype(np.float32)
            if pts.max() <= 1.0:
                pts[:, 0] *= w
                pts[:, 1] *= h
            pts = pts.astype(np.int32)
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask, [pts], 255)
            out = cv2.bitwise_and(out, out, mask=mask)

    return out


def _hsv_mask(hsv, ranges):
    mask = np.zeros(hsv.shape[:2], np.uint8)
    for lo, hi in ranges:
        mask |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    return mask


def _center_of(contour):
    m = cv2.moments(contour)
    if m["m00"] <= 0:
        x, y, w, h = cv2.boundingRect(contour)
        return x + w // 2, y + h // 2
    return int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"])


def detect_color_objects(bgr, config):
    """HSV 多颜色 + 形状分类。

    ring：RETR_CCOMP 两级轮廓，外轮廓有子轮廓（内孔）即为环。
    其余按填充率 + 高宽比：立式(高宽比>=cylinder_aspect_min) -> cylinder；
    近方形且填充率 < ball_fill_max -> ball（圆填充率≈0.79）；否则 -> block（≈1.0）。
    """
    cfg = config.get("color_detect", {})
    hsv_table = config.get("hsv_colors", {})
    colors = cfg.get("colors") or list(hsv_table.keys())
    min_area = float(cfg.get("min_area", 400))
    max_area = float(cfg.get("max_area", 1e9))
    open_k = int(cfg.get("morph_open_ksize", 5))
    close_k = int(cfg.get("morph_close_ksize", 0))
    ball_fill_max = float(cfg.get("ball_fill_max", 0.9))
    square_tol = float(cfg.get("square_aspect_tol", 0.15))
    cyl_aspect_min = float(cfg.get("cylinder_aspect_min", 1.2))
    ring_enable = bool(cfg.get("ring_enable", True))
    ring_min_area = float(cfg.get("ring_min_area", 300))

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    kernel = np.ones((open_k, open_k), np.uint8)
    results = []
    for name in colors:
        ranges = hsv_table.get(name)
        if not ranges:
            continue
        mask = _hsv_mask(hsv, ranges)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        if close_k > 0:
            close_kernel = np.ones((close_k, close_k), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:
            continue
        hierarchy = hierarchy[0]  # 每条: [Next, Previous, First_Child, Parent]
        for i, c in enumerate(contours):
            if hierarchy[i][3] >= 0:
                continue  # 内孔轮廓本身不作为目标输出
            area = cv2.contourArea(c)
            if area < min_area or area > max_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            cx, cy = _center_of(c)
            has_hole = hierarchy[i][2] >= 0
            if ring_enable and has_hole and area >= ring_min_area:
                category, confidence = f"{name}_ring", 1.0
            else:
                fill = area / float(w * h)
                aspect = h / float(w)
                if aspect >= cyl_aspect_min:
                    shape, confidence = "cylinder", min(1.0, aspect / 2.0)
                elif abs(w - h) <= square_tol * max(w, h) and fill < ball_fill_max:
                    shape, confidence = "ball", fill
                else:
                    shape, confidence = "block", fill
                category = f"{name}_{shape}"
            results.append({
                "category": category,
                "center": [cx, cy],
                "confidence": round(float(confidence), 2),
                "bbox": [int(x), int(y), int(w), int(h)],
            })
    return results


def detect_cones(bgr, config):
    """路锥：专用颜色段 + 立式过滤(高宽比 > min_aspect) + 纵向 MORPH_CLOSE 桥接白色条纹。"""
    cfg = config.get("cone_detect", {})
    color = cfg.get("color", "blue")
    ranges = config.get("hsv_colors", {}).get(color)
    if not ranges:
        return []
    min_area = float(cfg.get("min_area", 400))
    min_aspect = float(cfg.get("min_aspect", 1.2))
    ck = [int(v) for v in cfg.get("morph_close_ksize", [25, 9])]

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = _hsv_mask(hsv, ranges)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones(tuple(ck), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    results = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(c)
        aspect = h / float(w)
        if aspect < min_aspect:  # 立式过滤：方块/球（≈1.0）在此被滤掉
            continue
        cx, cy = _center_of(c)
        results.append({
            "category": "cone",
            "center": [cx, cy],
            "confidence": round(min(1.0, aspect / 2.0), 2),
            "bbox": [int(x), int(y), int(w), int(h)],
        })
    return results


def _match_one_template(gray, tpl, name, scales, thresh, max_targets):
    """多尺度 matchTemplate + 命中抹除，找最多 max_targets 个目标。"""
    work = gray.copy()
    out = []
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
        out.append({
            "category": name,
            "center": [int(x + w // 2), int(y + h // 2)],
            "confidence": round(float(score), 2),
            "bbox": [int(x), int(y), int(w), int(h)],
        })
        cv2.rectangle(work, (x, y), (x + w, y + h), 235, -1)  # 抹掉已找到的，继续找下一个
    return out


def detect_templates(bgr, config):
    """多尺度模板匹配。模板从 config 指定的文件路径加载（相对路径按 perception/ 解析）。"""
    cfg = config.get("template_detect", {})
    max_targets = int(cfg.get("max_targets_per_template", 3))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    results = []
    for entry in cfg.get("templates", []):
        tpl_path = Path(entry["path"])
        if not tpl_path.is_absolute():
            tpl_path = HERE / tpl_path
        tpl = imread_safe(tpl_path, cv2.IMREAD_GRAYSCALE)
        if tpl is None:
            continue  # 模板文件缺失不致命，跳过
        scales = entry.get("scales", [0.6, 0.8, 1.0, 1.2, 1.4])
        thresh = float(entry.get("threshold", 0.75))
        name = entry.get("name", tpl_path.stem)
        results.extend(_match_one_template(gray, tpl, name, scales, thresh, max_targets))
    return results


def detect_qr(bgr, config):
    """QR 检测 + 解码，多尺度放大重试（远处小目标直接检测常失败）。category = qr:<内容>。"""
    cfg = config.get("qr_detect", {})
    scales = cfg.get("scales", [1.0, 2.0, 3.0])
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
            pts_orig = pts / float(s)  # 坐标换算回原图
            cx, cy = pts_orig.mean(axis=0).astype(int)
            x, y, w, h = cv2.boundingRect(pts_orig.astype(np.float32))
            results.append({
                "category": f"qr:{text}",
                "center": [int(cx), int(cy)],
                "confidence": 1.0,
                "bbox": [int(x), int(y), int(w), int(h)],
            })
        if results:
            return results
    return []


def _aruco_detector(dict_name: str):
    """Return an OpenCV ArUco detector compatible with both 4.7+ (new API)
    and older versions. If the dictionary is unavailable, return None."""
    try:
        attr = getattr(cv2.aruco, dict_name)
    except AttributeError:
        return None
    try:
        dictionary = cv2.aruco.getPredefinedDictionary(attr)
        parameters = cv2.aruco.DetectorParameters()
        return cv2.aruco.ArucoDetector(dictionary, parameters)
    except Exception:
        # Older OpenCV API: dictionary object itself has detectMarkers.
        try:
            dictionary = cv2.aruco.Dictionary_get(attr)
            return lambda bgr, d=dictionary: cv2.aruco.detectMarkers(bgr, d)
        except Exception:
            return None


def detect_aruco(bgr, config):
    """ArUco / AprilTag fiducial marker detection.

    Config (config["aruco_detect"]):
      - enable: bool
      - dictionaries: list of OpenCV dictionary names, e.g.
        ["DICT_APRILTAG_36h11", "DICT_6X6_250"]
      - marker_length_m: optional real marker size (for downstream mono depth)

    Output category: "apriltag:<id>" for AprilTag dictionaries,
    otherwise "aruco:<id>".
    """
    cfg = config.get("aruco_detect", {})
    if not cfg.get("enable", False):
        return []

    seen_ids = set()
    results = []
    marker_len = cfg.get("marker_length_m")
    for dict_name in cfg.get("dictionaries", []):
        detector = _aruco_detector(dict_name)
        if detector is None:
            continue
        try:
            if callable(getattr(detector, "detectMarkers", None)):
                corners, ids, _ = detector.detectMarkers(bgr)
            else:
                corners, ids, _ = detector(bgr)
        except Exception:
            continue
        if ids is None:
            continue

        is_april = "APRILTAG" in dict_name.upper()
        for c, mid in zip(corners, ids.ravel()):
            if (dict_name, int(mid)) in seen_ids:
                continue
            seen_ids.add((dict_name, int(mid)))
            pts = c.reshape(-1, 2)
            cx, cy = pts.mean(axis=0).astype(int)
            x, y, w, h = cv2.boundingRect(pts.astype(np.float32))
            t = {
                "category": f"apriltag:{int(mid)}" if is_april else f"aruco:{int(mid)}",
                "center": [int(cx), int(cy)],
                "confidence": 0.95,
                "bbox": [int(x), int(y), int(w), int(h)],
            }
            if marker_len is not None:
                t["marker_length_m"] = float(marker_len)
            results.append(t)
    return results


_yolo_detector = None


def _get_yolo_detector(config):
    """Lazy singleton for the optional YOLO detector."""
    global _yolo_detector
    if _yolo_detector is None and config.get("yolo_detect", {}).get("enable", False):
        from yolo_detect import YoloDetector
        _yolo_detector = YoloDetector(config)
    return _yolo_detector


def run_pipeline(bgr, config):
    """总入口：按 config 的 enable 开关依次调用各检测器并合并结果。"""
    bgr = preprocess(bgr, config)
    targets = []
    if config.get("color_detect", {}).get("enable", True):
        targets.extend(detect_color_objects(bgr, config))
    if config.get("cone_detect", {}).get("enable", True):
        targets.extend(detect_cones(bgr, config))
    if config.get("template_detect", {}).get("enable", True):
        targets.extend(detect_templates(bgr, config))
    if config.get("qr_detect", {}).get("enable", True):
        targets.extend(detect_qr(bgr, config))
    if config.get("aruco_detect", {}).get("enable", False):
        targets.extend(detect_aruco(bgr, config))
    yolo = _get_yolo_detector(config)
    if yolo is not None:
        targets.extend(yolo.detect(bgr))

    roi_cfg = config.get("roi", {})
    if roi_cfg.get("enable", False):
        y_min = int(roi_cfg.get("y_min", 0))
        targets = [t for t in targets if t["center"][1] >= y_min]

    return targets
