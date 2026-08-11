#!/usr/bin/env python3
# sim 模式验收测试（本机跑）：对 practice/ 五张合成场景图端到端跑 perception_node.py --sim 并断言。
"""End-to-end acceptance test of sim mode against the practice/ synthetic scenes.

Runs `perception_node.py --sim --images <scene>` as a subprocess for each scene,
parses the final JSON line from stdout, and asserts the expected detections:
    color_scene.png -> red_block, green_ball, blue_block, yellow_ball (4 targets)
    cone_scene.png  -> exactly 2 "cone"
    ring_scene.png  -> red_ring, green_ring
    tpl_scene.png   -> exactly 2 "human_board"
    qr_scene.png    -> qr:A, qr:B
Exit code 0 only if every case passes.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NODE = HERE / "perception_node.py"
CONFIG = HERE / "config.json"
SCENES = ROOT / "practice"

COLOR_SHAPES = ("block", "ball", "cylinder", "ring")


def run_sim(image):
    proc = subprocess.run(
        [sys.executable, str(NODE), "--sim", "--images", str(image), "--config", str(CONFIG)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"sim mode exited {proc.returncode} on {image}\n{proc.stdout}\n{proc.stderr}"
        )
    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    try:
        return json.loads(lines[-1])  # 每张图最后一行是纯 JSON
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"cannot parse last stdout line {lines[-1]!r}: {exc}")


def check_schema(result):
    assert {"ts", "frame", "targets"} <= set(result), f"bad top-level keys: {sorted(result)}"
    assert isinstance(result["frame"], list) and len(result["frame"]) == 2
    for t in result["targets"]:
        assert {"category", "center", "confidence", "bbox", "depth_mm"} <= set(t), \
            f"bad target keys: {t}"
        assert len(t["center"]) == 2 and len(t["bbox"]) == 4
        assert 0.0 <= t["confidence"] <= 1.0


def check_case(name, result):
    """返回 (ok, detail)。按场景名分派断言。"""
    targets = result["targets"]
    cats = [t["category"] for t in targets]
    if name == "color_scene.png":
        got = {c for c in cats if c.rsplit("_", 1)[-1] in COLOR_SHAPES}
        want = {"red_block", "green_ball", "blue_block", "yellow_ball"}
        return got == want, f"color objects={sorted(got)} (want {sorted(want)})"
    if name == "cone_scene.png":
        n = cats.count("cone")
        return n == 2, f"cone count={n} (want exactly 2)"
    if name == "ring_scene.png":
        got = {c for c in cats if c.endswith("_ring")}
        want = {"red_ring", "green_ring"}
        return got == want, f"rings={sorted(got)} (want {sorted(want)})"
    if name == "tpl_scene.png":
        n = cats.count("human_board")
        return n == 2, f"human_board count={n} (want exactly 2)"
    if name == "qr_scene.png":
        got = {c for c in cats if c.startswith("qr:")}
        want = {"qr:A", "qr:B"}
        return got == want, f"qr codes={sorted(got)} (want {sorted(want)})"
    return False, f"unknown scene {name}"


def main():
    scenes = ["color_scene.png", "cone_scene.png", "ring_scene.png", "tpl_scene.png", "qr_scene.png"]
    results = []
    for name in scenes:
        image = SCENES / name
        if not image.exists():
            results.append((name, False, f"scene image missing: {image}"))
            continue
        try:
            result = run_sim(image)
            check_schema(result)
            ok, detail = check_case(name, result)
        except Exception as exc:  # 断言/解析错误都算 FAIL，继续跑完其余场景
            ok, detail = False, f"ERROR {exc}"
        results.append((name, ok, detail))
        print(f"[TEST] {'PASS' if ok else 'FAIL'} {name}: {detail}")

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"[TEST] summary: {passed}/{len(results)} passed")
    if passed != len(results):
        print("[TEST] OVERALL FAIL")
        return 1
    print("[TEST] OVERALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
