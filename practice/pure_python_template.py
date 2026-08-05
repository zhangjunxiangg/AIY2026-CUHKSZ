"""纯 Python 兜底模板匹配：零依赖标准库 NCC（归一化互相关）。

为什么要有它：点位标识已确认是**字母牌**（不是二维码），模板匹配是巡检方向的
主线算法；而板端 pip 装不了 cv2/numpy——如果预装没有，就得靠这个兜底。

性能注意：纯 Python 只跑得动小图。现场用法 = 先降采样（如 160×120 以内）
+ 减少尺度数 + 加大搜索步长。本脚本自测场景 80×60，毫秒~秒级。

用法：
    python pure_python_template.py    # 自测：合成字母牌 A/B，互相找
"""
import json
import sys

# 5x7 点阵字模（自测用；现场换成相机实拍的字母牌切片）
FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "11110", "10001", "10001", "10001", "11110"],
}


def render_letter(ch, scale=2, on=30, off=235):
    """把点阵字母渲染成灰度图（返回一维 list + 宽高）。"""
    rows = FONT[ch]
    h, w = len(rows) * scale, len(rows[0]) * scale
    img = [off] * (w * h)
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c == "1":
                for dy in range(scale):
                    for dx in range(scale):
                        img[(y * scale + dy) * w + x * scale + dx] = on
    return img, w, h


def resize_gray(src, sw, sh, dw, dh):
    """最近邻缩放（兜底只求简单快）。"""
    out = [0] * (dw * dh)
    for y in range(dh):
        sy = y * sh // dh
        for x in range(dw):
            out[y * dw + x] = src[sy * sw + x * sw // dw]
    return out


def ncc_at(img, iw, tpl, tw, th, ox, oy):
    """模板在 (ox,oy) 处的归一化互相关系数，越接近 1 越像。"""
    n = tw * th
    sum_t = sum(tpl)
    sum_t2 = sum(v * v for v in tpl)
    sum_i = sum_i2 = sum_it = 0
    for y in range(th):
        base = (oy + y) * iw + ox
        tbase = y * tw
        for x in range(tw):
            v = img[base + x]
            t = tpl[tbase + x]
            sum_i += v
            sum_i2 += v * v
            sum_it += v * t
    num = n * sum_it - sum_i * sum_t
    den_i = n * sum_i2 - sum_i * sum_i
    den_t = n * sum_t2 - sum_t * sum_t
    if den_i <= 0 or den_t <= 0:
        return -1.0
    return num / ((den_i * den_t) ** 0.5)


def match_template(gray, w, h, tpl, tw, th, scales=(0.75, 1.0, 1.25), thresh=0.7, step=2):
    """多尺度 NCC 模板匹配，返回最佳匹配（步长 step 提速）。"""
    best = None
    for s in scales:
        dw, dh = max(4, int(tw * s)), max(4, int(th * s))
        t = tpl if (dw, dh) == (tw, th) else resize_gray(tpl, tw, th, dw, dh)
        if dw > w or dh > h:
            continue
        for oy in range(0, h - dh + 1, step):
            for ox in range(0, w - dw + 1, step):
                score = ncc_at(gray, w, t, dw, dh, ox, oy)
                if best is None or score > best[0]:
                    best = (score, ox, oy, dw, dh)
    if best and best[0] >= thresh:
        score, x, y, dw, dh = best
        return [{"category": "letter_sign", "center": [x + dw // 2, y + dh // 2],
                 "confidence": round(score, 2)}]
    return []


def make_scene():
    """80x60 场景：A 放在 (10,8)，B 放在 (50,32)。"""
    w, h = 80, 60
    img = [235] * (w * h)
    for ch, ox, oy in [("A", 10, 8), ("B", 50, 32)]:
        t, tw, th = render_letter(ch)
        for y in range(th):
            for x in range(tw):
                img[(oy + y) * w + ox + x] = t[y * tw + x]
    return img, w, h


if __name__ == "__main__":
    scene, w, h = make_scene()
    ok = True
    # 用 A 的模板找 A：应命中 (10,8) 附近，中心约 (15,15)
    tpl_a, tw, th = render_letter("A")
    for r in match_template(scene, w, h, tpl_a, tw, th):
        print(json.dumps(r, ensure_ascii=False))
        cx, cy = r["center"]
        if abs(cx - 15) > 4 or abs(cy - 15) > 4:
            print(f"FAIL: A center ({cx},{cy}) too far from (15,15)")
            ok = False
    else:
        pass
    print("SELF-TEST PASSED" if ok else "SELF-TEST FAILED")
    sys.exit(0 if ok else 1)
