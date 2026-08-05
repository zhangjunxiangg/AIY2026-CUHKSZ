// astra_bridge.cpp — SDK→ROS 桥接节点（替代坏掉的 orbbec_camera_node）
// 直接用 Orbbec SDK 取帧，转成 sensor_msgs/Image 发布到 /astra_camera/* 话题。
// 容器内编译命令见 build_bridge.sh。
#include <ObSensor.hpp>
#include <ros/ros.h>
#include <sensor_msgs/Image.h>
#include <opencv2/opencv.hpp>
#include <memory>

static ros::Publisher g_pub_rgb;
static ros::Publisher g_pub_depth;

static void fill_header(sensor_msgs::Image &msg, const std::string &frame_id) {
    msg.header.stamp = ros::Time::now();
    msg.header.frame_id = frame_id;
}

int main(int argc, char **argv) {
    ros::init(argc, argv, "astra_bridge");
    ros::NodeHandle nh;
    g_pub_rgb = nh.advertise<sensor_msgs::Image>("/astra_camera/rgb/image_raw", 1);
    g_pub_depth = nh.advertise<sensor_msgs::Image>("/astra_camera/depth/image_raw", 1);

    try {
        auto ctx = std::make_shared<ob::Context>();
        auto devList = ctx->queryDeviceList();
        if (devList->deviceCount() == 0) {
            ROS_FATAL("astra_bridge: no device found");
            return 2;
        }
        auto dev = devList->getDevice(0);
        auto info = dev->getDeviceInfo();
        ROS_INFO("astra_bridge: device %s sn=%s", info->name(), info->serialNumber());

        ob::Pipeline pipe(dev);
        auto config = std::make_shared<ob::Config>();
        auto colorProfiles = pipe.getStreamProfileList(OB_SENSOR_COLOR);
        config->enableStream(colorProfiles->getVideoStreamProfile(640, 480, OB_FORMAT_MJPG, 30));
        auto depthProfiles = pipe.getStreamProfileList(OB_SENSOR_DEPTH);
        config->enableStream(depthProfiles->getVideoStreamProfile());

        pipe.start(config, [](const std::shared_ptr<ob::FrameSet> &fs) {
            auto color = fs->colorFrame();
            if (color && g_pub_rgb.getNumSubscribers() >= 0) {
                cv::Mat img;
                if (color->format() == OB_FORMAT_MJPG) {
                    img = cv::imdecode(cv::Mat(1, color->dataSize(), CV_8UC1, color->data()),
                                       cv::IMREAD_COLOR);
                }
                if (!img.empty()) {
                    sensor_msgs::Image msg;
                    fill_header(msg, "astra_camera_color_optical_frame");
                    msg.height = img.rows;
                    msg.width = img.cols;
                    msg.encoding = "bgr8";
                    msg.step = img.cols * 3;
                    msg.data.assign(img.data, img.data + (size_t)msg.step * img.rows);
                    g_pub_rgb.publish(msg);
                }
            }
            auto depth = fs->depthFrame();
            if (depth) {
                sensor_msgs::Image msg;
                fill_header(msg, "astra_camera_depth_optical_frame");
                msg.height = depth->height();
                msg.width = depth->width();
                msg.encoding = "16UC1";
                msg.step = depth->width() * 2;
                msg.data.assign((const uint8_t *)depth->data(),
                                (const uint8_t *)depth->data() + (size_t)msg.step * msg.height);
                g_pub_depth.publish(msg);
            }
        });
        ROS_INFO("astra_bridge: pipeline started, publishing /astra_camera/rgb|depth/image_raw");
        ros::spin();
        pipe.stop();
    } catch (ob::Error &e) {
        ROS_FATAL("astra_bridge: %s", e.getMessage());
        return 4;
    }
    return 0;
}
