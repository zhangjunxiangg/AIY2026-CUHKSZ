#!/usr/bin/env python3
import glob
import importlib
import os
import platform
import sys


def check(label, condition, detail=""):
    state = "PASS" if condition else "FAIL"
    print(f"{state:4} {label}{': ' + detail if detail else ''}")
    return bool(condition)


ok = True
ok &= check("architecture", platform.machine() in ("aarch64", "arm64"), platform.machine())
ok &= check("python", sys.version_info[:2] == (3, 12), sys.version.split()[0])
ok &= check("host-python", sys.executable.startswith("/data/local/release/"), sys.executable)

for module in ("rospy", "serial", "yaml", "numpy", "netifaces"):
    try:
        loaded = importlib.import_module(module)
        ok &= check(f"import {module}", True, getattr(loaded, "__version__", "OK"))
    except Exception as exc:
        ok &= check(f"import {module}", False, str(exc))

serial_candidates = sorted(glob.glob("/dev/ttyCH343USB*") + glob.glob("/dev/rrc") + glob.glob("/dev/ttyUSB*"))
ok &= check("serial-device", bool(serial_candidates), ",".join(serial_candidates) or "none")
if serial_candidates:
    ok &= check("serial-rw", os.access(serial_candidates[0], os.R_OK | os.W_OK), serial_candidates[0])

print("preflight=" + ("PASS" if ok else "FAIL"))
raise SystemExit(0 if ok else 1)
