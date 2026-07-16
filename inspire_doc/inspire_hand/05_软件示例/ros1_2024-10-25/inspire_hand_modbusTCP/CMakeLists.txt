cmake_minimum_required(VERSION 3.10)

# 设置项目名称
project(inspire_hand_modbus)  # 修改为小写

# 查找 libmodbus 库
find_package(PkgConfig REQUIRED)
pkg_check_modules(MODBUS REQUIRED libmodbus)

find_package(catkin REQUIRED COMPONENTS
  roscpp
  serial
  message_generation
  tf
  std_msgs
)

find_package(Boost REQUIRED)
include_directories(${Boost_INCLUDE_DIRS})


set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 包含头文件
include_directories(
  ${catkin_INCLUDE_DIRS}
  ${MODBUS_INCLUDE_DIRS}
)

# 添加服务文件
add_service_files(
  FILES
  get_current.srv
  get_error.srv
  get_pos_set.srv
  get_pos_act.srv
  get_force_act.srv
  get_force_set.srv
  get_angle_set.srv
  get_angle_act.srv
  get_temp.srv
  get_status.srv
  
  set_id.srv
  set_redu_ratio.srv
  set_pos.srv
  set_clear_error.srv
  set_reset_para.srv
  set_gesture_no.srv
  set_default_speed.srv
  set_speed.srv
  set_angle.srv
  set_save_flash.srv
  set_force.srv
  set_default_force.srv
  set_force_clb.srv
  set_current_limit.srv
)

# 指定消息生成
generate_messages(
  DEPENDENCIES
  std_msgs
)

catkin_package(
  CATKIN_DEPENDS roscpp rospy std_msgs message_runtime
)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/build)

# 添加可执行文件
add_executable(hand_modbus_control 
  src/main.cpp
  src/hand_control.cpp
)

add_executable(hand_control_hz 
  src/hand_control_hz.cpp
)

# 添加 hand_control_client 的可执行文件
add_executable(hand_control_client_modbus src/hand_control_client_modbus.cpp)

# 添加依赖
add_dependencies(hand_modbus_control ${catkin_EXPORTED_TARGETS} inspire_hand_modbus_gencpp)
add_dependencies(hand_control_client_modbus ${catkin_EXPORTED_TARGETS} inspire_hand_modbus_gencpp)

add_executable(handcontroltopicpublisher_modbus src/handcontroltopicpublisher_modbus.cpp)

# 链接库
target_link_libraries(hand_modbus_control
  ${catkin_LIBRARIES}
  ${MODBUS_LIBRARIES}
)

target_link_libraries(hand_control_hz
  ${catkin_LIBRARIES}
  ${MODBUS_LIBRARIES}
)

target_link_libraries(hand_control_client_modbus
  ${catkin_LIBRARIES}
  ${MODBUS_LIBRARIES}
)

target_link_libraries(handcontroltopicpublisher_modbus 
  ${catkin_LIBRARIES} 
  ${MODBUS_LIBRARIES}
  ${Boost_LIBRARIES}
)

