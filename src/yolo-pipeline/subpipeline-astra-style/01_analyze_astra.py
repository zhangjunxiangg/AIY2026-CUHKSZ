"""sub 01_analyze_astra —— 从 Astra 实拍样图提取风格统计量。

输入：父管线 util_paths.ASTRA_SAMPLES（一张或多张 Astra 实拍图）
门禁：
  - 样图存在、可解码、尺寸为 640x480（部署分辨率）
  - 统计量合法：通道均值在 [0,255]、拉普拉斯方差 > 0
产出：astra_style.json（BGR 均值/标准差、拉普拉斯方差、噪声估计）
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


def imread_safe(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)


def main(step):
    samples = [p for p in util_paths.ASTRA_SAMPLES if p.exists()]
    step.gate(len(samples) > 0,
              f"Astra 样图存在（{[str(p) for p in util_paths.ASTRA_SAMPLES]}）")

    means, stds, lap_vars, noises = [], [], [], []
    for p in samples:
        img = imread_safe(p)
        step.gate(img is not None, f"样图可解码（{p.name}）")
        step.gate(img.shape[:2] == (480, 640),
                  f"样图尺寸 {img.shape[1]}x{img.shape[0]} == 640x480（{p.name}）")
        m = img.reshape(-1, 3).mean(axis=0)
        s = img.reshape(-1, 3).std(axis=0)
        lap = cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        # 平坦区噪声估计：gray - gaussian(gray) 在梯度最小 20% 像素上的标准差
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        residual = gray - cv2.GaussianBlur(gray, (0, 0), 2)
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        mag = np.abs(gx) + np.abs(gy)
        noise = float(residual[mag <= np.percentile(mag, 20)].std())
        means.append(m)
        stds.append(s)
        lap_vars.append(lap)
        noises.append(noise)
        step.log(f"{p.name}: BGR均值={m.round(1).tolist()} 标准差={s.round(1).tolist()} "
                 f"拉普拉斯方差={lap:.1f} 平坦区噪声std={noise:.2f}")

    style = {
        "bgr_mean": np.mean(means, axis=0).tolist(),
        "bgr_std": np.mean(stds, axis=0).tolist(),
        "laplacian_var": float(np.mean(lap_vars)),
        "noise_std": float(np.mean(noises)),
        "sources": [p.name for p in samples],
    }
    step.gate(all(0 <= v <= 255 for v in style["bgr_mean"]), "通道均值在 [0,255]")
    step.gate(style["laplacian_var"] > 0, "拉普拉斯方差 > 0")

    out = step.dir / "astra_style.json"
    out.write_text(json.dumps(style, ensure_ascii=False, indent=1), encoding="utf-8")
    step.log(f"风格统计写入 {out}")


if __name__ == "__main__":
    run_step("01_analyze_astra", main)
