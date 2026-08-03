#!/system/bin/sh
set -eu

ROOT="${ROBOT_HOST_ROOT:-/data/robot-host}"
CAL="$ROOT/astra-arm-calibration"
STUDENT="$CAL/student"
WORK="$CAL/work"
VISION=rk3588s-vision
SOLVER="$STUDENT/astra-arm-handeye.py"
VALIDATOR="$STUDENT/validate-astra-handeye.py"
ACTIVE="$CAL/astra-to-base.json"
FACTORY="$CAL/factory-astra-to-base.json"
CANDIDATE="$WORK/candidate-astra-to-base.json"
DATASET="$WORK/dataset.json"
COMMAND="${1:-status}"

MARKER_ID="${MARKER_ID:-1}"
MARKER_SIZE_M="${MARKER_SIZE_M:-0.035}"
MARKER_DICTIONARY="${MARKER_DICTIONARY:-DICT_APRILTAG_36h11}"

require_file() {
    [ -f "$1" ] || {
        echo "ERROR: missing file: $1" >&2
        exit 2
    }
}

require_runtime() {
    require_file "$SOLVER"
    require_file "$VALIDATOR"
    "$ROOT/status-host-arm-4.1.sh" >/dev/null 2>&1 || {
        echo "ERROR: host arm is not ready" >&2
        exit 3
    }
    [ "$(docker inspect -f '{{.State.Running}}' "$VISION" 2>/dev/null || echo false)" = true ] || {
        echo "ERROR: Astra vision container is not running" >&2
        exit 4
    }
}

ensure_layout() {
    mkdir -p "$WORK"
    if [ -f "$ACTIVE" ] && [ ! -f "$FACTORY" ]; then
        cp "$ACTIVE" "$FACTORY.tmp"
        mv "$FACTORY.tmp" "$FACTORY"
        chmod 444 "$FACTORY" 2>/dev/null || true
    fi
}

prepare_container() {
    require_runtime
    ensure_layout
    docker exec "$VISION" rm -rf /tmp/student-astra-handeye /tmp/arm_interfaces
    docker exec "$VISION" mkdir -p /tmp/student-astra-handeye /tmp/arm_interfaces
    docker cp "$ROOT/host_arm/python/interfaces" "$VISION:/tmp/arm_interfaces/interfaces"
    docker cp "$SOLVER" "$VISION:/tmp/student-astra-handeye/astra-arm-handeye.py"
    docker cp "$VALIDATOR" "$VISION:/tmp/student-astra-handeye/validate-astra-handeye.py"
}

run_python() {
    docker exec "$VISION" bash -lc '
        source /opt/ros/noetic/setup.bash
        source /vision_ws/devel/setup.bash
        export PYTHONPATH=/tmp/arm_interfaces${PYTHONPATH:+:$PYTHONPATH}
        python3 "$@"
    ' bash "$@"
}

copy_dataset_in() {
    if [ -f "$DATASET" ]; then
        docker cp "$DATASET" "$VISION:/tmp/student-astra-handeye/dataset.json"
    fi
}

capture_training_sample() {
    prepare_container
    copy_dataset_in
    set +e
    run_python /tmp/student-astra-handeye/astra-arm-handeye.py capture \
        --dataset /tmp/student-astra-handeye/dataset.json \
        --image /tmp/student-astra-handeye/last-capture.jpg \
        --marker-id "$MARKER_ID" \
        --marker-size "$MARKER_SIZE_M" \
        --dictionary "$MARKER_DICTIONARY"
    rc=$?
    set -e
    docker cp "$VISION:/tmp/student-astra-handeye/last-capture.jpg" \
        "$WORK/last-capture.jpg" >/dev/null 2>&1 || true
    [ "$rc" -eq 0 ] || exit "$rc"
    docker cp "$VISION:/tmp/student-astra-handeye/dataset.json" "$DATASET"
    echo "LATEST_IMAGE=$WORK/last-capture.jpg"
}

verify_candidate() {
    require_file "$CANDIDATE"
    prepare_container
    docker exec "$VISION" rm -f \
        /tmp/student-astra-handeye/validation-dataset.json \
        /tmp/student-astra-handeye/validation-result.json
    docker cp "$CANDIDATE" "$VISION:/tmp/student-astra-handeye/candidate.json"
    run_python /tmp/student-astra-handeye/astra-arm-handeye.py capture \
        --dataset /tmp/student-astra-handeye/validation-dataset.json \
        --image /tmp/student-astra-handeye/last-validation.jpg \
        --marker-id "$MARKER_ID" \
        --marker-size "$MARKER_SIZE_M" \
        --dictionary "$MARKER_DICTIONARY"
    set +e
    run_python /tmp/student-astra-handeye/validate-astra-handeye.py \
        --solver /tmp/student-astra-handeye/astra-arm-handeye.py \
        --calibration /tmp/student-astra-handeye/candidate.json \
        --dataset /tmp/student-astra-handeye/validation-dataset.json \
        --output /tmp/student-astra-handeye/validation-result.json
    rc=$?
    set -e
    docker cp "$VISION:/tmp/student-astra-handeye/last-validation.jpg" \
        "$WORK/last-validation.jpg" >/dev/null 2>&1 || true
    docker cp "$VISION:/tmp/student-astra-handeye/validation-result.json" \
        "$WORK/validation-result.json" >/dev/null 2>&1 || true
    [ "$rc" -eq 0 ] || exit "$rc"
    cp "$CANDIDATE" "$WORK/validated-candidate.json"
}

install_candidate() {
    verify_candidate
    cmp -s "$CANDIDATE" "$WORK/validated-candidate.json" || {
        echo "ERROR: candidate changed after validation" >&2
        exit 5
    }
    [ ! -f "$ACTIVE" ] || cp "$ACTIVE" "$CAL/previous-astra-to-base.json"
    cp "$CANDIDATE" "$ACTIVE.tmp"
    mv "$ACTIVE.tmp" "$ACTIVE"
    echo "CALIBRATION_INSTALLED=$ACTIVE"
}

ensure_layout
case "$COMMAND" in
    marker)
        prepare_container
        run_python /tmp/student-astra-handeye/astra-arm-handeye.py marker \
            --marker-id "$MARKER_ID" \
            --marker-size "$MARKER_SIZE_M" \
            --dictionary "$MARKER_DICTIONARY" \
            --output /tmp/student-astra-handeye/marker.png
        docker cp "$VISION:/tmp/student-astra-handeye/marker.png" "$WORK/marker.png"
        echo "MARKER_IMAGE=$WORK/marker.png"
        echo "PRINT_BLACK_SQUARE_M=$MARKER_SIZE_M"
        ;;
    reset)
        rm -f "$DATASET" "$CANDIDATE" \
            "$WORK/last-capture.jpg" "$WORK/last-validation.jpg" \
            "$WORK/validation-result.json" "$WORK/validated-candidate.json"
        echo "STUDENT_DATASET_RESET=PASS"
        ;;
    capture)
        capture_training_sample
        ;;
    status)
        prepare_container
        copy_dataset_in
        run_python /tmp/student-astra-handeye/astra-arm-handeye.py status \
            --dataset /tmp/student-astra-handeye/dataset.json
        ;;
    solve)
        require_file "$DATASET"
        prepare_container
        docker cp "$DATASET" "$VISION:/tmp/student-astra-handeye/dataset.json"
        set +e
        run_python /tmp/student-astra-handeye/astra-arm-handeye.py solve \
            --dataset /tmp/student-astra-handeye/dataset.json \
            --output /tmp/student-astra-handeye/candidate.json
        rc=$?
        set -e
        docker cp "$VISION:/tmp/student-astra-handeye/candidate.json" "$CANDIDATE" \
            >/dev/null 2>&1 || true
        [ -f "$CANDIDATE" ] && echo "CANDIDATE=$CANDIDATE"
        exit "$rc"
        ;;
    verify)
        verify_candidate
        echo "VALIDATION=$WORK/validation-result.json"
        ;;
    install)
        install_candidate
        ;;
    restore-factory)
        require_file "$FACTORY"
        [ ! -f "$ACTIVE" ] || cp "$ACTIVE" "$CAL/previous-astra-to-base.json"
        cp "$FACTORY" "$ACTIVE.tmp"
        mv "$ACTIVE.tmp" "$ACTIVE"
        echo "FACTORY_CALIBRATION_RESTORED=$ACTIVE"
        ;;
    transform)
        [ "$#" -eq 4 ] || {
            echo "Usage: $0 transform CAMERA_X CAMERA_Y CAMERA_Z" >&2
            exit 2
        }
        require_file "$ACTIVE"
        prepare_container
        docker cp "$ACTIVE" "$VISION:/tmp/student-astra-handeye/active.json"
        run_python /tmp/student-astra-handeye/astra-arm-handeye.py transform \
            --calibration /tmp/student-astra-handeye/active.json \
            --x "$2" --y "$3" --z "$4"
        ;;
    self-test)
        prepare_container
        run_python /tmp/student-astra-handeye/astra-arm-handeye.py self-test
        ;;
    *)
        echo "Usage: $0 {marker|reset|capture|status|solve|verify|install|restore-factory|transform|self-test}" >&2
        exit 2
        ;;
esac
