cmake_minimum_required(VERSION 3.0.2)
project(chassis_controller)

find_package(catkin REQUIRED COMPONENTS geometry_msgs sensor_msgs rospy ros_robot_controller)
catkin_python_setup()
catkin_package()

catkin_install_python(PROGRAMS
  scripts/chassis_controller_node.py
  scripts/gamepad_teleop_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY launch config
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
