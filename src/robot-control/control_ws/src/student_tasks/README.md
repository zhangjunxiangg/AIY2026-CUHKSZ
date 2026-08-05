# Student Motion Control

This ROS1 package contains Zhang Junxiang's chassis motion primitives and
visual-approach integration. One pure-Python `MotionController` owns limits,
timing, terminal stop behavior, and result formatting. The fake backend and ROS
backend both use that core; the approach controller calls it directly in the
same process and never launches movement subprocesses.

Current completion level: `SOURCE_VERIFIED_HIL_PENDING`. No result in this
package proves that a physical robot moved, stopped, avoided an obstacle, or
arrived.

## Architecture

```text
robot_control_cli.py
  -> cli.py
     -> MotionController -----------------> FakeBackend
     -> ApproachController                 RosMotionBackend -> /cmd_vel
          -> RosScanProvider  <------------ /scan
          -> RosTargetProvider <----------- target JSON + validity

board_smoke_test.py -> configuration + graph + provider diagnostics only
```

Production motion has two ownership gates: a project `fcntl` process lock and
ROS graph conflict detection. Every non-zero publish also rechecks the lock,
subscriber, publisher conflicts, persistent emergency-stop state, and fresh
directional scan safety. SIGINT, SIGTERM, and SIGHUP set cancellation state;
the shared core performs the zero sequence outside the signal handler.

## Safety Invariants

- Planar speed magnitude is at most `0.20 m/s`, angular speed is at most
  `0.50 rad/s`, and duration is `0.1..10.0 s`.
- Production `move` and `approach` require `--operator-confirmed` in addition
  to the nearby-operator procedure in Spec 004.
- Missing, stale, synthetic, corrupt, or conflicting production evidence fails
  closed. Production selection never falls back to the fake backend.
- A missing or corrupt persistent estop file is treated as latched.
- `estop-reset` is zero-only and requires distinct consecutive fresh scans that
  are clear in every direction.
- `stop` may use a minimal zero-only configuration when unrelated production
  fields are invalid. It still requires an explicit topic, node name, zero
  sequence, and watchdog value and never substitutes a default topic.
- The only chassis output is configured `geometry_msgs/Twist` semantics. This
  package never publishes `motor_type` and never accesses
  `/ros_robot_controller/set_motor`.

## Offline Validation

Run from the repository root without HDC, SSH, ROS Master, network discovery,
or robot access:

```bash
python3 -m unittest discover \
  -s src/robot-control/control_ws/src/student_tasks/test \
  -p 'test_*.py' -v

python3 -m compileall -q src/robot-control/control_ws/src/student_tasks
sh -n src/robot-control/control_ws/src/student_tasks/deploy/robot-control
python3 -m json.tool \
  src/robot-control/control_ws/src/student_tasks/deploy/board-manifest.json >/dev/null
```

The fake CLI uses virtual time and performs no ROS or network operation:

```bash
PYTHONPATH=src/robot-control/control_ws/src/student_tasks/src \
python3 src/robot-control/control_ws/src/student_tasks/scripts/robot_control_cli.py \
  --backend fake status

PYTHONPATH=src/robot-control/control_ws/src/student_tasks/src \
python3 src/robot-control/control_ws/src/student_tasks/scripts/robot_control_cli.py \
  --backend fake move \
  --linear-x 0.10 --linear-y 0.00 --angular-z 0.00 --duration 0.10
```

Fake results are `OFFLINE_VERIFIED`; ROS mock and source results are
`SOURCE_VERIFIED_HIL_PENDING`.

## Measured Configuration

`config/robot.measured.template.json` is intentionally null and must remain
fail-closed. Create the board's `robot.measured.json` only from dated physical
measurements; do not fill it from examples or synthetic fixtures.

For chassis-only work before vision/calibration is accepted, use
`config/robot.motion.measured.template.json` as the v2 shape. It sets
`capabilities.motion=true` and `capabilities.approach=false`, and deliberately omits
the target, approach, calibration, and target ROS fields. The CLI rejects `approach`
with `CAPABILITY_DISABLED` and does not subscribe to a target provider.

Required evidence groups are:

| Group | Required measured facts |
|---|---|
| `provenance` | robot ID, source record, measurement time |
| `ros` | node prefix and exact cmd/scan topics; target topics/schema only when approach is enabled |
| `motion` | three direction signs, cadence, zero sequence, subscriber and watchdog timing |
| `ownership` | project-local lock/estop paths and evidence-backed publisher allowlist |
| `safety` | scan freshness and front/rear/left/right sector geometry, clearance, sample counts |
| `target` / `approach` / `calibration` | source/receive freshness, bounded corrections, and calibration only when approach is enabled |

An empty publisher allowlist needs no evidence. Any non-empty allowlist requires
a dated graph capture. Lock and estop paths must remain below
`/data/local/robot/jx/control_ws/`.

Validate the template rejection locally:

```bash
PYTHONPATH=src/robot-control/control_ws/src/student_tasks/src \
python3 src/robot-control/control_ws/src/student_tasks/scripts/robot_control_cli.py \
  --backend ros \
  --config src/robot-control/control_ws/src/student_tasks/config/robot.measured.template.json \
  status
```

Expected: exit `3`, one `robot-control/v1` JSON failure with
`PRODUCTION_CONFIG_REQUIRED`, no ROS fallback, and no motion.

## Production Commands

After the manifest has been reviewed and placed at
`/data/local/robot/jx/control_ws/`, the self-contained wrapper is:

```text
/data/local/robot/jx/control_ws/src/student_tasks/deploy/robot-control
```

The following are interface examples for the supervised Spec 004 session. Do
not run them as offline verification:

```sh
/data/local/robot/jx/control_ws/src/student_tasks/deploy/robot-control \
  --backend ros \
  --config /data/local/robot/jx/control_ws/src/student_tasks/config/robot.measured.json \
  status

/data/local/robot/jx/control_ws/src/student_tasks/deploy/robot-control \
  --backend ros \
  --config /data/local/robot/jx/control_ws/src/student_tasks/config/robot.measured.json \
  stop

/data/local/robot/jx/control_ws/src/student_tasks/deploy/robot-control \
  --backend ros \
  --config /data/local/robot/jx/control_ws/src/student_tasks/config/robot.measured.json \
  estop-reset

/data/local/robot/jx/control_ws/src/student_tasks/deploy/robot-control \
  --backend ros \
  --config /data/local/robot/jx/control_ws/src/student_tasks/config/robot.measured.json \
  --operator-confirmed move \
  --linear-x 0.10 --linear-y 0.00 --angular-z 0.00 --duration 0.10

/data/local/robot/jx/control_ws/src/student_tasks/deploy/robot-control \
  --backend ros \
  --config /data/local/robot/jx/control_ws/src/student_tasks/config/robot.measured.json \
  --operator-confirmed approach
```

Each invocation writes exactly one `robot-control/v1` JSON object to stdout.
Exit classes are `0` success, `2` input validation, `3` unavailable/readiness,
`4` runtime/cancellation, and `5` unconfirmed stop safety.

## Visual Target Contract

Automatic approach requires both configured `std_msgs/String` target JSON and
`std_msgs/Bool` validity topics. Point-only diagnostics are not accepted for
motion. JSON schema `robot-control/target-observation/v1` supports:

- `base_point`: `observed_at`, `frame_id=base_link`, `valid=true`, confidence,
  provenance source, and finite `x/y/z` in metres.
- `pixel_depth`: the same evidence plus calibrated camera frame and finite
  `u/v/depth_m`; depth must be positive.

Source timestamp and monotonic receive time are checked independently. Missing
confidence/provenance, false validity, stale/future data, wrong frames, unknown
fields, or schema mismatch keep movement stopped.

## Bundle and HIL Boundary

`deploy/board-manifest.json` is the complete production file allowlist.
`scripts/board_smoke_test.py` validates configuration, graph, scan, and target
readiness without constructing a motion request or publisher. The bundle has no
transfer script and no automatic-start service.

Deployment, measured-value backfill, direction checks, lidar clearance,
watchdog timing, signal behavior, persistent estop across real processes, and
visual arrival all remain under
`specs/004-hil-validation-handoff/`. Only that supervised evidence may promote
individual cases or the complete capability to `HIL_VERIFIED`.

The local HIL helpers are bounded: `hil_session.py` records explicit identity and
digests, `package_manifest.py` validates the allowlist and optionally stages to a
local directory, and `cmd_vel_observer.py` only observes `geometry_msgs/Twist`.
None performs board transfer, startup, or motion.
