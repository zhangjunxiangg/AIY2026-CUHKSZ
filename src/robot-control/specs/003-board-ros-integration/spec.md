# Feature Specification: Board ROS Integration

**Feature Branch**: `junxiang`  
**Created**: 2026-08-05  
**Status**: `SOURCE_VERIFIED_HIL_PENDING`
**Input**: A production ROS1 backend and deployment-ready CLI that adapt the offline-verified control core without requiring board access during implementation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect board readiness without motion (Priority: P1)

As the robot-control developer, I can run a read-only status command that reports ROS Master, `/cmd_vel`, `/scan`, target input, configuration, and motion-ownership readiness without emitting non-zero velocity.

**Why this priority**: Readiness evidence and precise blocking reasons are prerequisites for any supervised movement.

**Independent Test**: Use a fake ROS facade with graph and message fixtures to prove readiness and every missing/stale/conflicting condition, then source-check names against official files.

**Acceptance Scenarios**:

1. **Given** all required graph endpoints, fresh data, measured configuration, and no conflicting owner, **When** status runs, **Then** it returns source-verified readiness evidence and emits no non-zero command.
2. **Given** missing ROS Master, no `/cmd_vel` subscriber, missing/stale scan or target, invalid configuration, lock conflict, or competing `/cmd_vel` publisher, **When** status runs, **Then** it returns stable blocking reasons without movement.
3. **Given** ROS Python modules are not installed, **When** fake CLI or domain modules are imported, **Then** they still work; only explicit ROS backend selection fails clearly.

---

### User Story 2 - Publish bounded movement through ROS safely (Priority: P1)

As a supervised operator, I can invoke `move` or `stop` through the production CLI and know that the shared core owns limits while the ROS backend owns connection, exclusivity, and zero-velocity delivery.

**Why this priority**: This is the single production path from approved commands to `/cmd_vel`.

**Independent Test**: A fake ROS facade records message fields, publisher cadence, graph checks, lock behavior, and final zero sequence for all terminal paths; no ROS Master is contacted.

**Acceptance Scenarios**:

1. **Given** measured configuration, explicit supervised-motion authorization, one `/cmd_vel` subscriber, no competing publisher, and an acquired process lock, **When** a valid move runs, **Then** Twist-equivalent x/y/z fields are published at the configured cadence and an explicit zero sequence terminates it.
2. **Given** the project lock is held or any unapproved `/cmd_vel` publisher exists, **When** non-zero motion is requested, **Then** no non-zero output is emitted and the result identifies the conflict.
3. **Given** SIGINT, SIGTERM, or SIGHUP during movement, **When** cancellation propagates, **Then** the shared core enters its stop path and the process exits with a structured interrupted result.
4. **Given** stop is requested during degraded readiness, **When** a publisher can still be created, **Then** zero velocity is attempted without requiring non-zero-motion readiness.

---

### User Story 3 - Run visual approach against ROS data (Priority: P2)

As a higher-level Skill integrator, I can invoke one production approach process that consumes configured scan and target topics and calls the shared core directly for all corrections.

**Why this priority**: It delivers the assigned visual-to-motion engineering logic while preserving one process and one owner for the complete feedback loop.

**Independent Test**: Feed fake LaserScan, valid/invalid target messages, timestamp changes, and graph failures through ROS adapters and assert the Spec 002 state machine/result contract.

**Acceptance Scenarios**:

1. **Given** configured source-validated messages and measured configuration, **When** approach starts, **Then** scan and target messages are converted into domain observations with timestamps, frames, confidence, and provenance preserved.
2. **Given** invalid JSON, false validity, missing confidence, wrong frame, stale data, or incompatible schema, **When** the target provider is queried, **Then** it returns a structured unavailable/invalid reason and movement remains stopped.
3. **Given** a feedback correction is required, **When** it executes, **Then** the same process calls the shared controller and no movement CLI subprocess is spawned.

---

### User Story 4 - Prepare a reproducible board bundle (Priority: P2)

As the teammate deploying tomorrow, I can inspect a self-contained package manifest, measured-configuration template, read-only smoke test, and `/bin/run` wrapper with exact paths and no hidden setup state.

**Why this priority**: Source completion is not useful if board deployment is ambiguous or accidentally enables motion.

**Independent Test**: Validate file manifests, executable entry points, configuration rejection, imports, and shell syntax locally without copying or running anything on the board.

**Acceptance Scenarios**:

1. **Given** the deployment bundle, **When** its manifest is verified locally, **Then** every required tracked file and target path is explicit and no secret or synthetic production file is included.
2. **Given** the measured template still contains placeholders, **When** production status or motion is requested, **Then** readiness fails closed with the missing measurement fields.
3. **Given** the read-only smoke command, **When** reviewed or executed later on a board, **Then** it cannot issue non-zero motion and reports `SOURCE_VERIFIED_HIL_PENDING` until HIL records exist.

### Edge Cases

- The ROS node's own `/cmd_vel` publisher is excluded from conflict detection; all other publishers require an explicit measured allowlist, empty by default.
- Publisher graph changes after preflight cause the next publish/readiness check to fail and stop.
- A process may lose its lock file descriptor unexpectedly; non-zero publishing then fails closed.
- ROS time may be zero or jump; receive monotonic time and message source time are retained separately and freshness uses a documented policy.
- A latched target message can be old even if received immediately after subscription.
- A point without confidence is not promoted to a high-confidence target.
- Signal arrival before motion ownership causes a read-only interrupted result; after ownership it also triggers explicit stopping.
- Production selection never falls back to fake mode.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: ROS modules and ROS message packages MUST be imported only after explicit ROS backend/provider selection; domain imports and fake CLI MUST work when ROS is absent.
- **FR-002**: The ROS facade MUST expose only the graph, publisher, subscription, time, sleep, shutdown, and logging operations needed by adapters and MUST be replaceable by a deterministic non-network facade.
- **FR-003**: The ROS backend MUST publish only `geometry_msgs/Twist` semantics to configured `/cmd_vel`, mapping base x/y/angular z exactly and never emitting `motor_type` or accessing `/ros_robot_controller/set_motor`.
- **FR-004**: Non-zero motion readiness MUST require an available ROS Master, at least one `/cmd_vel` subscriber, measured production configuration, explicit supervised-motion authorization, an acquired project process lock, a clear persistent emergency-stop state, a fresh direction-appropriate allowed scan decision, and no unapproved competing `/cmd_vel` publisher.
- **FR-005**: The project process lock MUST be non-blocking, held for the full motion/approach ownership interval, released on exit, and report owner metadata when contention can be read safely.
- **FR-006**: Publisher conflict detection MUST exclude only the current node and explicitly measured allowlist entries; the default allowlist MUST be empty.
- **FR-007**: The ROS backend MUST re-check ownership, publisher conflicts, persistent emergency-stop state, and fresh direction-appropriate scan safety during non-zero publishing and MUST fail into the shared explicit-stop path if any gate is lost.
- **FR-008**: Stop MUST attempt a configured multi-message zero-velocity sequence even when non-zero readiness fails, and results MUST distinguish subscriber absence from publish failure.
- **FR-009**: SIGINT, SIGTERM, and SIGHUP MUST request cancellation through signal-safe state, converge on shared stop semantics when ownership exists, and restore prior handlers after the command.
- **FR-010**: LaserScan conversion MUST preserve source timestamp, receive monotonic time, angular metadata, range limits, and all ranges without deciding safety in the ROS adapter.
- **FR-011**: Target conversion MUST accept only a configured versioned contract, preserve source/receive time, validity, frame, confidence, and calibration provenance, and reject malformed or incomplete messages.
- **FR-012**: The production approach command MUST instantiate scan/target providers and call the Spec 002 approach controller directly in the same process; it MUST NOT invoke movement CLI subprocesses.
- **FR-013**: The command interface MUST extend the Spec 001 contract with explicit ROS `status`, `move`, `stop`, `approach`, and `estop-reset` behavior while preserving one JSON result and stable exit classes.
- **FR-014**: Non-zero production commands MUST require explicit supervised-motion authorization; status, stop, and read-only smoke checks MUST remain available without it.
- **FR-015**: Production configuration MUST be a versioned structured file whose required direction signs, lidar sectors/clearances, target topics/schema, speeds, tolerances, calibration records, lock path, and publisher allowlist are measured and dated; null, missing, stale, or synthetic fields MUST fail closed.
- **FR-016**: The deployment bundle MUST target `/data/local/robot/jx/control_ws/`, invoke Python through `/bin/run`, use English runtime diagnostics, include no secret material, and perform no deployment automatically.
- **FR-017**: A read-only board smoke tool MUST report graph/config/data readiness and forbidden-interface absence without creating a non-zero velocity request.
- **FR-018**: All mock/source validations from this feature MUST report `SOURCE_VERIFIED_HIL_PENDING`; only the deferred supervised HIL specification may promote evidence to `HIL_VERIFIED`.
- **FR-019**: Production emergency-stop latch state MUST persist atomically across CLI process lifetimes; a missing, unreadable, or corrupt state file MUST be treated as latched, and `estop-reset` MUST clear it only after the Spec 002 explicit reset and fresh all-direction clearance rules pass.

### Key Entities

- **RosFacade**: Narrow injectable interface over ROS graph, messages, pub/sub, timing, and shutdown.
- **RosMotionBackend**: Shared-core backend implementing readiness, ownership, Twist publishing, and stop evidence.
- **MotionLock**: File descriptor, path, owner metadata, acquisition time, and held state.
- **PublisherSnapshot**: Topic, node names, current node, allowlist, and conflict set.
- **RosScanProvider**: Thread-safe latest LaserScan conversion plus source/receive times and error state.
- **RosTargetProvider**: Thread-safe versioned target conversion, validity state, provenance, and error state.
- **ProductionConfiguration**: Versioned, measured, dated runtime settings and their validation findings.
- **SignalCancellationGuard**: Installed handlers, cancellation token, received signal, and restoration state.
- **Persistent Estop Store**: Atomic latch record, trigger evidence, reset state, schema, and corruption handling shared across CLI invocations.
- **DeploymentManifest**: Local source path, board target path, mode, purpose, and verification boundary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The complete offline suite passes with ROS imports actively blocked, while explicit ROS selection returns a single clear unavailable result.
- **SC-002**: Mock integration tests cover every readiness prerequisite and prove zero non-zero messages for all lock, publisher-conflict, configuration, and authorization failures.
- **SC-003**: Mocked successful movement preserves all requested Twist components, repeats at the configured rate, and ends with the configured zero sequence.
- **SC-004**: Mock signal tests cover SIGINT, SIGTERM, and SIGHUP and prove cancellation plus an explicit stop attempt on every owned path.
- **SC-005**: Scan and target conversion fixtures cover valid input and every documented malformed, stale, wrong-frame, false-validity, missing-confidence, and schema mismatch case.
- **SC-006**: Local deployment verification accounts for 100% of manifest files, rejects every unfilled measured template, and finds no secret or forbidden-interface reference in executable production code.
- **SC-007**: Every result produced by ROS mock/source validation uses `SOURCE_VERIFIED_HIL_PENDING` and no artifact claims robot motion or arrival.

## Assumptions

- ROS1 Noetic-style `rospy`, `rosgraph`, `geometry_msgs`, `sensor_msgs`, and `std_msgs` are available only inside the board `/bin/run` environment.
- Current source-authoritative topics are `/cmd_vel`, `/scan`, `/competition/aux_target_json`, and `/competition/aux_target_valid`; all remain configurable but production defaults are not silently substituted.
- `/competition/aux_target_json` must carry the versioned target contract, including confidence and provenance; `PointStamped` alone is insufficient for automatic motion.
- The existing chassis controller is the expected `/cmd_vel` subscriber, not a publisher.
- No real publisher allowlist can be approved without a dated on-board graph capture.

## Out of Scope

- Actual SSH/HDC connection, package copying, ROS Master access, topic publishing, or physical movement tonight.
- Mechanical-arm/夹爪 implementation, navigation/map integration, and permanent ROS service nodes.
- Filling measured configuration, installing init services, or assigning `HIL_VERIFIED`.

## Verification Boundary *(mandatory)*

- **Offline-verifiable**: Lazy imports, facade behavior, locking, config validation, signal cancellation, message conversion, CLI schemas, manifest integrity, and all error/stop paths using mocks.
- **Source-verifiable**: Current topic names, message fields, `run` requirement, watchdog/cadence, and board target path.
- **HIL-required**: ROS graph reality, publisher discovery behavior, subscriber connection, actual cadence, real signals, topic timestamps, direction signs, clearances, perception stream, stopping, and approach.
- **Forbidden substitutions**: Mock ROS messages, source matches, shell validation, file manifests, and open-loop odometry MUST NOT be treated as board or robot acceptance.
