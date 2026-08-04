---
description: "Dependency-ordered tasks for offline lidar safety and visual approach"
---

# Tasks: Safe Approach Simulation

**Input**: Design documents from `specs/002-safe-approach-simulation/`

**Tests**: All behavior is test-first. Synthetic evidence completes only `OFFLINE` tasks.

## Phase 1: Setup and Synthetic Boundaries

- [x] T001 [P] OFFLINE: Add explicitly synthetic scan, target, calibration, and convergence fixtures in `control_ws/src/student_tasks/test/fixtures/safe_approach.json`
- [x] T002 [P] OFFLINE: Add the offline-only configuration with provenance and non-production warning in `control_ws/src/student_tasks/config/offline.synthetic.json`
- [x] T003 OFFLINE: Write failing provenance, measured timestamp, and synthetic-production rejection tests for FR-015 in `control_ws/src/student_tasks/test/test_configuration.py`
- [x] T004 OFFLINE: Implement immutable provenance and configuration validation for FR-015 in `control_ws/src/student_tasks/src/student_tasks/configuration.py`

---

## Phase 2: Foundational Geometry

- [x] T005 OFFLINE: Write failing finite-vector, intrinsics, rigid-rotation, determinant, unprojection, transform, planar-distance, and bearing tests for FR-008/FR-009 in `control_ws/src/student_tasks/test/test_geometry.py`
- [x] T006 OFFLINE: Implement standard-library vector, intrinsics, rigid-transform, unprojection, and base-geometry helpers for FR-008/FR-009 in `control_ws/src/student_tasks/src/student_tasks/geometry.py`

**Checkpoint**: Camera-forward depth transforms into base x/y/z, and base z is never used as forward distance.

---

## Phase 3: User Story 1 - Directional Lidar Safety (Priority: P1)

**Goal**: Produce deterministic fail-closed safety decisions for every velocity direction.

**Independent Test**: Synthetic scans cover all single directions, diagonals, rotation, boundary angles, stale/future metadata, invalid ranges, insufficient samples, and obstacles.

- [x] T007 [US1] OFFLINE: Write failing scan metadata, range filtering, wrap-around sector, and sample-sufficiency tests for FR-001/FR-003 in `control_ws/src/student_tasks/test/test_safety.py`
- [x] T008 [US1] OFFLINE: Write failing direction-selection, diagonal-union, full-rotation, zero-velocity, and structured-evidence tests for FR-002/FR-004/FR-006 in `control_ws/src/student_tasks/test/test_safety.py`
- [x] T009 [US1] OFFLINE: Implement scan validation, normalized angular sectors, conservative clearance, and evidence models for FR-001/FR-003 in `control_ws/src/student_tasks/src/student_tasks/safety.py`
- [x] T010 [US1] OFFLINE: Implement velocity-to-sector selection and fail-closed decision evaluation for FR-002/FR-004/FR-006 in `control_ws/src/student_tasks/src/student_tasks/safety.py`

**Checkpoint**: No non-zero direction is allowed without fresh sufficient clearance in every required sector.

---

## Phase 4: User Story 2 - Latched Emergency Stop (Priority: P1)

**Goal**: Preserve an emergency stop until deliberate, stable, all-direction reset evidence exists.

**Independent Test**: Alternating clear/blocked/stale sequences prove latch persistence and exact reset-counter behavior.

- [x] T011 [US2] OFFLINE: Add failing latch trigger, clear-without-reset, reset request, counter reset, and exact stable-threshold tests for FR-004/FR-005/FR-006 in `control_ws/src/student_tasks/test/test_safety.py`
- [x] T012 [US2] OFFLINE: Implement latch state transitions, reason preservation, explicit reset, and consecutive clear-frame accounting for FR-004/FR-005/FR-006 in `control_ws/src/student_tasks/src/student_tasks/safety.py`

**Checkpoint**: Clear scans alone never resume non-zero motion.

---

## Phase 5: User Story 3 - Normalize Visual Targets (Priority: P1)

**Goal**: Convert both supported target forms into one validated `base_link` target with traceable evidence.

**Independent Test**: Known coordinate fixtures pass within `1e-6 m`; all freshness, validity, frame, confidence, depth, and calibration failures return stable errors.

- [x] T013 [US3] OFFLINE: Write failing base-target validation and geometry tests for FR-007/FR-009 in `control_ws/src/student_tasks/test/test_perception.py`
- [x] T014 [US3] OFFLINE: Write failing pixel-depth, camera-frame, intrinsics, transform freshness, and provenance tests for FR-008/FR-015 in `control_ws/src/student_tasks/test/test_perception.py`
- [x] T015 [US3] OFFLINE: Implement base target, pixel-depth target, calibration, normalized target, and stable rejection models for FR-007/FR-008/FR-009/FR-015 in `control_ws/src/student_tasks/src/student_tasks/perception.py`

**Checkpoint**: Every accepted target is fresh, valid, confidence-qualified, and explicitly in `base_link`.

---

## Phase 6: User Story 4 - Approach and Verify in One Process (Priority: P2)

**Goal**: Execute bounded rotate/translate corrections with fresh safety authorization and stable visual success.

**Independent Test**: Scripted providers and fake backend cover convergent success plus every documented terminal failure and stop path.

- [x] T016 [US4] OFFLINE: Write failing state ordering, direct-core invocation, rotate sign, positive-x translation, too-close refusal, and per-step re-observation tests for FR-010/FR-011/FR-012 in `control_ws/src/student_tasks/test/test_approach.py`
- [x] T017 [US4] OFFLINE: Write failing stable visual verification, odometry-exclusion, target-loss, estop, cancellation, timeout, iteration, motion-failure, and stop-failure tests for FR-013/FR-014 in `control_ws/src/student_tasks/test/test_approach.py`
- [x] T018 [US4] OFFLINE: Implement approach configuration, providers, state/result models, and bounded state machine for FR-010/FR-011/FR-012/FR-013 in `control_ws/src/student_tasks/src/student_tasks/approach.py`
- [x] T019 [US4] OFFLINE: Implement terminal stop convergence, state history, safety evidence, and stable error precedence for FR-014 in `control_ws/src/student_tasks/src/student_tasks/approach.py`

**Checkpoint**: Approach succeeds only from stable fresh vision and always terminates with an explicit shared-core stop.

---

## Phase 7: Polish and Verification

- [ ] T020 [P] OFFLINE: Export only stable safety, perception, and approach APIs and document coordinate units in `control_ws/src/student_tasks/src/student_tasks/__init__.py`
- [ ] T021 OFFLINE: Run performance and full offline quickstart scenarios and record evidence in `specs/002-safe-approach-simulation/verification.md`
- [ ] T022 OFFLINE: Audit FR-001 through FR-015 against automated tests, run the full suite, and update completion boxes in `specs/002-safe-approach-simulation/tasks.md`

---

## Dependencies & Execution Order

- Spec 001 must be implemented before T016-T019 can call its shared core.
- T003 must fail before T004; T005 before T006.
- User Story 1 precedes User Story 2 because the latch consumes safety decisions.
- User Story 3 depends on foundational geometry but is otherwise independent from lidar work.
- User Story 4 depends on User Stories 1-3 and the Spec 001 core.
- T021-T022 run only after every story checkpoint passes.

## Parallel Opportunities

- T001 and T002 touch independent fixture/config files.
- After geometry is complete, target-adapter tests can be written while lidar safety tests are being implemented.
- Public API documentation can be prepared after interfaces stabilize while verification scenarios run.

## Implementation Strategy

1. Lock synthetic-versus-measured provenance before accepting any configuration.
2. Establish coordinate math independently from perception policy.
3. Complete safety and latch behavior before writing the approach workflow.
4. Drive the entire workflow from scripted providers and the Spec 001 fake backend.
5. Finish at `OFFLINE_VERIFIED`; leave every physical threshold and calibration as HIL work.
