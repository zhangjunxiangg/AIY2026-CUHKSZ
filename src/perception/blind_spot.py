# 盲区处理策略：Astra 深度失效时，用已知物料尺寸做粗略单目测深，并标记盲区目标。
"""Blind-spot handling for low/close objects that the Astra depth camera cannot see.

Strategy (in priority order):
1. Use the depth value attached by the perception node if it is valid.
2. If depth is missing/invalid and the object category has a known real size
   in config (`blind_spot.mono_size`), estimate depth from the bbox size.
3. Otherwise mark the target as having no usable depth; the caller can then
   fall back to an auxiliary camera or dead-reckoning.
"""
from __future__ import annotations

from geometry3d import CameraIntrinsics


def is_depth_valid(depth_mm, min_mm: float = 600, max_mm: float = 8000) -> bool:
    """Check whether a raw depth value (mm) is usable."""
    if depth_mm is None:
        return False
    return min_mm <= float(depth_mm) <= max_mm


def estimate_target_depth(target: dict, intrinsics: CameraIntrinsics, config: dict) -> tuple[float | None, str]:
    """Return (depth_m, depth_source) for a perception target.

    depth_source is one of: "camera", "mono", "none".
    """
    cfg = config.get("blind_spot", {})
    min_mm = float(cfg.get("min_valid_mm", 600))
    max_mm = float(cfg.get("max_valid_mm", 8000))

    raw = target.get("depth_mm")
    if is_depth_valid(raw, min_mm, max_mm):
        return float(raw) / 1000.0, "camera"

    category = target.get("category", "")
    size_cfg = cfg.get("mono_size", {}).get(category)
    if size_cfg:
        depth_m = intrinsics.mono_depth_from_bbox(
            target.get("bbox", [0, 0, 0, 0]),
            real_width_m=size_cfg.get("width_m"),
            real_height_m=size_cfg.get("height_m"),
        )
        if depth_m is not None:
            return depth_m, "mono"

    return None, "none"


def annotate_blind_spot(targets: list, config: dict) -> list:
    """Add a `blind_spot` flag to targets whose depth is invalid and that lie
    below the configured image horizon (i.e. likely in the Astra near blind zone).
    """
    cfg = config.get("blind_spot", {})
    if not cfg.get("enable", False):
        return targets
    horizon = int(cfg.get("horizon_y", 320))
    min_mm = float(cfg.get("min_valid_mm", 600))
    max_mm = float(cfg.get("max_valid_mm", 8000))
    for t in targets:
        cx, cy = t.get("center", [0, 0])
        t["blind_spot"] = (cy >= horizon) and not is_depth_valid(t.get("depth_mm"), min_mm, max_mm)
    return targets
