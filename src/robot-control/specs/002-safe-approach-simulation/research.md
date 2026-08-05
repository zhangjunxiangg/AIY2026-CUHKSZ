# Research: Safe Approach Simulation

## Decision 1: Direction-selected sectors with full rotation coverage

- **Decision**: Translation checks sectors selected by x/y signs; any rotation checks all configured swept-footprint sectors.
- **Rationale**: A rotating chassis sweeps corners beyond the forward beam. Diagonal translation also occupies more than one direction.
- **Alternatives considered**: Global minimum for every translation is unnecessarily restrictive; forward-only checks miss lateral/rear/swept collisions.

## Decision 2: Minimum valid range plus sample sufficiency

- **Decision**: Use the minimum valid range in each required sector and require a measured minimum sample count.
- **Rationale**: Safety should react to a real close return rather than average it away. Sample sufficiency prevents an almost-empty scan from looking clear.
- **Alternatives considered**: Median and P10 are useful diagnostics but can hide a narrow obstacle. They may be reported later but do not replace the safety minimum.

## Decision 3: Global latched emergency stop

- **Decision**: Any non-zero request with unavailable or unsafe evidence sets a global latch. It clears only after explicit reset and consecutive fresh all-sector-clear observations.
- **Rationale**: A global latch prevents another command direction from automatically resuming after a transient obstacle or sensor failure.
- **Alternatives considered**: Auto-clear and per-direction latches reduce operator friction but allow surprising restart behavior.

## Decision 4: Standard-library rigid transform

- **Decision**: Represent rotation as nine row-major floats plus translation and validate finite values, orthonormality, and positive unit determinant.
- **Rationale**: The transform is small, deterministic, and does not require numpy on the board. Validation catches common malformed-calibration errors.
- **Alternatives considered**: A generic 4x4 library adds dependency risk; accepting unchecked matrices could mirror or scale the target.

## Decision 5: Rotate then forward translate

- **Decision**: v1 aligns bearing before positive-x translation and refuses automatic reverse when already too close.
- **Rationale**: It is easier to validate directional signs and lidar coverage on real hardware. It also avoids executing an unexpected reverse near the grasp target.
- **Alternatives considered**: Omnidirectional diagonal approach is faster but adds sign/calibration and sector interactions before HIL values exist.

## Decision 6: Stable visual verification only

- **Decision**: Arrival requires consecutive fresh normalized targets within bearing and stand-off tolerances.
- **Rationale**: `/odom` is command integration without wheel encoder feedback and cannot prove physical arrival.
- **Alternatives considered**: Time/distance integration is useful only for diagnostics; it is explicitly excluded from success.

## Decision 7: Configuration provenance is part of every safety object

- **Decision**: Configuration carries `synthetic` or `measured`, a source identifier, and measurement time.
- **Rationale**: Offline values must remain useful for tests but impossible to mistake for production evidence.
- **Alternatives considered**: Separate filenames alone are too easy to bypass after deployment.

## Source Evidence

- `/scan` and current measured frequency: `JUNXIANG/机器人控制对接文档.md`
- Candidate base target relay: `vendor/kaihong-src/kaihong_adapter/robot-runtime/student/interfaces/aux_target_relay.py`
- Historical feedback-flow reference only: `vendor/kaihong-src/ros_ws/src/competition/scripts/navigation_transport/automatic_pick.py`

The historical example's topic names, multi-servo commands, and angular limit are not reused.
