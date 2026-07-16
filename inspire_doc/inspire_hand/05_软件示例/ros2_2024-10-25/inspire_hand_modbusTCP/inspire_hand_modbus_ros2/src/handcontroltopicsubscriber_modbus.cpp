#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/int32_multi_array.hpp>
#include <sstream> // 用于字符串流

class TouchDataSubscriber : public rclcpp::Node {
public:
    TouchDataSubscriber() : Node("touch_data_subscriber") {
        // 创建订阅者，订阅 "touch_data" 话题
        subscription_ = this->create_subscription<std_msgs::msg::Int32MultiArray>(
            "touch_data",
            10,
            std::bind(&TouchDataSubscriber::topic_callback, this, std::placeholders::_1)
        );
    }

private:
    void topic_callback(const std_msgs::msg::Int32MultiArray::SharedPtr msg) {
        if (msg->data.size() < 1062) {
            //RCLCPP_WARN(this->get_logger(), "Received data size is less than expected (1062).");
            return;
        }
        // 打印小拇指数据
        RCLCPP_INFO(this->get_logger(), "小拇指数据: ");
        print_finger_data(msg->data, 0, 145);

        // 打印无名指数据
        RCLCPP_INFO(this->get_logger(), "无名指数据: ");
        print_finger_data(msg->data, 150, 330);

        // 打印中指数据
        RCLCPP_INFO(this->get_logger(), "中指数据: ");
        print_finger_data(msg->data, 335, 515);

        // 打印食指数据
        RCLCPP_INFO(this->get_logger(), "食指数据: ");
        print_finger_data(msg->data, 515, 700);

        // 打印大拇指数据
        RCLCPP_INFO(this->get_logger(), "大拇指数据: ");
        print_finger_data(msg->data, 700, 885);

        // 打印掌心数据
        RCLCPP_INFO(this->get_logger(), "掌心数据: ");
        print_finger_data(msg->data, 940, 1062);
    }

    void print_finger_data(const std::vector<int32_t>& data, size_t start, size_t end) {
        std::stringstream ss;
        for (size_t i = start; i < end; ++i) {
            ss << data[i];
            if (i < end - 1) {
                ss << ", ";
            }
        }
        RCLCPP_INFO(this->get_logger(), "%s", ss.str().c_str());
    }

    rclcpp::Subscription<std_msgs::msg::Int32MultiArray>::SharedPtr subscription_;
};

int main(int argc, char *argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<TouchDataSubscriber>());
    rclcpp::shutdown();
    return 0;
}

