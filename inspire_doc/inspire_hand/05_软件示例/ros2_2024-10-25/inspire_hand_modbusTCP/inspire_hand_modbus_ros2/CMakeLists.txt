cmake_minimum_required(VERSION 3.8)
project(inspire_hand_modbus_ros2)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 查找依赖项
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(service_interfaces REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(message_filters REQUIRED)
find_package(example_interfaces REQUIRED)
find_package(std_msgs REQUIRED)  # 确保添加 std_msgs
find_package(rosidl_default_generators REQUIRED)

# 查找 modbus 库
find_library(MODBUS_LIBRARIES NAMES modbus REQUIRED)

# 添加 modbus 的头文件路径
include_directories(/usr/include/modbus)

include_directories(include ${ament_INCLUDE_DIRS})

# 设置可执行文件输出目录
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

# 添加可执行文件
add_executable(hand_modbus_control_node 
  src/hand_control.cpp
)

add_executable(hand_control_client_modbus_node 
  src/hand_control_client_modbus.cpp
)

add_executable(handcontroltopicpublisher_modbus_node 
  src/handcontroltopicpublisher_modbus.cpp
)

add_executable(handcontroltopicsubscriber_modbus_node 
  src/handcontroltopicsubscriber_modbus.cpp
)

# 添加依赖
ament_target_dependencies(hand_modbus_control_node
  rclcpp
  service_interfaces
  std_msgs
)

ament_target_dependencies(hand_control_client_modbus_node
  rclcpp
  service_interfaces
  std_msgs
)

ament_target_dependencies(handcontroltopicpublisher_modbus_node
  rclcpp
  service_interfaces
  std_msgs
)

ament_target_dependencies(handcontroltopicsubscriber_modbus_node
  rclcpp
  service_interfaces
  std_msgs
)

# 链接 modbus 库
target_link_libraries(hand_modbus_control_node ${MODBUS_LIBRARIES})
target_link_libraries(hand_control_client_modbus_node ${MODBUS_LIBRARIES})
target_link_libraries(handcontroltopicpublisher_modbus_node ${MODBUS_LIBRARIES})
target_link_libraries(handcontroltopicsubscriber_modbus_node ${MODBUS_LIBRARIES})

# 安装目标
install(TARGETS
  hand_modbus_control_node
  hand_control_client_modbus_node
  handcontroltopicpublisher_modbus_node
  handcontroltopicsubscriber_modbus_node
  DESTINATION lib/${PROJECT_NAME}
)

# 测试和代码检查
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

# 最后，调用 ament_package()
ament_package()

