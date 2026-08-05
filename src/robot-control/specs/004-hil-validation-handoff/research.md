# Research: Supervised HIL Validation and Handoff

## Decision 1: Bind evidence to one immutable context

- **Decision**: Every HIL session records robot/board identity, source revision, manifest digest, measured-configuration digest, calibration identity, and deployment time.
- **Rationale**: Physical results cease to be trustworthy after hardware, code, configuration, or calibration changes.
- **Alternatives considered**: A date-only lab notebook is easier but cannot establish which executable or robot produced a result.

## Decision 2: Treat every non-zero action as a separate authorization transaction

- **Decision**: Print one concrete proposal, obtain nearby-operator `走`, execute once, stop, and consume the authorization.
- **Rationale**: It preserves the constitution's physical gate and prevents a broad approval from turning into unattended retries or loops.
- **Alternatives considered**: Per-session or per-test-group approval reduces interaction but is unsafe when parameters or surroundings change.

## Decision 3: Validate bottom-up

- **Decision**: Require read-only preflight and stop, then primitive directions, lidar/estop, target/calibration, one-step corrections, failure modes, and finally full approach.
- **Rationale**: A higher-level failure can be diagnosed only if lower-level direction and safety facts are already known.
- **Alternatives considered**: Starting with a complete demonstration is faster when it works but conflates wiring, signs, perception, control, and safety failures.

## Decision 4: Use independent physical evidence for motion and arrival

- **Decision**: Record visible direction plus measured distance/angle or calibrated vision. `/odom` remains diagnostic.
- **Rationale**: The platform's odometry integrates commands without wheel encoders and can report intended rather than actual motion.
- **Alternatives considered**: Odometry-only evidence was rejected by the source findings and constitution.

## Decision 5: Pair clear and blocked lidar cases by direction

- **Decision**: Each enabled motion direction needs both clear authorization and controlled obstacle rejection/stop evidence using recorded sector samples.
- **Rationale**: A scanner can appear healthy while sectors, angle signs, or distance thresholds are mapped incorrectly.
- **Alternatives considered**: A single front-obstacle case does not validate lateral/reverse/rotation policy.

## Decision 6: Persistent estop needs a process-boundary test

- **Decision**: Latch estop, terminate the owning CLI, confirm a new process remains blocked, then reset only after consecutive fresh all-direction-clear scans.
- **Rationale**: Spec 003 deliberately uses finite processes; persistence is the safety property under test.
- **Alternatives considered**: An in-process toggle does not prove atomic persistence or fail-closed startup.

## Decision 7: Separate deploy acceptance from motion acceptance

- **Decision**: Record manifest copy, permissions, identity, and read-only smoke before any post-deploy movement, and retain an exact rollback artifact.
- **Rationale**: Deployment correctness can be checked without moving, while motion results require separate supervision.
- **Alternatives considered**: One combined deploy-and-run command hides the point of failure and can move the wrong revision.

## Decision 8: Keep media outside the structured evidence core

- **Decision**: Structured records store media paths, timestamps, case IDs, and digests; large raw media need not be committed.
- **Rationale**: Logs and measurements remain reviewable while avoiding repository bloat and accidental sensitive capture.
- **Alternatives considered**: Committing all video is simple but noisy; omitting media identity makes later review ambiguous.

## Decision 9: Defer autonomous startup

- **Decision**: Do not install or accept `init.cfg` startup until manual launch, stop, safety, approach, rollback, and team integration are accepted.
- **Rationale**: Startup changes the risk from supervised invocation to movement-capable behavior immediately after boot.
- **Alternatives considered**: Early autostart improves demo convenience but expands the hazard and recovery surface before core acceptance.

## Source Basis

- Repository constitution: per-action `走`, hard limits, stop guarantees, verification levels.
- `JUNXIANG/机器人控制对接文档.md`: measured interface facts and pending values.
- `JUNXIANG/首次连板checklist.md`: established board and robot inspection sequence.
- Spec 001: shared motion/result contracts and fake baseline.
- Spec 002: directional scan, target, approach, estop/reset state model.
- Spec 003: ROS facade, ownership, persistent estop, production configuration, manifest, and smoke boundary.

No HIL fact is inferred from this research.
