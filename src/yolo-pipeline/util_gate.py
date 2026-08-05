"""门禁/日志/计时/STATUS 框架 —— 所有步骤共用。

用法：
    from util_gate import Step
    with Step("01_inspect_dataset") as step:
        step.log("...")
        step.gate(count >= MIN, f"图片数量 {count} < 最小要求 {MIN}")
        step.time_phase("scan", seconds)
    # 正常结束自动写 PASS；异常/门禁失败自动写 FAIL 并以退出码 1 终止
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from pathlib import Path

import util_paths


class GateFailure(Exception):
    """门禁失败：携带检查名、实测值、阈值，响亮地失败。"""


class Step:
    def __init__(self, name: str):
        self.name = name
        self.dir = util_paths.LOGS / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        fh = logging.FileHandler(self.dir / "step.log", encoding="utf-8")
        fh.setFormatter(fmt)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        self.logger.addHandler(fh)
        self.logger.addHandler(sh)
        self._t0 = time.time()
        self._timing: dict = {"step": name, "phases": {}, "gates": {}}

    # ---- 日志 ----
    def log(self, msg: str):
        self.logger.info(msg)

    def warn(self, msg: str):
        self.logger.warning(msg)

    # ---- 门禁 ----
    def gate(self, ok: bool, what: str):
        t = time.time()
        self._timing["gates"][what] = {"time": t - self._t0, "pass": bool(ok)}
        if ok:
            self.logger.info(f"[GATE PASS] {what}")
        else:
            self.logger.error(f"[GATE FAIL] {what}")
            raise GateFailure(what)

    def gate_predecessor(self, step_name: str):
        status = util_paths.LOGS / step_name / "STATUS.txt"
        ok = status.exists() and status.read_text().strip() == "PASS"
        self.gate(ok, f"前驱步骤 {step_name} STATUS=PASS（实测: "
                      f"{status.read_text().strip() if status.exists() else '缺失'}）")

    # ---- 计时 ----
    def time_phase(self, phase: str, seconds: float):
        self._timing["phases"][phase] = round(seconds, 3)
        self.logger.info(f"[TIME] {phase}: {seconds:.3f}s")

    @staticmethod
    def now() -> float:
        return time.time()

    # ---- 生命周期 ----
    def __enter__(self) -> "Step":
        self.log(f"===== step {self.name} start =====")
        return self

    def _finish(self, status: str):
        (self.dir / "timing.json").write_text(
            json.dumps(self._timing, ensure_ascii=False, indent=1), encoding="utf-8")
        (self.dir / "STATUS.txt").write_text(status)
        self.log(f"===== step {self.name} {status} "
                 f"({time.time() - self._t0:.1f}s) =====")

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._finish("PASS")
            return False
        self.logger.error("步骤异常终止:\n" + "".join(
            traceback.format_exception(exc_type, exc, tb)))
        self._finish("FAIL")
        return True  # 吞掉异常，由 main 统一退出码


def run_step(name: str, main_fn):
    """步骤入口：统一退出码。"""
    with Step(name) as step:
        main_fn(step)
    status = (util_paths.LOGS / name / "STATUS.txt").read_text().strip()
    sys.exit(0 if status == "PASS" else 1)
