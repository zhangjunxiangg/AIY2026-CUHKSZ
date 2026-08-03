#!/usr/bin/python3
#coding=utf8

# 通过深度图识别物体的外形进行分类
# 机械臂向下识别
# 可以识别长方体，球，圆柱体

import cv2
import tone
import math
import queue
import rospy
import threading
import numpy as np
import message_filters
import transforms3d as tfs
from sensor_msgs.msg import Image as RosImage
from sensor_msgs.msg import CameraInfo
from std_srvs.srv import SetBool,Trigger,TriggerResponse
from servo_msgs.msg import MultiRawIdPosDur
from interfaces.srv import GetRobotPose
from sdk import pid, fps
from servo_controllers.bus_servo_control import set_servos
from kinematics import kinematics_control

def xyz_quat_to_mat(xyz, quat):
    mat = tfs.quaternions.quat2mat(np.asarray(quat))
    mat = tfs.affines.compose(np.squeeze(np.asarray(xyz)), mat, [1, 1, 1])
    return mat

def xyz_euler_to_mat(xyz, euler, degrees=True):
    if degrees:
        mat = tfs.euler.euler2mat(math.radians(euler[0]), math.radians(euler[1]), math.radians(euler[2]))
    else:
        mat = tfs.euler.euler2mat(euler[0], euler[1], euler[2])
    mat = tfs.affines.compose(np.squeeze(np.asarray(xyz)), mat, [1, 1, 1])
    return mat

def mat_to_xyz_euler(mat, degrees=True):
    t, r, _, _ = tfs.affines.decompose(mat)
    if degrees:
        euler = np.degrees(tfs.euler.mat2euler(r))
    else:
        euler = tfs.euler.mat2euler(r)
    return t, euler

def depth_pixel_to_camera(pixel_coords, depth, intrinsics):
    fx, fy, cx, cy = intrinsics
    px, py = pixel_coords
    x = (px - cx) * depth / fx
    y = (py - cy) * depth / fy
    z = depth
    return np.array([x, y, z])

class RgbDepthImageNode:
    def __init__(self):
        rospy.init_node('shape_recognition', anonymous=True)
        self.fps = fps.FPS()
        self.last_shape = "none"  #上一个形状
        self.rgb_sub = None       #rbg话题
        self.depth_sub = None #深度话题
        self.info_sub = None #相机内参话题
        self.sync = None #时间同步器名
        self.moving = False #是否开始夹取
        self.count = 0 
        self.close = False #是否关闭节点
        self.endpoint = None #末端坐标
        self.shape = None #形状
        self.pick_state = False #是否开始检测
        self.target_shape = "None" #目标形状
        self.queue = queue.Queue(maxsize=1) #图像队列
        rospy.set_param('~status', 'start') #设置目前节点状态
        self.hand2cam_tf_matrix = [[0.0,0.0,1.0,-0.105],
                                   [-1.0,0.0,0.0,0.0],
                                   [0.0,-1.0,0.0,0.044],
                                   [0.0,0.0,0.0,1.0]]
        #舵机控制
        self.servos_pub = rospy.Publisher('/robot_1/servo_controllers/port_id_1/multi_id_pos_dur', MultiRawIdPosDur, queue_size=1)
        rospy.sleep(3)
        #初始化目标形状参数，方便设置
        rospy.set_param('~target_shape', 'box')
        rospy.Service('~pick', Trigger, self.pick_callback) #进行夹取
        rospy.Service('~stop', Trigger, self.stop_callback) #停止节点
        rospy.Service('~start', Trigger, self.start_callback) #启动形状识别
        rospy.Service('~colse', Trigger, self.colse_callback) #关闭节点
        rospy.sleep(2)
        rospy.wait_for_service('/robot_1/gemini_camera/set_ldp') #等待相机ldp服务
        rospy.ServiceProxy('/robot_1/gemini_camera/set_ldp', SetBool)(False) #关闭相机ldp服务器，近距离也能进行识别
        # threading.Thread(target=self.goto_default, args=()).start()
        # 同步时间戳, 时间允许有误差在0.03s
        # sync = message_filters.ApproximateTimeSynchronizer([rgb_sub, depth_sub, info_sub], 3, 0.03)
        # sync.registerCallback(self.multi_callback) #执行反馈函数
        # self.queue = queue.Queue(maxsize=1)
    #启动形状识别
    def start_callback(self,msg):
        threading.Thread(target=self.goto_default, args=()).start() #得到相机目前的末端位置
        self.rgb_sub = message_filters.Subscriber('/robot_1/gemini_camera/rgb/image_raw', RosImage, queue_size=1) # rgb话题
        self.depth_sub = message_filters.Subscriber('/robot_1/gemini_camera/depth/image_raw', RosImage, queue_size=1) # 深度话题
        self.info_sub = message_filters.Subscriber('/robot_1/gemini_camera/depth/camera_info', CameraInfo, queue_size=1) # 相机内参话题
        # 同步时间戳, 时间允许有误差在0.03s
        self.sync = message_filters.ApproximateTimeSynchronizer([self.rgb_sub, self.depth_sub, self.info_sub], 3, 0.03)
        self.sync.registerCallback(self.multi_callback) #执行反馈函数
        return TriggerResponse(success=True)
    #停止形状识别
    def stop_callback(self,msg):
        self.rgb_sub.unregister() #关闭话题
        self.depth_sub.unregister()
        self.info_sub.unregister()
        return TriggerResponse(success=True)
    #关闭节点
    def colse_callback(self,msg):
        self.close = True
        return TriggerResponse(success=True)
    #进行夹取
    def pick_callback(self,msg):
        #设置目标形状
        self.target_shape = rospy.get_param('/shape_recognition/target_shape',"box")
        #进入机械臂进入夹取状态
        set_servos(self.servos_pub, 1, ((1, 500), (2, 500), (3, 150), (4, 130), (5, 500), (10, 200)))
        rospy.sleep(2)
        self.pick_state = True
        rospy.set_param('~pick', True)
        return TriggerResponse(success=True)
    
    # 得到机械臂末端坐标
    def goto_default(self):
        while not rospy.is_shutdown():
            endpoint = rospy.ServiceProxy('/kinematics/get_current_pose', GetRobotPose)()
            # print(endpoint)
            pose_t = endpoint.pose.position
            pose_r = endpoint.pose.orientation
            self.endpoint = xyz_quat_to_mat([pose_t.x, pose_t.y, pose_t.z], [pose_r.w, pose_r.x, pose_r.y, pose_r.z]) 

    # 夹取函数
    def move(self, shape, pose_t, angle):  
        rospy.sleep(0.5)
        pose_t[2] += 0.02
        ret1 = kinematics_control.set_pose_target(pose_t, 85) # 根据逆运动学得到舵机脉宽
        if len(ret1[1]) > 0:
            set_servos(self.servos_pub, 1.5, ((1, ret1[1][0]), (2, ret1[1][1]), (3, ret1[1][2]), (4, ret1[1][3]),(5, ret1[1][4])))
            rospy.sleep(1.5)
        pose_t[2] -= 0.05
        # print(pose_t)
        ret2 = kinematics_control.set_pose_target(pose_t, 85)
        # print(ret2)
        if angle != 0 and len(ret2[1]) > 0:
            angle = angle % 180
            angle = angle - 180 if angle > 90 else (angle + 180 if angle < -90 else angle)
            angle = 500 + int(1000 * (angle + ret2[3][-1]) / 240)
        else:
            angle = 500
        if len(ret2[1]) > 0:
            set_servos(self.servos_pub, 0.5, ((5, angle),))
            rospy.sleep(0.5)
            set_servos(self.servos_pub, 1, ((1, ret2[1][0]), (2, ret2[1][1]), (3, ret2[1][2]), (4, ret2[1][3]),(5, angle)))
            rospy.sleep(1)
            set_servos(self.servos_pub, 0.6, ((10, 750),))
            rospy.sleep(0.6)
        if len(ret1[1]) > 0:
            set_servos(self.servos_pub, 1, ((1, ret1[1][0]), (2, ret1[1][1]), (3, ret1[1][2]), (4, ret1[1][3]),(5, angle)))
            rospy.sleep(1)
        set_servos(self.servos_pub, 1, ((1, 500), (2, 720), (3, 100), (4, 150), (5, 500), (10, 650)))
        rospy.sleep(1)
        rospy.set_param('~status', 'stop')
        self.pick_state = False
        self.moving = False
    # 时间同步回调函数
    def multi_callback(self, ros_rgb_image, ros_depth_image, depth_camera_info):
        if self.queue.empty():
            self.queue.put_nowait((ros_rgb_image, ros_depth_image, depth_camera_info))
            node.image_proc()
        #判断是否需要关闭节点
        if self.close :
            rospy.signal_shutdown('shutdown')
    # 开始检测
    def image_proc(self):
        #得到图像信息
        ros_rgb_image, ros_depth_image, depth_camera_info = self.queue.get(block=True)
        try:
            if self.pick_state:
                # 转换图像格式
                rgb_image = np.ndarray(shape=(ros_rgb_image.height, ros_rgb_image.width, 3), dtype=np.uint8, buffer=ros_rgb_image.data)
                depth_image = np.ndarray(shape=(ros_depth_image.height, ros_depth_image.width), dtype=np.uint16, buffer=ros_depth_image.data)

                ih, iw = depth_image.shape[:2]

                depth_image = depth_image.copy()
                # 屏蔽掉一些区域，降低识别条件，使识别跟可靠
                depth_image[:, 0:50] = np.array([[1000,]*50]* 400)
                depth_image[:, 590:640] = np.array([[1000,]*50]* 400)
                depth_image[320:400, :] = np.array([[1000,]*640]* 80)
                # depth_image[0:30, :] = np.array([[1000,]*640]* 30)
                depth = np.copy(depth_image).reshape((-1, ))
                depth[depth<=0] = 55555 # 距离为0可能是进入死区，或者颜色问题识别不到，将距离赋一个大值
                min_index = np.argmin(depth) # 距离最小的像素
                min_y = min_index // iw
                min_x = min_index - min_y * iw

                min_dist = depth_image[min_y, min_x] # 获取最小距离值
                # print(min_dist)
                sim_depth_image = np.clip(depth_image, 0, 300).astype(np.float64) / 300 * 255
                depth_image = np.where(depth_image > min_dist + 17, 0, depth_image) # 将深度值大于最小距离15mm的像素置0
                sim_depth_image_sort = np.clip(depth_image, 0, 2000).astype(np.float64) / 2000 * 255                
                depth_gray = sim_depth_image_sort.astype(np.uint8)
                depth_gray = cv2.GaussianBlur(depth_gray, (3, 3), 0)
                _, depth_bit = cv2.threshold(depth_gray, 1, 255, cv2.THRESH_BINARY)
                depth_bit = cv2.erode(depth_bit, np.ones((3, 3), np.uint8))
                depth_bit = cv2.dilate(depth_bit, np.ones((3, 3), np.uint8))
                depth_color_map = cv2.applyColorMap(sim_depth_image.astype(np.uint8), cv2.COLORMAP_JET)

                contours, hierarchy = cv2.findContours(depth_bit, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
                shape = 'None'
                contour = None
                for obj in contours:
                    if min_dist > 220: #最小距离不能大于220
                        break
                    area = cv2.contourArea(obj) 
                    # print(area)
                    if area < 3000 or area > 15000 or self.moving is True:
                        continue
                    cv2.drawContours(depth_color_map, obj, -1, (255, 255, 0), 4) # 绘制轮廓线
                    perimeter = cv2.arcLength(obj, True)  # 计算轮廓周长
                    approx = cv2.approxPolyDP(obj, 0.04 * perimeter, True) # 获取轮廓角点坐标
                    cv2.drawContours(depth_color_map, approx, -1, (255, 0, 0), 4) # 绘制轮廓线
                    CornerNum = len(approx)

                    x, y, w, h = cv2.boundingRect(approx)
                    x_contour_depth = depth_image[y + int(h / 2) - 2: y + int(h / 2) + 2, x: x + w] # 获取轮廓中心一整行的深度数据
                    y_contour_depth = depth_image[y : y + h, x + int(w / 2) - 2: x + int(w / 2)+2 ] # 获取轮廓中心一整行的深度数据
                    # 我们根据X轴像素的标准差来判断是曲面类物体(圆柱体/球体)还是多面体(立方体、长方体)
                    # 曲面的标准差较大
                    # 因摄像头与桌面有一定角度， 所以Y轴的标准差在平面上也会比较大,不好判断. X轴不存在这个问题
                    x_depth  =  np.where(x_contour_depth == 0, np.nan, x_contour_depth) # 计算这行数据中有效数据的标准差
                    y_depth  =  np.where(y_contour_depth == 0, np.nan, y_contour_depth) # 计算这行数据中有效数据的标准差
                    x_depth_std = np.nanstd(x_depth)
                    y_depth_std = np.nanstd(y_depth)
                    # print(w,h)
                    # print(abs(w/h),abs(h/w))
                    # print(x_depth_std,y_depth_std, CornerNum)
                    # print(x_depth_std - y_depth_std)
                    if x_depth_std <= 0.9 and y_depth_std <= 1.15 and CornerNum == 4: 
                        objType="cuboid_1" # 立方体/长方体
                    else:
                        # print(CornerNum)
                        if abs(w/h) > 1.7 or abs(h/w) > 1.7 and CornerNum == 4:
                            if x_depth_std <= 0.9 and y_depth_std <= 1.15:
                                objType="cuboid_2" # 立方体/长方体
                            else:
                                if w > 100 or h > 100:
                                    objType="cuboid_3" # 立方体/长方体
                                else:
                                    objType="cylinder_2" # 圆柱体
                                    self.shape = 'cylinder'
                        else:
                            if abs(x_depth_std - y_depth_std) > 0.5 :
                                if x_depth_std <= 0.9 and y_depth_std <= 1.15:
                                    objType="cuboid_4" # 立方体/长方体
                                else:
                                    if w > 100 or h > 100:
                                        objType="cuboid_5" # 立方体/长方体
                                    else:
                                        objType="cylinder_3" # 圆柱体
                                        self.shape = 'cylinder'
                            else:
                                if w > 100 or h > 100:
                                    objType="cuboid_6" # 立方体/长方体
                                    self.shape = 'cylinder'
                                else:
                                    objType="cylinder_4" # 圆柱体
                                    self.shape = 'cylinder'
                    shape=objType
                    # print(shape)
                    contour = obj
                    if 'cubo' in objType:
                        # 判断是正方体还是长方体
                        # 这里取巧，我们的木块正方体的高度都不超过4.0直接判断一下
                        # 不取巧的方法就是通过最小外接矩形的四个角点及中心点像素坐标
                        # 调用 depth_pixel_to_camera获取各点在空间中的位置
                        # 然后计算其真实变成及中心点高度
                        # 再通过真实值判断其形状
                        if abs(w - h) < 10:
                            if w > 100 or h > 100:
                                objType = "cube_1" # 正方体
                                self.shape = 'cube'
                            else:
                                objType = "box_1"  # 长方体
                                self.shape = 'box'
                        else:
                            objType = "cube_2" # 正方体
                            self.shape = 'cube'

                    cv2.rectangle(depth_color_map, (x, y), (x + w, y + h), (255, 255, 255), 2)
                    cv2.putText(depth_color_map, objType[:-2], (x + w // 2, y + (h //2) - 10), cv2.FONT_HERSHEY_COMPLEX, 1.0, (0, 0, 0), 2, cv2.LINE_AA)
                    cv2.putText(depth_color_map, objType[:-2], (x + w // 2, y + (h //2) - 10), cv2.FONT_HERSHEY_COMPLEX, 1.0, (255, 255, 255), 1)
                    print(self.shape)
                    if self.shape == rospy.get_param('/shape_recognition/target_shape',"box"):
                        break
                    else:
                        self.shape = "None"
                # print(self.shape,self.target_shape)
                if self.last_shape == shape and shape != 'None'and self.shape == self.target_shape:
                    print(self.count)
                    self.count += 1
                    self.shape = 'None'
                else:
                    self.count = 0
                if contour is not None :
                    angle = 0
                    if shape == "cylinder_1" or shape == "cuboid_1":
                        center, (width, height), angle = cv2.minAreaRect(contour)
                        if angle < -45:
                            angle += 90
                        if width > height and width / height > 1.5:
                            print("wh: ", width, height)
                            angle = angle + 90
                        cv2.drawContours(depth_color_map, [np.int0(cv2.boxPoints((center, (width,height), angle)))], -1, (0, 0, 255), 2, cv2.LINE_AA)
                    if self.count > 3:
                        # print("dddd")
                        (cx, cy), r = cv2.minEnclosingCircle(obj)
                        K = depth_camera_info.K
                        position = depth_pixel_to_camera((cx, cy), min_dist / 1000, (K[0], K[4], K[2], K[5]))
                        position[0] -= 0.0171
                        pose_end = np.matmul(self.hand2cam_tf_matrix, xyz_euler_to_mat(position, (0, 0, 0)))
                        world_pose = np.matmul(self.endpoint, pose_end)
                        pose_t, pose_r = mat_to_xyz_euler(world_pose)
                        # print(pose_t[2])
                        min_x, min_y = cx, cy
                        print(pose_t)
                        # angle = 0
                        offset_x = -0.01
                        offset_y = 0.0
                        offset_z = -0.015
                        pose_t[0] += offset_x
                        pose_t[1] += offset_y
                        pose_t[2] += offset_z
                        self.count = 0
                        self.moving = True
                        threading.Thread(target=self.move, args=(shape[:-2], pose_t, angle)).start()
                self.last_shape = shape

                bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
                self.fps.update()

            else:
                rospy.sleep(0.01)
        except Exception as e:
            rospy.logerr('callback error:', str(e))



if __name__ == "__main__":
    
    node = RgbDepthImageNode()
    try:
        rospy.spin()
    except exception as e:
        # mecnum_pub.publish(twist())
        rospy.logerr(str(e))

