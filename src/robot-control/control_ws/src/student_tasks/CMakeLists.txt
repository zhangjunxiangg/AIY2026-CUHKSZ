cmake_minimum_required(VERSION 3.0.2)
project(student_tasks)

find_package(catkin REQUIRED COMPONENTS
  geometry_msgs
  rosgraph
  rospy
  sensor_msgs
  std_msgs
)

catkin_package(
  CATKIN_DEPENDS geometry_msgs rosgraph rospy sensor_msgs std_msgs
)

catkin_install_python(PROGRAMS
  scripts/board_smoke_test.py
  scripts/cmd_vel_observer.py
  scripts/hil_session.py
  scripts/package_manifest.py
  scripts/robot_control_cli.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY src/student_tasks/
  DESTINATION ${CATKIN_PACKAGE_PYTHON_DESTINATION}
  FILES_MATCHING PATTERN "*.py"
)

install(FILES
  README.md
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)

install(FILES
  config/robot.measured.template.json
  config/robot.motion.measured.template.json
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/config
)

install(PROGRAMS
  deploy/robot-control
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/deploy
)

install(FILES
  deploy/README.md
  deploy/board-manifest.json
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/deploy
)
