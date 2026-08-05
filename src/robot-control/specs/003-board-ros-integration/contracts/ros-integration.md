# ROS Integration Contract v1

## Authoritative Topics

| Role | Default | Type | Motion rule |
|---|---|---|---|
| Chassis output | `/cmd_vel` | `geometry_msgs/Twist` | only production output; x/y/angular z only |
| Safety scan | `/scan` | `sensor_msgs/LaserScan` | required fresh evidence for automatic non-zero movement |
| Target data | `/competition/aux_target_json` | `std_msgs/String` | must contain `robot-control/target-observation/v1` |
| Target validity | `/competition/aux_target_valid` | `std_msgs/Bool` | must be true and fresh with target data |
| Point diagnostic | `/competition/aux_target` | `geometry_msgs/PointStamped` | status only; never sufficient by itself for movement |

Production configuration names each topic explicitly. Missing values are not replaced by these documented candidates.

## Readiness

Non-zero readiness is the conjunction of:

1. ROS modules and Master available.
2. Measured configuration valid.
3. Explicit operator authorization present.
4. Project lock held.
5. `/cmd_vel` has at least one subscriber.
6. No publisher other than the exact current node and measured allowlist.
7. Persistent emergency-stop state is clear.
8. A fresh scan passes Spec 002 directional safety for the requested velocity.
9. Required target providers contain contract-valid fresh data for automatic approach.

`stop` bypasses items 2-9 as necessary to attempt zero output, but it reports each degraded condition.

## Twist Mapping

Domain `linear_x`, `linear_y`, and `angular_z` are multiplied only by their measured direction signs, then assigned to `Twist.linear.x`, `Twist.linear.y`, and `Twist.angular.z`. All other fields remain zero. The backend has no API for `motor_type` or `/ros_robot_controller/set_motor`.

## Signal Contract

SIGINT, SIGTERM, and SIGHUP set cancellation state only. Publishing/logging/file operations never run inside the handler. Core polling observes cancellation and executes its normal terminal zero sequence.

## CLI Extension

```text
robot-control --backend ros --config FILE status
robot-control --backend ros --config FILE stop
robot-control --backend ros --config FILE --operator-confirmed move ...
robot-control --backend ros --config FILE --operator-confirmed approach
robot-control --backend ros --config FILE estop-reset
```

All commands preserve `robot-control/v1` one-JSON-result output and Spec 001 exit classes.
