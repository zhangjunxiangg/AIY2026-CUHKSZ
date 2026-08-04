"""Synchronous one-result command adapter for the shared controller."""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Sequence
from typing import TextIO

from .core import MotionController
from .errors import ControlError, ControlFailure, ErrorCategory, control_error
from .fake_backend import FakeBackend
from .models import MotionRequest, MotionResult, Velocity, VerificationLevel


EXIT_BY_CATEGORY = {
    ErrorCategory.USAGE: 2,
    ErrorCategory.VALIDATION: 2,
    ErrorCategory.UNAVAILABLE: 3,
    ErrorCategory.RUNTIME: 4,
    ErrorCategory.STOP_SAFETY: 5,
}


class _UsageFailure(Exception):
    pass


class _ContractParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _UsageFailure(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _ContractParser(prog="robot-control", add_help=True)
    parser.add_argument("--backend", choices=("fake", "ros"), default="fake")
    parser.add_argument("--config")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_ContractParser)
    commands.add_parser("status", help="Report backend readiness without motion")
    commands.add_parser("stop", help="Attempt the explicit zero sequence")
    move = commands.add_parser("move", help="Execute one bounded motion request")
    move.add_argument("--linear-x", required=True, type=float)
    move.add_argument("--linear-y", required=True, type=float)
    move.add_argument("--angular-z", required=True, type=float)
    move.add_argument("--duration", required=True, type=float)
    move.add_argument("--publish-rate", type=float, default=20.0)
    move.add_argument("--operation-id")
    return parser


def _failure_result(
    operation: str,
    backend: str,
    error: ControlError,
    *,
    operation_id: str | None = None,
    data: dict[str, object] | None = None,
) -> MotionResult:
    return MotionResult(
        operation=operation,
        operation_id=operation_id,
        ok=False,
        backend=backend,
        verification=VerificationLevel.OFFLINE_VERIFIED,
        zero_velocity_attempted=False,
        zero_velocity_confirmed=False,
        elapsed_s=0.0,
        data=data or {},
        error=error,
    )


def _infer_operation(arguments: Sequence[str]) -> str:
    for value in arguments:
        if value in {"status", "move", "stop"}:
            return value
    return "status"


def _infer_backend(arguments: Sequence[str]) -> str:
    try:
        index = arguments.index("--backend")
        return arguments[index + 1]
    except (ValueError, IndexError):
        return "fake"


def _run_parsed(arguments: argparse.Namespace) -> MotionResult:
    if arguments.backend == "ros":
        return _failure_result(
            arguments.command,
            "ros",
            control_error("BACKEND_UNAVAILABLE", "ROS backend is not available in this feature"),
            operation_id=getattr(arguments, "operation_id", None),
            data={"fallback_used": False, "config": arguments.config},
        )

    backend = FakeBackend()
    controller = MotionController(backend)
    if arguments.command == "status":
        return controller.status()
    if arguments.command == "stop":
        return controller.stop()
    if arguments.command == "move":
        operation_id = arguments.operation_id or "move-%s" % uuid.uuid4().hex
        request = MotionRequest(
            operation_id=operation_id,
            velocity=Velocity(arguments.linear_x, arguments.linear_y, arguments.angular_z),
            duration_s=arguments.duration,
            publish_rate_hz=arguments.publish_rate,
        )
        return controller.move(request)
    return _failure_result(
        "status",
        arguments.backend,
        control_error("INVALID_INPUT", "unknown command"),
    )


def exit_code_for(result: MotionResult) -> int:
    if result.ok:
        return 0
    if result.error is None:
        return 4
    return EXIT_BY_CATEGORY[result.error.category]


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Parse, execute once, and write exactly one JSON object to stdout."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    output = sys.stdout if stdout is None else stdout
    diagnostics = sys.stderr if stderr is None else stderr
    operation = _infer_operation(arguments)
    backend = _infer_backend(arguments)

    try:
        parsed = build_parser().parse_args(arguments)
        operation = parsed.command
        backend = parsed.backend
        result = _run_parsed(parsed)
    except _UsageFailure as exc:
        diagnostics.write("error: %s\n" % exc)
        result = _failure_result(operation, backend, control_error("INVALID_INPUT", str(exc)))
    except ControlFailure as exc:
        result = _failure_result(operation, backend, exc.error, data=dict(exc.context))
    except KeyboardInterrupt:
        result = _failure_result(operation, backend, control_error("CANCELLED", "command was interrupted"))
    except Exception as exc:
        diagnostics.write("error: internal command failure\n")
        result = _failure_result(
            operation,
            backend,
            control_error("BACKEND_FAILURE", "command failed: %s" % exc),
        )

    output.write(result.to_json())
    output.write("\n")
    output.flush()
    return exit_code_for(result)
