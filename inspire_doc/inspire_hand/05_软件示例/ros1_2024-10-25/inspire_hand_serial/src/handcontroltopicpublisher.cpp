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
int test_flags_;
serial::Serial *com_port_;
float curangle_[6];
float curforce_[6];

void readResponse(serial::Serial *port, std::vector<uint8_t>& input)
{
    auto start_read_time = std::chrono::high_resolution_clock::now();
    auto timeout_duration = std::chrono::milliseconds(100); // Adjust timeout as needed

    while (true)
    {
        std::vector<uint8_t> buffer;
        port->read(buffer, (size_t)128);

        if (!buffer.empty())
        {
            input.insert(input.end(), buffer.begin(), buffer.end());
        }

        if (!input.empty() || 
            std::chrono::high_resolution_clock::now() - start_read_time > timeout_duration) 
        {
            break; // Exit if data is received or timeout
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(1)); // Prevent busy waiting
    }

    auto end_read_time = std::chrono::high_resolution_clock::now();
    auto read_duration = std::chrono::duration_cast<std::chrono::microseconds>(end_read_time - start_read_time).count();
    ROS_INFO_STREAM("Read duration: " << read_duration << " microseconds");

    std::string response_data;
    for (const auto& byte : input)
    {
        char str[16];
        sprintf(str, "%02X", byte);
        response_data += str + std::string(" ");
    }
    ROS_INFO_STREAM("Raw response: " << response_data);
}

void getANGLE_ACT1(serial::Serial *port)
{
    std::vector<uint8_t> output;

    output.push_back(0xEB);
    output.push_back(0x90);
    output.push_back(hand_id_);
    output.push_back(0x01); // Data Length
    output.push_back(0xD7); // Command

    unsigned int check_num = 0;
    int len = output[3] + 5;
    for (int i = 2; i < len - 1; i++)
        check_num += output[i];
    output.push_back(check_num & 0xff);

    port->write(output);
    std::this_thread::sleep_for(std::chrono::milliseconds(15)); // Allow time for the command to be processed

    std::vector<uint8_t> input;
    readResponse(port, input);

    if (!input.empty())
    {
        float temp[6] = {0.0};
        for (int j = 0; j < 6; j++)
            temp[j] = ((input[6 + j * 2] << 8) & 0xff00) + input[5 + j * 2];

        for (int j = 0; j < 6; j++)
            curangle_[j] = temp[j];
    }
    else
    {
        ROS_WARN_STREAM("No response received for ANGLE!");
    }
}

void getFORCE_ACT1(serial::Serial *port)
{
    std::vector<uint8_t> output;

    output.push_back(0xEB);
    output.push_back(0x90);
    output.push_back(hand_id_);
    output.push_back(0x04); // Data Length
    output.push_back(0x11); // Command
    output.push_back(0x2E);
    output.push_back(0x06);
    output.push_back(0x0C);

    unsigned int check_num = 0;
    int len = output[3] + 5;
    for (int i = 2; i < len - 1; i++)
        check_num += output[i];
    output.push_back(check_num & 0xff);

    port->write(output);
    std::this_thread::sleep_for(std::chrono::milliseconds(15)); // Allow time for the command to be processed

    std::vector<uint8_t> input;
    readResponse(port, input);

    if (!input.empty())
    {
        int temp[6] = {0};
        for (int j = 0; j < 6; j++)
        {
            temp[j] = ((input[8 + j * 2] << 8) & 0xff00) + input[7 + j * 2];
            if (temp[j] > 32768)
                temp[j] -= 65536;
            curforce_[j] = static_cast<float>(temp[j]);
        }
    }
    else
    {
        ROS_WARN_STREAM("No response received for FORCE!");
    }
}

int main(int argc, char *argv[])
{
    ros::init(argc, argv, "handcontroltopicpublisher");
    ros::NodeHandle nh;

    // Read parameters
    nh.getParam("inspire_hand/hand_id", hand_id_);
    nh.getParam("inspire_hand/portname", port_name_);
    nh.getParam("inspire_hand/baudrate", baudrate_);
    nh.getParam("inspire_hand/test_flags", test_flags_);

    // Initialize and open serial port
    com_port_ = new serial::Serial(port_name_, (uint32_t)baudrate_, serial::Timeout::simpleTimeout(10));

    // Create the publisher outside the loop
    ros::Publisher chatter_pub = nh.advertise<std_msgs::Int32MultiArray>("chatter", 1000);

    ros::Rate loop_rate(10);

    while (ros::ok())
    {
        getANGLE_ACT1(com_port_);
        getFORCE_ACT1(com_port_);

        std_msgs::Int32MultiArray array;
        array.data.clear();

        for (int i = 0; i < 6; i++)
        {
            array.data.push_back(static_cast<int>(curangle_[i]));
        }
        for (int i = 0; i < 6; i++)
        {
            array.data.push_back(static_cast<int>(curforce_[i]));
        }

        // Publish array
        chatter_pub.publish(array);

        loop_rate.sleep();
    }

    return (EXIT_SUCCESS);
}

