#include <ros/ros.h>
#include <std_msgs/Int32MultiArray.h>
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
    ros::Time last_read_time = ros::Time::now(); // 跟踪上次读取时间
    int current_read_count = 0; // 每秒的读取计数

    while (ros::ok()) {
        std::vector<int16_t> new_data;

        for (int addr = TOUCH_SENSOR_BASE_ADDR; addr < 5124; addr += 122) {
            uint16_t data[122]; 
            int remaining_registers = std::min(122, 5124 - addr);
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
                ROS_WARN("Failed to read from address: %d", addr);
            }
        }

        // 计算读取频率
        ros::Time current_time = ros::Time::now();
        ros::Duration duration = current_time - last_read_time;

        if (duration.toSec() >= 1.0) { // 每秒计算一次频率
            double read_frequency = static_cast<double>(current_read_count) / duration.toSec();
            ROS_INFO("Current Read Count: %d, Reading Frequency: %.2f Hz", current_read_count, read_frequency);
            ROS_INFO("Produced %zu new data items", new_data.size());
            
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

void processData(ros::Publisher &pub) {
    ros::Time last_time = ros::Time::now(); // 跟踪上次接收时间
    int message_count = 0; // 记录消息计数
    int last_total_read_count = 0; // 记录上一个周期的总读取次数

    while (ros::ok()) {
        std::vector<int16_t> new_data;
        data_queue.wait_and_pop(new_data); // 等待数据到达队列

        std_msgs::Int32MultiArray array;
        std::vector<int> int_data(new_data.begin(), new_data.end());
        array.data = int_data;

        pub.publish(array); // 发布数据
        message_count++; // 增加消息计数

        // 计算频率和丢包率
        ros::Time current_time = ros::Time::now();
        ros::Duration duration = current_time - last_time;

        if (duration.toSec() >= 1.0) { // 每秒计算一次频率
            double frequency = static_cast<double>(message_count) / duration.toSec();
            ROS_INFO("Message Frequency: %.2f Hz", frequency);

            {
                std::lock_guard<std::mutex> lock(count_mutex);
                int current_read_count = total_read_count - last_total_read_count; // 计算当前周期的读取次数
                int dropped_messages = current_read_count - message_count;
                double drop_rate = current_read_count > 0 ? static_cast<double>(dropped_messages) / current_read_count * 100.0 : 0.0;
                ROS_INFO("Drop Rate: %.2f%%", drop_rate);

                // 更新上一个周期的总读取次数
                last_total_read_count = total_read_count; 
            }

            // 重置计数和时间
            ROS_INFO("message_count: %d", message_count);
            ROS_INFO("Consumed %zu data items", new_data.size()); 
            ROS_INFO("Queue Size: %zu", data_queue.size()); // 使用 size() 方法
            message_count = 0;
            last_time = current_time;
        }
    }
}

int main(int argc, char *argv[]) {
    ros::init(argc, argv, "handcontroltopicpublisher_modbus");
    ros::NodeHandle nh;

    ros::Publisher touch_pub = nh.advertise<std_msgs::Int32MultiArray>("touch_data", 10000);

    ctx = modbus_new_tcp(MODBUS_IP, MODBUS_PORT);
    if (modbus_connect(ctx) == -1) {
        ROS_ERROR("Failed to connect to Modbus server.");
        return -1;
    }

    std::thread read_thread(readModbusData);
    std::thread process_thread(processData, std::ref(touch_pub));

    read_thread.join();
    process_thread.join();

    modbus_close(ctx);
    modbus_free(ctx);
    return 0;
}

