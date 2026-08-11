# YOLO 检测包装：支持 ONNX / RKNN 两种后端。
# 如果模型不存在或后端不可用，检测器自动失效，不阻塞其它检测器。
# 注：ultralytics（AGPL-3.0）后端已于 2026-08-11 移除——M-Robots 社区（开放原子
# 基金会法务审查）不允许包含/引用 copyleft 依赖。请先用训练管线把 .pt 导出为
# .onnx（或 .rknn），推理侧只需 onnxruntime（MIT）。
"""YOLO detector wrapper with permissive-license backends.

Supported backends (in priority order):
  - "onnx": ONNX model (`.onnx`) via `pip install onnxruntime` (MIT)
  - "rknn": RKNN model (`.rknn`) via board-side `rknnlite2`

Config (config["yolo_detect"]):
  - enable: bool
  - model_path: path to model file (.onnx / .rknn; .pt is NOT supported)
  - backend: "auto" | "onnx" | "rknn"
  - conf_threshold: float
  - nms_threshold: float
  - input_size: int
  - class_map: {category_name: class_index}
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


class YoloDetector:
    def __init__(self, config: dict):
        cfg = config.get("yolo_detect", {})
        self.enable = bool(cfg.get("enable", False))
        self.model_path = cfg.get("model_path", "")
        self.backend = cfg.get("backend", "auto")
        self.conf = float(cfg.get("conf_threshold", 0.5))
        self.nms = float(cfg.get("nms_threshold", 0.45))
        self.input_size = int(cfg.get("input_size", 640))
        # Build reverse mapping: class_index -> category_name
        class_map = cfg.get("class_map", {})
        self.index_to_cat = {int(v): k for k, v in class_map.items()}

        self.model = None
        self.backend_name = None
        if not self.enable or not self.model_path:
            return
        p = Path(self.model_path)
        if not p.exists():
            print(f"[YOLO] model not found: {self.model_path}, detector disabled")
            return

        self._load_model(p)

    def _load_model(self, p: Path):
        if self.backend == "auto":
            suffix = p.suffix.lower()
            if suffix == ".onnx":
                self.backend = "onnx"
            elif suffix == ".rknn":
                self.backend = "rknn"
            elif suffix == ".pt":
                print("[YOLO] .pt requires ultralytics (AGPL-3.0) which is not allowed; "
                      "export to .onnx first (model.export(format='onnx')), disabled")
                return
            else:
                print(f"[YOLO] unknown model suffix {suffix}, disabled")
                return
        if self.backend == "ultralytics":
            print("[YOLO] backend 'ultralytics' removed (AGPL-3.0 not allowed); "
                  "use backend='onnx' with an exported .onnx model, disabled")
            return

        try:
            if self.backend == "onnx":
                import onnxruntime as ort
                self.model = ort.InferenceSession(str(p), providers=["CPUExecutionProvider"])
                self.backend_name = "onnx"
            elif self.backend == "rknn":
                from rknnlite2.api import RKNNLite
                self.model = RKNNLite()
                self.model.load_rknn(str(p))
                self.model.init_runtime(core_mask=RKNNLite.NPU_CORE_0)
                self.backend_name = "rknn"
            else:
                print(f"[YOLO] unknown backend {self.backend}, disabled")
        except Exception as exc:
            print(f"[YOLO] failed to load backend {self.backend}: {exc}")

    def _letterbox(self, bgr: np.ndarray) -> tuple[np.ndarray, float, float, int, int]:
        """Resize with letterboxing, return padded image and scale factors."""
        h, w = bgr.shape[:2]
        scale = self.input_size / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        top = (self.input_size - new_h) // 2
        bottom = self.input_size - new_h - top
        left = (self.input_size - new_w) // 2
        right = self.input_size - new_w - left
        padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
        return padded, scale, left, top

    def _nms(self, boxes: np.ndarray, scores: np.ndarray) -> list:
        """Standard greedy NMS."""
        if len(boxes) == 0:
            return []
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
            iou = inter / (areas[i] + areas[order[1:]] - inter)
            order = order[1:][iou < self.nms]
        return keep

    def _onnx_postprocess(self, output: np.ndarray, scale: float, pad_left: int, pad_top: int) -> list:
        """YOLOv8 ONNX output: (1, 84, N) where 84 = 4 bbox + 80 classes."""
        preds = output[0]  # (84, N)
        boxes_xywh = preds[:4, :].T
        scores = preds[4:, :].max(axis=0)
        classes = preds[4:, :].argmax(axis=0)

        mask = scores >= self.conf
        if not mask.any():
            return []
        boxes_xywh = boxes_xywh[mask]
        scores = scores[mask]
        classes = classes[mask]

        # Convert xywh -> xyxy in original image coordinates
        cx, cy, bw, bh = boxes_xywh[:, 0], boxes_xywh[:, 1], boxes_xywh[:, 2], boxes_xywh[:, 3]
        x1 = cx - bw / 2 - pad_left
        y1 = cy - bh / 2 - pad_top
        x2 = cx + bw / 2 - pad_left
        y2 = cy + bh / 2 - pad_top
        x1, y1, x2, y2 = x1 / scale, y1 / scale, x2 / scale, y2 / scale
        boxes = np.stack([x1, y1, x2, y2], axis=1)

        keep = self._nms(boxes, scores)
        results = []
        for i in keep:
            cat = self.index_to_cat.get(int(classes[i]))
            if cat is None:
                continue
            x1i, y1i, x2i, y2i = boxes[i]
            results.append({
                "category": cat,
                "center": [int((x1i + x2i) / 2), int((y1i + y2i) / 2)],
                "confidence": round(float(scores[i]), 3),
                "bbox": [int(x1i), int(y1i), int(x2i - x1i), int(y2i - y1i)],
            })
        return results

    def detect(self, bgr: np.ndarray) -> list:
        if self.model is None:
            return []

        if self.backend_name in ("onnx", "rknn"):
            try:
                padded, scale, pad_left, pad_top = self._letterbox(bgr)
                blob = padded.astype(np.float32) / 255.0
                blob = blob.transpose(2, 0, 1)[None, ...]  # (1, 3, H, W)
                if self.backend_name == "onnx":
                    output = self.model.run(None, {self.model.get_inputs()[0].name: blob})[0]
                else:
                    output = self.model.inference(inputs=[blob])[0]
                return self._onnx_postprocess(output, scale, pad_left, pad_top)
            except Exception as exc:
                print(f"[YOLO] {self.backend_name} inference failed: {exc}")
                return []

        return []
