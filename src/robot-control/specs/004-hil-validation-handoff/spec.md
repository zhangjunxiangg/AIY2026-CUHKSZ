# Feature Specification: Supervised HIL Validation and Handoff

**Feature Branch**: `junxiang`  
**Created**: 2026-08-05  
**Status**: Draft - HIL execution deferred  
**Input**: Define the supervised board-validation, evidence, deployment, rollback, and teammate-handoff process for the motion-control deliverables. No physical execution is authorized while the operator is away from the robot.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Establish read-only board readiness (Priority: P1)

As the motion-control operator, I can prove that the intended board, runtime, configuration, ROS graph, sensors, and ownership conditions are ready before any motion is proposed.

**Why this priority**: A wrong board, stale configuration, missing scan, or competing publisher makes every subsequent physical result unsafe or meaningless.

**Independent Test**: Complete a read-only preflight record containing board identity, source revision, runtime version, configuration provenance, topic/type snapshots, current publishers/subscribers, persistent-estop state, and smoke output without issuing non-zero velocity.

**Acceptance Scenarios**:

1. **Given** the operator is beside a powered robot, **When** the read-only preflight is performed, **Then** every required identity, graph, configuration, and data-readiness field is recorded before motion authorization is requested.
2. **Given** any required field is absent, stale, synthetic, inconsistent, or unmeasured, **When** preflight is evaluated, **Then** the session is blocked with a named reason and no non-zero command is proposed.
3. **Given** an unexpected `/cmd_vel` publisher or unknown deployed revision, **When** ownership is checked, **Then** the session remains blocked until the conflict is deliberately resolved and a new snapshot is recorded.

---

### User Story 2 - Validate minimum bounded motion and safety (Priority: P1)

As the operator beside the robot, I can validate stop, direction signs, motion bounds, lidar sectors, and persistent emergency-stop behavior one isolated step at a time.

**Why this priority**: These measurements determine whether later visual corrections command the expected physical direction and stop safely around obstacles.

**Independent Test**: Execute the minimum supervised matrix in a cleared area, with a separate proposal and explicit `走` response for every non-zero action, and record observed direction, displacement, stopping, scan evidence, estop persistence, and reset evidence.

**Acceptance Scenarios**:

1. **Given** preflight passes and the area is clear, **When** a minimum motion is proposed with exact velocity, duration, expected displacement, clearance, and risk, **Then** no movement occurs until the nearby operator explicitly says `走` for that one action.
2. **Given** authorization is granted, **When** the first x, y, or angular direction check runs, **Then** it uses the smallest practical bounded command and terminates with recorded zero-velocity evidence before another proposal.
3. **Given** the observed direction differs from the proposal or the operator calls stop, **When** the discrepancy is detected, **Then** further non-zero checks stop, the estop/zero path is exercised, and configuration is not silently edited from assumption.
4. **Given** an obstacle enters the active direction sector or scan evidence becomes stale, **When** motion is requested or is in progress, **Then** non-zero output is rejected or stopped and the trigger is recorded.
5. **Given** emergency stop has latched across process exit, **When** reset is requested, **Then** only a zero-output reset with consecutive fresh all-direction-clear scans may clear it.

---

### User Story 3 - Validate visual approach under supervision (Priority: P2)

As the operator and vision teammate, we can prove that target frames, calibration provenance, correction directions, target-loss handling, obstacle response, and final tolerance work together without relying on open-loop odometry as arrival proof.

**Why this priority**: The team's higher-level Skill depends on a trustworthy target-to-motion contract, but it must build on already accepted primitive motion and safety behavior.

**Independent Test**: Run a staged visual-approach matrix from stationary observation through one-step corrections to a bounded complete approach, recording target and scan inputs, state transitions, commands, stop evidence, final physical measurements, and failure cases.

**Acceptance Scenarios**:

1. **Given** primitive motion and safety acceptance has passed, **When** a stationary target observation is inspected, **Then** schema, frame, confidence, freshness, calibration provenance, bearing, and range are recorded before correction is enabled.
2. **Given** one correction is proposed, **When** the operator authorizes it with `走`, **Then** observed physical rotation/translation agrees with the target error sign and a fresh observation is required before the next correction.
3. **Given** target loss, stale data, invalid calibration, low confidence, obstacle detection, timeout, or operator cancellation, **When** approach is active, **Then** it terminates in explicit stop with a stable recorded reason.
4. **Given** the controller reports arrival, **When** the final result is accepted, **Then** independent physical/vision evidence confirms the documented tolerance; `/odom` alone cannot establish success.

---

### User Story 4 - Deploy, roll back, and hand off reproducibly (Priority: P2)

As the team integrator, I can deploy only the reviewed manifest, reproduce the accepted configuration, restore the previous version if validation fails, and consume a concise interface/evidence package.

**Why this priority**: A passing one-off terminal session is not a usable team capability unless its exact revision, configuration, invocation, rollback, and remaining limitations are known.

**Independent Test**: Review a completed deployment record linking source revision, manifest digest, board paths, measured configuration, HIL cases, rollback artifact, interface examples, and unresolved blockers.

**Acceptance Scenarios**:

1. **Given** source/offline gates pass and the previous artifact is recoverable, **When** the candidate is staged for HIL, **Then** only manifest-listed files are copied to the documented target root, read-only smoke passes before movement, and production acceptance remains pending until mandatory HIL passes.
2. **Given** smoke or minimum acceptance fails after deployment, **When** rollback is invoked, **Then** the previous known revision is restored and a read-only post-rollback check is recorded before any new movement proposal.
3. **Given** evidence is handed to the Skill integrator, **When** they review it, **Then** they can identify commands/contracts, verified limits, measured configuration, known failure codes, verification level, and every remaining HIL limitation without inspecting private notes.

### Edge Cases

- A verbal `走` applies only to the immediately preceding proposal; it expires after any parameter, environment, board state, or configuration change.
- Silence, ambiguous language, remote chat approval, or approval from a person not beside the robot is not motion authorization.
- Every new non-zero command, including a retry with identical parameters and every visual-approach run, requires a fresh proposal and fresh `走`.
- An emergency or zero command does not wait for `走`; stopping is always allowed.
- The first physical movement after reboot, redeploy, configuration change, direction-sign change, or safety-threshold change returns to the minimum-command gate.
- A physically obstructed wheel, lifted chassis, low battery, loose cable, or moved sensor invalidates affected evidence and is recorded rather than averaged away.
- Source timestamps that are zero, future, discontinuous, or inconsistent with receipt time block freshness acceptance.
- HIL results from a different robot identity, deployed revision, calibration, or configuration digest do not transfer automatically.
- Video loss does not by itself invalidate numeric logs, but it blocks any criterion that explicitly requires visible physical-direction or clearance evidence.
- A partial test session remains useful evidence, but unchecked cases stay `HIL_PENDING` and the feature cannot be labeled globally `HIL_VERIFIED`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The HIL procedure MUST begin with a zero-output, read-only preflight and MUST prohibit non-zero proposals until all mandatory readiness fields pass.
- **FR-002**: Preflight MUST record date/time, operator, robot identity, board identity, source revision, deployment-manifest digest, runtime/Python/ROS versions, measured-configuration digest, power/environment notes, and verification-artifact paths.
- **FR-003**: Preflight MUST record configured topic names and observed message types, `/cmd_vel` subscribers and publishers, scan freshness, target freshness/schema/frame/confidence/provenance, process-lock availability, and persistent-estop state.
- **FR-004**: Every non-zero HIL action MUST have a discrete proposal stating velocity components, duration, theoretical maximum displacement/rotation, expected physical direction, required clearance, stop method, and specific risks.
- **FR-005**: Every non-zero HIL action MUST require the operator to be physically beside the robot and explicitly say `走` after reviewing its proposal; authorization MUST be single-use and MUST NOT be inferred or carried forward.
- **FR-006**: Stop, estop, and zero-velocity commands MUST remain immediately available without motion authorization.
- **FR-007**: The first movement in each affected test context MUST use the smallest practical command, with default starting values no greater than `0.10 m/s` for `2.0 s` and a comparably small rotation, while all constitutional hard limits remain enforced.
- **FR-008**: Direction acceptance MUST separately measure forward/backward, left/right, and counterclockwise/clockwise signs and MUST not derive a missing direction only by assumption.
- **FR-009**: Each bounded-motion record MUST include requested values, actual start/end time, observed direction, measured displacement or angle where feasible, publish/stop evidence, result code, and pass/fail rationale.
- **FR-010**: Lidar acceptance MUST measure direction-sector association, clear and blocked distances, freshness, minimum valid samples, and stop/rejection response for each enabled motion direction.
- **FR-011**: Persistent-estop acceptance MUST prove latch survival across process exit and MUST prove reset remains zero-only and requires the configured consecutive fresh all-direction-clear observations.
- **FR-012**: Any unexpected direction, uncontrolled continuation, ownership conflict, stale safety data, invalid configuration, or operator concern MUST terminate the active case and block later non-zero cases until a documented re-preflight passes.
- **FR-013**: Visual-approach HIL MUST be gated on accepted primitive direction, stop, lidar, target-contract, and calibration evidence from the same robot/revision/configuration context.
- **FR-014**: Visual-approach cases MUST cover stationary inspection, one authorized rotation correction, one authorized translation correction, target loss, stale/invalid target, obstacle interruption, operator cancellation, timeout/iteration limit, and bounded arrival.
- **FR-015**: Approach arrival MUST be accepted using recorded physical or calibrated vision measurements within configured bearing and stand-off tolerances; `/odom` alone MUST NOT count as arrival evidence.
- **FR-016**: Every case MUST record command/result JSON, filtered English runtime logs, relevant scan/target snapshots, configuration/revision digests, and required photo/video evidence without secrets.
- **FR-017**: Evidence records MUST use stable case identifiers and one of `PASS`, `FAIL`, `BLOCKED`, or `NOT_RUN`, with `NOT_RUN` and `BLOCKED` never counted as accepted.
- **FR-018**: Candidate staging before movement MUST use only the reviewed manifest under `/data/local/robot/jx/control_ws/`, retain a recoverable previous revision, and pass read-only smoke; production acceptance and autonomous startup MUST remain pending until required HIL gates pass.
- **FR-019**: Rollback instructions MUST identify the exact previous artifact, restoration command, post-rollback read-only checks, and the conditions that require rollback.
- **FR-020**: The handoff MUST identify public commands/contracts, measured configuration, accepted case IDs, known failure codes, current verification level, unresolved risks, and the teammate responsible for each remaining dependency.
- **FR-021**: The overall feature MUST remain `HIL_PENDING` until every mandatory case passes in one traceable robot/revision/configuration context; individual artifacts may be labeled `HIL_VERIFIED` only after supervised recorded execution.
- **FR-022**: The procedure MUST never publish `motor_type`, call `/ros_robot_controller/set_motor`, scan unknown networks, expose secrets, or treat an offline/source-only result as physical evidence.

### Key Entities

- **HIL Session**: One supervised validation context bound to operator, robot, board, revision, deployment, configuration, environment, and time.
- **Motion Proposal**: Single-use statement of requested motion, predicted effect, clearance, stop behavior, risk, and operator authorization.
- **Validation Case**: Stable case ID, prerequisites, procedure, evidence requirements, result, and blocking dependencies.
- **Measurement Record**: Requested/observed values with units, timestamps, method, uncertainty, and provenance.
- **Evidence Index**: Mapping from cases to command/result JSON, filtered logs, scan/target snapshots, photos/videos, and digests.
- **Deployment Record**: Source revision, manifest/config digests, target paths, backup identity, deploy result, smoke result, and rollback result.
- **Handoff Record**: Accepted interface surface, verification scope, limitations, owners, and integration examples.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of mandatory preflight fields are present and passing before the first non-zero proposal; otherwise the recorded count of non-zero commands is zero.
- **SC-002**: 100% of executed non-zero cases have a directly preceding single-use proposal and recorded nearby-operator `走` authorization.
- **SC-003**: All six primitive direction signs are measured, or each unmeasured direction remains explicitly blocked; no sign is accepted solely from source or symmetry.
- **SC-004**: Every executed motion, cancellation, failure, and successful completion has an explicit zero-stop attempt in its evidence record.
- **SC-005**: All enabled direction sectors have at least one accepted clear case and one accepted blocked/rejection case with fresh scan evidence.
- **SC-006**: Persistent estop is shown latched across at least one process boundary and cannot reset until the configured consecutive clear-frame count is met.
- **SC-007**: The visual matrix records all ten required case classes, with mandatory success cases passing and failure cases producing their specified safe terminal reason.
- **SC-008**: Every accepted arrival result has an independent final bearing/range measurement within configured tolerance and zero cases use `/odom` as sole proof.
- **SC-009**: 100% of mandatory validation cases link to revision/configuration identity and their required evidence artifacts, with no secrets present.
- **SC-010**: A teammate can run read-only status, identify the supported motion/approach contracts, and identify the rollback artifact using only the handoff package.

## Assumptions

- HIL execution occurs later, with the user physically beside the same robot and able to observe and stop it.
- The test area can provide measured clearance, stable floor conditions, movable obstacles, and a target suitable for vision validation.
- Specs 001-003 have passed their offline/source verification and have a reviewed deployment manifest before this procedure begins.
- The vision teammate supplies versioned target observations and calibration provenance; missing evidence blocks approach cases rather than being guessed.
- A phone or other camera is available for direction, stop, obstacle, and approach evidence; exact media filenames are assigned by the evidence template.
- This feature plans and records manual HIL work; it does not add a permanent service node or automate physical authorization.

## Out of Scope

- Any HDC, SSH, ROS Master, deployment, topic publication, or robot movement during tonight's offline implementation session.
- Mechanical-arm or gripper acceptance except where their physical placement affects chassis clearance.
- Navigation-map accuracy, long-range autonomous navigation, grasp success, competition Skill orchestration, and unattended motion.
- Automatic promotion to `HIL_VERIFIED`, automatic startup installation, or reuse of evidence across unmatched revisions/configurations.

## Verification Boundary *(mandatory)*

- **Offline-verifiable**: Procedure completeness, checklist structure, case IDs, evidence templates, formulas, manifest/rollback fields, and traceability to Specs 001-003.
- **Source-verifiable**: Proposed topic/type names, runtime invocation, hard limits, forbidden interfaces, and expected CLI/result contracts.
- **HIL-required**: Board identity, graph reality, physical signs/displacement, stop timing, lidar sectors/distances, estop persistence, calibration correctness, target-to-motion behavior, obstacle response, and arrival tolerance.
- **Forbidden substitutions**: Mock messages, source inspection, successful imports, shell syntax, open-loop `/odom`, unsupervised video, or a prior robot/revision/configuration MUST NOT replace supervised HIL evidence.
