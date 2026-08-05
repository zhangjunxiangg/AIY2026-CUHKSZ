# Board Bundle

This directory defines a source-only, manually reviewed board bundle. Nothing
here copies files, changes mount state, starts a process, installs a service, or
issues a motion command.

## Prepare

1. Validate every entry in `board-manifest.json` against the local source tree.
2. Place each allowed source at its exact target path and apply the listed mode.
3. Keep `robot.measured.template.json` unchanged as the fail-closed reference.
4. After supervised measurements exist, create an untracked
   `config/robot.measured.json` on the board and fill every required field. For an
   earlier chassis-only session, use the v2 motion-only shape and leave approach
   disabled until the target contract and calibration are accepted.

The measured file must not contain credentials or host addresses. Its topic,
direction, clearance, timing, calibration, ownership, and allowlist values must
come from dated board evidence.

## Read-Only Check

Run the smoke entry only after the files and measured configuration have been
reviewed:

```sh
PYTHONPATH=/data/local/robot/jx/control_ws/src/student_tasks/src \
/bin/run python3 /data/local/robot/jx/control_ws/src/student_tasks/scripts/board_smoke_test.py \
  --config /data/local/robot/jx/control_ws/src/student_tasks/config/robot.measured.json
```

The command subscribes to configured data and inspects the graph. It does not
create a velocity publisher. Its maximum claim is
`SOURCE_VERIFIED_HIL_PENDING`.

For a motion-only v2 configuration, the smoke result reports the target provider as
`CAPABILITY_DISABLED`; that is expected and is not target readiness.

## Control Entry

The wrapper is self-contained:

```sh
/data/local/robot/jx/control_ws/src/student_tasks/deploy/robot-control \
  --backend ros \
  --config /data/local/robot/jx/control_ws/src/student_tasks/config/robot.measured.json \
  status
```

Movement remains subject to the separate supervised HIL procedure and explicit
operator confirmation. No automatic startup configuration is part of this
bundle.
