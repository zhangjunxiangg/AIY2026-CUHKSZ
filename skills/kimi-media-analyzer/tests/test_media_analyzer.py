from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from media_analyzer import (  # noqa: E402
    CODING_IMAGE_LIMIT,
    HttpResponse,
    MediaAnalyzerError,
    ProviderSettings,
    analyze_media,
    inspect_media,
    load_schema,
    resolve_provider,
    validate_analysis,
    validate_media_for_provider,
)


def valid_analysis(media_kind: str = "image") -> dict[str, Any]:
    return {
        "media_kind": media_kind,
        "summary": "A red test object is visible.",
        "duration_observed_seconds": None if media_kind == "image" else 2.0,
        "scenes": [
            {
                "index": 0,
                "start_seconds": None if media_kind == "image" else 0.0,
                "end_seconds": None if media_kind == "image" else 2.0,
                "description": "One test scene.",
                "objects": ["red object"],
                "actions": [],
                "visible_text": ["TEST-42"],
                "confidence": 0.8,
            }
        ],
        "objects": [{"label": "red object", "occurrences": 1, "confidence": 0.8}],
        "visible_text": [
            {
                "text": "TEST-42",
                "timestamp_seconds": None,
                "location": "center",
                "confidence": 0.9,
            }
        ],
        "risks": [],
        "uncertainties": ["Exact dimensions cannot be determined."],
    }


@pytest.fixture
def tiny_png(tmp_path: Path) -> Path:
    path = tmp_path / "test.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nnot-a-real-decoder-test")
    return path


@pytest.fixture
def coding_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("MOONSHOT_API_KEY", "KIMI_INTL_API_KEY", "KIMI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("KIMI_API_KEY", "test-key-never-persist")


def test_bundled_schema_is_valid() -> None:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)


def test_inspect_media_produces_hash_and_kind(tiny_png: Path) -> None:
    media = inspect_media(tiny_png)
    assert media.media_kind == "image"
    assert media.mime_type == "image/png"
    assert media.size_bytes == tiny_png.stat().st_size
    assert len(media.sha256) == 64


def test_inspect_media_rejects_unknown_and_empty_files(tmp_path: Path) -> None:
    unknown = tmp_path / "notes.txt"
    unknown.write_text("hello", encoding="utf-8")
    with pytest.raises(MediaAnalyzerError, match="Unsupported media type"):
        inspect_media(unknown)
    empty = tmp_path / "empty.mp4"
    empty.touch()
    with pytest.raises(MediaAnalyzerError, match="empty"):
        inspect_media(empty)


def test_resolve_provider_uses_kimi_key_without_exposing_value(
    coding_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("media_analyzer._load_mclaw_provider", lambda: None)
    settings = resolve_provider("image")
    assert settings.api_mode == "anthropic_messages"
    assert settings.base_url == "https://api.kimi.com/coding"
    assert settings.credential_source == "environment:KIMI_API_KEY"
    assert "test-key-never-persist" not in repr(settings)


def test_video_switches_away_from_image_only_k3_256k(
    coding_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "media_analyzer._load_mclaw_provider",
        lambda: (
            {
                "name": "kimi-coding",
                "api_mode": "anthropic_messages",
                "base_url": "https://api.kimi.com/coding/",
                "api_key_env": "KIMI_API_KEY",
                "model": "k3-256k",
            },
            lambda _: None,
        ),
    )
    assert resolve_provider("image").model == "k3-256k"
    assert resolve_provider("video").model == "k3"


def test_coding_transport_enforces_size_limit(tmp_path: Path) -> None:
    path = tmp_path / "large.png"
    path.write_bytes(b"x")
    media = inspect_media(path)
    oversized = type(media)(
        path=media.path,
        filename=media.filename,
        media_kind=media.media_kind,
        mime_type=media.mime_type,
        size_bytes=CODING_IMAGE_LIMIT + 1,
        sha256=media.sha256,
    )
    settings = ProviderSettings(
        provider="kimi-coding",
        api_mode="anthropic_messages",
        base_url="https://api.kimi.com/coding",
        model="k3-256k",
        credential_source="environment:KIMI_API_KEY",
        api_key="secret",
    )
    with pytest.raises(MediaAnalyzerError, match="above"):
        validate_media_for_provider(oversized, settings)


def test_anthropic_flow_saves_validated_json(
    tmp_path: Path, tiny_png: Path, coding_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("media_analyzer._load_mclaw_provider", lambda: None)
    seen: dict[str, Any] = {}

    def fake_request(method, url, headers, body, content_type, timeout, api_key):
        seen.update(
            method=method,
            url=url,
            headers=headers,
            payload=json.loads(body),
            content_type=content_type,
            timeout=timeout,
            api_key=api_key,
        )
        return HttpResponse(
            {
                "id": "msg_test",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "record_media_analysis",
                        "input": valid_analysis(),
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            },
            {},
        )

    output = tmp_path / "result.json"
    result = analyze_media(tiny_png, output, http_request=fake_request)
    persisted = json.loads(output.read_text(encoding="utf-8"))
    Draft202012Validator(load_schema(), format_checker=None).validate(persisted)
    assert result == persisted
    assert seen["url"] == "https://api.kimi.com/coding/v1/messages"
    assert seen["payload"]["messages"][0]["content"][0]["type"] == "image"
    assert persisted["request"]["delivery"] == "inline_base64"
    assert persisted["request"]["remote_file_id"] is None
    assert "test-key-never-persist" not in output.read_text(encoding="utf-8")


def test_openai_flow_uploads_then_saves_structured_result(
    tmp_path: Path, tiny_png: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("media_analyzer._load_mclaw_provider", lambda: None)
    monkeypatch.setenv("MOONSHOT_API_KEY", "platform-test-key")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    calls: list[str] = []

    def fake_request(method, url, headers, body, content_type, timeout, api_key):
        calls.append(url)
        if url.endswith("/files"):
            assert b'name="purpose"\r\n\r\nimage' in body
            return HttpResponse({"id": "file_test"}, {})
        payload = json.loads(body)
        media_part = payload["messages"][0]["content"][0]
        assert media_part["image_url"]["url"] == "ms://file_test"
        return HttpResponse(
            {
                "id": "chat_test",
                "choices": [{"message": {"content": json.dumps(valid_analysis())}}],
                "usage": {"total_tokens": 42},
            },
            {"x-request-id": "header_test"},
        )

    output = tmp_path / "platform-result.json"
    result = analyze_media(tiny_png, output, http_request=fake_request)
    assert calls == [
        "https://api.moonshot.ai/v1/files",
        "https://api.moonshot.ai/v1/chat/completions",
    ]
    assert result["request"]["remote_file_id"] == "file_test"
    assert result["request"]["remote_file_retained"] is True
    Draft202012Validator(load_schema()).validate(result)


def test_invalid_model_data_is_rejected_without_writing(
    tmp_path: Path, tiny_png: Path, coding_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("media_analyzer._load_mclaw_provider", lambda: None)
    invalid = valid_analysis()
    invalid["objects"][0]["confidence"] = 7

    def fake_request(*_args):
        return HttpResponse(
            {
                "id": "bad",
                "content": [
                    {"type": "tool_use", "name": "record_media_analysis", "input": invalid}
                ],
            },
            {},
        )

    output = tmp_path / "must-not-exist.json"
    with pytest.raises(MediaAnalyzerError, match="expected 0..1"):
        analyze_media(tiny_png, output, http_request=fake_request)
    assert not output.exists()


def test_existing_output_is_rejected_before_network_call(
    tmp_path: Path, tiny_png: Path
) -> None:
    output = tmp_path / "existing.json"
    output.write_text('{"keep": true}\n', encoding="utf-8")

    def forbidden_request(*_args):
        raise AssertionError("network must not be called")

    with pytest.raises(MediaAnalyzerError, match="Refusing to overwrite"):
        analyze_media(tiny_png, output, http_request=forbidden_request)
    assert json.loads(output.read_text(encoding="utf-8")) == {"keep": True}


def test_validator_rejects_missing_and_extra_fields() -> None:
    missing = valid_analysis()
    missing.pop("uncertainties")
    with pytest.raises(MediaAnalyzerError, match="missing"):
        validate_analysis(missing, "image")
    extra = valid_analysis()
    extra["invented"] = True
    with pytest.raises(MediaAnalyzerError, match="unexpected"):
        validate_analysis(extra, "image")


def test_check_only_command_is_secret_safe(
    tiny_png: Path, coding_env: None
) -> None:
    environment = dict(os.environ)
    environment["KIMI_MEDIA_BOOTSTRAPPED"] = "1"
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "analyze_media.py"), str(tiny_png), "--check-only"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["network_called"] is False
    assert payload["api_key"] == "<redacted>"
    assert "test-key-never-persist" not in completed.stdout + completed.stderr
