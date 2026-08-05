#!/usr/bin/env python3
"""util_gate.py — gate/日志/timing/STATUS 框架（gated success pipeline）

每个 step 一个实例：
    g = Gate("01_camera_ready")      # 创建 logs/01_camera_ready/
    g.log("...")
    g.gate("topic_alive", ok, measured=..., expected=...)   # FAIL 即写 STATUS 并退出
    g.pass_()                      # 全部 gate 通过后调用，写 STATUS=PASS

predecessor 检查：
    g.require_prev("01_camera_ready")   # 上一步 STATUS 必须 PASS
"""
from __future__ import annotations

import json
import os
import sys
import time

LOGS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


class GateFail(SystemExit):
    pass


class Gate:
    def __init__(self, step: str):
        self.step = step
        self.dir = os.path.join(LOGS_ROOT, step)
        os.makedirs(self.dir, exist_ok=True)
        self.log_path = os.path.join(self.dir, "step.log")
        self._log_fh = open(self.log_path, "a", encoding="utf-8")
        self.t0 = time.time()
        self.timing = {}
        self.n_gates = 0
        self.log(f"===== step {self.step} start {time.strftime('%Y-%m-%d %H:%M:%S')} =====")

    def log(self, msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        self._log_fh.write(line + "\n")
        self._log_fh.flush()

    def time_it(self, phase: str, seconds: float):
        self.timing[phase] = round(seconds, 3)
        self.log(f"timing: {phase} = {seconds:.3f}s")

    def gate(self, name: str, ok: bool, measured="", expected=""):
        self.n_gates += 1
        if ok:
            self.log(f"GATE PASS: {name} (measured={measured})")
        else:
            self.log(f"GATE FAIL: {name} (measured={measured}, expected={expected})")
            self._write_status("FAIL", f"gate '{name}': measured={measured}, expected={expected}")
            raise GateFail(f"GATE FAIL: {name}")

    def require_prev(self, prev_step: str):
        status = os.path.join(LOGS_ROOT, prev_step, "STATUS.txt")
        ok = False
        if os.path.exists(status):
            with open(status, encoding="utf-8") as f:
                ok = f.read().strip().startswith("PASS")
        self.gate(f"prev_{prev_step}_pass", ok,
                  measured=open(status).read().strip() if os.path.exists(status) else "STATUS.txt missing",
                  expected="PASS")

    def artifact_path(self, filename: str) -> str:
        return os.path.join(self.dir, filename)

    def pass_(self):
        with open(os.path.join(self.dir, "timing.json"), "w", encoding="utf-8") as f:
            json.dump({"total_s": round(time.time() - self.t0, 3), "phases": self.timing}, f, indent=2)
        self._write_status("PASS", f"{self.n_gates} gates passed")
        self.log(f"===== step {self.step} PASS =====")
        self._log_fh.close()

    def _write_status(self, status: str, detail: str):
        with open(os.path.join(self.dir, "STATUS.txt"), "w", encoding="utf-8") as f:
            f.write(f"{status} {time.strftime('%Y-%m-%d %H:%M:%S')} {detail}\n")


def main(step: str, fn):
    """标准 step 入口：fn(g) 抛 GateFail 即 FAIL。"""
    g = Gate(step)
    try:
        fn(g)
        g.pass_()
        return 0
    except GateFail:
        return 1
    except Exception as e:  # 裸异常也要留 STATUS
        g.log(f"EXCEPTION: {type(e).__name__}: {e}")
        g._write_status("FAIL", f"exception: {type(e).__name__}: {e}")
        return 2
