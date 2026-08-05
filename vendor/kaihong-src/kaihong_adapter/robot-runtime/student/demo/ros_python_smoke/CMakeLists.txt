cmake_minimum_required(VERSION 3.0.2)
project(ros_python_smoke)

find_package(catkin REQUIRED COMPONENTS rospy)

catkin_package()

catkin_install_python(
  PROGRAMS scripts/hello_ros.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
