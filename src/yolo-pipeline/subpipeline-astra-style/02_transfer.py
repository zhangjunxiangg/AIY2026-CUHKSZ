"""sub 02_transfer —— 把手机图逐张转换为 Astra 风格。

变换链（只动光度/模糊，不动几何）：
  1. 缩放到 640x480（INTER_AREA，归一化标签坐标不受影响）
  2. 自适应高斯模糊：二分 sigma 使拉普拉斯方差降到 Astra 水平
  3. 通道-wise 均值/标准差匹配（Reinhard，BGR 空间）
  4. 平坦区噪声补足（方差可加性，模拟 Astra 传感器底噪）
  5. JPEG quality=85 重编码（模拟 UVC mjpeg 压缩感）
标签处理：源图若有同名 .txt 则原样复制（坐标不变）。
门禁：
  - 前驱 sub 01 PASS
  - 每张输出可解码、尺寸 640x480
  - 坏图排除比例 <= MAX_EXCLUDE_FRACTION
产出：../dataset_transformed/*.jpg (+.txt)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import util_paths
from util_gate import run_step

SIGMA_MAX = 3.0
JPEG_QUALITY = 85


def imread_safe(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)


def lap_var(img):
    return cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()


def match_blur(img, target_var):
    """二分 sigma，使模糊后拉普拉斯方差 <= target_var（不超过）。"""
    if lap_var(img) <= target_var:
        return img, 0.0
    lo, hi = 0.2, SIGMA_MAX
    best = img
    for _ in range(8):
        mid = (lo + hi) / 2
        blurred = cv2.GaussianBlur(img, (0, 0), mid)
        if lap_var(blurred) > target_var:
            lo = mid
        else:
            hi = mid
            best = blurred
    return best, hi


def match_color(img, dst_mean, dst_std):
    src = img.astype(np.float32)
    m = src.reshape(-1, 3).mean(axis=0)
    s = src.reshape(-1, 3).std(axis=0) + 1e-6
    out = (src - m) * (np.array(dst_std) / s) + np.array(dst_mean)
    return np.clip(out, 0, 255).astype(np.uint8)


def flat_noise_std(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    residual = gray - cv2.GaussianBlur(gray, (0, 0), 2)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.abs(gx) + np.abs(gy)
    return float(residual[mag <= np.percentile(mag, 20)].std())


def match_noise(img, target_std, rng):
    """补足平坦区噪声到 target_std（方差可加性）。"""
    cur = flat_noise_std(img)
    if cur >= target_std:
        return img, 0.0
    add = float(np.sqrt(target_std ** 2 - cur ** 2))
    noise = rng.normal(0, add, img.shape).astype(np.float32)
    out = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    return out, add


def main(step):
    step.gate_predecessor("01_analyze_astra")
    style = json.loads((util_paths.LOGS / "01_analyze_astra" / "astra_style.json")
                       .read_text(encoding="utf-8"))
    target_var = style["laplacian_var"]
    step.log(f"目标模糊度 lap_var={target_var:.1f}, "
             f"BGR均值={[round(v,1) for v in style['bgr_mean']]}")

    src_dir = util_paths.DATASET_RAW
    imgs = sorted(p for p in src_dir.glob("*.jpg")) + sorted(src_dir.glob("*.png"))
    step.gate(len(imgs) > 0, f"{src_dir} 中存在图片（实测 {len(imgs)}）")

    out_dir = util_paths.TRANSFORMED
    if out_dir.exists():
        for f in out_dir.glob("*"):
            f.unlink()
    out_dir.mkdir(exist_ok=True)

    ok, excluded, sigmas, noises = 0, [], [], []
    rng = np.random.default_rng(42)
    t0 = step.now()
    for p in imgs:
        try:
            img = imread_safe(p)
            if img is None:
                raise ValueError("decode None")
            img = cv2.resize(img, (640, 480), interpolation=cv2.INTER_AREA)
            img, sigma = match_blur(img, target_var)
            img = match_color(img, style["bgr_mean"], style["bgr_std"])
            noise_add_total = 0.0
            # JPEG 重编码会磨掉部分噪声，最多补两轮并按解码结果校准
            for _ in range(2):
                img, noise_add = match_noise(img, style["noise_std"], rng)
                noise_add_total += noise_add
                encoded = cv2.imencode(".jpg", img,
                                       [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])[1]
                decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                if flat_noise_std(decoded) >= style["noise_std"] * 0.95:
                    break
                img = decoded
            sigmas.append(sigma)
            noises.append(noise_add_total)
            dst = out_dir / (p.stem + ".jpg")
            encoded.tofile(str(dst))
            lab = p.with_suffix(".txt")
            if lab.exists():
                (out_dir / lab.name).write_bytes(lab.read_bytes())
            # 输出回读验证
            chk = imread_safe(dst)
            if chk is None or chk.shape[:2] != (480, 640):
                raise ValueError("output decode/size check failed")
            ok += 1
        except Exception as e:
            excluded.append({"file": p.name, "reason": str(e)})
            step.warn(f"[EXCLUDE] {p.name}: {e}")
    step.time_phase("transfer_all", step.now() - t0)

    loss = len(excluded) / max(len(imgs), 1)
    step.gate(loss <= util_paths.MAX_EXCLUDE_FRACTION,
              f"坏图比例 {loss:.1%} <= 预算 {util_paths.MAX_EXCLUDE_FRACTION:.0%}")
    step.gate(ok == len(imgs) - len(excluded),
              f"输出数量 {ok} == 输入 {len(imgs)} - 排除 {len(excluded)}")

    stats = {"ok": ok, "excluded": excluded,
             "sigma_mean": float(np.mean(sigmas)), "sigma_max": float(np.max(sigmas)),
             "noise_add_mean": float(np.mean(noises)),
             "target_lap_var": target_var}
    (step.dir / "transfer_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    step.log(f"转换完成 {ok} 张 -> {out_dir}，sigma 均值 {stats['sigma_mean']:.2f}，"
             f"噪声补足均值 {stats['noise_add_mean']:.2f}")


if __name__ == "__main__":
    run_step("02_transfer", main)
