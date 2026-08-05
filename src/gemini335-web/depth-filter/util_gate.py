"""Shared gate/logging helpers for the depth-filter sub-pipeline.

Every step writes logs/<step>/{step.log,timing.json,STATUS.txt} so the next
step's first gate is reading its predecessor's STATUS. Fail loud, fail early.
"""

import json
import os
import time


class GateFailure(Exception):
    pass


class Step:
    def __init__(self, out_root, name):
        self.name = name
        self.log_dir = os.path.join(out_root, "logs", name)
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_path = os.path.join(self.log_dir, "step.log")
        self.timing = {}
        self._log_lines = []
        self.log(f"step {name} start {time.strftime('%H:%M:%S')}")

    def log(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        self._log_lines.append(line)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def timeit(self, key):
        return _Timer(self, key)

    def gate(self, ok, check, measured, threshold):
        status = "PASS" if ok else "FAIL"
        self.log(f"gate {check}: {status} (measured={measured}, threshold={threshold})")
        if not ok:
            self.finish("FAIL")
            raise GateFailure(f"{check}: measured={measured} threshold={threshold}")

    def require_predecessor(self, out_root, name):
        path = os.path.join(out_root, "logs", name, "STATUS.txt")
        ok = os.path.exists(path) and open(path).read().strip() == "PASS"
        self.gate(ok, f"predecessor {name} STATUS=PASS", open(path).read().strip() if os.path.exists(path) else "missing", "PASS")

    def finish(self, status):
        with open(os.path.join(self.log_dir, "timing.json"), "w") as fh:
            json.dump(self.timing, fh, indent=2)
        with open(os.path.join(self.log_dir, "STATUS.txt"), "w") as fh:
            fh.write(status)
        self.log(f"step {self.name} {status}")


class _Timer:
    def __init__(self, step, key):
        self.step, self.key = step, key

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        ms = (time.perf_counter() - self.t0) * 1000.0
        self.step.timing.setdefault(self.key, []).append(round(ms, 3))
        return False
