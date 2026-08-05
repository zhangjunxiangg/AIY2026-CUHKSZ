---
description: "Deferred supervised HIL execution and evidence tasks"
---

# Tasks: Supervised HIL Validation and Handoff

**Input**: Design documents from `specs/004-hil-validation-handoff/`

**Execution boundary**: Every task below requires later board/robot access. All remain unchecked tonight. `HIL:` means mock, source, or offline evidence cannot complete the task.

**Operator gate**: Before every task attempt that may emit non-zero velocity, present exact parameters, theoretical movement, expected direction, measured clearance, stop method, and risks to the operator beside the robot. Execute only after that operator says `走`; consume the approval after one attempt.

## Phase 0: Local Preparation Completed Offline

- [x] LOC-001 Implement capability-scoped v2 production configuration; preserve v1 full-configuration compatibility.
- [x] LOC-002 Add motion-only measured template without placeholder vision fields and add manifest entries.
- [x] LOC-003 Add local session initializer, manifest validator/local stager, and read-only `/cmd_vel` observer.
- [x] LOC-004 Run offline regression, compile, shell, JSON, source-contract, and manifest checks.

These local tasks do not create HIL evidence and do not change the unchecked status of
T001-T040 below.

## Phase 1: HIL Session Setup

- [ ] T001 HIL: Create the session identity with operator, robot/board IDs, source revision, manifest/configuration/calibration digests, environment, and artifact roots in `control_ws/src/student_tasks/hil/sessions/<session-id>/session.json`
- [ ] T002 HIL: Create the case/evidence directory index and secret-free media index in `control_ws/src/student_tasks/hil/sessions/<session-id>/media-index.json`
- [ ] T003 HIL: Record the exact known-good previous artifact, stage only the reviewed candidate manifest, record modes/digests, and run zero-output smoke as DEP-001 in `control_ws/src/student_tasks/hil/sessions/<session-id>/deployment.json`

**Checkpoint**: One immutable robot/revision/configuration context and rollback target are recorded; the candidate is staged with read-only smoke before physical validation.

---

## Phase 2: Foundational Read-Only and Stop Gates

- [ ] T004 [US1] HIL: Execute PRE-001 board/runtime/revision/manifest/configuration identity preflight and save it in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/PRE-001.json`
- [ ] T005 [US1] HIL: Execute PRE-002 topic/type/subscriber/publisher/process-lock graph preflight with zero non-zero publishes in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/PRE-002.json`
- [ ] T006 [US1] HIL: Execute PRE-003 scan/target dual-time, target-contract/calibration, and persistent-estop preflight in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/PRE-003.json`
- [ ] T007 [US1] HIL: Execute STOP-001 normal explicit zero sequence and save result plus publish evidence in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/STOP-001.json`
- [ ] T008 [US1] HIL: Execute STOP-002 zero-only stop under degraded readiness and save the attempted-zero result in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/STOP-002.json`
- [ ] T009 [US1] HIL: Audit T004-T008 against FR-001-FR-006/FR-016-FR-017/FR-021-FR-022 and mark the preflight gate only in `control_ws/src/student_tasks/hil/sessions/<session-id>/session.json`

**Checkpoint**: Readiness is complete, observed, and zero-only. Any missing/stale/synthetic/conflicting result blocks all later phases.

---

## Phase 3: User Story 2 - Minimum Motion and Safety (Priority: P1)

**Goal**: Measure signs and physical response, then validate ownership, directional lidar, and persistent estop/reset.

**Independent Test**: Each isolated case has one consumed `走` proposal if non-zero occurs, physical evidence, result JSON, and explicit stop; all six signs and all enabled sectors are measured.

- [ ] T010 [US2] HIL: Present a <=0.10 m/s, <=2.0 s forward proposal, obtain fresh `走`, execute DIR-XP once, measure physical direction/displacement, and save `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/DIR-XP.json`
- [ ] T011 [US2] HIL: Present the minimum backward proposal, obtain fresh `走`, execute DIR-XN once, measure physical direction/displacement, and save `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/DIR-XN.json`
- [ ] T012 [US2] HIL: Present the minimum left proposal, obtain fresh `走`, execute DIR-YP once, measure physical direction/displacement, and save `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/DIR-YP.json`
- [ ] T013 [US2] HIL: Present the minimum right proposal, obtain fresh `走`, execute DIR-YN once, measure physical direction/displacement, and save `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/DIR-YN.json`
- [ ] T014 [US2] HIL: Present the minimum counterclockwise proposal, obtain fresh `走`, execute DIR-AZP once, measure physical direction/angle, and save `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/DIR-AZP.json`
- [ ] T015 [US2] HIL: Present the minimum clockwise proposal, obtain fresh `走`, execute DIR-AZN once, measure physical direction/angle, and save `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/DIR-AZN.json`
- [ ] T016 [P] [US2] HIL: Prove a contending project process cannot acquire motion ownership in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/OWN-001.json`
- [ ] T017 [P] [US2] HIL: Capture an unexpected `/cmd_vel` publisher conflict and zero non-zero output in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/OWN-002.json`
- [ ] T018 [US2] HIL: Execute fresh clear and controlled blocked/rejection cases for forward/backward/left/right sectors and save all eight records under `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/SCAN-*.json`
- [ ] T019 [US2] HIL: Trigger the expected safety latch, terminate its process, and prove a new process remains blocked in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/ESTOP-001.json`
- [ ] T020 [US2] HIL: Prove estop reset rejects stale or directionally blocked scans without non-zero output in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/ESTOP-002.json`
- [ ] T021 [US2] HIL: Prove estop reset accepts only the configured consecutive fresh all-direction-clear scans and remains zero-only in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/ESTOP-003.json`
- [ ] T022 [US2] HIL: Audit FR-004-FR-012/FR-016-FR-017/FR-021-FR-022, backfill only dated measured signs/sectors/clearances, and record the safety gate in `control_ws/src/student_tasks/hil/sessions/<session-id>/session.json`

**Checkpoint**: All primitive and safety cases pass in the same context. A failed sign, stop, scan, ownership, or estop case blocks approach.

---

## Phase 4: User Story 3 - Visual Approach (Priority: P2)

**Goal**: Prove the vision-to-motion contract, one-step corrections, safe terminal failures, and independently measured arrival.

**Independent Test**: Ten approach case classes have matching target/scan snapshots, state/result traces, explicit stops, and physical evidence where movement occurs.

- [ ] T023 [US3] HIL: Inspect stationary target schema, frame, confidence, dual timestamps, calibration provenance, bearing, and range in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/TGT-001.json`
- [ ] T024 [US3] HIL: Present one bounded rotation correction, obtain fresh `走`, execute APP-ROT-001 once, record before/after target sign and video in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/APP-ROT-001.json`
- [ ] T025 [US3] HIL: Present one bounded translation correction, obtain fresh `走`, execute APP-TRANS-001 once, record before/after range and video in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/APP-TRANS-001.json`
- [ ] T026 [US3] HIL: Execute target-loss and stale/invalid-target safe terminal cases in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/APP-LOSS-001.json` and `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/APP-STALE-001.json`
- [ ] T027 [US3] HIL: Execute controlled obstacle-interruption and operator-cancellation stop cases in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/APP-OBS-001.json` and `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/APP-CANCEL-001.json`
- [ ] T028 [US3] HIL: Execute timeout/iteration-limit safe termination in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/APP-TIME-001.json`
- [ ] T029 [US3] HIL: Present the bounded full-approach proposal, obtain fresh `走`, execute APP-ARRIVE-001, and record independent final bearing/range evidence in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/APP-ARRIVE-001.json`
- [ ] T030 [US3] HIL: Audit FR-013-FR-017/FR-021-FR-022 and SC-007-SC-009, explicitly rejecting `/odom`-only arrival, in `control_ws/src/student_tasks/hil/sessions/<session-id>/session.json`

**Checkpoint**: The target-to-motion pipeline is accepted only if every mandatory success and failure case safely matches its expected result.

---

## Phase 5: User Story 4 - Deploy, Roll Back, and Hand Off (Priority: P2)

**Goal**: Reproduce the reviewed bundle, retain recovery, and deliver an independently usable integration record.

**Independent Test**: Manifest/digests/modes/smoke/rollback and all public contracts can be understood from the completed deployment and handoff records.

- [ ] T031 [US4] HIL: Audit DEP-001 plus all mandatory HIL evidence and record production acceptance as DEP-ACCEPT-001 in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/DEP-ACCEPT-001.json`
- [ ] T032 [US4] HIL: Audit the exact previous artifact and restoration procedure; if any rollback trigger fired, restore it and record post-rollback read-only preflight in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/RBK-001.json`
- [ ] T033 [US4] HIL: Complete public commands/contracts, verified measurements, accepted cases, errors, limits, blockers, dependency owners, and rollback reference in `control_ws/src/student_tasks/hil/sessions/<session-id>/handoff.json`
- [ ] T034 [US4] HIL: Have the Skill integrator perform the read-only HAND-001 package audit and record acknowledgment in `control_ws/src/student_tasks/hil/sessions/<session-id>/cases/HAND-001.json`
- [ ] T035 [US4] HIL: Audit FR-018-FR-022 and SC-009-SC-010, leaving autonomous startup uninstalled, in `control_ws/src/student_tasks/hil/sessions/<session-id>/session.json`

---

## Phase 6: Final Evidence and Verification Promotion

- [ ] T036 HIL: Validate every case JSON against `specs/004-hil-validation-handoff/contracts/evidence-record.schema.json` and record schema results in `control_ws/src/student_tasks/hil/sessions/<session-id>/evidence-audit.json`
- [ ] T037 HIL: Verify 100% mapping from FR-001-FR-022 and SC-001-SC-010 to accepted case/evidence IDs in `control_ws/src/student_tasks/hil/sessions/<session-id>/traceability.json`
- [ ] T038 HIL: Assign individual case verification levels, preserving `BLOCKED`/`NOT_RUN`/`FAIL`, and set overall `HIL_VERIFIED` only if every mandatory case passes in `control_ws/src/student_tasks/hil/sessions/<session-id>/session.json`
- [ ] T039 HIL: Update `src/robot-control/机器人控制对接文档.md` only with dated measured facts and accepted interface evidence from the completed session
- [ ] T040 HIL: Record final limitations, demo-operating instructions, rollback reference, and owners in `control_ws/src/student_tasks/hil/sessions/<session-id>/handoff.json`

## Dependencies and Execution Order

- T001-T003 establish immutable identity, recovery prerequisites, candidate staging, and zero-output smoke before preflight.
- T004-T009 are a hard zero-output gate before any non-zero task.
- T010-T022 must pass before T023-T030.
- T023 must pass before any visual correction; T024-T028 precede T029 full arrival.
- Deployment/rollback/handoff tasks consume accepted evidence but never retroactively fix missing HIL cases.
- T036-T040 run only after all executed cases have stopped and evidence capture is complete.

## Parallel Opportunities

- T016 and T017 use independent ownership/conflict evidence after primitive directions pass.
- Evidence indexing and filtered-log capture may proceed alongside review, but no two non-zero robot actions run concurrently.
- Handoff drafting may begin after primitive/safety acceptance, but final verification labels wait for the full audit.

## Execution Strategy

1. Stop at read-only readiness if any identity or data fact is uncertain.
2. Prove the stop path before testing the smallest isolated directions.
3. Measure and persist facts; never tune by undocumented guess.
4. Establish safety rejection/recovery before visual movement.
5. Run one-step visual cases before a complete approach.
6. Keep deployment, rollback, and verification promotion explicit and reversible.

## Tonight's Status

All 40 tasks remain intentionally unchecked. Documentation analysis may approve this task plan, but only supervised physical evidence can complete any task.
