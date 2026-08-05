# Implementation Plan: Board ROS Integration

**Branch**: `junxiang` | **Date**: 2026-08-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-board-ros-integration/spec.md`

## Summary

Adapt the offline-verified shared controller to ROS1 with lazy imports and a narrow injectable facade. Production motion requires a non-blocking inter-process lock, clean `/cmd_vel` publisher ownership, measured configuration, and explicit operator authorization. Scan and versioned target subscribers feed the in-process approach controller. Signals cancel through the shared stop path, emergency-stop state persists atomically across CLI invocations, and a non-executing board bundle is validated locally.

## Technical Context

**Language/Version**: Python 3.11-compatible; board version to be confirmed by HIL checklist  
**Primary Dependencies**: Standard library; board-provided `rospy`, `rosgraph`, `geometry_msgs`, `sensor_msgs`, `std_msgs` imported lazily  
**Storage**: Versioned JSON production configuration; atomic JSON estop state; advisory `fcntl` lock  
**Testing**: `unittest`, fake ROS facade/messages, subprocess signal tests, source-contract scans, shell/JSON validation  
**Target Platform**: M-Robots OS aarch64 under `/bin/run`; all current validation on macOS without ROS/network  
**Project Type**: ROS1 adapter and synchronous CLI extending the existing Python package  
**Performance Goals**: 20 Hz default publish cadence; provider snapshots under 10 ms; bounded signal-to-cancellation poll at one publish interval in source tests  
**Constraints**: No ROS import in domain path; no board/network access tonight; empty publisher allowlist; no CLI subprocess in approach loop; no synthetic production configuration  
**Scale/Scope**: One CLI/approach process, one project lock, one `/cmd_vel` publisher, one scan provider, one target provider

## Constitution Check

*GATE: Passed before research and re-checked after design.*

- [x] All files are scoped to `src/robot-control/` and no secret path is accessed.
- [x] Vendor interfaces and hard motion limits are preserved.
- [x] CLI and automatic control share one testable control core.
- [x] Every terminal path has an explicit zero-velocity assertion.
- [x] Missing production evidence fails closed instead of using guessed values.
- [x] Offline, source-verified, and HIL evidence are reported separately.
- [x] HIL tasks retain the operator's explicit physical-motion gate.
- [x] Tests precede implementation and every requirement maps to a task.

No violations require justification.

## Verification Boundary

- `OFFLINE_VERIFIED`: configuration/lock/store/facade mechanics and deterministic adapter behavior.
- `SOURCE_VERIFIED_HIL_PENDING`: ROS topic/message mappings and the complete integration bundle after official-source inspection and mock tests.
- `HIL_VERIFIED`: not assignable by this feature.
- No HDC, SSH, ROS Master, network scan, file transfer, or publisher command is part of implementation verification.

## Project Structure

### Documentation (this feature)

```text
specs/003-board-ros-integration/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── deployment.md
│   ├── production-config.schema.json
│   └── ros-integration.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (`src/robot-control/` root)

```text
control_ws/src/student_tasks/
├── config/
│   └── robot.measured.template.json
├── deploy/
│   ├── README.md
│   ├── board-manifest.json
│   └── robot-control
├── scripts/
│   ├── board_smoke_test.py
│   └── robot_control_cli.py
├── src/student_tasks/
│   ├── estop_store.py
│   ├── process_lock.py
│   ├── production_config.py
│   ├── ros_backend.py
│   ├── ros_facade.py
│   ├── ros_providers.py
│   └── signals.py
└── test/
    ├── fake_ros.py
    ├── test_deployment.py
    ├── test_estop_store.py
    ├── test_process_lock.py
    ├── test_production_config.py
    ├── test_ros_backend.py
    ├── test_ros_providers.py
    ├── test_signals.py
    └── test_source_contracts.py
```

**Structure Decision**: ROS-specific modules stay at the package boundary and depend inward on Specs 001/002. The CLI selects them explicitly; fake and domain imports never resolve ROS packages.

## Design

### Lazy ROS Facade

`load_ros_facade()` performs local imports of board modules and returns adapters for graph snapshots, anonymous node initialization, publisher/subscriber creation, message construction, ROS/source time, monotonic time, sleep, shutdown, and English logging. Tests inject `FakeRosFacade`; no module-level ROS import is permitted.

### Ownership and Publishing

1. `MotionLock` uses non-blocking `fcntl.flock`, writes bounded owner metadata after acquisition, holds the descriptor for the full command, and unlinks only its own record after release.
2. `RosMotionBackend` initializes a uniquely named node, creates one `/cmd_vel` publisher, checks at least one subscriber, and reads ROS Master publishers.
3. Conflicts are publishers other than the exact current node and entries in a measured allowlist. The template allowlist is empty.
4. Ownership, conflicts, persistent estop state, and a fresh Spec 002 directional scan decision are rechecked before every non-zero publish. A safety rejection is persisted and any failure raises into `MotionController`'s `finally` stop sequence.
5. Stop can create/use a publisher without satisfying measured motion fields, lock ownership, scan, target, or authorization. It still reports connection/publish failures.

### Providers and Time

- LaserScan conversion copies source stamp, records receive monotonic time, and carries raw metadata/ranges to Spec 002.
- Target JSON must match `robot-control/target-observation/v1`; valid state is separately observed and both source and receive times are preserved.
- Freshness prefers a valid source timestamp and also caps time since receipt. Zero/future/inconsistent source time fails closed.
- The point-only topic may be reported by status but is not sufficient for automatic motion because it lacks confidence/provenance.

### Signals and Persistent Estop

- A guard installs SIGINT/SIGTERM/SIGHUP handlers that only record the signal and set a thread-safe cancellation token.
- Core/approach polling performs stop work outside the signal handler; prior handlers are restored in `finally`.
- `PersistentEstopStore` writes a versioned record to a temporary sibling, flushes/fsyncs, then atomically replaces the configured path with mode `0600`.
- Missing, corrupt, or unreadable production state is represented as latched. `estop-reset` loads that latch, consumes fresh scans through the Spec 002 reset algorithm, and never publishes non-zero velocity.

### Production CLI and Bundle

- `status`, `stop`, and `board_smoke_test.py` are read-only/zero-only and require no motion authorization.
- `move` and `approach` require `--operator-confirmed`; the backend independently enforces authorization, fresh directional scan safety, persistent estop, and ownership so direct shared-core use cannot bypass CLI policy.
- `estop-reset` is zero-only and requires fresh all-direction scan evidence.
- The wrapper sets package `PYTHONPATH` and executes `/bin/run python3` from `/data/local/robot/jx/control_ws/`.
- The manifest documents copying only; no deploy script, SSH target, IP, secret, or init service is included.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Persistent estop JSON in a stateless CLI design | Safety latch must survive a terminated approach process and be reset deliberately | Memory-only latch disappears between invocations; a permanent ROS node is intentionally outside v1 |
