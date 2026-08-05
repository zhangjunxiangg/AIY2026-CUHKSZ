from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


SKILL_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    os.environ.get("KIMI_MEDIA_LIVE_TEST") != "1",
    reason="set KIMI_MEDIA_LIVE_TEST=1 to spend quota and call the configured Kimi service",
)
def test_real_kimi_writes_schema_valid_json(tmp_path: Path) -> None:
    configured_path = os.environ.get("KIMI_MEDIA_LIVE_PATH", "")
    media_path = Path(configured_path).expanduser().resolve()
    if not configured_path or not media_path.is_file():
        pytest.fail("KIMI_MEDIA_LIVE_PATH must name an existing image or video")
    output = tmp_path / "live-result.json"
    environment = dict(os.environ)
    environment.pop("KIMI_MEDIA_BOOTSTRAPPED", None)
    command = [
        str(SKILL_DIR / "scripts" / "analyze_media.py"),
        str(media_path),
        "--output",
        str(output),
        "--focus",
        "Create a conservative general-purpose test analysis.",
    ]
    optional_flags = {
        "KIMI_MEDIA_LIVE_API_MODE": "--api-mode",
        "KIMI_MEDIA_LIVE_BASE_URL": "--base-url",
        "KIMI_MEDIA_LIVE_MODEL": "--model",
        "KIMI_MEDIA_LIVE_KEY_ENV": "--api-key-env",
    }
    for environment_name, flag in optional_flags.items():
        if value := os.environ.get(environment_name):
            command.extend([flag, value])
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    schema = json.loads(
        (SKILL_DIR / "references" / "media-analysis.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(result)
    assert result["source"]["path"] == str(media_path)
    assert result["analysis"]["media_kind"] == result["source"]["media_kind"]
    assert isinstance(result["analysis"]["summary"], str)
    assert result["analysis"]["summary"].strip()
