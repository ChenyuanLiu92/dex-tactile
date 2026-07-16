#include <ros/ros.h>
#include <inspire_hand_modbus/set_id.h>
#include <inspire_hand_modbus/set_redu_ratio.h>
#include <inspire_hand_modbus/set_pos.h>
#include <cstdlib>
#include "hand_control.h"
#include <modbus.h> 

// Modbus 客户端的全局变量
modbus_t *ctx;

// 发送 Modbus 请求
void sendModbusPositionCommand(int pos0, int pos1, int pos2, int pos3, int pos4, int pos5) {
    // 起始寄存器地址
    uint16_t startAddress = 0x05CE; // 根据需求修改起始地址
    uint16_t registerCount = 6;      // 总共 6 个寄存器值

    // 创建要发送的数据
    uint16_t data[6] = {pos0, pos1, pos2, pos3, pos4, pos5};

    // 发送数据
    int rc = modbus_write_registers(ctx, startAddress, registerCount, data);
    if (rc == -1) {
        ROS_ERROR("Failed to write registers: %s", modbus_strerror(errno));
    } else {
        ROS_INFO("Successfully wrote %d positions to Modbus starting from address 0x%04X", registerCount, startAddress);
    }

    // 读取响应（如果需要）
    uint8_t response[256];
    int response_length = modbus_receive(ctx, response);
    if (response_length >= 0) {
        // 处理响应内容
        ROS_INFO("Received response from Modbus server");
    } else {
        ROS_ERROR("Failed to read response from Modbus server: %s", modbus_strerror(errno));
    }
}

int main(int argc, char **argv) {
    ros::init(argc, argv, "hand_control_client");
    ros::NodeHandle nh;

    // 创建 Modbus TCP 客户端
    ctx = modbus_new_tcp("192.168.11.210", 6000); 
    if (modbus_connect(ctx) == -1) {
        ROS_ERROR("Unable to connect to Modbus server: %s", modbus_strerror(errno));
        return -1;
    }

    // 创建服务客户端
    ros::ServiceClient setIdClient = nh.serviceClient<inspire_hand_modbus::set_id>("inspire_hand_modbus/set_id");
    ros::ServiceClient setRatioClient = nh.serviceClient<inspire_hand_modbus::set_redu_ratio>("inspire_hand_modbus/set_redu_ratio");
    ros::ServiceClient setPosClient = nh.serviceClient<inspire_hand_modbus::set_pos>("inspire_hand_modbus/set_pos");

    // 创建服务请求
    inspire_hand_modbus::set_id setIdSrv;
    inspire_hand_modbus::set_redu_ratio setRatioSrv;
    inspire_hand_modbus::set_pos setPosSrv;

    // 设置 ID
    setIdSrv.request.id = 1; // 示例值
    if (setIdClient.call(setIdSrv)) {
        ROS_INFO("Set ID successful: %d", setIdSrv.response.success);
    } else {
        ROS_ERROR("Failed to call service set_id");
    }

    // 设置减速比
    setRatioSrv.request.redu_ratio = 10; // 示例值
    if (setRatioClient.call(setRatioSrv)) {
        ROS_INFO("Set reduction ratio successful: %d", setRatioSrv.response.success);
    } else {
        ROS_ERROR("Failed to call service set_redu_ratio");
    }

    // 设置位置
    setPosSrv.request.pos0 = 300; //小拇指
    setPosSrv.request.pos1 = 300;
    setPosSrv.request.pos2 = 300;
    setPosSrv.request.pos3 = 300;
    setPosSrv.request.pos4 = 100;
    setPosSrv.request.pos5 = 600; // 示例值
    if (setPosClient.call(setPosSrv)) {
        ROS_INFO("Set position successful: %d", setPosSrv.response.success);
    } else {
        ROS_ERROR("Failed to call service set_pos");
    }

    // 发送 Modbus 请求，传递位置参数
    sendModbusPositionCommand(
        setPosSrv.request.pos0, 
        setPosSrv.request.pos1, 
        setPosSrv.request.pos2, 
        setPosSrv.request.pos3, 
        setPosSrv.request.pos4, 
        setPosSrv.request.pos5
    );

    // 关闭 Modbus 连接
    modbus_close(ctx);
    modbus_free(ctx);

    return 0;
}

