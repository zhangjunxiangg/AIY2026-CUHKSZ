# Quickstart: Motion Domain Core Offline Validation

## Prerequisites

- Run from repository root on the developer Mac.
- Do not connect HDC, SSH, a ROS Master, or a robot.
- Python 3.11 or newer is available.

## Test Suite

```bash
python3 -m unittest discover -s src/robot-control/control_ws/src/student_tasks/test -p 'test_*.py' -v
```

Expected: limit, control-core, fake-backend, and CLI tests pass without ROS imports or network access.

## Fake Status

```bash
PYTHONPATH=src/robot-control/control_ws/src/student_tasks/src \
python3 src/robot-control/control_ws/src/student_tasks/scripts/robot_control_cli.py --backend fake status
```

Expected: one JSON line with `ok=true`, backend `fake`, and verification `OFFLINE_VERIFIED`.

## Fake Bounded Move

```bash
PYTHONPATH=src/robot-control/control_ws/src/student_tasks/src \
python3 src/robot-control/control_ws/src/student_tasks/scripts/robot_control_cli.py --backend fake move \
  --linear-x 0.10 --linear-y 0 --angular-z 0 --duration 0.10 --operation-id offline-demo
```

Expected: one success object whose evidence ends in zero velocity. This is simulation only and must not be described as robot movement.

## Fail-Closed Boundary

```bash
PYTHONPATH=src/robot-control/control_ws/src/student_tasks/src \
python3 src/robot-control/control_ws/src/student_tasks/scripts/robot_control_cli.py --backend fake move \
  --linear-x 0.20 --linear-y 0.20 --angular-z 0 --duration 1
```

Expected: exit code `2`, `LIMIT_EXCEEDED`, and no non-zero backend event.

Selecting `--backend ros` before Spec 003 must return `BACKEND_UNAVAILABLE`; it must never contact a ROS Master or fall back to fake.
