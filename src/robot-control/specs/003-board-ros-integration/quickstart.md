# Quickstart: Board ROS Integration Source Validation

## Hard Boundary

Run from the developer Mac with no HDC/SSH/ROS Master connection. Do not set a robot IP. These commands validate source and mocks only.

## Complete Tests with ROS Blocked

```bash
python3 -m unittest discover -s src/robot-control/control_ws/src/student_tasks/test -p 'test_*.py' -v
```

Expected: all domain, safety, approach, ROS-facade, lock, signal, configuration, store, source-contract, and deployment tests pass.

## Production Template Must Fail Closed

```bash
PYTHONPATH=src/robot-control/control_ws/src/student_tasks/src \
python3 src/robot-control/control_ws/src/student_tasks/scripts/robot_control_cli.py \
  --backend ros --config src/robot-control/control_ws/src/student_tasks/config/robot.measured.template.json status
```

Expected: one JSON failure describing unfilled measured fields. If ROS modules are absent, the result may also report ROS unavailable; it must not fall back to fake.

## Syntax and Manifest

```bash
python3 -m compileall -q src/robot-control/control_ws/src/student_tasks
sh -n src/robot-control/control_ws/src/student_tasks/deploy/robot-control
python3 -m json.tool src/robot-control/control_ws/src/student_tasks/deploy/board-manifest.json >/dev/null
```

Expected: all commands exit zero after implementation. This does not execute the board wrapper.

## Verification Label

The highest permitted result tonight is `SOURCE_VERIFIED_HIL_PENDING`. Continue with `specs/004-hil-validation-handoff/` only when the user is physically beside the robot and authorizes each movement.
