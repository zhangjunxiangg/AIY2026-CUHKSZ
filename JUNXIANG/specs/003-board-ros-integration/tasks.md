---
description: "Dependency-ordered source implementation tasks for the ROS1 board adapter"
---

# Tasks: Board ROS Integration

**Input**: Design documents from `specs/003-board-ros-integration/`

**Tests**: Tests and source checks precede implementation. No task in this file authorizes a ROS Master or robot connection.

**Completion target**: `SOURCE_VERIFIED_HIL_PENDING`, never `HIL_VERIFIED`.

## Phase 1: Setup and Test Boundary

- [x] T001 [P] OFFLINE: Create deterministic graph, publisher, subscriber, message, clock, and failure fakes in `control_ws/src/student_tasks/test/fake_ros.py`
- [x] T002 [P] SOURCE: Add a fully null measured-configuration template that cannot pass validation in `control_ws/src/student_tasks/config/robot.measured.template.json`
- [x] T003 OFFLINE: Write failing schema, null, synthetic, timestamp, topic, path, direction-sign, hard-limit, allowlist-evidence, and cross-field tests for FR-015 in `control_ws/src/student_tasks/test/test_production_config.py`
- [x] T004 OFFLINE: Implement standard-library production configuration loading, typed conversion, and aggregated fail-closed findings for FR-015 in `control_ws/src/student_tasks/src/student_tasks/production_config.py`

---

## Phase 2: Foundational Ownership, Estop, and Signals

- [x] T005 [P] OFFLINE: Write failing non-blocking contention, descriptor lifetime, owner metadata, stale record, and safe release tests for FR-005 in `control_ws/src/student_tasks/test/test_process_lock.py`
- [x] T006 OFFLINE: Implement advisory `fcntl` ownership with bounded metadata and identity-safe release for FR-005 in `control_ws/src/student_tasks/src/student_tasks/process_lock.py`
- [x] T007 [P] OFFLINE: Write failing missing-state latch, latch persistence, atomic replacement, mode, corruption, and reset-state tests for FR-019 in `control_ws/src/student_tasks/test/test_estop_store.py`
- [x] T008 OFFLINE: Implement versioned atomic mode-0600 emergency-stop persistence and corrupt-state fail-closed recovery for FR-019 in `control_ws/src/student_tasks/src/student_tasks/estop_store.py`
- [x] T009 [P] OFFLINE: Write failing handler-installation, first-signal, SIGINT/SIGTERM/SIGHUP, cancellation-only handler, and restoration tests for FR-009 in `control_ws/src/student_tasks/test/test_signals.py`
- [x] T010 OFFLINE: Implement thread-safe cancellation state and scoped signal handler restoration for FR-009 in `control_ws/src/student_tasks/src/student_tasks/signals.py`

**Checkpoint**: Production state and ownership primitives work without ROS or network access.

---

## Phase 3: User Story 1 - Inspect Board Readiness Without Motion (Priority: P1)

**Goal**: Provide injectable ROS loading and complete read-only readiness evidence.

**Independent Test**: Fake graph/data fixtures cover available and every blocking condition while imports remain usable with ROS packages blocked.

- [x] T011 [US1] OFFLINE: Write failing lazy-import, explicit-load failure, facade surface, graph, pub/sub, message, time, and English-log tests for FR-001/FR-002 in `control_ws/src/student_tasks/test/test_ros_facade.py`
- [x] T012 [US1] SOURCE: Implement local ROS imports and the narrow real/fake facade boundary for FR-001/FR-002 in `control_ws/src/student_tasks/src/student_tasks/ros_facade.py`
- [x] T013 [US1] OFFLINE: Write failing status tests for Master, subscriber, configuration, authorization, lock availability, persistent estop, directional scan, self-publisher exclusion, empty allowlist, external conflict, and no-motion evidence for FR-004/FR-006 in `control_ws/src/student_tasks/test/test_ros_backend.py`
- [x] T014 [US1] SOURCE: Implement structured ROS readiness, graph snapshots, subscriber inspection, and exact conflict calculation for FR-004/FR-006/FR-018 in `control_ws/src/student_tasks/src/student_tasks/ros_backend.py`

**Checkpoint**: Status never creates a non-zero Twist and reports all readiness blockers deterministically.

---

## Phase 4: User Story 2 - Publish Bounded Movement Through ROS (Priority: P1)

**Goal**: Map the shared core to the one approved ROS output with ownership and stop guarantees.

**Independent Test**: Fake publishers record exact fields/cadence/final zeros and prove zero non-zero messages for every readiness or ownership failure.

- [x] T015 [US2] OFFLINE: Write failing Twist-field, measured-sign, subscriber, authorization, lock, conflict, persistent-estop, fresh directional scan, runtime recheck, stop-under-degradation, and forbidden-interface tests for FR-003/FR-004/FR-007/FR-008/FR-019 in `control_ws/src/student_tasks/test/test_ros_backend.py`
- [x] T016 [US2] OFFLINE: Add failing owned-movement SIGINT/SIGTERM/SIGHUP cancellation and final-stop integration tests for FR-009 in `control_ws/src/student_tasks/test/test_signals.py`
- [x] T017 [US2] SOURCE: Implement ROS motion ownership, Twist construction, per-publish exclusivity/safety/estop checks, zero-sequence evidence, and source verification labels for FR-003/FR-004/FR-007/FR-008/FR-018/FR-019 in `control_ws/src/student_tasks/src/student_tasks/ros_backend.py`

**Checkpoint**: The ROS backend contains no API or executable reference to forbidden motor interfaces and every owned path ends in zeros.

---

## Phase 5: User Story 3 - Run Visual Approach Against ROS Data (Priority: P2)

**Goal**: Convert configured scan/target streams and run one in-process shared-core approach command.

**Independent Test**: Fake subscribers deliver source/receive timing and all valid/invalid messages into the Spec 002 state machine without subprocess motion.

- [x] T018 [US3] OFFLINE: Write failing LaserScan raw-field/source-time/receive-time and target schema/validity/frame/confidence/provenance/staleness conversion tests for FR-010/FR-011 in `control_ws/src/student_tasks/test/test_ros_providers.py`
- [x] T019 [US3] SOURCE: Implement thread-safe scan and versioned JSON target providers with dual-time evidence and structured failures for FR-010/FR-011 in `control_ws/src/student_tasks/src/student_tasks/ros_providers.py`
- [x] T020 [US3] OFFLINE: Write failing CLI ROS selection, no-fallback, authorization, one-result, in-process approach, estop persistence, and clear-scan reset tests for FR-012/FR-013/FR-014/FR-019 in `control_ws/src/student_tasks/test/test_cli.py`
- [x] T021 [US3] SOURCE: Extend backend selection and CLI commands for ROS status/move/stop/approach/estop-reset with direct controller composition for FR-012/FR-013/FR-014/FR-019 in `control_ws/src/student_tasks/src/student_tasks/cli.py`
- [x] T022 [US3] SOURCE: Update the thin executable entry point for scoped signal handling and stable exit behavior for FR-009/FR-013 in `control_ws/src/student_tasks/scripts/robot_control_cli.py`

**Checkpoint**: One approach process owns providers, safety state, core, and backend for its entire feedback loop.

---

## Phase 6: User Story 4 - Prepare a Reproducible Board Bundle (Priority: P2)

**Goal**: Deliver locally verifiable, non-executing deployment assets and a read-only smoke entry.

**Independent Test**: Manifest coverage, paths, modes, wrapper syntax, template rejection, smoke AST behavior, and forbidden/secret exclusions pass locally.

- [x] T023 [US4] OFFLINE: Write failing read-only smoke behavior and AST no-nonzero-request tests for FR-017 in `control_ws/src/student_tasks/test/test_deployment.py`
- [x] T024 [US4] SOURCE: Implement JSON-only read-only graph/config/provider smoke reporting for FR-017/FR-018 in `control_ws/src/student_tasks/scripts/board_smoke_test.py`
- [x] T025 [US4] OFFLINE: Write failing manifest completeness, target-root, wrapper `/bin/run`, shell syntax, template rejection, secret exclusion, and verification-label tests for FR-016/FR-018 in `control_ws/src/student_tasks/test/test_deployment.py`
- [x] T026 [US4] SOURCE: Add ROS runtime dependencies and install entries without auto-start behavior for FR-016 in `control_ws/src/student_tasks/CMakeLists.txt` and `control_ws/src/student_tasks/package.xml`
- [x] T027 [US4] SOURCE: Create the non-executing board manifest, self-contained wrapper, and deployment instructions for FR-016 in `control_ws/src/student_tasks/deploy/board-manifest.json`, `control_ws/src/student_tasks/deploy/robot-control`, and `control_ws/src/student_tasks/deploy/README.md`
- [x] T028 [US4] SOURCE: Add official-topic/type/run-path/watchdog checks and executable forbidden-interface scans for FR-003/FR-018 in `control_ws/src/student_tasks/test/test_source_contracts.py`

**Checkpoint**: Bundle validation succeeds locally but no board operation has occurred.

---

## Phase 7: Polish and Source Verification

- [x] T029 [P] SOURCE: Document ROS CLI examples, measured configuration workflow, and explicit HIL boundary in `control_ws/src/student_tasks/README.md`
- [ ] T030 SOURCE: Execute `specs/003-board-ros-integration/quickstart.md` with ROS/network unavailable and record results in `specs/003-board-ros-integration/verification.md`
- [ ] T031 SOURCE: Audit FR-001 through FR-019 against tests/tasks, run full regression and source scans, and update completion boxes in `specs/003-board-ros-integration/tasks.md`

---

## Dependencies & Execution Order

- Specs 001 and 002 implementation are prerequisites for CLI composition in T020-T022.
- T003, T005, T007, and T009 must fail before their paired implementations T004, T006, T008, and T010.
- User Story 1 establishes the facade/status surface before User Story 2 publishes through it.
- User Story 3 depends on completed backend ownership and provider conversions.
- User Story 4 depends on stable entry points but does not execute them.
- T030-T031 run only after all story checkpoints pass.

## Parallel Opportunities

- T001 and T002 can proceed independently.
- Config, process-lock, estop-store, and signal test files are independent before implementation.
- Provider tests can be written while backend motion tests are being implemented.
- Deployment tests/assets can begin after CLI paths stabilize while source-contract tests are prepared.

## Implementation Strategy

1. Make production configuration impossible to accidentally satisfy with placeholders.
2. Establish lock, persistent latch, and signal cancellation before ROS publishing.
3. Implement status and graph evidence before non-zero behavior.
4. Add publishing only behind the shared controller and both ownership gates.
5. Compose providers and approach in one process.
6. Validate the deployment manifest locally and stop at `SOURCE_VERIFIED_HIL_PENDING`.
