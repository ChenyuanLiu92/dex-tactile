#!/usr/bin/env python

import rospy
from inspire_hand.srv import get_pos_set  
import time

def call_service():
    rospy.wait_for_service('/inspire_hand/get_pos_set')
    try:
        set_pos_service = rospy.ServiceProxy('/inspire_hand/get_pos_set', get_pos_set)
        
        set_position = [500.0, 500.0, 500.0, 500.0, 500.0, 500.0]
        
        start_time = time.time()
        response_count = 0
        total_time = 0
        
        while not rospy.is_shutdown():
            # 调用服务，确保使用正确的参数名称
            response = set_pos_service(setpos=set_position)  # 使用 'setpos' 参数
            response_count += 1
            
            current_time = time.time()
            duration = current_time - start_time
            total_time += duration
            
            if response_count % 10 == 0:  # 每10次打印一次信息
                print("Response received: ", response)
                print("Average response time for last 10 calls: {:.4f} seconds".format(total_time / response_count))
            
            time.sleep(0.01)  # 间隔0.011秒再调用

    except rospy.ServiceException as e:
        print("Service call failed: %s" % e)

if __name__ == "__main__":
    rospy.init_node('test_service_node')
    call_service()

