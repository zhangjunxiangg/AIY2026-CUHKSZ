#!/usr/bin/env python3
"""Auto-generate a YOLO dataset from existing images using the classical pipeline.

The script runs the current perception pipeline (HSV + cone + template + QR + ArUco)
on every image, converts the resulting bboxes into YOLO format, and writes:

    <out_dir>/
      images/
        train/
        val/
      labels/
        train/
        val/
      data.yaml
      classes.txt

Usage:
    python collect_yolo_dataset.py --images /path/to/photos --out datasets/aimaterials

You can then train with Ultralytics:
    yolo detect train data=datasets/aimaterials/data.yaml model=yolov8n.pt epochs=100 imgsz=640
"""
from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

import cv2
import numpy as np
import yaml

from detectors import imread_safe, load_config, run_pipeline


def _map_category(category: str, class_names: list[str]) -> int | None:
    """Map a pipeline category to a YOLO class index.

    Handles ArUco/AprilTag ids: apriltag:5 -> 'apriltag', aruco:3 -> 'aruco'.
    """
    if category.startswith("apriltag:"):
        lookup = "apriltag"
    elif category.startswith("aruco:"):
        lookup = "aruco"
    else:
        lookup = category
    if lookup in class_names:
        return class_names.index(lookup)
    return None


def _bbox_to_yolo(bbox: list, img_w: int, img_h: int) -> tuple[float, float, float, float]:
    x, y, w, h = bbox
    cx = (x + w / 2.0) / img_w
    cy = (y + h / 2.0) / img_h
    nw = w / img_w
    nh = h / img_h
    return cx, cy, nw, nh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", required=True, help="directory of source images")
    parser.add_argument("--out", required=True, help="output dataset directory")
    parser.add_argument("--config", help="perception config.json path")
    parser.add_argument("--split", type=float, default=0.8, help="train ratio")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--viz", action="store_true", help="save preview images with boxes")
    parser.add_argument(
        "--classes",
        nargs="+",
        default=[
            "red_block", "green_block", "blue_block", "yellow_block",
            "red_ball", "green_ball", "blue_ball", "yellow_ball",
            "cone", "human_board", "wood_cylinder",
            "letter_A", "letter_B", "letter_C", "letter_D",
            "apriltag", "aruco",
        ],
        help="YOLO class names in order",
    )
    args = parser.parse_args()

    random.seed(args.seed)
    config = load_config(args.config)
    img_dir = Path(args.images)
    out_dir = Path(args.out)

    img_paths = sorted(p for p in img_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"))
    if not img_paths:
        print(f"[DATASET] no images found in {img_dir}")
        return 1

    random.shuffle(img_paths)
    split_idx = int(len(img_paths) * args.split)
    train_paths = img_paths[:split_idx]
    val_paths = img_paths[split_idx:]

    for split, paths in (("train", train_paths), ("val", val_paths)):
        (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)
        if args.viz:
            (out_dir / "viz" / split).mkdir(parents=True, exist_ok=True)

    total_labels = 0
    for split, paths in (("train", train_paths), ("val", val_paths)):
        for src in paths:
            bgr = imread_safe(src)
            if bgr is None:
                print(f"[DATASET] skip unreadable {src}")
                continue
            h, w = bgr.shape[:2]
            targets = run_pipeline(bgr, config)

            dst_img = out_dir / "images" / split / src.name
            shutil.copy2(src, dst_img)

            label_lines = []
            for t in targets:
                cls_id = _map_category(t["category"], args.classes)
                if cls_id is None:
                    continue
                cx, cy, nw, nh = _bbox_to_yolo(t["bbox"], w, h)
                label_lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

            dst_label = out_dir / "labels" / split / (src.stem + ".txt")
            dst_label.write_text("\n".join(label_lines), encoding="utf-8")
            total_labels += len(label_lines)

            if args.viz:
                viz = bgr.copy()
                for t in targets:
                    cls_id = _map_category(t["category"], args.classes)
                    if cls_id is None:
                        continue
                    x, y, bw, bh = t["bbox"]
                    cv2.rectangle(viz, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
                    cv2.putText(viz, args.classes[cls_id], (x, y - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                cv2.imwrite(str(out_dir / "viz" / split / src.name), viz)

    (out_dir / "classes.txt").write_text("\n".join(args.classes), encoding="utf-8")
    data_yaml = {
        "path": str(out_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "nc": len(args.classes),
        "names": {i: name for i, name in enumerate(args.classes)},
    }
    with (out_dir / "data.yaml").open("w", encoding="utf-8") as f:
        yaml.dump(data_yaml, f, default_flow_style=False, allow_unicode=True)

    print(f"[DATASET] train={len(train_paths)} val={len(val_paths)} total labels={total_labels}")
    print(f"[DATASET] wrote {out_dir / 'data.yaml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
