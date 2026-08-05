#!/system/bin/sh
set -eu

ROOT=/data/robot-host
[ "$ROOT" = /data/robot-host ] || {
    echo "ERROR: unexpected root: $ROOT" >&2
    exit 2
}
[ -d "$ROOT" ] || {
    echo "ERROR: missing $ROOT" >&2
    exit 2
}

# Student-facing documentation is consolidated into student/README.md.
rm -f -- \
    /data/robot-host/README.md \
    /data/robot-host/STATUS.md \
    /data/robot-host/MINIMAL-PICK-TRANSPORT-ASTRA.md

# Remove the complete fixed-pose reference demo. Keep student/demo because it
# contains the bounded, perception-only color sorting starter used by M-Claw.
rm -rf -- /data/robot-host/competition
rm -f -- \
    /data/robot-host/arm-stack.sh \
    /data/robot-host/calibrated-grasp-poses.yaml \
    /data/robot-host/capture-slam-pose-container.sh \
    /data/robot-host/execute-pregrasp-offset.py \
    /data/robot-host/hardware-audit-4.1.sh \
    /data/robot-host/probe-container-kinematics.py \
    /data/robot-host/probe-host-arm-imports.py \
    /data/robot-host/read-current-pose-container.sh \
    /data/robot-host/run-pregrasp-step-4.1.sh \
    /data/robot-host/run-solve-pregrasp-4.1.sh \
    /data/robot-host/solve-pregrasp-offset.py \
    /data/robot-host/start-arm-docker-4.1.sh \
    /data/robot-host/start-navigation-docker-4.1.sh \
    /data/robot-host/start-slam-docker-4.1.sh \
    /data/robot-host/test-host-arm-cutover-4.1.sh

# Historical calibration datasets are not runtime inputs.  The fixed Astra
# transform is backed up before this script is run and remains in place.
rm -rf -- \
    /data/robot-host/astra-arm-calibration/archive \
    /data/robot-host/astra-arm-red-calibration \
    /data/robot-host/astra-arm-red-pnp-calibration \
    /data/robot-host/d435i-arm-calibration
rm -f -- /data/robot-host/astra-arm-calibration/dataset.json

# Generated images, caches, backups and duplicate competition files.
rm -rf -- \
    /data/robot-host/__pycache__ \
    /data/robot-host/driver-backups
find /data/robot-host -type d -name __pycache__ -prune -exec rm -rf -- {} \; 2>/dev/null || true
rm -f -- \
    /data/robot-host/arm-camera-approach-final.jpg \
    /data/robot-host/arm-camera-blue-once.jpg \
    /data/robot-host/arm-camera-centered.jpg \
    /data/robot-host/arm-camera-jog.jpg \
    /data/robot-host/arm-camera-video20.jpg \
    /data/robot-host/arm-camera-video26.jpg \
    /data/robot-host/current-red-grasp-scene.jpg \
    /data/robot-host/current-scene-after-left.jpg \
    /data/robot-host/current-scene-after-turn.jpg \
    /data/robot-host/current-scene-after-turn2.jpg \
    /data/robot-host/current-scene.jpg \
    /data/robot-host/d435i-color.jpg \
    /data/robot-host/pregrasp-step.jpg \
    /data/robot-host/scene-detect-latest.jpg \
    /data/robot-host/scene-detect.jpg \
    /data/robot-host/arm-camera-jog.log \
    /data/robot-host/start-host-chassis.sh.bak-pre-no-config \
    /data/robot-host/mclaw-pick-demo-bridge.sh \
    /data/robot-host/minimal_pick_transport_astra_demo.py \
    /data/robot-host/minimal_pick_transport_astra.yaml \
    /data/robot-host/run-minimal-pick-transport-astra-4.1.sh

# Legacy engineering calibration scripts and one-off actuator experiments remain
# in the local repository. The supported student workflow under
# astra-arm-calibration/student is intentionally preserved.
rm -f -- \
    /data/robot-host/analyze-red-pnp-residuals.py \
    /data/robot-host/analyze-handeye-samples.py \
    /data/robot-host/astra-arm-handeye.py \
    /data/robot-host/astra-arm-red-calibration.py \
    /data/robot-host/astra-arm-red-pnp.py \
    /data/robot-host/d435i-arm-handeye.py \
    /data/robot-host/filter-handeye-dataset.py \
    /data/robot-host/replace-last-calibration-sample.py \
    /data/robot-host/run-astra-arm-calibration-4.1.sh \
    /data/robot-host/run-astra-arm-red-calibration-4.1.sh \
    /data/robot-host/run-astra-arm-red-pnp-4.1.sh \
    /data/robot-host/run-d435i-arm-calibration-4.1.sh \
    /data/robot-host/arm-camera-calibration-jog.py \
    /data/robot-host/run-arm-camera-calibration-jog-4.1.sh \
    /data/robot-host/arm-joints-small-motion-test.py \
    /data/robot-host/arm-small-motion-test.py \
    /data/robot-host/arm-visible-motion-test.py \
    /data/robot-host/arm-visible-sequence-test.py \
    /data/robot-host/run-arm-joints-small-motion-test-4.1.sh \
    /data/robot-host/run-arm-small-motion-test-4.1.sh \
    /data/robot-host/run-arm-visible-motion-test-4.1.sh \
    /data/robot-host/run-arm-visible-sequence-test-4.1.sh \
    /data/robot-host/command-arm-pulses-openloop.py \
    /data/robot-host/command-gripper-openloop.py \
    /data/robot-host/run-command-arm-pulses-4.1.sh \
    /data/robot-host/run-command-gripper-openloop-4.1.sh \
    /data/robot-host/test-forward-low.sh \
    /data/robot-host/run-low-motion-test.sh

# ROS logs are recreated.  Clear only the validated log directory.
if [ -d /data/robot-host/log ]; then
    find /data/robot-host/log -mindepth 1 -maxdepth 1 -exec rm -rf -- {} \;
fi
mkdir -p /data/robot-host/log /data/robot-host/run

echo "cleanup=PASS"
