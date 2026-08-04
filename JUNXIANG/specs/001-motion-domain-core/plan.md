# Implementation Plan: Motion Domain Core

**Branch**: `junxiang` | **Date**: 2026-08-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-motion-domain-core/spec.md`

## Summary

Build the hardware-independent foundation used by both the board CLI and the later visual controller. A single `MotionController` owns validation, backend readiness checks, bounded publish loops, cancellation handling, result construction, and final stop semantics. A deterministic fake backend and injectable clock make every behavior testable without ROS, networking, or hardware.

## Technical Context

**Language/Version**: Python 3.11-compatible syntax; developed on Python 3.14 and source-checked for the board runtime  
**Primary Dependencies**: Python standard library only in the domain core  
**Storage**: Read-only runtime configuration objects; no database  
**Testing**: `unittest` with deterministic fake clock/backend; subprocess contract tests  
**Target Platform**: macOS arm64 for offline verification; M-Robots OS aarch64 for later integration  
**Project Type**: Pure Python library plus synchronous CLI inside a ROS1 package layout  
**Performance Goals**: Deterministic bounded loop at configurable 10-20 Hz; local command startup under 1 second  
**Constraints**: No ROS imports in domain modules; standard library only; zero network access in fake mode; explicit stop on every owned terminal path  
**Scale/Scope**: One chassis owner, one active motion, three commands, and a small stable error taxonomy

## Constitution Check

*GATE: Passed before research and re-checked after design.*

- [x] All files are scoped to `JUNXIANG/` and no secret path is accessed.
- [x] Vendor interfaces and hard motion limits are preserved.
- [x] CLI and automatic control share one testable control core.
- [x] Every terminal path has an explicit zero-velocity assertion.
- [x] Missing production evidence fails closed instead of using guessed values.
- [x] Offline, source-verified, and HIL evidence are reported separately.
- [x] HIL tasks retain the operator's explicit physical-motion gate.
- [x] Tests precede implementation and every requirement maps to a task.

No justified violations are required.

## Verification Boundary

- `OFFLINE_VERIFIED`: domain validation, fake-backend event order, loop timing, terminal stops, result serialization, and CLI exit mapping.
- Source evidence only: vendor hard limits and coordinate convention.
- Deferred HIL: physical direction, displacement, real publish cadence, and stop effectiveness.
- Fake events and local elapsed time are forbidden as HIL evidence.

## Project Structure

### Documentation (this feature)

```text
specs/001-motion-domain-core/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── motion-request.schema.json
│   └── motion-result.schema.json
├── checklists/requirements.md
└── tasks.md
```

### Source Code (`JUNXIANG/` root)

```text
control_ws/src/student_tasks/
├── CMakeLists.txt
├── package.xml
├── README.md
├── scripts/
│   └── robot_control_cli.py
├── src/student_tasks/
│   ├── __init__.py
│   ├── backend.py
│   ├── cli.py
│   ├── core.py
│   ├── errors.py
│   ├── fake_backend.py
│   ├── limits.py
│   └── models.py
└── test/
    ├── test_cli.py
    ├── test_core.py
    └── test_limits.py
```

**Structure Decision**: Use the official independent catkin-package shape while keeping all domain modules importable as ordinary Python. Later ROS files extend this package rather than creating a second control implementation.

## Design

1. Immutable domain values validate finite numbers, coordinate convention, hard limits, durations, and verification labels.
2. `MotionBackend` is a structural protocol for status, readiness, ownership, velocity publishing, time, and sleep. Domain code knows no ROS types.
3. `MotionController` validates before ownership, acquires one motion session, publishes at a bounded rate, and attempts a configurable zero-velocity sequence in `finally` before releasing ownership.
4. Stop failure has precedence in safety reporting: an original exception remains in details, but the stable terminal code identifies that zero velocity could not be confirmed.
5. `FakeBackend` owns a fake monotonic clock and ordered immutable events. Its type cannot resolve a ROS backend or perform network I/O.
6. The CLI selects fake mode explicitly for offline use. Production backend selection is defined later; requesting it before integration returns a fail-closed error.

## Complexity Tracking

No constitution violations or additional projects are introduced.
