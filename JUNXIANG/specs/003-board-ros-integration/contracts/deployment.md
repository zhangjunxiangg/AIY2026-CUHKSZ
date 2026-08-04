# Board Deployment Contract

## Boundary

This feature prepares files only. It does not connect, copy, remount, launch ROS, publish, install an init service, or move hardware.

## Target Root

```text
/data/local/robot/jx/control_ws/
```

The wrapper command is:

```text
/data/local/robot/jx/control_ws/src/student_tasks/deploy/robot-control
```

It sets package `PYTHONPATH` and executes the CLI through `/bin/run python3`. Every command is self-contained and does not depend on a previous shell.

## Bundle Rules

- `board-manifest.json` is the complete allowlist of deployment files.
- `robot.measured.template.json` is included only as a template and is rejected until every required value is measured and dated.
- `offline.synthetic.json`, tests, fixtures, specs, secrets, IP addresses, keys, tokens, and local environment files are not production manifest entries.
- `board_smoke_test.py` is read-only and cannot construct a non-zero motion request.
- No `init.cfg` is delivered before HIL approval.
