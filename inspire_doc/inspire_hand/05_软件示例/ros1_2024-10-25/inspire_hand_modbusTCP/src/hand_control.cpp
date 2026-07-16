#include "hand_control.h"

// Constructor
inspire_hand::hand_serial::hand_serial(ros::NodeHandle *nh)
{
    // Initialize Modbus TCP context
    id = 1;
    ip_address_ = "192.168.11.210"; // Replace with your device's IP
    port_ = 6000; // Default Modbus TCP port
    ctx_ = modbus_new_tcp(ip_address_.c_str(), port_);
    
    if (modbus_connect(ctx_) == -1) {
        ROS_ERROR("Unable to connect to Modbus server: %s", modbus_strerror(errno));
        modbus_free(ctx_);
        ctx_ = nullptr;
    }

    ROS_INFO("Connected to Modbus server at %s:%d", ip_address_.c_str(), port_);
}

// Destructor
inspire_hand::hand_serial::~hand_serial()
{
    if (ctx_) {
        modbus_close(ctx_);
        modbus_free(ctx_);
    }
}

// Callback to get error information
bool inspire_hand::hand_serial::getERRORCallback(inspire_hand_modbus::get_error::Request &req,
                                                 inspire_hand_modbus::get_error::Response &res)
{
    ROS_INFO("Hand: Get error request received");

    uint16_t tab_reg[6]; // 用于存储读取的寄存器值

    // 读取寄存器 (地址从 1606 开始)
    int rc = modbus_read_registers(ctx_, 1606, 6, tab_reg);
    if (rc == -1) {
        ROS_ERROR("Failed to read error registers: %s", modbus_strerror(errno));
        res.success = false; // Error
        return true; // 返回成功
    }

    // 解析故障信息并存储到响应中
    for (int i = 0; i < 3; i++) {
        // 每个寄存器包含两个字节
        res.errorvalue[i * 2] = static_cast<float>(tab_reg[i] & 0xFF);    // 低字节在前
        res.errorvalue[i * 2 + 1] = static_cast<float>((tab_reg[i] >> 8) & 0xFF); // 高字节在后
        
        // 输出故障信息
        ROS_INFO("ERROR(%d): %f", i * 2, res.errorvalue[i * 2]);         // 输出低字节
        ROS_INFO("ERROR(%d): %f", i * 2 + 1, res.errorvalue[i * 2 + 1]); // 输出高字节
    }

    res.success = true; // 成功
    return true; // 返回成功
}

#include <ros/ros.h>

bool inspire_hand::hand_serial::getSTATUSCallback(inspire_hand_modbus::get_status::Request &req,
                                                  inspire_hand_modbus::get_status::Response &res)
{
    ROS_INFO("Hand: Get status request received");

    uint16_t tab_reg[6]; // 用于存储读取的寄存器值

    // 读取寄存器 (地址从 1612 开始)
    int rc = modbus_read_registers(ctx_, 1612, 6, tab_reg);
    if (rc == -1) {
        ROS_ERROR("Failed to read status registers: %s", modbus_strerror(errno));
        res.success = false; // Error
        return true; // 返回成功
    }

    // 解析状态信息并存储到响应中
    for (int i = 0; i < 3; i++) {
        // 每个寄存器包含两个字节
        res.statusvalue[i * 2] = static_cast<int16_t>(tab_reg[i] & 0xFF);    // 低字节在前
        res.statusvalue[i * 2 + 1] = static_cast<int16_t>((tab_reg[i] >> 8) & 0xFF); // 高字节在后
        
        // 输出状态信息
        ROS_INFO("STATUS(%d): %d", i * 2, res.statusvalue[i * 2]);         // 输出低字节
        ROS_INFO("STATUS(%d): %d", i * 2 + 1, res.statusvalue[i * 2 + 1]); // 输出高字节
    }

    res.success = true; // 成功
    return true; // 返回成功
}

bool inspire_hand::hand_serial::getFORCE_ACTCallback(inspire_hand_modbus::get_force_act::Request &req,
                                                     inspire_hand_modbus::get_force_act::Response &res) {
    ROS_INFO("Hand: Get Force Actual values request received");

    // 直接读取各个手指的实际受力值
    res.curforce[0] = readRegister(1582); // 小拇指实际受力值
    res.curforce[1] = readRegister(1584); // 无名指实际受力值
    res.curforce[2] = readRegister(1586); // 中指实际受力值
    res.curforce[3] = readRegister(1588); // 食指实际受力值
    res.curforce[4] = readRegister(1590); // 大拇指弯实际受力值
    res.curforce[5] = readRegister(1592); // 大拇指旋转实际受力值

    // 检查读取的值是否有效
    for (int i = 0; i < 6; ++i) {

	ROS_INFO("Read FORCE_ACT(%d) value: %d", i, res.curforce[i]);
    }
    return true; // 返回成功
}

bool inspire_hand::hand_serial::getCURRENTCallback(inspire_hand_modbus::get_current::Request &req,
                                                   inspire_hand_modbus::get_current::Response &res) {
    ROS_INFO("Hand: Get Current values request received");

    // 直接读取各个电缸的电流值
    res.current[0] = static_cast<int16_t>(readRegister(1594)); // 小拇指电缸电流值
    res.current[1] = static_cast<int16_t>(readRegister(1596)); // 无名指电缸电流值
    res.current[2] = static_cast<int16_t>(readRegister(1598)); // 中指电缸电流值
    res.current[3] = static_cast<int16_t>(readRegister(1600)); // 食指电缸电流值
    res.current[4] = static_cast<int16_t>(readRegister(1602)); // 大拇指弯曲电缸电流值
    res.current[5] = static_cast<int16_t>(readRegister(1604)); // 大拇指旋转电缸电流值

    // 检查读取的值是否有效，并记录日志
    for (int i = 0; i < 6; ++i) {
        // 这里假设 readRegister 返回 -1 表示读取失败
        if (res.current[i] != -1.0) { 
            ROS_INFO("Read CURRENT(%d) value: %d mA", i, res.current[i]);
        } else {
            ROS_WARN("Failed to read CURRENT(%d) value", i);
        }
    }

    return true; // 返回成功
}

bool inspire_hand::hand_serial::getANGLE_SETCallback(inspire_hand_modbus::get_angle_set::Request &req,
                                                     inspire_hand_modbus::get_angle_set::Response &res) {
    ROS_INFO("Hand: Get Angle Set values request received");

    // 直接读取各个手指的上电初始角度
    res.setangle[0] = static_cast<int16_t>(readRegister(1486)); // 小拇指上电初始角度
    res.setangle[1] = static_cast<int16_t>(readRegister(1488)); // 无名指上电初始角度
    res.setangle[2] = static_cast<int16_t>(readRegister(1490)); // 中指上电初始角度
    res.setangle[3] = static_cast<int16_t>(readRegister(1492)); // 食指上电初始角度
    res.setangle[4] = static_cast<int16_t>(readRegister(1494)); // 大拇指弯曲上电初始角度
    res.setangle[5] = static_cast<int16_t>(readRegister(1496)); // 大拇指旋转上电初始角度

    // 检查读取的值是否有效，并记录日志
    for (int i = 0; i < 6; ++i) {
        // 这里假设 readRegister 返回 -1 表示读取失败
        if (res.setangle[i] != -1) { // 假设 -1 表示读取失败
            ROS_INFO("Read ANGLE_SET(%d) value: %d", i, res.setangle[i]);
        } else {
            ROS_WARN("Failed to read ANGLE_SET(%d) value", i);
        }
    }

    return true; // 返回成功
}

bool inspire_hand::hand_serial::getANGLE_ACTCallback(inspire_hand_modbus::get_angle_act::Request &req,
                                                     inspire_hand_modbus::get_angle_act::Response &res) {
    ROS_INFO("Hand: Get Angle Actual values request received");

    // 直接读取各个手指的角度实际值
    res.curangle[0] = static_cast<int16_t>(readRegister(1546)); // 小拇指角度实际值
    res.curangle[1] = static_cast<int16_t>(readRegister(1548)); // 无名指角度实际值
    res.curangle[2] = static_cast<int16_t>(readRegister(1550)); // 中指角度实际值
    res.curangle[3] = static_cast<int16_t>(readRegister(1552)); // 食指角度实际值
    res.curangle[4] = static_cast<int16_t>(readRegister(1554)); // 大拇指弯曲角度实际值
    res.curangle[5] = static_cast<int16_t>(readRegister(1556)); // 大拇指旋转角度实际值

    // 检查读取的值是否有效，并记录日志
    for (int i = 0; i < 6; ++i) {
        // 假设 -1 表示读取失败
        if (res.curangle[i] != -1) {
            ROS_INFO("Read ANGLE_ACT(%d) value: %d", i, res.curangle[i]);
        } else {
            ROS_WARN("Failed to read ANGLE_ACT(%d) value", i);
        }
    }

    return true; // 返回成功
}

bool inspire_hand::hand_serial::getFORCE_SETCallback(inspire_hand_modbus::get_force_set::Request &req,
                                                     inspire_hand_modbus::get_force_set::Response &res) {
    ROS_INFO("Hand: Get Force Set values request received");

    // 直接读取各个手指的力控设置值
    res.setforce[0] = static_cast<int16_t>(readRegister(1498)); // 小拇指力控设置值
    res.setforce[1] = static_cast<int16_t>(readRegister(1500)); // 无名指力控设置值
    res.setforce[2] = static_cast<int16_t>(readRegister(1502)); // 中指力控设置值
    res.setforce[3] = static_cast<int16_t>(readRegister(1504)); // 食指力控设置值
    res.setforce[4] = static_cast<int16_t>(readRegister(1506)); // 大拇指弯曲力控设置值
    res.setforce[5] = static_cast<int16_t>(readRegister(1508)); // 大拇指旋转力控设置值

    // 检查读取的值是否有效，并记录日志
    for (int i = 0; i < 6; ++i) {
        // 假设 -1 表示读取失败
        if (res.setforce[i] != -1) {
            ROS_INFO("Read FORCE_SET(%d) value: %d", i, res.setforce[i]);
        } else {
            ROS_WARN("Failed to read FORCE_SET(%d) value", i);
        }
    }

    return true; // 返回成功
}

bool inspire_hand::hand_serial::getTEMPCallback(inspire_hand_modbus::get_temp::Request &req,
                                                inspire_hand_modbus::get_temp::Response &res)
{
    ROS_INFO("Hand: Get temperature request received");

    uint16_t tab_reg[6]; // 用于存储读取的寄存器值

    // 读取寄存器 (地址从 1618 开始)
    int rc = modbus_read_registers(ctx_, 1618, 6, tab_reg);
    if (rc == -1) {
        ROS_ERROR("Failed to read temperature registers: %s", modbus_strerror(errno));
        res.success = false; // Error
        return true; // 返回成功
    }

    // 解析温度值并存储到响应中
    for (int i = 0; i < 3; i++) {
        // 每个寄存器包含两个字节
        res.tempvalue[i * 2] = static_cast<int16_t>(tab_reg[i] & 0xFF);       // 低字节;
        res.tempvalue[i * 2 + 1] = static_cast<int16_t>((tab_reg[i] >> 8) & 0xFF); // 高字节
        
        // 输出温度信息
        ROS_INFO("TEMP(%d): %d", i * 2, res.tempvalue[i * 2]);      // 输出低字节
        ROS_INFO("TEMP(%d): %d", i * 2 + 1, res.tempvalue[i * 2 + 1]); // 输出高字节
    }

    res.success = true; // 成功
    return true; // 返回成功
}

bool inspire_hand::hand_serial::getPOS_SETCallback(inspire_hand_modbus::get_pos_set::Request &req,
                                                   inspire_hand_modbus::get_pos_set::Response &res)
{
    ROS_INFO("Hand: Get Position Set values request received");

    // 直接读取各个手指的驱动器位置设置值
    res.setpos[0] = static_cast<int16_t>(readRegister(1474)); // 小拇指驱动器位置设置值
    res.setpos[1] = static_cast<int16_t>(readRegister(1476)); // 无名指驱动器位置设置值
    res.setpos[2] = static_cast<int16_t>(readRegister(1478)); // 中指驱动器位置设置值
    res.setpos[3] = static_cast<int16_t>(readRegister(1480)); // 食指驱动器位置设置值
    res.setpos[4] = static_cast<int16_t>(readRegister(1482)); // 大拇指弯曲驱动器位置设置值
    res.setpos[5] = static_cast<int16_t>(readRegister(1484)); // 大拇指旋转驱动器位置设置值

    // 检查读取的值是否有效，并记录日志
    for (int i = 0; i < 6; ++i) {
        // 假设 -1 表示读取失败
        if (res.setpos[i] != -1) {
            ROS_INFO("Read POS_SET(%d) value: %d", i, res.setpos[i]);
        } else {
            ROS_WARN("Failed to read POS_SET(%d) value", i);
        }
    }

    return true; // 返回成功
}

bool inspire_hand::hand_serial::getPOS_ACTCallback(inspire_hand_modbus::get_pos_act::Request &req,
                                                   inspire_hand_modbus::get_pos_act::Response &res)
{
    ROS_INFO("Hand: Get Position Actual values request received");

    // 直接读取各个手指的驱动器实际位置值
    res.curpos[0] = static_cast<int16_t>(readRegister(1534)); // 小拇指驱动器实际值
    res.curpos[1] = static_cast<int16_t>(readRegister(1536)); // 无名指驱动器实际值
    res.curpos[2] = static_cast<int16_t>(readRegister(1538)); // 中指驱动器实际值
    res.curpos[3] = static_cast<int16_t>(readRegister(1540)); // 食指驱动器实际值
    res.curpos[4] = static_cast<int16_t>(readRegister(1542)); // 大拇指弯曲驱动器实际值
    res.curpos[5] = static_cast<int16_t>(readRegister(1544)); // 大拇指旋转驱动器实际值

    // 检查读取的值是否有效，并记录日志
    for (int i = 0; i < 6; ++i) {
        // 假设 -1 表示读取失败
        if (res.curpos[i] != -1) {
            ROS_INFO("Read POS_ACT(%d) value: %d", i, res.curpos[i]);
        } else {
            ROS_WARN("Failed to read POS_ACT(%d) value", i);
        }
    }

    return true; // 返回成功
}

// Callback to set ID
bool inspire_hand::hand_serial::setIDCallback(inspire_hand_modbus::set_id::Request &req,
                                              inspire_hand_modbus::set_id::Response &res)
{
    ROS_INFO("Hand: Set ID request received");

    // 检查请求中的 ID 是否在合法范围内
    if (req.id >= 1 && req.id <= 254) {
        // 将 ID 写入 Modbus 寄存器
        int write_result = writeRegister(1000, req.id);
        
        if (write_result == 0) {
            res.idgrab = true; // ID 写入成功
            res.success = true; // 操作成功

            // 读取寄存器以验证写入的 ID
            int read_value = readRegister(1000);
            if (read_value != -1) {
                ROS_INFO("Read ID from Modbus register: %d", read_value);
                if (read_value == req.id) {
                    ROS_INFO("ID verification successful.");
                } else {
                    ROS_WARN("ID verification failed! Expected: %d, Read: %d", req.id, read_value);
                    res.success = false; // 操作失败
                }
     }
   }
 }
 return true; // 返回成功
}

// Callback to set Reduction Ratio
bool inspire_hand::hand_serial::setREDU_RATIOCallback(inspire_hand_modbus::set_redu_ratio::Request &req,
                                                      inspire_hand_modbus::set_redu_ratio::Response &res)
{
    ROS_INFO("Hand: Set Reduction Ratio request received");

    // 检查请求中的 redu_ratio 是否在合法范围内
    if (req.redu_ratio >= 0 && req.redu_ratio <= 4) {
        // 将 redu_ratio 写入 Modbus 寄存器
        int write_result = writeRegister(1002, req.redu_ratio);
        
        if (write_result == 0) {
            res.redu_ratiograb = true; // 写入成功
            res.success = true; // 操作成功

            // 读取寄存器以验证写入的 redu_ratio
            int read_value = readRegister(1002);
            if (read_value != -1) {
                ROS_INFO("Read REDU_RATIO from Modbus register: %d", read_value);
                if (read_value == req.redu_ratio) {
                    ROS_INFO("Reduction Ratio verification successful.");
                } else {
                    ROS_WARN("Reduction Ratio verification failed! Expected: %d, Read: %d", req.redu_ratio, read_value);
                    res.success = false; // 操作失败
                }
            } 

    return true; // 返回成功
     }
  }
}

bool inspire_hand::hand_serial::setGESTURE_NOCallback(inspire_hand_modbus::set_gesture_no::Request &req,
                                                      inspire_hand_modbus::set_gesture_no::Response &res)
{
    // 调用 setGESTURE_NO 方法并传递手势编号
    res.gesture_nograb = setGESTURE_NO(req.gesture_no);
    
    if (res.gesture_nograb) {
        ROS_INFO("Gesture number %d set successfully.", req.gesture_no);
    } else {
        ROS_ERROR("Failed to set gesture number %d.", req.gesture_no);
    }
    
    return true; // 返回成功
}

bool inspire_hand::hand_serial::setGESTURE_NO(int gesture_no)
{
    int register_address = 0x0910;  // 当前动作序列索引寄存器
    int action_register_address = 0x0912; // 动作序列号寄存器地址

    // 首先将手势编号写入 Modbus 寄存器 2320
    if (writeRegister(register_address, gesture_no) == -1) {
        ROS_ERROR("Failed to set gesture number: %d", gesture_no);
        return false; // 写入失败
    }

    // 然后写入执行动作序列号的寄存器 2322
    if (writeRegister(action_register_address, 1) == -1) {
        ROS_ERROR("Failed to execute action sequence for gesture number: %d", gesture_no);
        return false; // 写入失败
    }

    return true; // 写入成功
}

// Callback to set position
bool inspire_hand::hand_serial::setPOSCallback(inspire_hand_modbus::set_pos::Request &req,
                                               inspire_hand_modbus::set_pos::Response &res)
{
    ROS_INFO("hand: set pos");
    
    // 检查请求中的位置参数是否合法
    if (req.pos0 >= 0 && req.pos1 >= 0 && req.pos2 >= 0 && req.pos3 >= 0 && req.pos4 >= 0 && req.pos5 >= 0)
    {
        if (req.pos0 <= 2000 && req.pos1 <= 2000 && req.pos2 <= 2000 && req.pos3 <= 2000 && req.pos4 <= 2000 && req.pos5 <= 2000)
        {
            // 将位置值写入 Modbus 寄存器
            res.pos_accepted = (writeRegister(1474, req.pos0) == 0) && // 小拇指
                               (writeRegister(1476, req.pos1) == 0) && // 无名指
                               (writeRegister(1478, req.pos2) == 0) && // 中指
                               (writeRegister(1480, req.pos3) == 0) && // 食指
                               (writeRegister(1482, req.pos4) == 0) && // 大拇指
                               (writeRegister(1484, req.pos5) == 0);   // 大拇指转动自由度

            // 读取某个寄存器的值（位置0）
            int read_value = readRegister(1474);
            if (read_value != -1) {
                ROS_INFO("Read position0 value: %d", read_value);
            }
        }
        else
        {
            ROS_WARN("Hand: pos error! Position values must be <= 2000.");
            res.pos_accepted = false;
        }
    }
    else
    {
        ROS_WARN("Hand: pos error! Position values must be >= 0.");
        res.pos_accepted = false;
    }
    
    return true; // 返回成功
}

bool inspire_hand::hand_serial::setSPEEDCallback(inspire_hand_modbus::set_speed::Request &req,
                                                 inspire_hand_modbus::set_speed::Response &res)
{
    ROS_INFO("hand: set speed");

    // 检查请求中的速度参数是否合法
    if (req.speed0 >= 0 && req.speed1 >= 0 && req.speed2 >= 0 && req.speed3 >= 0 && req.speed4 >= 0 && req.speed5 >= 0)
    {
        if (req.speed0 <= 1000 && req.speed1 <= 1000 && req.speed2 <= 1000 && req.speed3 <= 1000 && req.speed4 <= 1000 && req.speed5 <= 1000)
        {
            // 将速度值写入 Modbus 寄存器
            res.speed_accepted = (writeRegister(1522, req.speed0) == 0) && // 小拇指速度
                                 (writeRegister(1524, req.speed1) == 0) && // 无名指速度
                                 (writeRegister(1526, req.speed2) == 0) && // 中指速度
                                 (writeRegister(1528, req.speed3) == 0) && // 食指速度
                                 (writeRegister(1530, req.speed4) == 0) && // 大拇指弯曲速度
                                 (writeRegister(1532, req.speed5) == 0);   // 大拇指旋转速度

            // 读取某个寄存器的值（小拇指速度）
            int read_value = readRegister(1522);
            if (read_value != -1) {
                ROS_INFO("Read speed0 value: %d", read_value);
            }
        }
        else
        {
            ROS_WARN("Hand: speed error! Speed values must be <= 1000.");
            res.speed_accepted = false;
        }
    }
    else
    {
        ROS_WARN("Hand: speed error! Speed values must be >= 0.");
        res.speed_accepted = false;
    }
    
    return true; // 返回成功
}

bool inspire_hand::hand_serial::setDEFAULT_SPEEDCallback(inspire_hand_modbus::set_default_speed::Request &req,
                                                         inspire_hand_modbus::set_default_speed::Response &res)
{
    ROS_INFO("hand: set default speed");

    // 检查请求中的初始速度参数是否合法
    if (req.speed0 >= 0 && req.speed1 >= 0 && req.speed2 >= 0 && 
        req.speed3 >= 0 && req.speed4 >= 0 && req.speed5 >= 0)
    {
        if (req.speed0 <= 1000 && req.speed1 <= 1000 && req.speed2 <= 1000 && 
            req.speed3 <= 1000 && req.speed4 <= 1000 && req.speed5 <= 1000)
        {
            // 将上电初始速度值写入 Modbus 寄存器
            res.default_speed_accepted = (writeRegister(1032, req.speed0) == 0) && // 小拇指上电速度
                                          (writeRegister(1034, req.speed1) == 0) && // 无名指上电速度
                                          (writeRegister(1036, req.speed2) == 0) && // 中指上电速度
                                          (writeRegister(1038, req.speed3) == 0) && // 食指上电速度
                                          (writeRegister(1040, req.speed4) == 0) && // 大拇指弯曲上电速度
                                          (writeRegister(1042, req.speed5) == 0);   // 大拇指旋转上电速度

            // 读取某个寄存器的值（小拇指上电速度）
            int read_value = readRegister(1032);
            if (read_value != -1) {
                ROS_INFO("Read default speed0 value: %d", read_value);
            }

            // 写入寄存器 1005 以保存设置
            uint16_t save_value = 1; // 代表保存设置
            int save_rc = writeRegister(1005, save_value);
            if (save_rc == -1) {
                ROS_ERROR("Failed to write to Modbus register 1005 to save settings");
                res.default_speed_accepted = false; // 保存失败
            }
            else {
                ROS_INFO("Settings saved successfully to Modbus register 1005");
            }
        }
        else
        {
            ROS_WARN("Hand: default speed error! Default speed values must be <= 1000.");
            res.default_speed_accepted = false;
        }
    }
    else
    {
        ROS_WARN("Hand: default speed error! Default speed values must be >= 0.");
        res.default_speed_accepted = false;
    }

    return true; // 返回成功
}

bool inspire_hand::hand_serial::setANGLECallback(inspire_hand_modbus::set_angle::Request &req,
                                                 inspire_hand_modbus::set_angle::Response &res)
{
    ROS_INFO("hand: set angle");

    // 检查请求中的角度参数是否合法
    if ((req.angle0 >= -1 && req.angle0 <= 1000) &&
        (req.angle1 >= -1 && req.angle1 <= 1000) &&
        (req.angle2 >= -1 && req.angle2 <= 1000) &&
        (req.angle3 >= -1 && req.angle3 <= 1000) &&
        (req.angle4 >= -1 && req.angle4 <= 1000) &&
        (req.angle5 >= -1 && req.angle5 <= 1000))
    {
        // 将角度值写入 Modbus 寄存器
        res.angle_accepted = (writeRegister(1486, req.angle0) == 0) && // 小拇指角度
                             (writeRegister(1488, req.angle1) == 0) && // 无名指角度
                             (writeRegister(1490, req.angle2) == 0) && // 中指角度
                             (writeRegister(1492, req.angle3) == 0) && // 食指角度
                             (writeRegister(1494, req.angle4) == 0) && // 大拇指弯曲角度
                             (writeRegister(1496, req.angle5) == 0);   // 大拇指旋转角度

        // 读取某个寄存器的值（小拇指角度）
        int read_value = readRegister(1486);
        if (read_value != -1) {
            ROS_INFO("Read angle0 value: %d", read_value);
        }
    }
    else
    {
        ROS_WARN("Hand: angle error! Angle values must be in the range of -1 to 1000.");
        res.angle_accepted = false;
    }

    return true; // 返回成功
}

bool inspire_hand::hand_serial::setFORCECallback(inspire_hand_modbus::set_force::Request &req,
                                                 inspire_hand_modbus::set_force::Response &res)
{
    ROS_INFO("hand: set force");

    // 检查请求中的力控设置值是否合法
    if ((req.force0 >= 0 && req.force0 <= 3000) &&
        (req.force1 >= 0 && req.force1 <= 3000) &&
        (req.force2 >= 0 && req.force2 <= 3000) &&
        (req.force3 >= 0 && req.force3 <= 3000) &&
        (req.force4 >= 0 && req.force4 <= 3000) &&
        (req.force5 >= 0 && req.force5 <= 3000))
    {
        // 将力控设置值写入 Modbus 寄存器
        res.force_accepted = (writeRegister(1498, req.force0) == 0) && // 小拇指力控设置值
                             (writeRegister(1500, req.force1) == 0) && // 无名指力控设置值
                             (writeRegister(1502, req.force2) == 0) && // 中指力控设置值
                             (writeRegister(1504, req.force3) == 0) && // 食指力控设置值
                             (writeRegister(1506, req.force4) == 0) && // 大拇指弯曲力控设置值
                             (writeRegister(1508, req.force5) == 0);   // 大拇指旋转力控设置值

        // 读取某个寄存器的值（小拇指力控设置值）
        int read_value = readRegister(1498);
        if (read_value != -1) {
            ROS_INFO("Read FORCE_SET(0) value: %d", read_value);
        }
    }
    else
    {
        ROS_WARN("Hand: force error! Force values must be in the range of 0 to 1000.");
        res.force_accepted = false;
    }

    return true; // 返回成功
}

bool inspire_hand::hand_serial::setDEFAULT_FORCECallback(inspire_hand_modbus::set_default_force::Request &req,
                                                         inspire_hand_modbus::set_default_force::Response &res) {
    ROS_INFO("Hand: Set Default Force request received");

    // 检查请求中的初始力控参数是否合法
    if (req.force0 >= 0 && req.force1 >= 0 && req.force2 >= 0 && 
        req.force3 >= 0 && req.force4 >= 0 && req.force5 >= 0) {
        
        if (req.force0 <= 3000 && req.force1 <= 3000 && req.force2 <= 3000 && 
            req.force3 <= 3000 && req.force4 <= 3000 && req.force5 <= 3000) {
            
            // 将上电初始力控值写入 Modbus 寄存器
            res.default_force_accepted = (writeRegister(1044, req.force0) == 0) && // 小拇指上电初始力控
                                          (writeRegister(1046, req.force1) == 0) && // 无名指上电初始力控
                                          (writeRegister(1048, req.force2) == 0) && // 中指上电初始力控
                                          (writeRegister(1050, req.force3) == 0) && // 食指上电初始力控
                                          (writeRegister(1052, req.force4) == 0) && // 大拇指弯曲上电初始力控
                                          (writeRegister(1054, req.force5) == 0);   // 大拇指旋转上电初始力控

            // 读取某个寄存器的值（小拇指上电初始力控）
            int read_value = readRegister(1044);
            if (read_value != -1) {
                ROS_INFO("Read default force0 value: %d", read_value);
            }

            // 写入寄存器 1005 以保存设置
            uint16_t save_value = 1; // 代表保存设置
            int save_rc = writeRegister(1005, save_value);
            if (save_rc == -1) {
                ROS_ERROR("Failed to write to Modbus register 1005 to save settings");
                res.default_force_accepted = false; // 保存失败
            } else {
                ROS_INFO("Settings saved successfully to Modbus register 1005");
            }
        } else {
            ROS_WARN("Hand: default force error! Default force values must be <= 1000 for fingers and <= 1500 for thumbs.");
            res.default_force_accepted = false;
        }
    } else {
        ROS_WARN("Hand: default force error! Default force values must be >= 0.");
        res.default_force_accepted = false;
    }

    return true; // 返回成功
}

bool inspire_hand::hand_serial::setFORCE_CLBCallback(inspire_hand_modbus::set_force_clb::Request &req,
                                                     inspire_hand_modbus::set_force_clb::Response &res) {
    ROS_INFO("Hand: Set Force Calibration request received");

    uint16_t calibration_value = 1000; // 要写入的校准值

    // 写入寄存器 1486 到 1496
    for (int register_address = 1486; register_address <= 1496; register_address += 2) {
        int rc = writeRegister(register_address, calibration_value);
        if (rc == -1) {
            ROS_ERROR("Failed to write to Modbus register %d: %s", register_address, modbus_strerror(errno));
            res.setforce_clb_accepted = false; // 写入失败
            return true; // 返回成功，虽然操作失败
        }
    }

    // 延时 10 毫秒
    usleep(10000); // 10ms

    // 向寄存器 1009 写入 1，进行力控校准
    uint16_t force_calibration_value = 1;
    int rc = writeRegister(1009, force_calibration_value);
    
    if (rc == -1) {
        ROS_ERROR("Failed to write to Modbus register 1009: %s", modbus_strerror(errno));
        res.setforce_clb_accepted = false; // 写入失败
    } else {
        res.setforce_clb_accepted = true; // 写入成功
    }
    
    return true; // 返回成功
}

bool inspire_hand::hand_serial::setCURRENT_LIMITCallback(inspire_hand_modbus::set_current_limit::Request &req,
                                                         inspire_hand_modbus::set_current_limit::Response &res) {
    ROS_INFO("Hand: Set Current Limit request received");

    // 检查请求中的电流保护值是否合法
    if ((req.current0 >= 0 && req.current0 <= 1500) &&
        (req.current1 >= 0 && req.current1 <= 1500) &&
        (req.current2 >= 0 && req.current2 <= 1500) &&
        (req.current3 >= 0 && req.current3 <= 1500) &&
        (req.current4 >= 0 && req.current4 <= 1500) &&
        (req.current5 >= 0 && req.current5 <= 1500)) {
        
        // 将电流保护值写入 Modbus 寄存器
        res.current_limit_accepted = (writeRegister(1020, req.current0) == 0) && // 小拇指电流保护值
                                     (writeRegister(1022, req.current1) == 0) && // 无名指电流保护值
                                     (writeRegister(1024, req.current2) == 0) && // 中指电流保护值
                                     (writeRegister(1026, req.current3) == 0) && // 食指电流保护值
                                     (writeRegister(1028, req.current4) == 0) && // 大拇指弯曲电流保护值
                                     (writeRegister(1030, req.current5) == 0);   // 大拇指旋转电流保护值

        // 读取某个寄存器的值（小拇指电流保护值）
        int read_value = readRegister(1020);
        if (read_value != -1) {
            ROS_INFO("Read CURRENT_LIMIT(0) value: %d", read_value);
        }
    } else {
        ROS_WARN("Hand: current limit error! Current values must be in the range of 0 to 1500.");
        res.current_limit_accepted = false;
    }

    return true; // 返回成功
}

bool inspire_hand::hand_serial::setCLEAR_ERRORCallback(inspire_hand_modbus::set_clear_error::Request &req,
                                                       inspire_hand_modbus::set_clear_error::Response &res)
{
    ROS_INFO("Hand: Set CLEAR ERROR request received");

    uint16_t value = 1; // 写入1，代表清除错误
    int rc = writeRegister(1004, value);
    
    if (rc == -1) {
        ROS_ERROR("Failed to write to Modbus register: %s", modbus_strerror(errno));
        res.setclear_error_accepted = false; // 写入失败
    } else {
        res.setclear_error_accepted = true; // 写入成功
    }

    return true; // 返回成功
}

// Callback to reset parameters
bool inspire_hand::hand_serial::setRESET_PARACallback(inspire_hand_modbus::set_reset_para::Request &req,
                                                      inspire_hand_modbus::set_reset_para::Response &res) {
    ROS_INFO("Hand: Set RESET PARAMETER request received");

    uint16_t value = 1; // 写入1，代表重置参数
    int rc = writeRegister(1006, value);
    
    if (rc == -1) {
        ROS_ERROR("Failed to write to Modbus register: %s", modbus_strerror(errno));
        res.setreset_para_accepted = false; // 写入失败
    } else {
        res.setreset_para_accepted = true; // 写入成功
    }
   
    return true; // 返回成功
}

bool inspire_hand::hand_serial::setSAVE_FLASHCallback(inspire_hand_modbus::set_save_flash::Request &req,
                                                      inspire_hand_modbus::set_save_flash::Response &res) {
    ROS_INFO("Hand: Set SAVE FLASH request received");

    uint16_t value = 1; // 写入1，代表保存到闪存
    int rc = writeRegister(1005, value);
    
    if (rc == -1) {
        ROS_ERROR("Failed to write to Modbus register: %s", modbus_strerror(errno));
        res.setsave_flash_accepted = false; // 写入失败
    } else {
        res.setsave_flash_accepted = true; // 写入成功
    }
   
    return true; // 返回成功
}

// Read a register
int inspire_hand::hand_serial::readRegister(int reg_addr)
{
    uint16_t value;
    if (modbus_read_registers(ctx_, reg_addr, 1, &value) == -1) { // 只读取一个寄存器
        ROS_ERROR("Failed to read register %d: %s", reg_addr, modbus_strerror(errno));
        return -1; // Error
    }
    return value; // 返回读取的值
}

// Write to a register
int inspire_hand::hand_serial::writeRegister(int reg_addr, int value)
{
    if (modbus_write_register(ctx_, reg_addr, value) == -1) {
        ROS_ERROR("Failed to write register %d: %s", reg_addr, modbus_strerror(errno));
        return -1; // Error
    }
    return 0; // Success
}

// Write multiple registers (optional, if needed)
int inspire_hand::hand_serial::writeMultipleRegisters(int start_addr, const uint16_t *values, int num_values)
{
    if (modbus_write_registers(ctx_, start_addr, num_values, values) == -1) {
        ROS_ERROR("Failed to write registers starting at %d: %s", start_addr, modbus_strerror(errno));
        return -1; // Error
    }
    return 0; // Success
}

