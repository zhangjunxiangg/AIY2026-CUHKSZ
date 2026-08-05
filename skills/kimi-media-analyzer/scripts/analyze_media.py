#!/usr/bin/env python3
"""Standalone command for the kimi-media-analyzer Skill."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from media_analyzer import (
    MediaAnalyzerError,
    analyze_media,
    default_output_path,
    inspect_media,
    resolve_provider,
    validate_media_for_provider,
)


def _bootstrap_mclaw_runtime() -> None:
    try:
        import mclaw  # noqa: F401

        return
    except (ImportError, ModuleNotFoundError):
        pass
    if os.environ.get("KIMI_MEDIA_BOOTSTRAPPED") == "1":
        return
    run_wrapper = Path("/bin/run")
    if run_wrapper.exists() and os.access(run_wrapper, os.X_OK):
        environment = dict(os.environ)
        environment["KIMI_MEDIA_BOOTSTRAPPED"] = "1"
        os.execve(str(run_wrapper), [str(run_wrapper), "python3", str(Path(__file__).resolve()), *sys.argv[1:]], environment)
    mclaw_command = shutil.which("mclaw")
    if not mclaw_command:
        return
    try:
        first_line = Path(mclaw_command).read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return
    if not first_line.startswith("#!"):
        return
    interpreter = first_line[2:].strip()
    if not Path(interpreter).is_file():
        return
    environment = dict(os.environ)
    environment["KIMI_MEDIA_BOOTSTRAPPED"] = "1"
    os.execve(interpreter, [interpreter, str(Path(__file__).resolve()), *sys.argv[1:]], environment)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze a local image or video with Kimi and save validated JSON."
    )
    parser.add_argument("media_path", help="Local image or video path")
    parser.add_argument("--output", help="Destination JSON path")
    parser.add_argument("--focus", help="Optional analysis focus while keeping the stable schema")
    parser.add_argument("--force", action="store_true", help="Overwrite the exact output path if it exists")
    parser.add_argument("--model", help="Override the Kimi model id")
    parser.add_argument("--base-url", help="Override the configured Kimi API base URL")
    parser.add_argument("--api-key-env", help="Name of the authorized environment variable containing the key")
    parser.add_argument(
        "--api-mode",
        choices=("anthropic", "openai", "openrouter"),
        help="Override transport: anthropic for Coding Plan, openai for Moonshot Platform, openrouter for OpenRouter Kimi K3",
    )
    parser.add_argument("--timeout", type=float, default=180.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate media and show secret-free resolved configuration without calling Kimi",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _bootstrap_mclaw_runtime()
    args = _parser().parse_args(argv)
    mode = {
        "anthropic": "anthropic_messages",
        "openai": "chat_completions",
        "openrouter": "openrouter",
    }.get(args.api_mode)
    try:
        media = inspect_media(args.media_path)
        settings = resolve_provider(
            media.media_kind,
            api_mode=mode,
            base_url=args.base_url,
            model=args.model,
            api_key_env=args.api_key_env,
        )
        validate_media_for_provider(media, settings)
        output = Path(args.output).expanduser().resolve() if args.output else default_output_path(media.path)
        if args.check_only:
            print(json.dumps({
                "ok": True,
                "media_path": str(media.path),
                "media_kind": media.media_kind,
                "mime_type": media.mime_type,
                "size_bytes": media.size_bytes,
                "output": str(output),
                "provider": settings.provider,
                "api_mode": settings.api_mode,
                "base_url": settings.base_url,
                "model": settings.model,
                "credential_source": settings.credential_source,
                "api_key": "<redacted>",
                "network_called": False,
            }, ensure_ascii=False, indent=2))
            return 0
        result = analyze_media(
            media.path,
            output,
            focus=args.focus,
            force=args.force,
            api_mode=mode,
            base_url=args.base_url,
            model=args.model,
            api_key_env=args.api_key_env,
            timeout=args.timeout,
        )
        print(json.dumps({
            "ok": True,
            "output": str(output),
            "schema_version": result["schema_version"],
            "model": result["request"]["model"],
            "summary": result["analysis"]["summary"],
            "uncertainties": result["analysis"]["uncertainties"],
        }, ensure_ascii=False, indent=2))
        return 0
    except MediaAnalyzerError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
