#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/int32_multi_array.hpp>
#include <modbus/modbus.h>
#include <vector>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <chrono>
#include <queue>

using namespace std;

// 定义 Modbus TCP 相关参数
const char* MODBUS_IP = "192.168.11.210"; 
const int MODBUS_PORT = 6000; 
const int TOUCH_SENSOR_BASE_ADDR = 3000;

modbus_t *ctx;

template <typename T>
class ThreadSafeQueue {
public:
    void push(T value) {
        std::lock_guard<std::mutex> lock(mtx);
        queue.push(std::move(value));
        cond_var.notify_one();
    }

    void wait_and_pop(T& value) {
        std::unique_lock<std::mutex> lock(mtx);
        cond_var.wait(lock, [this] { return !queue.empty(); });
        value = std::move(queue.front());
        queue.pop();
    }

    size_t size() { // 添加 size() 方法
        std::lock_guard<std::mutex> lock(mtx);
        return queue.size();
    }

private:
    std::queue<T> queue;
    std::mutex mtx;
    std::condition_variable cond_var;
};

// 全局变量
int total_read_count = 0; // 记录总读取次数
std::mutex count_mutex; // 用于保护读取计数的互斥量
ThreadSafeQueue<std::vector<int16_t>> data_queue;

void readModbusData() {
    rclcpp::Time last_read_time = rclcpp::Clock().now(); // 跟踪上次读取时间
    int current_read_count = 0; // 每秒的读取计数

    while (rclcpp::ok()) {
        std::vector<int16_t> new_data;

        for (int addr = TOUCH_SENSOR_BASE_ADDR; addr < 5124; addr += 120) {
            uint16_t data[120]; 
            int remaining_registers = std::min(120, 5124 - addr);
            int num_read = modbus_read_registers(ctx, addr, remaining_registers, data); 

            if (num_read != -1) {
                for (int i = 0; i < num_read; i += 2) {
                    if (i + 1 < num_read) {
                        int16_t sensor_value = (data[i] & 0xFF) | ((data[i + 1] & 0xFF) << 8);
                        new_data.push_back(sensor_value);
                    }
                }
                data_queue.push(new_data); // 将新数据推入队列
                current_read_count++; // 增加当前周期的读取计数
            } else {
                RCLCPP_WARN(rclcpp::get_logger("readModbusData"), "Failed to read from address: %d", addr);
            }
        }

        // 计算读取频率
        rclcpp::Time current_time = rclcpp::Clock().now();
        auto duration = (current_time - last_read_time).nanoseconds();

        if (duration >= 1e9) { // 每秒计算一次频率
            double read_frequency = static_cast<double>(current_read_count) / (duration / 1e9);
            RCLCPP_INFO(rclcpp::get_logger("readModbusData"), "Current Read Count: %d, Reading Frequency: %.2f Hz", current_read_count, read_frequency);
            RCLCPP_INFO(rclcpp::get_logger("readModbusData"), "Produced %zu new data items", new_data.size());
            
            {
                std::lock_guard<std::mutex> lock(count_mutex);
                total_read_count += current_read_count; // 更新总读取次数
            }

            // 重置当前的读取计数和时间
            current_read_count = 0;
            last_read_time = current_time;
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(40));
    }
}

void processData(rclcpp::Publisher<std_msgs::msg::Int32MultiArray>::SharedPtr pub) {
    rclcpp::Time last_time = rclcpp::Clock().now(); // 跟踪上次接收时间
    int message_count = 0; // 记录消息计数

    while (rclcpp::ok()) {
        std::vector<int16_t> new_data;
        data_queue.wait_and_pop(new_data); // 等待数据到达队列

        // 如果没有数据，继续循环
        if (new_data.empty()) {
            continue;
        }
        std_msgs::msg::Int32MultiArray array;

        if (new_data.size() >= 1062) {
    	for (size_t i = 0; i < new_data.size(); ++i) { // 遍历整个 new_data
        array.data.push_back(new_data[i] != 0 ? 1 : 0); // 添加到 array.data
    }
}

        // 发布数组格式的数据
        pub->publish(array);
        message_count++; // 增加消息计数

        // 计算频率
        rclcpp::Time current_time = rclcpp::Clock().now();
        auto duration = (current_time - last_time).nanoseconds();

        if (duration >= 1e9) { // 每秒计算一次频率
            double frequency = static_cast<double>(message_count) / (duration / 1e9);
            RCLCPP_INFO(rclcpp::get_logger("processData"), "Message Frequency: %.2f Hz", frequency);
            message_count = 0; // 重置消息计数
            last_time = current_time; // 更新最后一次时间
        }
    }
}


int main(int argc, char *argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::Node::SharedPtr node = rclcpp::Node::make_shared("handcontroltopicpublisher_modbus");

    auto touch_pub = node->create_publisher<std_msgs::msg::Int32MultiArray>("touch_data", 10);

    ctx = modbus_new_tcp(MODBUS_IP, MODBUS_PORT);
    if (modbus_connect(ctx) == -1) {
        RCLCPP_ERROR(rclcpp::get_logger("main"), "Failed to connect to Modbus server.");
        return -1;
    }

    std::thread read_thread(readModbusData);
    std::thread process_thread(processData, touch_pub);

    rclcpp::executors::MultiThreadedExecutor exec;
    exec.add_node(node);
    
    read_thread.detach(); // 使读取线程在后台运行
    process_thread.detach(); // 使处理线程在后台运行

    exec.spin();

    modbus_close(ctx);
    modbus_free(ctx);
    rclcpp::shutdown();
    return 0;
}

