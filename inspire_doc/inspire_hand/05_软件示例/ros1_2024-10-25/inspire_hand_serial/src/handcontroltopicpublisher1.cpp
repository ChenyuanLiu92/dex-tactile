#include <ros/ros.h>
#include <hand_control.h>
#include <stdio.h>
#include <stdlib.h>
#include <vector>
#include <iostream>
#include <std_msgs/String.h>
#include "std_msgs/MultiArrayLayout.h"
#include "std_msgs/MultiArrayDimension.h"
#include "std_msgs/Int32MultiArray.h"
#include <chrono>
#include <thread>

using namespace std;

int hand_id_;
std::string port_name_;
int baudrate_;
int test_flags;
serial::Serial *com_port_;
uint8_t hand_state_;

void readResponse(serial::Serial *port, std::vector<uint8_t>& input); 

void setANGLE1(serial::Serial *port, int angle0, int angle1, int angle2, int angle3, int angle4, int angle5) 		
{
    std::vector<uint8_t> output;
    auto start_send_time = std::chrono::high_resolution_clock::now();
    
    // Prepare the message to send
    output.push_back(0xEB);
    output.push_back(0x90);
    output.push_back(hand_id_);
    output.push_back(0x0F);
    output.push_back(0x12);
    output.push_back(0xCE);
    output.push_back(0x05);
    
    // Store angles in output
    output.push_back(angle0 & 0xff);
    output.push_back((angle0 >> 8) & 0xff);
    output.push_back(angle1 & 0xff);
    output.push_back((angle1 >> 8) & 0xff);
    output.push_back(angle2 & 0xff);
    output.push_back((angle2 >> 8) & 0xff);
    output.push_back(angle3 & 0xff);
    output.push_back((angle3 >> 8) & 0xff);
    output.push_back(angle4 & 0xff);
    output.push_back((angle4 >> 8) & 0xff);
    output.push_back(angle5 & 0xff);
    output.push_back((angle5 >> 8) & 0xff);
    
    // Checksum calculation
    unsigned int check_num = 0;
    int len = output[3] + 5;
    for (int i = 2; i < len - 1; i++)
        check_num += output[i];
    output.push_back(check_num & 0xff);

    // Send message to the module
    port->write(output);
    
    auto end_send_time = std::chrono::high_resolution_clock::now();
    auto send_duration = std::chrono::duration_cast<std::chrono::microseconds>(end_send_time - start_send_time).count();
    ROS_INFO_STREAM("Send duration: " << send_duration << " microseconds");
    
    // Sleep to allow time for the command to be processed
    std::this_thread::sleep_for(std::chrono::milliseconds(15));
    
    // Read response
    std::vector<uint8_t> input;
    readResponse(port, input);

    // Log response
    std::string s2;
    for (const auto& byte : input) {
       char str[16];
       sprintf(str, "%02X", byte);
       s2 += str + std::string(" ");
}
    if (test_flags == 1)
       ROS_INFO_STREAM("Read: " << s2);
    
}

void readResponse(serial::Serial *port, std::vector<uint8_t>& input) {
    // 记录读取开始时间
    auto start_read_time = std::chrono::high_resolution_clock::now();
    auto timeout_duration = std::chrono::milliseconds(100); // Adjust timeout as needed

    while (true) {
        // Read available data
        std::vector<uint8_t> buffer;
        port->read(buffer, (size_t)128);

        if (!buffer.empty()) {
            input.insert(input.end(), buffer.begin(), buffer.end());
        }

        // Check if we got a response (customize your condition here)
        if (!input.empty() || 
            std::chrono::high_resolution_clock::now() - start_read_time > timeout_duration) {
            break; // Exit if data is received or timeout
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(1)); // Prevent busy waiting
    }

    // 记录读取结束时间，并计算持续时间
    auto end_read_time = std::chrono::high_resolution_clock::now();
    auto read_duration = std::chrono::duration_cast<std::chrono::microseconds>(end_read_time - start_read_time).count();
    ROS_INFO_STREAM("Read duration: " << read_duration << " microseconds");

    // 打印读取到的原始数据
    std::string response_data;
    for (const auto& byte : input) {
        char str[16];
        sprintf(str, "%02X", byte);
        response_data += str + std::string(" ");
    }
    ROS_INFO_STREAM("Raw response: " << response_data);
    }

int Arr[12];

void arrayCallback1(const std_msgs::Int32MultiArray::ConstPtr& array) {
    int i = 0;
    for (const auto& value : array->data) {
        Arr[i++] = value;
        printf("%d, ", Arr[i - 1]);
    }
    setANGLE1(com_port_, Arr[0], Arr[1], Arr[2], Arr[3], Arr[4], Arr[5]);
}

int main(int argc, char *argv[]) {
    ros::init(argc, argv, "handcontroltopicpublisher1");
    ros::NodeHandle nh;

    // Subscribe to topic
    ros::Subscriber sub = nh.subscribe("chatter1", 100, arrayCallback1);
    
    // Read launch file params
    nh.getParam("inspire_hand/hand_id", hand_id_);
    nh.getParam("inspire_hand/portname", port_name_);
    nh.getParam("inspire_hand/baudrate", baudrate_);
    nh.getParam("inspire_hand/test_flags", test_flags);
    
    // Initialize and open serial port
    com_port_ = new serial::Serial(port_name_, (uint32_t)baudrate_, serial::Timeout::simpleTimeout(10));

    ros::spin();
    return EXIT_SUCCESS;
}
