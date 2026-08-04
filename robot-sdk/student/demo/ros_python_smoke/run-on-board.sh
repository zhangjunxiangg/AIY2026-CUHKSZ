#!/system/bin/sh
set -eu

SOURCE=/data/robot-host/student/demo/ros_python_smoke
IMAGE=rk3588s-ros1-vision:noetic

test -f "$SOURCE/CMakeLists.txt"
test -f "$SOURCE/package.xml"
test -f "$SOURCE/scripts/hello_ros.py"

docker run --rm \
    -v "$SOURCE:/input:ro" \
    --entrypoint bash \
    "$IMAGE" -lc '
set -e
export ROS_MASTER_URI=http://127.0.0.1:11311
source /opt/ros/noetic/setup.bash
mkdir -p /tmp/ros_python_smoke_ws/src
cp -a /input /tmp/ros_python_smoke_ws/src/ros_python_smoke
chmod 755 /tmp/ros_python_smoke_ws/src/ros_python_smoke/scripts/hello_ros.py
cd /tmp/ros_python_smoke_ws
catkin_make
source devel/setup.bash
roscore >/tmp/roscore.log 2>&1 &
roscore_pid=$!
trap "kill $roscore_pid >/dev/null 2>&1 || true" EXIT
ready=0
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if rostopic list >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 1
done
test "$ready" -eq 1
rosrun ros_python_smoke hello_ros.py
'
