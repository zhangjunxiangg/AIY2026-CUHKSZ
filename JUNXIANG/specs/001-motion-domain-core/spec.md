# Feature Specification: Motion Domain Core

**Feature Branch**: `junxiang`  
**Created**: 2026-08-05  
**Status**: Draft  
**Input**: A shared, hardware-independent motion-control core with bounded movement, explicit stopping, deterministic simulation, and a machine-readable command interface.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Issue a bounded chassis command (Priority: P1)

As the robot-control developer, I can submit a planar velocity and duration and receive a deterministic result, so every caller uses the same safety limits and stop behavior.

**Why this priority**: All manual and automatic chassis behavior depends on one trustworthy movement primitive.

**Independent Test**: Submit valid and invalid motion requests to a deterministic backend and inspect the accepted command sequence and result without ROS, a network, or hardware.

**Acceptance Scenarios**:

1. **Given** finite values within all hard limits, **When** a movement is requested, **Then** the request is accepted, bounded velocity is emitted for the requested duration, and explicit zero velocity is the final event.
2. **Given** a planar speed, angular speed, or duration outside a hard limit, **When** a movement is requested, **Then** no non-zero output is emitted and a stable validation error is returned.
3. **Given** cancellation, timeout, or backend failure during movement, **When** the operation terminates, **Then** an explicit stop is attempted and the failure result records whether stopping was confirmed.

---

### User Story 2 - Stop and inspect the controller (Priority: P1)

As an operator or higher-level controller, I can request status or stop through the same core without initiating motion.

**Why this priority**: Safe recovery and preflight checks must remain available even when non-zero movement is rejected.

**Independent Test**: Invoke status and stop against a deterministic backend and verify that status is read-only and stop emits only zero velocity.

**Acceptance Scenarios**:

1. **Given** an available backend, **When** status is requested, **Then** a structured readiness result is returned without any non-zero motion.
2. **Given** any backend state, **When** stop is requested, **Then** only zero velocity is emitted and the result distinguishes confirmed stop from stop failure.

---

### User Story 3 - Use a stable command contract (Priority: P2)

As a teammate integrating a Skill or test harness, I can invoke `status`, `move`, and `stop` commands and parse exactly one versioned result object.

**Why this priority**: Stable machine-readable behavior lets higher layers integrate without depending on internal classes or human-oriented output.

**Independent Test**: Run every command and representative failure from a local process, parse the single standard-output result, and compare exit codes and fields with the published contract.

**Acceptance Scenarios**:

1. **Given** a valid command, **When** it completes, **Then** standard output contains exactly one valid result object and diagnostics do not corrupt it.
2. **Given** invalid syntax, validation failure, backend unavailability, or interrupted execution, **When** the command exits, **Then** it uses a stable non-zero exit class and a stable error code.
3. **Given** production mode is requested without measured production configuration, **When** a non-zero move is submitted, **Then** the command fails closed before motion.

### Edge Cases

- Non-finite numbers, booleans presented as numbers, and malformed structured input are rejected.
- Combined x/y velocity is checked by planar magnitude, not by checking each axis independently.
- A zero-velocity `move` request still obeys duration validation and ends with an explicit stop.
- Failure while publishing the final stop is preserved as a stop-safety failure rather than hidden by the original error.
- Repeated stop requests remain safe and deterministic.
- The fake backend cannot select or contact a production transport.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST represent planar velocity, bounded motion requests, controller status, motion results, errors, and verification level as validated domain values.
- **FR-002**: The system MUST reject non-finite numeric values and MUST reject a planar linear magnitude greater than `0.20 m/s`, an absolute angular speed greater than `0.50 rad/s`, or a duration outside `0.1..10.0 s`.
- **FR-003**: The system MUST expose one control-core operation for bounded movement and MUST use that operation for both command-line and future automatic callers.
- **FR-004**: Every movement terminal path MUST attempt an explicit zero-velocity output, including success, validation failure after ownership, cancellation, timeout, exception, and interruption.
- **FR-005**: A validation failure detected before motion ownership MUST emit no non-zero velocity and MUST return a structured rejection.
- **FR-006**: The system MUST provide a deterministic fake backend that records ordered events and performs no network or hardware access.
- **FR-007**: The system MUST provide read-only status and idempotent stop operations independent of non-zero movement readiness.
- **FR-008**: The command interface MUST expose `status`, `move`, and `stop`, emit exactly one versioned machine-readable result on standard output, keep diagnostics separate, and use documented stable exit classes.
- **FR-009**: Results MUST include operation identity, success state, stable error code when applicable, stop-attempt evidence, backend identity, and one of the approved verification levels.
- **FR-010**: Production mode MUST reject synthetic or missing production configuration before permitting non-zero motion.
- **FR-011**: Domain and fake-backend behavior MUST be usable and testable without ROS modules installed.
- **FR-012**: The system MUST never publish `motor_type` or access `/ros_robot_controller/set_motor`.

### Key Entities

- **Velocity**: Forward, lateral, and angular components with finite-value and hard-limit validation.
- **Motion Request**: A velocity plus bounded duration and operation identifier.
- **Motion Result**: Terminal outcome, stop evidence, backend identity, verification level, timing, and optional structured error.
- **Controller Status**: Readiness, backend identity, motion ownership state, and blocking reasons.
- **Control Error**: Stable code, human-readable detail, retryability, and failure category.
- **Backend Event**: Ordered fake or production transport event used as evidence of commands and stops.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All documented boundary values and invalid-number cases produce deterministic accept/reject outcomes in offline tests.
- **SC-002**: Automated tests prove that 100% of movement terminal-path scenarios end with an attempted explicit stop and that no rejected request emits non-zero velocity.
- **SC-003**: Every command and documented error path yields exactly one parseable versioned result with a stable exit class.
- **SC-004**: The full domain-core test suite runs on the developer Mac with ROS unavailable and performs zero network or hardware operations.
- **SC-005**: Production-mode tests prove that missing or synthetic configuration blocks 100% of non-zero movement attempts.

## Assumptions

- Version 1 controls the chassis only; mechanical-arm primitives and navigation are outside this feature.
- Velocity direction follows `base_link`: x forward, y left, angular z counter-clockwise.
- The transport watchdog is a fallback; active zero-velocity output remains mandatory.
- Configuration provenance is supplied by a later integration feature, but this core defines the validation boundary now.
- Offline success authorizes only the `OFFLINE_VERIFIED` label and never physical-motion claims.

## Out of Scope

- ROS topic discovery, ROS publishing, process locks, and signal installation.
- Lidar interpretation, perception adapters, approach controllers, mapping, and navigation.
- Robot deployment, startup configuration, or any physical movement.

## Verification Boundary *(mandatory)*

- **Offline-verifiable**: Value validation, error mapping, fake-backend ordering, shared-core behavior, JSON command contract, and stop semantics.
- **Source-verifiable**: Hard limits and direction convention may be cross-checked against the official M-Claw source.
- **HIL-required**: Physical direction, achieved displacement, watchdog timing, and real stop effectiveness.
- **Forbidden substitutions**: Fake events, elapsed wall time, source inspection, and open-loop odometry MUST NOT be presented as physical validation.
