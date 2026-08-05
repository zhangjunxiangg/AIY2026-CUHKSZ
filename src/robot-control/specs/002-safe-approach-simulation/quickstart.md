# Quickstart: Safe Approach Offline Validation

## Boundary

Run only on the developer Mac. The fixture file is explicitly synthetic; success means algorithmic behavior only.

## Full Tests

```bash
python3 -m unittest discover -s src/robot-control/control_ws/src/student_tasks/test -p 'test_*.py' -v
```

Expected: existing domain-core tests and the new geometry, perception, safety, and approach tests all pass with no ROS import.

## Focused Safety Tests

```bash
python3 -m unittest discover -s src/robot-control/control_ws/src/student_tasks/test -p 'test_safety.py' -v
```

Expected coverage includes every translation direction, diagonals, rotation, invalid/stale scans, insufficient rays, obstacle latch, and deliberate reset.

## Focused Approach Tests

```bash
python3 -m unittest discover -s src/robot-control/control_ws/src/student_tasks/test -p 'test_approach.py' -v
```

Expected: scripted sequences cover rotate, translate, stable visual verification, target loss, safety latch, cancellation, timeout, iteration bound, motion failure, and stop failure.

## Production Rejection

The synthetic file `control_ws/src/student_tasks/config/offline.synthetic.json` may drive tests only. Loading it through the later ROS production backend must return `PRODUCTION_CONFIG_REQUIRED` before any non-zero velocity.
