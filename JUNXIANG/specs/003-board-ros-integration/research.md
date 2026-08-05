# Research: Board ROS Integration

## Decision 1: Lazy narrow facade

- **Decision**: Import ROS only inside `load_ros_facade()` and adapt it to a small project interface.
- **Rationale**: Domain/CLI fake mode remains usable on the Mac, and every ROS interaction can be reproduced with deterministic fakes.
- **Alternatives considered**: Module-level `rospy` imports break all offline imports; mocking global ROS modules is brittle and leaks message details inward.

## Decision 2: Advisory file lock plus ROS graph inspection

- **Decision**: Require both an exclusive project `fcntl` lock and absence of unapproved `/cmd_vel` publishers.
- **Rationale**: The file lock prevents two project CLIs from racing, while graph inspection detects external teleop/navigation publishers that do not honor the lock.
- **Alternatives considered**: Either mechanism alone misses one conflict class. A custom arbiter node is deferred because it would become a permanent service architecture.

## Decision 3: Recheck all volatile gates during publishing

- **Decision**: Re-evaluate lock-held state, publishers, persistent estop, and current direction-aware scan safety before each non-zero message.
- **Rationale**: Preflight evidence can become stale after another node starts, an obstacle appears, or another process latches estop. Rechecking bounds exposure and routes failure through explicit stop.
- **Alternatives considered**: Start-only inspection is cheaper but creates a race for the entire command duration.

## Decision 4: Source and receive time are both required

- **Decision**: Preserve the ROS header/source timestamp and local monotonic receive time, applying independent freshness checks.
- **Rationale**: Latched old messages can arrive immediately, while ROS/wall time can jump. One timestamp alone cannot distinguish both problems.
- **Alternatives considered**: Receipt-only time accepts latched stale data; source-only time is vulnerable to clock misconfiguration.

## Decision 5: Versioned JSON target for motion

- **Decision**: Use `/competition/aux_target_json` plus `/competition/aux_target_valid` for automatic motion; point-only data remains status evidence.
- **Rationale**: `PointStamped` has frame and source time but lacks validity confidence, target schema, and calibration provenance required by fail-closed rules.
- **Alternatives considered**: Assigning implicit confidence to PointStamped was rejected as guessed safety evidence.

## Decision 6: Atomic persistent estop record

- **Decision**: Persist latch state in a versioned mode-0600 JSON file with temp-write, fsync, and atomic replace; missing or corrupt production state is latched.
- **Rationale**: The shared-core architecture uses finite CLI processes; the safety state must survive their exit without a permanent ROS node.
- **Alternatives considered**: Memory-only state loses the latch; ROS parameters are external mutable state and unavailable when the Master is down.

## Decision 7: Explicit CLI operator flag plus procedural gate

- **Decision**: Require `--operator-confirmed` for non-zero ROS commands and also retain the documented requirement that the operator be beside the robot and say “走”.
- **Rationale**: Software cannot prove physical supervision, but it can prevent accidental command omission and record the caller's assertion.
- **Alternatives considered**: No flag is easier to misuse; a magic phrase/API token does not actually prove supervision.

## Decision 8: Manifest-only deployment

- **Decision**: Deliver wrapper, target paths, and file manifest without a transfer or startup script.
- **Rationale**: Tonight has no board; local source work must not silently cross into deployment or enable autonomous startup before HIL.
- **Alternatives considered**: Automatic SSH/HDC deployment and init.cfg were rejected until board and physical acceptance are available.

## Source Evidence

- Twist mapping, rate, signals, stop sequence: `mclaw-skill/scripts/ros_cmd_vel.py`
- `/cmd_vel` and watchdog wiring: `robot-runtime/src/chassis_controller/launch/chassis.launch`
- Scan field iteration: `robot-runtime/scan-sector-report.py`
- Candidate targets: `robot-runtime/student/interfaces/aux_target_relay.py`
- `/bin/run` and board path rules: `docs/板端开发参考/M-Robots开发踩坑与参考库.md`

All source matches remain `SOURCE_VERIFIED_HIL_PENDING`.
