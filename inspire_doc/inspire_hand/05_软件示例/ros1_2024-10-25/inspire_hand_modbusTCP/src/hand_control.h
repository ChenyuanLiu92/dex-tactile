#ifndef HAND_CONTROL_H
#define HAND_CONTROL_H

#include <ros/ros.h>
#include <modbus/modbus.h>
#include <sensor_msgs/JointState.h>
#include <inspire_hand_modbus/get_pos_set.h>
#include <inspire_hand_modbus/get_pos_act.h>
#include <inspire_hand_modbus/get_force_act.h>
#include <inspire_hand_modbus/get_force_set.h>
#include <inspire_hand_modbus/get_current.h>
#include <inspire_hand_modbus/get_error.h>
#include <inspire_hand_modbus/get_angle_act.h>
#include <inspire_hand_modbus/get_angle_set.h>
#include <inspire_hand_modbus/get_temp.h>
#include <inspire_hand_modbus/set_clear_error.h>
#include <inspire_hand_modbus/get_status.h>

#include <inspire_hand_modbus/set_id.h>
#include <inspire_hand_modbus/set_redu_ratio.h>
#include <inspire_hand_modbus/set_reset_para.h>
#include <inspire_hand_modbus/set_pos.h>
#include <inspire_hand_modbus/set_gesture_no.h>
#include <inspire_hand_modbus/set_default_speed.h>
#include <inspire_hand_modbus/set_speed.h>
#include <inspire_hand_modbus/set_angle.h>
#include <inspire_hand_modbus/set_save_flash.h>
#include <inspire_hand_modbus/set_force.h>
#include <inspire_hand_modbus/set_force_clb.h>
#include <inspire_hand_modbus/set_default_force.h>
#include <inspire_hand_modbus/set_current_limit.h>

// ...其他服务头文件...

namespace inspire_hand
{

class hand_serial
{
public:
    hand_serial(ros::NodeHandle *nh);
    ~hand_serial();

    bool getERRORCallback(inspire_hand_modbus::get_error::Request &req,
                          inspire_hand_modbus::get_error::Response &res);

    bool getERROR(float errorvalue[6]);
    
    bool getFORCE_ACTCallback(inspire_hand_modbus::get_force_act::Request &req,
                              inspire_hand_modbus::get_force_act::Response &res);
    
    bool getCURRENTCallback(inspire_hand_modbus::get_current::Request &req,
                            inspire_hand_modbus::get_current::Response &res);
    
    bool getANGLE_SETCallback(inspire_hand_modbus::get_angle_set::Request &req,
                              inspire_hand_modbus::get_angle_set::Response &res);
                              
    bool getANGLE_ACTCallback(inspire_hand_modbus::get_angle_act::Request &req,
                              inspire_hand_modbus::get_angle_act::Response &res);
                                 
    bool getFORCE_SETCallback(inspire_hand_modbus::get_force_set::Request &req,
                              inspire_hand_modbus::get_force_set::Response &res);
    
    bool getTEMPCallback(inspire_hand_modbus::get_temp::Request &req,
                         inspire_hand_modbus::get_temp::Response &res);
    
    bool getPOS_SETCallback(inspire_hand_modbus::get_pos_set::Request &req,
                            inspire_hand_modbus::get_pos_set::Response &res);
                            
    bool getPOS_ACTCallback(inspire_hand_modbus::get_pos_act::Request &req,
                            inspire_hand_modbus::get_pos_act::Response &res);
                            
    bool getSTATUSCallback(inspire_hand_modbus::get_status::Request &req,
                           inspire_hand_modbus::get_status::Response &res);
                                                                                                                    
    
    bool setCLEAR_ERRORCallback(inspire_hand_modbus::set_clear_error::Request &req,
                                inspire_hand_modbus::set_clear_error::Response &res);         
                              
    bool setIDCallback(inspire_hand_modbus::set_id::Request &req,
                       inspire_hand_modbus::set_id::Response &res);

    bool setREDU_RATIOCallback(inspire_hand_modbus::set_redu_ratio::Request &req,
                               inspire_hand_modbus::set_redu_ratio::Response &res);
    
    bool setPOSCallback(inspire_hand_modbus::set_pos::Request &req,
                        inspire_hand_modbus::set_pos::Response &res);
    
    bool setGESTURE_NOCallback(inspire_hand_modbus::set_gesture_no::Request &req,
                               inspire_hand_modbus::set_gesture_no::Response &res);
    
    bool setGESTURE_NO(int gesture_no);
    
    bool setSPEEDCallback(inspire_hand_modbus::set_speed::Request &req,
                          inspire_hand_modbus::set_speed::Response &res);
                          
    bool setDEFAULT_SPEEDCallback(inspire_hand_modbus::set_default_speed::Request &req,
                                  inspire_hand_modbus::set_default_speed::Response &res);
    
    bool setANGLECallback(inspire_hand_modbus::set_angle::Request &req,
                          inspire_hand_modbus::set_angle::Response &res);
                       
    bool setSAVE_FLASHCallback(inspire_hand_modbus::set_save_flash::Request &req,
                               inspire_hand_modbus::set_save_flash::Response &res);
                               
    bool setFORCE_CLBCallback(inspire_hand_modbus::set_force_clb::Request &req,
                              inspire_hand_modbus::set_force_clb::Response &res);
                              
    bool setFORCECallback(inspire_hand_modbus::set_force::Request &req,
                          inspire_hand_modbus::set_force::Response &res); 
                          
    bool setDEFAULT_FORCECallback(inspire_hand_modbus::set_default_force::Request &req,
                                  inspire_hand_modbus::set_default_force::Response &res);
                                  
    bool setCURRENT_LIMITCallback(inspire_hand_modbus::set_current_limit::Request &req,
                                  inspire_hand_modbus::set_current_limit::Response &res);
    
    bool setRESET_PARACallback(inspire_hand_modbus::set_reset_para::Request &req,
                               inspire_hand_modbus::set_reset_para::Response &res);
                                   
    int id;
    int writeMultipleRegisters(int start_addr, const uint16_t* values, int num_values);
    int getRegisterValue(int reg_addr) {
        return readRegister(reg_addr); // 通过公有方法调用私有方法
    }
    // ...其他回调函数...

private:
    // Modbus TCP 上下文
    modbus_t *ctx_;

    // 设备参数
    std::string ip_address_;
    int port_;

    // ...其他设置函数...
    // 读取和写入 Modbus 数据的通用方法
    int readRegister(int reg_addr);
    int writeRegister(int reg_addr, int value);
};

} // namespace inspire_hand

#endif

