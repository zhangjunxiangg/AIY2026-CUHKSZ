# Quickstart: Deferred Supervised HIL Validation

## Tonight's Boundary

Offline implementation may run without a board. It is limited to configuration validation,
manifest checking/staging into an explicitly local directory, session-record preparation,
and read-only observer code. Nothing in this phase contacts the board, creates a ROS
publisher, or sends velocity. The feature status remains `HIL_PENDING`.

The v2 production configuration can enable chassis motion while explicitly disabling
visual approach. A motion-only file omits `target`, `approach`, `calibration`, and the
three target ROS fields; it must not contain placeholder values. `approach` returns
`CAPABILITY_DISABLED` until the vision contract and calibration are measured.

Local checks:

```bash
PYTHONPATH=JUNXIANG/control_ws/src/student_tasks/src \
python3 JUNXIANG/control_ws/src/student_tasks/scripts/package_manifest.py \
  --manifest JUNXIANG/control_ws/src/student_tasks/deploy/board-manifest.json
```

The command is manifest-only by default. `--stage-dir <local-directory>` is the only
optional copy operation and stages locally; it never transfers or starts anything.

## Start a Session Tomorrow

1. Be physically beside the robot with a clear area, visible stop control, measurement tools, and video recording ready.
2. Confirm robot/board identity; record source revision, manifest/configuration/calibration digests, and the exact recoverable previous artifact.
3. Stage only the reviewed Spec 003 manifest, then run zero-output identity and smoke checks. Do not accept it for production yet.
4. Run the remaining Spec 003 status paths in read-only mode. Record graph, types, ownership, scan/target freshness, and persistent-estop state.
5. Run an explicit zero-only stop check. Do not infer readiness from it.
6. Work through [case-matrix.md](contracts/case-matrix.md) in dependency order.

The first board session must re-read the exact link and battery voltage. Battery
telemetry is recorded as environment evidence, but `11000 mV` is not a validated hard
gate for this robot. A reported power fault, missing `/scan`, unknown ownership, or an
unfilled measured configuration blocks all non-zero cases. M-Claw must be exited before
the control CLI owns `/cmd_vel`.

## Before Each Non-Zero Case

Use [supervision.md](contracts/supervision.md). Present the exact parameters, theoretical movement, expected direction, measured clearance, stop plan, and risk. Wait for the nearby operator to say `走`. Execute exactly once, stop, record evidence, and require a new proposal for any retry or next correction.

The first linear check starts at no more than:

```text
speed: 0.10 m/s
duration: 2.0 s
theoretical maximum: 0.20 m
```

Use a smaller value when the available clearance or robot condition calls for it. Rotation parameters are proposed only after measured sign/clearance review and remain below `0.50 rad/s` and `10.0 s`.

## Gate Order

```text
backup + manifest-only candidate staging + read-only smoke
  -> read-only preflight
  -> explicit stop
  -> six primitive directions
  -> ownership + lidar + persistent estop/reset
  -> stationary target/calibration
  -> one-step visual corrections
  -> visual failure modes
  -> bounded arrival
  -> production acceptance / rollback audit
  -> teammate handoff
```

Stop at the first failed or blocked prerequisite. A fix, reboot, redeploy, configuration change, or sensor movement requires re-preflight and may require a new session.

## Evidence Review

Validate every case record against `contracts/evidence-record.schema.json`. A case is accepted only when its required artifacts and stop evidence are linked, its context digests match the session, and reviewer rationale supports `PASS`. Never convert `BLOCKED` or `NOT_RUN` into a pass.

## Completion

Only after all mandatory rows pass in one compatible context may the handoff identify the complete control capability as `HIL_VERIFIED`. Otherwise report the exact accepted case IDs and keep the overall status `HIL_PENDING`.
