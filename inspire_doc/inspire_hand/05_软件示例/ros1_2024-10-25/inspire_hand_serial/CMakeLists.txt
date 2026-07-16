cmake_minimum_required(VERSION 2.8.3)
project(inspire_hand)

find_package(catkin REQUIRED COMPONENTS
  roscpp
  serial
  message_generation
  tf
  std_msgs
  genmsg
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 设置可执行文件的输出目录
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/build)  # 可执行文件
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/build)  # 动态库

include_directories(
  ${catkin_INCLUDE_DIRS}
  ${PROJECT_SOURCE_DIR}/include/
)

# 设置源文件
set(SOURCES
  src/hand_control.cpp
  src/hand_control_lib.cpp
)

# 设置头文件
set(HEADERS
  include/hand_control.h
)

# 遍历添加服务文件
set(SERVICE_FILES
  set_id.srv
  set_redu_ratio.srv
  set_clear_error.srv
  set_save_flash.srv
  set_reset_para.srv
  set_force_clb.srv
  set_gesture_no.srv
  set_current_limit.srv
  set_default_speed.srv
  set_default_force.srv
  set_user_def_angle.srv
  set_pos.srv
  set_angle.srv
  set_force.srv
  set_speed.srv
  get_pos_act.srv
  get_angle_act.srv
  get_force_act.srv
  get_current.srv
  get_error.srv
  get_status.srv
  get_temp.srv
  get_pos_set.srv
  get_angle_set.srv
  get_force_set.srv
)

foreach(SERVICE_FILE ${SERVICE_FILES})
  add_service_files(FILES ${SERVICE_FILE})
endforeach()

generate_messages(DEPENDENCIES std_msgs)

catkin_package(
  INCLUDE_DIRS include
  LIBRARIES
  DEPENDS roscpp serial tf
)

add_executable(${PROJECT_NAME} ${SOURCES} ${HEADERS})
add_dependencies(${PROJECT_NAME} ${catkin_EXPORTED_TARGETS} inspire_hand_gencpp)
target_link_libraries(${PROJECT_NAME} ${ROS_LIBRARIES} ${catkin_LIBRARIES})

# 添加其他可执行文件
set(EXECUTABLES
  hand_control_client
  handcontroltopicpublisher
  handcontroltopicsubscriber
  handcontroltopicpublisher1
  handcontroltopicsubscriber1
)

foreach(EXECUTABLE ${EXECUTABLES})
  add_executable(${EXECUTABLE} src/${EXECUTABLE}.cpp)
  target_link_libraries(${EXECUTABLE} ${ROS_LIBRARIES} ${catkin_LIBRARIES})
  add_dependencies(${EXECUTABLE} inspire_hand_gencpp)
endforeach()

