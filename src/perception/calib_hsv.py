#!/usr/bin/env python3
# HSV 现场取样工具（本机用，需要 GUI）：鼠标点图取色，打印建议 HSV 范围供填进 config.json。
"""Click-to-sample HSV calibration helper (local GUI tool, OpenCV window).

Usage:
    python calib_hsv.py <image> [--slot red] [--json]

Keys:
    left click  sample a pixel, print its BGR/HSV and a suggested HSV range
    + / -       grow / shrink the tolerance applied around the sample
    s           print a config.json snippet for the chosen color slot
    q / Esc     quit
"""
from __future__ import annotations

import argparse
import json

import cv2


def suggest_range(hsv_val, tol):
    """以取样点为中心 ±tol 生成 [lo, hi]，H 限 0~180，S/V 限 0~255。"""
    h, s, v = (int(x) for x in hsv_val)
    th, ts, tv = tol
    lo = [max(0, h - th), max(0, s - ts), max(0, v - tv)]
    hi = [min(180, h + th), min(255, s + ts), min(255, v + tv)]
    return lo, hi


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="image file to sample")
    parser.add_argument("--slot", default="custom",
                        help="color slot name used in the printed config snippet")
    parser.add_argument("--json", action="store_true",
                        help="print machine-readable JSON lines instead of text")
    args = parser.parse_args()

    bgr = cv2.imread(args.image)
    if bgr is None:
        raise SystemExit(f"cannot read image: {args.image}")
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    state = {"point": None, "tol": [10, 60, 60]}

    def report(x, y):
        bgr_val = [int(v) for v in bgr[y, x]]
        hsv_val = [int(v) for v in hsv[y, x]]
        lo, hi = suggest_range(hsv_val, state["tol"])
        if args.json:
            print(json.dumps({
                "point": [x, y], "bgr": bgr_val, "hsv": hsv_val,
                "tol": list(state["tol"]), "range": [lo, hi],
            }))
        else:
            print(f"[CALIB] point=({x},{y}) BGR={bgr_val} HSV={hsv_val}")
            print(f"[CALIB]   suggested range lo={lo} hi={hi} (tol={state['tol']})")

    def on_mouse(event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["point"] = (x, y)
            report(x, y)

    cv2.namedWindow("calib_hsv", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("calib_hsv", on_mouse)
    print("[CALIB] left-click: sample | +/-: tolerance | s: config snippet | q: quit")
    while True:
        view = bgr.copy()
        if state["point"]:
            cv2.drawMarker(view, state["point"], (0, 255, 255), cv2.MARKER_CROSS, 20, 2)
        cv2.imshow("calib_hsv", view)
        key = cv2.waitKey(30) & 0xFF
        if key in (ord("q"), 27):
            break
        if key in (ord("+"), ord("=")):
            state["tol"] = [t + 5 for t in state["tol"]]
            print(f"[CALIB] tolerance -> {state['tol']}")
        elif key == ord("-"):
            state["tol"] = [max(1, t - 5) for t in state["tol"]]
            print(f"[CALIB] tolerance -> {state['tol']}")
        elif key == ord("s"):
            if not state["point"]:
                print("[CALIB] click a point first")
                continue
            x, y = state["point"]
            lo, hi = suggest_range(hsv[y, x], state["tol"])
            snippet = json.dumps({args.slot: [[lo, hi]]}, ensure_ascii=False)
            print("[CALIB] merge this into config.json -> hsv_colors "
                  "(append the range pair if the slot already exists):")
            print(snippet)
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
