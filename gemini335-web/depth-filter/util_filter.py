"""Depth filter chain + metrics, shared by offline eval and the web streamer.

Depth convention: uint16 millimetres, 0 = invalid. Never fabricate large-area
valid depth; small holes may persist from the temporal accumulator for a few
frames, big holes stay black.

Chain (per frame):
  1. despeckle   - 3x3 morphological open on the valid mask (fast; removes
                   isolated speckle clusters)
  2. masked median - 5x5 median with invalid sorted high (edge-preserving,
                     kills salt-and-pepper depth noise)
  3. temporal EMA with hysteresis motion gating - pixels stay in the smooth
                     path unless their depth stays >= gate_mm away from the
                     accumulator for snap_frames consecutive frames (real
                     motion snaps, noise spikes do not); invalid pixels hold
                     their last value for hold_frames then drop to invalid

Tuned on RK3588S (see run1 metrics): alpha 0.15, gate 250mm, snap after 3
consecutive out-of-gate frames. p95 <= 15 ms/frame budget.
"""

import os

import cv2
import numpy as np

DEPTH_MAX_MM = 5000.0


class DepthFilter:
    def __init__(self,
                 alpha=float(os.environ.get("DF_ALPHA", "0.15")),
                 gate_mm=float(os.environ.get("DF_GATE_MM", "250")),
                 hold_frames=int(os.environ.get("DF_HOLD_FRAMES", "5")),
                 snap_frames=int(os.environ.get("DF_SNAP_FRAMES", "3")),
                 median_ksize=int(os.environ.get("DF_MEDIAN_KSIZE", "5"))):
        self.alpha = alpha
        self.gate_mm = gate_mm
        self.hold_frames = hold_frames
        self.snap_frames = snap_frames
        self.median_ksize = median_ksize
        self._kernel = np.ones((3, 3), np.uint8)
        self.acc = None
        self.hold = None
        self.oog_count = None

    def process(self, depth):
        # 1. despeckle via morphological open on the validity mask
        opened = cv2.morphologyEx((depth > 0).astype(np.uint8),
                                  cv2.MORPH_OPEN, self._kernel)
        x = depth * opened
        # 2. masked median: invalid sorts high, then mapped back to invalid
        big = np.where(x > 0, x, 65535).astype(np.uint16)
        med = cv2.medianBlur(big, self.median_ksize)
        x = np.where(med >= 60000, 0, med).astype(np.uint16)
        valid = x > 0
        xf = x.astype(np.float32)
        if self.acc is None:
            self.acc = xf.copy()
            self.hold = np.where(valid, 0, 255).astype(np.uint8)
            self.oog_count = np.zeros(x.shape, np.uint8)
            return x
        # 3. temporal EMA with hysteresis snap
        diff = cv2.absdiff(xf, self.acc)
        self.oog_count = np.where(valid & (diff >= self.gate_mm),
                                  self.oog_count + 1, 0).astype(np.uint8)
        snap = self.oog_count >= self.snap_frames
        smooth = valid & ~snap
        cv2.accumulateWeighted(xf, self.acc, self.alpha,
                               mask=smooth.astype(np.uint8))
        if snap.any():
            self.acc[snap] = xf[snap]
            self.oog_count[snap] = 0
        self.hold = np.where(valid, 0,
                             np.minimum(self.hold.astype(np.uint16) + 1, 255)
                             ).astype(np.uint8)
        out = np.where(valid | (self.hold <= self.hold_frames), self.acc, 0.0)
        return np.clip(out, 0, 65535).astype(np.uint16)

    def params(self):
        return {"alpha": self.alpha, "gate_mm": self.gate_mm,
                "hold_frames": self.hold_frames,
                "snap_frames": self.snap_frames,
                "median_ksize": self.median_ksize}


class DepthFilterV2:
    """V2: same smoothing core as V1, plus anti-ghosting.

    Real motion is spatially coherent; noise is isolated. A pixel whose depth
    disagrees with the accumulator snaps IMMEDIATELY when its neighbourhood
    (15x15 box) contains >= snap_density out-of-gate pixels; isolated
    disagreements still need snap_frames consecutive frames. Invalid-pixel
    hold is shortened to hold_frames=3 so departed objects fade fast.

    Env overrides: DF_ALPHA, DF_GATE_MM, DF_HOLD_FRAMES, DF_SNAP_FRAMES,
    DF_MEDIAN_KSIZE, DF_SNAP_DENSITY, DF_BOX_KSIZE.
    """

    def __init__(self,
                 alpha=float(os.environ.get("DF_ALPHA", "0.15")),
                 gate_mm=float(os.environ.get("DF_GATE_MM", "250")),
                 hold_frames=int(os.environ.get("DF_HOLD_FRAMES", "3")),
                 snap_frames=int(os.environ.get("DF_SNAP_FRAMES", "3")),
                 median_ksize=int(os.environ.get("DF_MEDIAN_KSIZE", "5")),
                 snap_density=float(os.environ.get("DF_SNAP_DENSITY", "0.20")),
                 box_ksize=int(os.environ.get("DF_BOX_KSIZE", "15"))):
        self.alpha = alpha
        self.gate_mm = gate_mm
        self.hold_frames = hold_frames
        self.snap_frames = snap_frames
        self.median_ksize = median_ksize
        self.snap_density = snap_density
        self.box_ksize = box_ksize
        self._kernel = np.ones((3, 3), np.uint8)
        self.acc = None
        self.hold = None
        self.oog_count = None

    def process(self, depth):
        opened = cv2.morphologyEx((depth > 0).astype(np.uint8),
                                  cv2.MORPH_OPEN, self._kernel)
        x = depth * opened
        big = np.where(x > 0, x, 65535).astype(np.uint16)
        med = cv2.medianBlur(big, self.median_ksize)
        x = np.where(med >= 60000, 0, med).astype(np.uint16)
        valid = x > 0
        xf = x.astype(np.float32)
        if self.acc is None:
            self.acc = xf.copy()
            self.hold = np.where(valid, 0, 32767).astype(np.int16)
            self.oog_count = np.zeros(x.shape, np.uint8)
            return x
        diff = cv2.absdiff(xf, self.acc)
        oog = valid & (diff >= self.gate_mm)
        # Spatially coherent disagreement -> snap this very frame.
        # Density via uint8 boxFilter (fast); skipped entirely when too few
        # out-of-gate pixels exist to form a coherent region.
        fast_snap = np.zeros(oog.shape, bool)
        oog_u8 = oog.view(np.uint8)
        if cv2.countNonZero(oog_u8) >= int(
                self.snap_density * self.box_ksize * self.box_ksize):
            density = cv2.boxFilter(oog_u8 * 255, -1,
                                    (self.box_ksize, self.box_ksize),
                                    normalize=True)
            fast_snap = oog & (density >= int(self.snap_density * 255))
        # isolated disagreement -> hysteresis as before
        self.oog_count = np.where(oog & ~fast_snap,
                                  self.oog_count + 1, 0).astype(np.uint8)
        snap = fast_snap | (self.oog_count >= self.snap_frames)
        smooth = valid & ~snap
        cv2.accumulateWeighted(xf, self.acc, self.alpha,
                               mask=smooth.astype(np.uint8))
        if snap.any():
            cv2.copyTo(xf, snap.view(np.uint8) * 255, self.acc)
            self.oog_count[snap] = 0
        np.add(self.hold, 1, out=self.hold)
        self.hold[valid] = 0
        out = np.where(valid | (self.hold <= self.hold_frames),
                       self.acc, 0.0).astype(np.uint16)
        return out

    def params(self):
        return {"alpha": self.alpha, "gate_mm": self.gate_mm,
                "hold_frames": self.hold_frames,
                "snap_frames": self.snap_frames,
                "median_ksize": self.median_ksize,
                "snap_density": self.snap_density,
                "box_ksize": self.box_ksize}


def ghost_disagreement(raw_seq, filt_seq, gate_mm=250.0):
    """Ghost metric: fraction of pixels where the FILTERED output still
    disagrees with the CURRENT raw frame by more than gate_mm (valid both).
    Ghosting = filtered lags reality -> disagreement spikes during motion."""
    both = (raw_seq > 0) & (filt_seq > 0)
    dis = (np.abs(raw_seq.astype(np.int32) - filt_seq.astype(np.int32))
           > gate_mm) & both
    per_frame = dis.sum(axis=(1, 2)) / np.maximum(both.sum(axis=(1, 2)), 1)
    return {"mean": float(per_frame.mean()),
            "p95": float(np.percentile(per_frame, 95))}


def colorize(depth, max_mm=DEPTH_MAX_MM):
    gray = np.clip(depth.astype(np.float32) * (255.0 / max_mm), 0, 255)
    gray = gray.astype(np.uint8)
    img = cv2.applyColorMap(255 - gray, cv2.COLORMAP_TURBO)
    img[depth == 0] = 0
    return img


def temporal_std(seq):
    """Per-pixel std over time (mm) on pixels valid in >=80% of frames."""
    frac = (seq > 0).mean(axis=0)
    mask = frac >= 0.8
    if not mask.any():
        return {"median_std_mm": float("nan"), "p95_std_mm": float("nan"),
                "eval_px": 0}
    std = seq.astype(np.float32).std(axis=0)
    vals = std[mask]
    return {"median_std_mm": float(np.median(vals)),
            "p95_std_mm": float(np.percentile(vals, 95)),
            "eval_px": int(mask.sum())}


def valid_ratio(seq):
    return float((seq > 0).mean())


def speckle_clusters(seq, min_cluster=24):
    counts = []
    for frame in seq:
        valid = (frame > 0).astype(np.uint8)
        n, _, stats, _ = cv2.connectedComponentsWithStats(valid, 8)
        if n <= 1:
            counts.append(0)
        else:
            counts.append(int((stats[1:, cv2.CC_STAT_AREA] < min_cluster).sum()))
    return float(np.mean(counts))
