---
description: "Dependency-ordered implementation tasks for the shared motion domain core"
---

# Tasks: Motion Domain Core

**Input**: Design documents from `specs/001-motion-domain-core/`

**Tests**: Tests are mandatory and precede corresponding behavior.

**Verification labels**: `OFFLINE:` is the only completion level in this feature. No task authorizes ROS, network, deployment, or hardware access.

## Phase 1: Setup

- [x] T001 OFFLINE: Create the catkin-compatible package skeleton and Python package markers in `control_ws/src/student_tasks/CMakeLists.txt`, `control_ws/src/student_tasks/package.xml`, and `control_ws/src/student_tasks/src/student_tasks/__init__.py`
- [x] T002 [P] OFFLINE: Document package scope, offline commands, and verification labels in `control_ws/src/student_tasks/README.md`
- [x] T003 [P] OFFLINE: Add the standard-library test import/bootstrap helper in `control_ws/src/student_tasks/test/support.py`

---

## Phase 2: Foundational Domain Contracts

- [x] T004 [P] OFFLINE: Write failing finite-number, planar-magnitude, angular, duration, operation-ID, and forbidden-interface sentinel tests for FR-001/FR-002/FR-012 in `control_ws/src/student_tasks/test/test_limits.py`
- [x] T005 [P] OFFLINE: Write failing serialization and stable-error tests for FR-009 in `control_ws/src/student_tasks/test/test_models.py`
- [x] T006 OFFLINE: Implement hard constants and validation helpers for FR-002/FR-012 in `control_ws/src/student_tasks/src/student_tasks/limits.py`
- [x] T007 OFFLINE: Implement versioned immutable domain values and error taxonomy for FR-001/FR-009 in `control_ws/src/student_tasks/src/student_tasks/models.py` and `control_ws/src/student_tasks/src/student_tasks/errors.py`
- [x] T008 OFFLINE: Define the ROS-free backend protocol and cancellation contract for FR-003/FR-011 in `control_ws/src/student_tasks/src/student_tasks/backend.py`

**Checkpoint**: Domain values reject all unsafe or malformed requests without importing ROS.

---

## Phase 3: User Story 1 - Issue a Bounded Chassis Command (Priority: P1)

**Goal**: Execute one validated bounded request through the shared core with guaranteed final stopping.

**Independent Test**: Deterministic fake events show bounded velocity events followed by the required zero sequence for success, cancellation, timeout, backend failure, and stop failure.

- [ ] T009 [P] [US1] OFFLINE: Write failing deterministic clock, ordered-event, and no-I/O fake-backend tests for FR-006/FR-011 in `control_ws/src/student_tasks/test/test_fake_backend.py`
- [ ] T010 [US1] OFFLINE: Write failing success, validation rejection, cancellation, timeout, backend exception, and stop-failure tests for FR-003/FR-004/FR-005 in `control_ws/src/student_tasks/test/test_core.py`
- [ ] T011 [US1] OFFLINE: Implement the virtual clock, injectable failures, ordered event log, and ownership behavior for FR-006 in `control_ws/src/student_tasks/src/student_tasks/fake_backend.py`
- [ ] T012 [US1] OFFLINE: Implement shared bounded movement, readiness/configuration gates, cancellation, timing, and final stop precedence for FR-003/FR-004/FR-005/FR-010 in `control_ws/src/student_tasks/src/student_tasks/core.py`

**Checkpoint**: User Story 1 passes independently with no real sleeps, ROS imports, or network calls.

---

## Phase 4: User Story 2 - Stop and Inspect the Controller (Priority: P1)

**Goal**: Provide read-only status and idempotent explicit stopping even when movement readiness is false.

**Independent Test**: Status records no velocity event; repeated stop records only zero-velocity events and returns confirmed or failed stop evidence.

- [ ] T013 [US2] OFFLINE: Add failing read-only status, unavailable status, repeated stop, and stop-failure tests for FR-007 in `control_ws/src/student_tasks/test/test_core.py`
- [ ] T014 [US2] OFFLINE: Implement structured status and idempotent stop paths for FR-007/FR-009 in `control_ws/src/student_tasks/src/student_tasks/core.py`

**Checkpoint**: Status and stop are independently usable without enabling non-zero movement.

---

## Phase 5: User Story 3 - Use a Stable Command Contract (Priority: P2)

**Goal**: Expose the shared core through a synchronous, versioned, one-result CLI.

**Independent Test**: Subprocess tests parse exactly one stdout object for success and every exit class while stderr remains separate.

- [ ] T015 [US3] OFFLINE: Write failing subprocess contract tests for commands, output cardinality, schema fields, exit classes, and production fail-closed behavior for FR-008/FR-010 in `control_ws/src/student_tasks/test/test_cli.py`
- [ ] T016 [US3] OFFLINE: Implement parser, fake-backend selection, JSON result output, and stable exit mapping for FR-008/FR-009/FR-010 in `control_ws/src/student_tasks/src/student_tasks/cli.py`
- [ ] T017 [US3] OFFLINE: Add the thin executable entry point that imports the shared CLI for FR-003/FR-008 in `control_ws/src/student_tasks/scripts/robot_control_cli.py`

**Checkpoint**: User Story 3 passes from a clean subprocess and never silently selects production transport.

---

## Phase 6: Polish and Verification

- [ ] T018 [P] OFFLINE: Add public API docstrings and export only stable domain/core symbols in `control_ws/src/student_tasks/src/student_tasks/__init__.py`
- [ ] T019 OFFLINE: Run all commands in `specs/001-motion-domain-core/quickstart.md` and record the offline evidence in `specs/001-motion-domain-core/verification.md`
- [ ] T020 OFFLINE: Run the full package test suite and requirement-to-task audit, then update completed boxes in `specs/001-motion-domain-core/tasks.md`

---

## Dependencies & Execution Order

- Setup tasks T001-T003 precede all source and test work.
- Foundational tests T004-T005 must fail before T006-T008 implement their contracts.
- User Story 1 is the MVP and blocks User Story 2 because both use `MotionController`.
- User Story 3 depends on the completed core but not on any ROS feature.
- T019-T020 run only after all story checkpoints pass.

## Parallel Opportunities

- T002 and T003 touch independent documentation/test-bootstrap files.
- T004 and T005 cover independent limit and model contracts.
- T009 can be written alongside T010 before implementation begins.
- T018 can proceed after the public API stabilizes while quickstart evidence is prepared.

## Implementation Strategy

1. Complete the domain validation and fake backend before any CLI code.
2. Make every terminal-path test fail for the intended reason, then implement the smallest shared-core behavior that passes it.
3. Add status/stop as a separate independently testable slice.
4. Add the CLI only as an adapter; no control behavior may be duplicated there.
5. Stop at `OFFLINE_VERIFIED`; do not deploy or infer physical behavior.
