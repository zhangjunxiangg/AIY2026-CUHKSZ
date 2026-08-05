#!/usr/bin/env python3
"""Kimi image/video analysis core with M-Claw credential resolution."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import tempfile
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = "kimi-media-analysis.v1"
MIB = 1024 * 1024
CODING_IMAGE_LIMIT = 10 * MIB
CODING_VIDEO_LIMIT = 20 * MIB
PLATFORM_MEDIA_LIMIT = 100 * MIB

MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".mp4": "video/mp4",
    ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".flv": "video/x-flv",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".wmv": "video/x-ms-wmv",
    ".3gp": "video/3gpp",
}
CODING_IMAGE_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
CODING_VIDEO_MIMES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "video/x-msvideo",
    "video/x-flv",
    "video/3gpp",
}


class MediaAnalyzerError(RuntimeError):
    """Safe, user-facing failure that never includes credential values."""


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    filename: str
    media_kind: str
    mime_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class ProviderSettings:
    provider: str
    api_mode: str
    base_url: str
    model: str
    credential_source: str
    api_key: str = field(repr=False)


@dataclass(frozen=True)
class HttpResponse:
    data: dict[str, Any]
    headers: dict[str, str]


HttpRequest = Callable[[str, str, dict[str, str], bytes, str, float, str], HttpResponse]


def schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "media-analysis.schema.json"


def load_schema() -> dict[str, Any]:
    try:
        value = json.loads(schema_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MediaAnalyzerError(f"Cannot load bundled JSON Schema: {exc}") from None
    if not isinstance(value, dict):
        raise MediaAnalyzerError("Bundled JSON Schema is not an object")
    return value


def analysis_schema() -> dict[str, Any]:
    document = load_schema()
    definitions = document.get("$defs")
    if not isinstance(definitions, dict) or not isinstance(definitions.get("analysis"), dict):
        raise MediaAnalyzerError("Bundled JSON Schema has no analysis definition")
    result = dict(definitions["analysis"])
    result["$defs"] = {
        "nullableConfidence": definitions["nullableConfidence"],
    }
    return result


def inspect_media(path: str | os.PathLike[str]) -> MediaInfo:
    candidate = Path(path).expanduser().resolve()
    if not candidate.exists():
        raise MediaAnalyzerError(f"Media file does not exist: {candidate}")
    if not candidate.is_file():
        raise MediaAnalyzerError(f"Media path is not a regular file: {candidate}")
    size = candidate.stat().st_size
    if size <= 0:
        raise MediaAnalyzerError(f"Media file is empty: {candidate}")
    mime_type = MIME_BY_SUFFIX.get(candidate.suffix.lower())
    if not mime_type:
        guessed, _ = mimetypes.guess_type(candidate.name)
        mime_type = guessed or ""
    if mime_type.startswith("image/"):
        media_kind = "image"
    elif mime_type.startswith("video/"):
        media_kind = "video"
    else:
        raise MediaAnalyzerError(
            f"Unsupported media type for {candidate.name}; use a supported image or video format"
        )
    digest = hashlib.sha256()
    with candidate.open("rb") as stream:
        for chunk in iter(lambda: stream.read(MIB), b""):
            digest.update(chunk)
    return MediaInfo(candidate, candidate.name, media_kind, mime_type, size, digest.hexdigest())


def _safe_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise MediaAnalyzerError("Kimi base URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise MediaAnalyzerError("Kimi base URL must not contain credentials, query, or fragment")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _is_kimi_endpoint(base_url: str) -> bool:
    host = (urlsplit(base_url).hostname or "").lower()
    return host == "api.kimi.com" or host.endswith(".moonshot.ai") or host.endswith(".moonshot.cn")


def _load_mclaw_provider() -> tuple[dict[str, Any], Callable[[str], str | None]] | None:
    try:
        from mclaw.cli.config import get_env_value, load_config
    except (ImportError, ModuleNotFoundError):
        return None
    try:
        config = load_config()
    except Exception as exc:
        raise MediaAnalyzerError(f"M-Claw configuration cannot be loaded: {type(exc).__name__}") from None
    active = str(config.get("active_provider") or "").strip()
    provider = (config.get("providers") or {}).get(active)
    if not active or not isinstance(provider, dict):
        return None
    safe = {
        "name": active,
        "api_mode": str(provider.get("api_mode") or "").strip(),
        "base_url": str(provider.get("base_url") or "").strip(),
        "api_key_env": str(provider.get("api_key_env") or "").strip(),
        "model": str(config.get("model") or "").strip(),
    }
    return safe, get_env_value


def _get_named_key(name: str, mclaw_get: Callable[[str], str | None] | None) -> tuple[str, str]:
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,63}", name):
        raise MediaAnalyzerError(f"Invalid credential environment variable name: {name!r}")
    if value := os.environ.get(name, "").strip():
        return value, f"environment:{name}"
    if mclaw_get is not None:
        try:
            value = (mclaw_get(name) or "").strip()
        except Exception:
            value = ""
        if value:
            return value, f"mclaw:{name}"
    return "", ""


def resolve_provider(
    media_kind: str,
    *,
    api_mode: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key_env: str | None = None,
) -> ProviderSettings:
    mclaw = _load_mclaw_provider()
    configured: dict[str, Any] = {}
    mclaw_get: Callable[[str], str | None] | None = None
    if mclaw is not None:
        configured, mclaw_get = mclaw

    chosen_mode = api_mode or str(configured.get("api_mode") or "")
    chosen_base = base_url or str(configured.get("base_url") or "")
    chosen_model = model or str(configured.get("model") or "")
    chosen_env = api_key_env or str(configured.get("api_key_env") or "")
    provider_name = str(configured.get("name") or "kimi")

    if not chosen_env:
        for candidate in ("MOONSHOT_API_KEY", "KIMI_INTL_API_KEY", "KIMI_API_KEY"):
            key, source = _get_named_key(candidate, mclaw_get)
            if key:
                chosen_env = candidate
                break
        else:
            key = source = ""
    else:
        key, source = _get_named_key(chosen_env, mclaw_get)

    if not key:
        raise MediaAnalyzerError(
            "No Kimi credential is available. Configure it in M-Claw or provide an authorized environment variable."
        )

    if not chosen_mode:
        chosen_mode = "chat_completions" if chosen_env in {"MOONSHOT_API_KEY", "KIMI_INTL_API_KEY"} else "anthropic_messages"
    aliases = {
        "anthropic": "anthropic_messages",
        "openai": "chat_completions",
    }
    chosen_mode = aliases.get(chosen_mode, chosen_mode)
    if chosen_mode not in {"anthropic_messages", "chat_completions"}:
        raise MediaAnalyzerError(f"Unsupported Kimi API mode: {chosen_mode}")

    if not chosen_base:
        chosen_base = (
            "https://api.kimi.com/coding"
            if chosen_mode == "anthropic_messages"
            else "https://api.moonshot.ai/v1"
        )
    chosen_base = _safe_base_url(chosen_base)
    if not _is_kimi_endpoint(chosen_base):
        raise MediaAnalyzerError(f"Configured endpoint is not a recognized Kimi/Moonshot host: {chosen_base}")

    if not chosen_model:
        chosen_model = "k3" if chosen_mode == "anthropic_messages" else "kimi-k3"
    if media_kind == "video" and chosen_model in {"k3-256k", "kimi-k3-256k"}:
        chosen_model = "k3" if chosen_mode == "anthropic_messages" else "kimi-k3"

    return ProviderSettings(
        provider=provider_name,
        api_mode=chosen_mode,
        base_url=chosen_base,
        model=chosen_model,
        credential_source=source,
        api_key=key,
    )


def validate_media_for_provider(media: MediaInfo, settings: ProviderSettings) -> None:
    if settings.api_mode == "anthropic_messages":
        supported = CODING_IMAGE_MIMES if media.media_kind == "image" else CODING_VIDEO_MIMES
        limit = CODING_IMAGE_LIMIT if media.media_kind == "image" else CODING_VIDEO_LIMIT
        if media.mime_type not in supported:
            raise MediaAnalyzerError(
                f"{media.mime_type} is not supported by the Kimi Coding inline transport"
            )
    else:
        limit = PLATFORM_MEDIA_LIMIT
    if media.size_bytes > limit:
        raise MediaAnalyzerError(
            f"Media is {media.size_bytes} bytes, above the {limit}-byte limit for {settings.api_mode}"
        )


def _endpoint(base_url: str, suffix: str, api_mode: str) -> str:
    normalized = base_url.rstrip("/")
    if api_mode == "anthropic_messages" and not normalized.endswith("/v1"):
        normalized += "/v1"
    return f"{normalized}/{suffix.lstrip('/')}"


def _sanitize_error(text: str, api_key: str) -> str:
    clean = text.replace(api_key, "<redacted>") if api_key else text
    clean = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "<redacted>", clean)
    return clean[:1000]


def default_http_request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes,
    content_type: str,
    timeout: float,
    api_key: str,
) -> HttpResponse:
    request_headers = {**headers, "Content-Type": content_type}
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            response_headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        detail = exc.read(16_384).decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            detail = str((parsed.get("error") or {}).get("message") or detail)
        except (json.JSONDecodeError, AttributeError):
            pass
        raise MediaAnalyzerError(
            f"Kimi API HTTP {exc.code}: {_sanitize_error(detail, api_key)}"
        ) from None
    except urllib.error.URLError as exc:
        raise MediaAnalyzerError(f"Kimi API connection failed: {exc.reason}") from None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise MediaAnalyzerError("Kimi API returned a non-JSON response") from None
    if not isinstance(data, dict):
        raise MediaAnalyzerError("Kimi API returned a non-object JSON response")
    return HttpResponse(data, response_headers)


def _json_request(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    settings: ProviderSettings,
    timeout: float,
    request: HttpRequest,
) -> HttpResponse:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return request("POST", url, headers, body, "application/json", timeout, settings.api_key)


def _prompt(media_kind: str, focus: str | None) -> str:
    extra = f"\nAnalysis focus: {focus.strip()}" if focus and focus.strip() else ""
    return (
        f"Analyze the attached {media_kind}. Record only visually observable evidence. "
        "Use null or empty arrays when information cannot be determined. Do not invent "
        "identities, measurements, timestamps, speech, intent, or hidden events. Scene "
        "timestamps may be approximate and must be non-negative. Confidence is 0 to 1 or null."
        f"{extra}"
    )


def _multipart_file(media: MediaInfo, purpose: str) -> tuple[bytes, str]:
    boundary = f"----kimi-media-{uuid.uuid4().hex}"
    chunks = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\n{purpose}\r\n".encode(),
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"{media.filename.replace(chr(34), '_')}\"\r\n"
            f"Content-Type: {media.mime_type}\r\n\r\n"
        ).encode("utf-8"),
        media.path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _call_anthropic(
    media: MediaInfo,
    settings: ProviderSettings,
    focus: str | None,
    timeout: float,
    request: HttpRequest,
) -> tuple[dict[str, Any], dict[str, Any]]:
    encoded = base64.b64encode(media.path.read_bytes()).decode("ascii")
    payload = {
        "model": settings.model,
        "max_tokens": 8192,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": media.media_kind,
                        "source": {
                            "type": "base64",
                            "media_type": media.mime_type,
                            "data": encoded,
                        },
                    },
                    {"type": "text", "text": _prompt(media.media_kind, focus)},
                ],
            }
        ],
        "tools": [
            {
                "name": "record_media_analysis",
                "description": "Return the complete structured analysis of the attached media.",
                "input_schema": analysis_schema(),
            }
        ],
        "tool_choice": {"type": "tool", "name": "record_media_analysis"},
    }
    headers = {
        "x-api-key": settings.api_key,
        "anthropic-version": "2023-06-01",
    }
    response = _json_request(
        _endpoint(settings.base_url, "messages", settings.api_mode),
        headers,
        payload,
        settings,
        timeout,
        request,
    )
    for block in response.data.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "record_media_analysis":
            value = block.get("input")
            if isinstance(value, dict):
                return value, {
                    "request_id": response.data.get("id") or response.headers.get("request-id"),
                    "usage": response.data.get("usage") if isinstance(response.data.get("usage"), dict) else {},
                    "delivery": "inline_base64",
                    "remote_file_id": None,
                    "remote_file_retained": False,
                }
    raise MediaAnalyzerError("Kimi response did not contain the required structured tool result")


def _call_openai(
    media: MediaInfo,
    settings: ProviderSettings,
    focus: str | None,
    timeout: float,
    request: HttpRequest,
) -> tuple[dict[str, Any], dict[str, Any]]:
    upload_body, upload_type = _multipart_file(media, media.media_kind)
    upload = request(
        "POST",
        _endpoint(settings.base_url, "files", settings.api_mode),
        {"Authorization": f"Bearer {settings.api_key}"},
        upload_body,
        upload_type,
        timeout,
        settings.api_key,
    )
    file_id = upload.data.get("id")
    if not isinstance(file_id, str) or not file_id:
        raise MediaAnalyzerError("Kimi file upload returned no file id")
    part_type = "image_url" if media.media_kind == "image" else "video_url"
    payload = {
        "model": settings.model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {part_type: {"url": f"ms://{file_id}"}, "type": part_type},
                    {"type": "text", "text": _prompt(media.media_kind, focus)},
                ],
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "media_analysis",
                "strict": True,
                "schema": analysis_schema(),
            },
        },
    }
    try:
        response = _json_request(
            _endpoint(settings.base_url, "chat/completions", settings.api_mode),
            {"Authorization": f"Bearer {settings.api_key}"},
            payload,
            settings,
            timeout,
            request,
        )
    except MediaAnalyzerError as exc:
        raise MediaAnalyzerError(
            f"{exc}; uploaded media was retained remotely as {file_id}"
        ) from None
    try:
        content = response.data["choices"][0]["message"]["content"]
        value = content if isinstance(content, dict) else json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise MediaAnalyzerError(
            f"Kimi completion did not contain valid JSON; uploaded media remains as {file_id}"
        ) from None
    if not isinstance(value, dict):
        raise MediaAnalyzerError(f"Kimi analysis is not a JSON object; uploaded media remains as {file_id}")
    return value, {
        "request_id": response.data.get("id") or response.headers.get("x-request-id"),
        "usage": response.data.get("usage") if isinstance(response.data.get("usage"), dict) else {},
        "delivery": "moonshot_file_upload",
        "remote_file_id": file_id,
        "remote_file_retained": True,
    }


def _expect_keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    missing = expected - set(value)
    extra = set(value) - expected
    if missing:
        raise MediaAnalyzerError(f"Analysis validation failed at {path}: missing {sorted(missing)}")
    if extra:
        raise MediaAnalyzerError(f"Analysis validation failed at {path}: unexpected {sorted(extra)}")


def _confidence(value: Any, path: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise MediaAnalyzerError(f"Analysis validation failed at {path}: expected 0..1 or null")


def _nonnegative(value: Any, path: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise MediaAnalyzerError(f"Analysis validation failed at {path}: expected non-negative number or null")


def _string_list(value: Any, path: str) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise MediaAnalyzerError(f"Analysis validation failed at {path}: expected string array")


def validate_analysis(value: Any, media_kind: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MediaAnalyzerError("Analysis validation failed: expected object")
    top = {"media_kind", "summary", "duration_observed_seconds", "scenes", "objects", "visible_text", "risks", "uncertainties"}
    _expect_keys(value, top, "analysis")
    if value["media_kind"] != media_kind:
        raise MediaAnalyzerError("Analysis validation failed: media_kind does not match the input")
    if not isinstance(value["summary"], str):
        raise MediaAnalyzerError("Analysis validation failed at summary: expected string")
    _nonnegative(value["duration_observed_seconds"], "duration_observed_seconds")
    if not isinstance(value["scenes"], list):
        raise MediaAnalyzerError("Analysis validation failed at scenes: expected array")
    scene_keys = {"index", "start_seconds", "end_seconds", "description", "objects", "actions", "visible_text", "confidence"}
    for index, scene in enumerate(value["scenes"]):
        if not isinstance(scene, dict):
            raise MediaAnalyzerError(f"Analysis validation failed at scenes[{index}]: expected object")
        _expect_keys(scene, scene_keys, f"scenes[{index}]")
        if isinstance(scene["index"], bool) or not isinstance(scene["index"], int) or scene["index"] < 0:
            raise MediaAnalyzerError(f"Analysis validation failed at scenes[{index}].index")
        _nonnegative(scene["start_seconds"], f"scenes[{index}].start_seconds")
        _nonnegative(scene["end_seconds"], f"scenes[{index}].end_seconds")
        if not isinstance(scene["description"], str):
            raise MediaAnalyzerError(f"Analysis validation failed at scenes[{index}].description")
        for name in ("objects", "actions", "visible_text"):
            _string_list(scene[name], f"scenes[{index}].{name}")
        _confidence(scene["confidence"], f"scenes[{index}].confidence")
    if not isinstance(value["objects"], list):
        raise MediaAnalyzerError("Analysis validation failed at objects: expected array")
    for index, item in enumerate(value["objects"]):
        if not isinstance(item, dict):
            raise MediaAnalyzerError(f"Analysis validation failed at objects[{index}]")
        _expect_keys(item, {"label", "occurrences", "confidence"}, f"objects[{index}]")
        if not isinstance(item["label"], str):
            raise MediaAnalyzerError(f"Analysis validation failed at objects[{index}].label")
        if isinstance(item["occurrences"], bool) or not isinstance(item["occurrences"], int) or item["occurrences"] < 1:
            raise MediaAnalyzerError(f"Analysis validation failed at objects[{index}].occurrences")
        _confidence(item["confidence"], f"objects[{index}].confidence")
    if not isinstance(value["visible_text"], list):
        raise MediaAnalyzerError("Analysis validation failed at visible_text: expected array")
    for index, item in enumerate(value["visible_text"]):
        if not isinstance(item, dict):
            raise MediaAnalyzerError(f"Analysis validation failed at visible_text[{index}]")
        _expect_keys(item, {"text", "timestamp_seconds", "location", "confidence"}, f"visible_text[{index}]")
        if not isinstance(item["text"], str) or not (item["location"] is None or isinstance(item["location"], str)):
            raise MediaAnalyzerError(f"Analysis validation failed at visible_text[{index}]")
        _nonnegative(item["timestamp_seconds"], f"visible_text[{index}].timestamp_seconds")
        _confidence(item["confidence"], f"visible_text[{index}].confidence")
    _string_list(value["risks"], "risks")
    _string_list(value["uncertainties"], "uncertainties")
    return value


def default_output_path(media_path: Path) -> Path:
    return media_path.with_name(f"{media_path.stem}.kimi-analysis.json")


def _write_json_atomic(path: Path, value: dict[str, Any], force: bool) -> None:
    destination = path.expanduser().resolve()
    if destination.exists() and not force:
        raise MediaAnalyzerError(
            f"Output already exists: {destination}. Refusing to overwrite without --force."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def analyze_media(
    media_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str] | None = None,
    *,
    focus: str | None = None,
    force: bool = False,
    api_mode: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key_env: str | None = None,
    timeout: float = 180.0,
    http_request: HttpRequest = default_http_request,
) -> dict[str, Any]:
    media = inspect_media(media_path)
    destination = Path(output_path).expanduser().resolve() if output_path else default_output_path(media.path)
    if destination.exists() and not force:
        raise MediaAnalyzerError(
            f"Output already exists: {destination}. Refusing to overwrite without --force."
        )
    settings = resolve_provider(
        media.media_kind,
        api_mode=api_mode,
        base_url=base_url,
        model=model,
        api_key_env=api_key_env,
    )
    validate_media_for_provider(media, settings)
    if timeout <= 0:
        raise MediaAnalyzerError("Timeout must be greater than zero")
    if settings.api_mode == "anthropic_messages":
        analysis, metadata = _call_anthropic(media, settings, focus, timeout, http_request)
    else:
        analysis, metadata = _call_openai(media, settings, focus, timeout, http_request)
    validate_analysis(analysis, media.media_kind)
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "path": str(media.path),
            "filename": media.filename,
            "media_kind": media.media_kind,
            "mime_type": media.mime_type,
            "size_bytes": media.size_bytes,
            "sha256": media.sha256,
        },
        "request": {
            "provider": settings.provider,
            "api_mode": settings.api_mode,
            "base_url": settings.base_url,
            "model": settings.model,
            "credential_source": settings.credential_source,
            "request_id": metadata["request_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "delivery": metadata["delivery"],
            "remote_file_id": metadata["remote_file_id"],
            "remote_file_retained": metadata["remote_file_retained"],
            "usage": metadata["usage"],
        },
        "analysis": analysis,
    }
    _write_json_atomic(destination, result, force)
    return result
