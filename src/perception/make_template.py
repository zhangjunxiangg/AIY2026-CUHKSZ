#!/usr/bin/env python3
# 模板裁剪工具（本机用，需要 GUI）：框选 ROI 存为 templates/<name>.png，并打印 config 片段。
"""Crop a template ROI from an image (local GUI tool, cv2.selectROI).

Usage:
    python make_template.py <image> <template_name> [--out templates/] [--threshold 0.75]

Saves templates/<template_name>.png and prints the config.json snippet to add
under template_detect.templates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="source image to crop from")
    parser.add_argument("name", help="template name, e.g. letter_A, human_board")
    parser.add_argument("--out", default=str(HERE / "templates"),
                        help="output directory (default: templates/ next to this file)")
    parser.add_argument("--threshold", type=float, default=0.75,
                        help="match threshold written into the config snippet")
    args = parser.parse_args()

    bgr = cv2.imread(args.image)
    if bgr is None:
        raise SystemExit(f"cannot read image: {args.image}")
    roi = cv2.selectROI("make_template", bgr, showCrosshair=True)
    cv2.destroyAllWindows()
    x, y, w, h = (int(v) for v in roi)
    if w <= 0 or h <= 0:
        raise SystemExit("empty ROI, nothing saved")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.name}.png"
    if not cv2.imwrite(str(out_path), bgr[y:y + h, x:x + w]):
        raise SystemExit(f"failed to write {out_path}")
    print(f"[TEMPLATE] saved {out_path} ({w}x{h})")

    # 默认输出目录就用 config 约定的相对路径，自定义目录则给绝对路径
    cfg_path = f"templates/{args.name}.png" if out_dir.resolve() == (HERE / "templates").resolve() \
        else str(out_path)
    snippet = {
        "name": args.name,
        "path": cfg_path,
        "threshold": args.threshold,
        "scales": [0.6, 0.8, 1.0, 1.2, 1.4],
    }
    print("[TEMPLATE] add this to config.json -> template_detect.templates:")
    print(json.dumps(snippet, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
