# Approach Contract v1

## Provider Interfaces

- `TargetProvider.latest(now)` returns one raw target observation or a structured absence reason.
- `ScanProvider.latest(now)` returns one scan snapshot or a structured absence reason.
- Providers MUST NOT block beyond the approach controller's injected timing policy.
- The controller normalizes targets and evaluates scans; providers do not authorize motion.

## State Semantics

| State | Entry evidence | Allowed non-zero command | Exit |
|---|---|---|---|
| `PRECHECK` | fresh target + scan + configuration | none | rotate, translate, verify, or terminal failure |
| `ROTATE` | bearing outside tolerance + safety allow | bounded angular z only | stop then re-observe |
| `TRANSLATE` | aligned target beyond stand-off + safety allow | bounded positive linear x only | stop then re-observe |
| `VERIFY` | target within both tolerances | none | increment stable count or resume correction |
| `STOPPING` | every terminal route | zero only | terminal state |

`SUCCEEDED` requires the configured number of consecutive fresh visual confirmations. No command integration or odometry field is accepted as arrival evidence.

## Stable Terminal Errors

`TARGET_UNAVAILABLE`, `TARGET_STALE`, `TARGET_INVALID`, `TARGET_FRAME_INVALID`, `CALIBRATION_REQUIRED`, `TARGET_TOO_CLOSE`, `SCAN_UNAVAILABLE`, `SAFETY_REJECTED`, `ESTOP_LATCHED`, `CANCELLED`, `APPROACH_TIMEOUT`, `ITERATION_LIMIT`, `MOTION_FAILED`, and `STOP_FAILED`.

## Execution Boundary

The approach controller calls `MotionController.move` directly inside its process. An implementation that invokes `robot_control_cli.py move` for each correction violates this contract.
