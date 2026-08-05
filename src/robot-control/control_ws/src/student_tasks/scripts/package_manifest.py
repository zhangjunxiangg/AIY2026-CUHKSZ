#!/usr/bin/env python3
"""Validate a board manifest and optionally stage it into a local directory."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any


SCHEMA = "robot-control/manifest-check/v1"


def validate_manifest(manifest_path: str | Path) -> tuple[dict[str, Any] | None, list[str]]:
    path = Path(manifest_path)
    findings: list[str] = []
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, ["manifest cannot be read: %s" % exc]
    if not isinstance(manifest, dict):
        return None, ["manifest root must be an object"]
    if manifest.get("schema") != "robot-control/board-manifest/v1":
        findings.append("manifest schema is unsupported")
    target_root = manifest.get("target_root")
    if not isinstance(target_root, str) or not target_root.startswith("/") or not target_root.endswith("/"):
        findings.append("target_root must be an absolute directory")
        target_root = ""
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        findings.append("entries must be a non-empty array")
        entries = []
    seen: set[str] = set()
    package_root = path.parent.parent.parent.parent
    for index, entry in enumerate(entries):
        prefix = "entries[%d]" % index
        if not isinstance(entry, dict):
            findings.append("%s must be an object" % prefix)
            continue
        source = entry.get("source")
        target = entry.get("target")
        mode = entry.get("mode")
        if not isinstance(source, str) or not source or Path(source).is_absolute() or ".." in Path(source).parts:
            findings.append("%s.source must be a relative safe path" % prefix)
            continue
        if source in seen:
            findings.append("duplicate source: %s" % source)
        seen.add(source)
        source_path = package_root / source
        if not source_path.is_file():
            findings.append("missing source: %s" % source)
        if not isinstance(target, str) or not target.startswith(target_root):
            findings.append("%s.target must stay below target_root" % prefix)
        if not isinstance(mode, str) or mode not in {"0644", "0755"}:
            findings.append("%s.mode must be 0644 or 0755" % prefix)
        if entry.get("production_allowed") is not True:
            findings.append("%s.production_allowed must be true" % prefix)
    return manifest, findings


def stage_manifest(manifest: dict[str, Any], stage_dir: str | Path) -> list[str]:
    root = Path(stage_dir)
    root.mkdir(parents=True, exist_ok=True)
    package_root = Path(__file__).resolve().parents[3]
    staged: list[str] = []
    for entry in manifest["entries"]:
        source = package_root / entry["source"]
        relative_target = Path(entry["target"]).relative_to(manifest["target_root"])
        target = root / relative_target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        os.chmod(target, stat.S_IMODE(int(entry["mode"], 8)))
        staged.append(str(target))
    return staged


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="package-manifest")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--stage-dir")
    parsed = parser.parse_args(arguments)
    manifest, findings = validate_manifest(parsed.manifest)
    if manifest is None or findings:
        sys.stdout.write(json.dumps({"schema": SCHEMA, "ok": False, "findings": findings}, separators=(",", ":")) + "\n")
        return 2
    result: dict[str, Any] = {"schema": SCHEMA, "ok": True, "manifest": parsed.manifest, "staged": []}
    if parsed.stage_dir:
        try:
            result["staged"] = stage_manifest(manifest, parsed.stage_dir)
        except (OSError, ValueError, KeyError) as exc:
            sys.stdout.write(json.dumps({"schema": SCHEMA, "ok": False, "findings": ["staging failed: %s" % exc]}, separators=(",", ":")) + "\n")
            return 2
    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
