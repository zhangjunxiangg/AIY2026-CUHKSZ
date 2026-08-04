# Student Motion Control

This package contains Zhang Junxiang's chassis-control deliverables. The pure
Python domain core is shared by the synchronous CLI and visual approach logic;
ROS adapters remain at the package boundary.

## Offline Boundary

Run all local checks from the repository root without HDC, SSH, ROS, or robot
access:

```bash
python3 -m unittest discover -s JUNXIANG/control_ws/src/student_tasks/test -p 'test_*.py' -v
```

Fake-backend results are `OFFLINE_VERIFIED`. ROS source/mock results are
`SOURCE_VERIFIED_HIL_PENDING`. Only the deferred supervised HIL procedure may
assign `HIL_VERIFIED`.

The package never publishes `motor_type` and never accesses the controller's
forbidden low-level motor service.
