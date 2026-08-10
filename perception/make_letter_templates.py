#!/usr/bin/env python3
"""Generate synthetic A/B/C/D letter templates for matchTemplate.

Usage:
    python make_letter_templates.py --out-dir templates --font path/to/font.ttf

If no font is provided, the script uses PIL's default bitmap font, which is only
suitable for testing. For the real venue, pass the closest matching TTF font
(e.g. Arial Bold, Source Han Sans).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def render_letter(letter: str, size: int = 128, font_path: str | None = None) -> np.ndarray:
    """Render a single letter on a white canvas and return a grayscale numpy array."""
    img = Image.new("L", (size, size), color=255)
    draw = ImageDraw.Draw(img)
    if font_path:
        font = ImageFont.truetype(font_path, int(size * 0.75))
    else:
        try:
            font = ImageFont.truetype("arialbd.ttf", int(size * 0.75))
        except OSError:
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(size * 0.75))
            except OSError:
                font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), letter, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = ((size - w) // 2 - bbox[0], (size - h) // 2 - bbox[1])
    draw.text(pos, letter, fill=0, font=font)
    return np.array(img, dtype=np.uint8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="templates", help="output directory")
    parser.add_argument("--font", help="path to a TTF font matching the venue letters")
    parser.add_argument("--size", type=int, default=128, help="template image size")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for letter in "ABCD":
        gray = render_letter(letter, size=args.size, font_path=args.font)
        # Convert to BGR for consistency with the rest of the pipeline.
        bgr = np.stack([gray, gray, gray], axis=2)
        out_path = out_dir / f"letter_{letter}.png"
        Image.fromarray(bgr).save(out_path)
        print(f"[LETTER] wrote {out_path}")

    print("[LETTER] done. Add the generated templates to config.json template_detect.templates.")


if __name__ == "__main__":
    main()
