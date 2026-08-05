# Feature Specification: Safe Approach Simulation

**Feature Branch**: `junxiang`  
**Created**: 2026-08-05  
**Status**: `OFFLINE_VERIFIED` (physical/HIL validation pending)
**Input**: Direction-aware lidar gating, latched emergency stop, validated target adapters, and a closed-loop visual approach workflow that remains offline-testable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Gate movement with directional lidar safety (Priority: P1)

As the motion controller, I can evaluate a proposed chassis velocity against a fresh scan in the directions the robot would occupy, so unsafe or unproven movement is rejected before non-zero output.

**Why this priority**: Automatic movement cannot be allowed when obstacle evidence is missing, stale, insufficient, or blocked.

**Independent Test**: Feed synthetic scans and velocity requests into the safety evaluator and compare deterministic decisions without ROS or hardware.

**Acceptance Scenarios**:

1. **Given** a fresh scan with enough valid clear samples in every required sector, **When** a directional move is evaluated, **Then** it is allowed with explicit sector evidence.
2. **Given** a blocked, stale, malformed, or sample-deficient required sector, **When** non-zero motion is evaluated, **Then** it is rejected and the emergency stop becomes latched.
3. **Given** rotational motion, **When** any configured swept-footprint sector is blocked or unproven, **Then** rotation is rejected rather than checking only the forward sector.

---

### User Story 2 - Latch and deliberately reset emergency stop (Priority: P1)

As the operator or controller, I can observe a latched emergency stop and reset it only after explicit request plus fresh, stable, all-direction clear evidence.

**Why this priority**: Automatic resumption when an obstacle briefly disappears can create an unexpected second movement.

**Independent Test**: Trigger the latch, provide alternating blocked/clear frames, and prove reset fails until the configured consecutive clear-frame condition is met.

**Acceptance Scenarios**:

1. **Given** a latched emergency stop, **When** obstacles disappear without a reset request, **Then** all non-zero movement remains rejected.
2. **Given** a reset request but stale or unstable clearance, **When** reset is evaluated, **Then** the latch remains set with a reason.
3. **Given** an explicit reset request and the required consecutive fresh all-direction clear frames, **When** reset completes, **Then** the latch clears without initiating motion.

---

### User Story 3 - Normalize visual targets safely (Priority: P1)

As the approach controller, I can consume either an already transformed `base_link` target or pixel-plus-depth data with a traceable camera transform and obtain one validated base-frame target.

**Why this priority**: Movement based on stale, invalid, or misframed perception is unsafe; `base_link.z` must never be mistaken for forward depth.

**Independent Test**: Adapt known synthetic target/calibration fixtures and reject wrong frames, stale data, invalid depth, and missing transform provenance.

**Acceptance Scenarios**:

1. **Given** a fresh valid target explicitly in `base_link`, **When** it is normalized, **Then** forward distance derives from x/y and z remains height.
2. **Given** pixel coordinates, metric camera depth, intrinsics, and a traceable camera-to-base transform, **When** they are normalized, **Then** the expected base-frame point is produced.
3. **Given** missing/stale calibration, wrong frame, stale target, invalid flag, low confidence, or non-finite depth, **When** normalization is attempted, **Then** no motion-ready target is returned.

---

### User Story 4 - Approach and verify a target in one process (Priority: P2)

As a higher-level Skill, I can request a bounded approach that repeatedly re-observes the target, rotates, translates, and verifies stable arrival while using the same shared motion core.

**Why this priority**: This is the engineering bridge from vision output to reliable chassis movement, but it depends on all preceding safety capabilities.

**Independent Test**: A scripted target/scan sequence drives the state machine through success and every terminal failure while fake backend events prove explicit stops.

**Acceptance Scenarios**:

1. **Given** fresh targets and safe scans that converge, **When** approach runs, **Then** it performs bounded corrections and succeeds only after the required stable visual confirmations.
2. **Given** target loss, stale perception, safety rejection, cancellation, timeout, iteration limit, or backend error, **When** approach terminates, **Then** it reports a stable failure state and ends stopped.
3. **Given** only open-loop odometry changes but no fresh target confirmation, **When** arrival is evaluated, **Then** the workflow does not declare success.

### Edge Cases

- Diagonal translation requires every corresponding directional sector to be clear.
- Zero velocity is always allowed through the safety evaluator and does not clear an existing latch.
- NaN, infinity, zeros, and out-of-range lidar returns are excluded; too few remaining samples fail closed.
- Scan timestamps from the future beyond the configured clock tolerance are invalid.
- A target behind the robot rotates first and cannot request backward translation merely to shorten the path.
- New target observations may change bearing and distance between correction steps.
- Pixel depth is camera-forward depth before transformation; base-frame z is height after transformation.
- Synthetic thresholds and calibration are valid only for offline fixtures.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST validate scan timestamps, angular metadata, range bounds, finite samples, and minimum usable sample count before using a scan for non-zero motion.
- **FR-002**: The system MUST select required lidar sectors from the signs of forward, lateral, and angular velocity; diagonal motion MUST require all implicated sectors, and rotation MUST cover the configured swept footprint.
- **FR-003**: Each required sector MUST use configured clearance and sample-count rules and MUST return structured per-sector evidence.
- **FR-004**: Missing, stale, malformed, sample-deficient, or blocked safety evidence MUST reject non-zero movement and latch emergency stop.
- **FR-005**: A latched emergency stop MUST persist across clear observations and MUST clear only after explicit reset plus a configured number of consecutive fresh all-direction clear observations.
- **FR-006**: Zero velocity MUST remain permissible for stopping regardless of scan or latch state and MUST NOT implicitly reset the latch.
- **FR-007**: The system MUST validate freshness, validity, confidence, finite coordinates, and `frame_id=base_link` for pre-transformed targets.
- **FR-008**: The pixel-depth adapter MUST require valid intrinsics, metric depth, and a traceable camera-to-base transform; it MUST reject missing or stale calibration.
- **FR-009**: Normalized target geometry MUST use base-frame x as forward, y as left, z as up, planar distance `hypot(x,y)`, and bearing `atan2(y,x)`.
- **FR-010**: The approach workflow MUST run within one process, call the shared control core directly, and MUST NOT spawn a movement CLI process for feedback corrections.
- **FR-011**: The approach workflow MUST use explicit `PRECHECK`, `ROTATE`, `TRANSLATE`, `VERIFY`, `STOPPING`, and terminal states with bounded corrections, timeout, cancellation, and iteration limits.
- **FR-012**: Every non-zero correction MUST use a fresh normalized target and a current allowed safety decision before calling the motion core.
- **FR-013**: Success MUST require configured consecutive fresh visual observations within bearing and stand-off tolerances; open-loop odometry MUST NOT establish success.
- **FR-014**: Every approach terminal path MUST invoke an explicit stop and return state history, stable error code, safety evidence, and one approved verification level.
- **FR-015**: Synthetic safety, calibration, and approach configuration MUST be clearly marked and MUST be rejected by later production integration.

### Key Entities

- **Laser Scan Snapshot**: Timestamped angular metadata, range bounds, and ordered range samples.
- **Safety Configuration**: Directional sectors, clearance thresholds, sample minimums, age tolerance, and reset stability count with provenance.
- **Safety Decision**: Allowed state, required directions, sector evidence, latch state, and stable reason.
- **Emergency Stop Latch**: Latched state, trigger reason/time, clear-frame count, and explicit reset state.
- **Raw Target Observation**: Base-frame point or pixel-plus-depth data with freshness, validity, confidence, and source identity.
- **Calibration**: Camera intrinsics and rigid camera-to-base transform with provenance and measurement timestamp.
- **Normalized Target**: Validated base-frame point, planar distance, bearing, height, confidence, and source evidence.
- **Approach Configuration**: Speeds, correction durations, tolerances, stable-frame count, target/scan ages, timeout, and iteration limit.
- **Approach Result**: Terminal state, state history, correction results, last target/safety evidence, stop evidence, and error.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Offline tests cover 100% of direction combinations, including diagonal and rotational requests, with deterministic allow/reject evidence.
- **SC-002**: Every stale, missing, malformed, insufficient, or blocked safety fixture rejects non-zero motion and latches emergency stop.
- **SC-003**: Emergency stop remains latched through arbitrary clear frames until explicit reset, and reset succeeds only at the exact configured stable-frame threshold.
- **SC-004**: Coordinate fixtures produce expected base-frame points within `1e-6 m`, and all invalid frame/depth/calibration fixtures are rejected.
- **SC-005**: Scripted approach tests cover success plus target loss, safety latch, cancellation, timeout, iteration limit, backend failure, and stop failure; every terminal path records an explicit stop attempt.
- **SC-006**: No approach success test can pass using elapsed commands or odometry alone; it requires the configured number of fresh visual confirmations.

## Assumptions

- Production direction sectors, clearances, tolerances, speeds, and calibration are unavailable tonight and remain measured-configuration inputs.
- Offline tests use files and objects explicitly marked `synthetic`.
- Camera optical coordinates are x right, y down, z forward before applying the supplied transform.
- Version 1 rotates until target bearing is within tolerance, then translates forward; it does not optimize diagonal omnidirectional paths.
- The controller obtains a current scan and target through injected providers; ROS subscription is Spec 003.

## Out of Scope

- ROS message conversion, topic subscription, publisher ownership checks, process locks, and signal handling.
- Automatic mechanical-arm motion, grasping, navigation maps, AMCL, and move_base.
- Choosing real thresholds, producing real calibration, deployment, or physical validation.

## Verification Boundary *(mandatory)*

- **Offline-verifiable**: Scan validation, directional gating, latch/reset rules, coordinate transforms, target validation, approach transitions, cancellation, and terminal stops with deterministic providers.
- **Source-verifiable**: Candidate target topics, message types, coordinate convention, and lidar message layout.
- **HIL-required**: Real sector orientation, robot footprint clearance, braking distance, perception latency, correction signs, approach tolerance, and physical arrival.
- **Forbidden substitutions**: Synthetic scans, synthetic transforms, scripted convergence, open-loop odometry, and fake backend events MUST NOT be presented as real obstacle avoidance or arrival.
