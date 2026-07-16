#include <ros/ros.h>
#include <std_msgs/Int32MultiArray.h>

ros::Time last_time;

void callback(const std_msgs::Int32MultiArray::ConstPtr& msg) {
    ros::Time current_time = ros::Time::now();
    
    if (last_time.isZero()) {
        last_time = current_time;
        return;
    }

    ros::Duration time_diff = current_time - last_time;
    ROS_INFO("Time interval: %.2f seconds", time_diff.toSec());

    last_time = current_time;
}

int main(int argc, char** argv) {
    ros::init(argc, argv, "bag_analyzer");
    ros::NodeHandle nh;

    ros::Subscriber sub = nh.subscribe("/touch_data", 10000, callback);
    ros::spin();

    return 0;
}

