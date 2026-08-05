# Supervised Motion Contract

## Non-Zero Gate

For each individual non-zero action, present all of:

1. Case and attempt ID.
2. Exact `linear_x`, `linear_y`, `angular_z`, and duration.
3. Planar magnitude and theoretical maximum displacement/rotation.
4. Expected robot-relative direction.
5. Measured free space and active lidar sector.
6. Stop/estop method and who controls it.
7. Specific collision, sign, tipping, cable, and perception risks.

Then ask the nearby operator for authorization. Only the exact response `走` authorizes the immediately proposed action. The procedure records the authorization time and consumes it when the command begins.

## Invalid Authorization

Silence, prior approval, “continue”, a remote message, another person, approval before parameters are shown, or approval followed by any changed parameter/context is invalid. A retry always requires a fresh proposal and fresh `走`.

## Stop Priority

Zero velocity, stop, and estop never wait for authorization. Any operator concern, unexpected direction, lost ownership, stale scan, target loss, or control error immediately enters the explicit-stop path and blocks dependent cases.

## First-Motion Rule

After boot, deployment, configuration/sensor change, or re-preflight, begin at no more than `0.10 m/s` for `2.0 s` for linear motion and a comparably small bounded rotation. Reduce further when clearance or mounting warrants it. Constitutional maxima remain absolute ceilings, not suggested test values.
