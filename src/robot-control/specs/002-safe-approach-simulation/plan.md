# Implementation Plan: Safe Approach Simulation

**Branch**: `junxiang` | **Date**: 2026-08-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-safe-approach-simulation/spec.md`

## Summary

Extend the shared domain core with pure-Python scan validation, direction-aware clearance decisions, an explicit emergency-stop latch, camera/base target adapters, and a bounded visual approach state machine. Providers and the motion core are injected, so tests drive complete success and failure flows with synthetic data while production values remain unavailable and fail closed.

## Technical Context

**Language/Version**: Python 3.11-compatible standard-library Python  
**Primary Dependencies**: Spec 001 `student_tasks` domain/core modules; no ROS or numeric libraries  
**Storage**: Immutable in-memory observations/configuration plus returned state history  
**Testing**: `unittest`, virtual clock, fake backend, and scripted scan/target providers  
**Target Platform**: macOS offline verification; source-compatible with later M-Robots OS integration  
**Project Type**: Shared Python control library inside the existing ROS1 package layout  
**Performance Goals**: One safety/geometry decision in under 5 ms for 4,000 scan samples on the Mac; no wall-clock sleeps in tests  
**Constraints**: No ROS imports, subprocess motion, network, hardware, guessed production thresholds, or odometry-based arrival  
**Scale/Scope**: Four translation sectors, rotational swept-sector coverage, two target input forms, one active approach workflow

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

- `OFFLINE_VERIFIED`: deterministic scan/sector decisions, latch/reset behavior, coordinate transforms, target rejection, state transitions, and fake-backend terminal stops.
- `SOURCE_VERIFIED_HIL_PENDING`: candidate target topic semantics and ROS LaserScan field mapping, handled by Spec 003.
- HIL remains mandatory for real sector orientation, clearance, braking, direction signs, target accuracy, and arrival.
- Synthetic fixtures and scripted convergence are forbidden physical evidence.

## Project Structure

### Documentation (this feature)

```text
specs/002-safe-approach-simulation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── approach.md
│   ├── safety-decision.schema.json
│   └── target-observation.schema.json
├── checklists/requirements.md
└── tasks.md
```

### Source Code (`src/robot-control/` root)

```text
control_ws/src/student_tasks/
├── config/
│   └── offline.synthetic.json
├── src/student_tasks/
│   ├── approach.py
│   ├── configuration.py
│   ├── geometry.py
│   ├── perception.py
│   └── safety.py
└── test/
    ├── fixtures/
    │   └── safe_approach.json
    ├── test_approach.py
    ├── test_configuration.py
    ├── test_geometry.py
    ├── test_perception.py
    └── test_safety.py
```

**Structure Decision**: Add domain modules to the same package and call `MotionController` in-process. ROS adapters remain separate in Spec 003 so importing any file above cannot contact the board.

## Design

### Directional Safety

1. Normalize scan angles and compute each sample angle from `angle_min + index * angle_increment`.
2. Reject invalid metadata, stale/future scans, empty scans, and inconsistent angular spans.
3. Exclude non-finite, zero, below-minimum, and above-maximum readings. Each required sector must retain its configured minimum sample count.
4. Translation selects `front`, `rear`, `left`, and/or `right` by velocity signs. Any angular velocity selects every configured swept-footprint sector.
5. The decision uses the minimum valid clearance. Any required sector below its measured threshold rejects motion and latches emergency stop.
6. Reset is a separate command. Once requested, only consecutive fresh scans proving every sector clear advance the counter; any invalid/blocked frame resets the counter.

### Target Normalization

1. Base observations require `frame_id=base_link`, freshness, validity, confidence, and finite bounded x/y/z.
2. Pixel-depth input is unprojected using camera optical convention `(right, down, forward)` and then transformed by a validated rigid rotation/translation into `base_link`.
3. A rigid transform must be finite, orthonormal within tolerance, have determinant near +1, and carry provenance/time metadata.
4. Geometry derives `planar_distance=hypot(base_x, base_y)` and `bearing=atan2(base_y, base_x)`; base z is retained only as height.

### Approach State Machine

1. `PRECHECK` obtains fresh target and scan. A target closer than stand-off minus tolerance returns `TARGET_TOO_CLOSE`; v1 does not automatically reverse.
2. `ROTATE` emits one bounded angular correction when bearing exceeds tolerance.
3. `TRANSLATE` emits one bounded positive-x correction when distance exceeds stand-off plus tolerance.
4. Each correction is authorized against the current scan immediately before direct `MotionController.move` invocation.
5. `VERIFY` requires consecutive fresh target observations within both tolerances. Any deviation resets stability and returns to rotate/translate.
6. Target loss grace, total timeout, and iteration count are explicit bounds. Every terminal route passes through `STOPPING` and `MotionController.stop`.

## Complexity Tracking

No constitution violations or duplicated control processes are introduced.
