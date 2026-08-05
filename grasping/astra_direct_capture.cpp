// astra_direct_capture.cpp — 绕过 ROS，直接用 Orbbec SDK 抓 Astra 帧
// 用途：验证相机底层链路（SDK→USB）是否健康，排除 ROS 包装层嫌疑。
// 容器内编译：
//   g++ -std=c++11 astra_direct_capture.cpp -o astra_direct_capture \
//     -I/vision_ws/src/orbbec_camera/SDK/include \
//     -L/vision_ws/src/orbbec_camera/SDK/lib/arm64 -lOrbbecSDK \
//     -Wl,-rpath,/vision_ws/src/orbbec_camera/SDK/lib/arm64
// 运行：./astra_direct_capture [帧数=5] [输出目录=/tmp/astra_direct]
#include <ObSensor.hpp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <sys/stat.h>

static void save_pgm16(const char *path, const uint16_t *data, int w, int h) {
    FILE *f = fopen(path, "wb");
    if (!f) return;
    fprintf(f, "P5\n%d %d\n65535\n", w, h);
    for (int i = 0; i < w * h; i++) {   // PGM 是大端
        uint16_t v = data[i];
        fputc((v >> 8) & 0xff, f);
        fputc(v & 0xff, f);
    }
    fclose(f);
}

static void save_yuyv(const char *path, const uint8_t *data, int w, int h) {
    // YUYV 转灰度 PGM（只取 Y 分量，验证用足够）
    FILE *f = fopen(path, "wb");
    if (!f) return;
    fprintf(f, "P5\n%d %d\n255\n", w, h);
    for (int i = 0; i < w * h; i++) fputc(data[i * 2], f);
    fclose(f);
}

int main(int argc, char **argv) {
    int n_frames = argc > 1 ? atoi(argv[1]) : 5;
    std::string outdir = argc > 2 ? argv[2] : "/tmp/astra_direct";
    bool node_mode = argc > 3 && std::string(argv[3]) == "--node-mode";
    mkdir(outdir.c_str(), 0777);

    try {
        // 复现 ROS 节点：用相同的 XML config 创建 Context
        std::shared_ptr<ob::Context> ctx;
        if (node_mode) {
            printf("[node-mode] context with OrbbecSDKConfig_v1.0.xml\n");
            ctx = std::make_shared<ob::Context>(
                "/vision_ws/src/orbbec_camera/config/OrbbecSDKConfig_v1.0.xml");
        } else {
            ctx = std::make_shared<ob::Context>();
        }
        auto devList = ctx->queryDeviceList();
        if (devList->deviceCount() == 0) {
            fprintf(stderr, "FAIL: no device found\n");
            return 2;
        }
        auto dev = devList->getDevice(0);
        auto info = dev->getDeviceInfo();
        printf("device: %s sn=%s vid=0x%04x pid=0x%04x conn=%s\n",
               info->name(), info->serialNumber(), info->vid(), info->pid(),
               info->connectionType());

        if (node_mode) {
            // 复现 ROS 节点 init：查询彩色相机曝光/增益/白平衡
            printf("[node-mode] querying color exposure/gain/white-balance...\n");
            try {
                int exposure = dev->getIntProperty(OB_PROP_COLOR_EXPOSURE_INT);
                printf("[node-mode] exposure=%d OK\n", exposure);
                int gain = dev->getIntProperty(OB_PROP_COLOR_GAIN_INT);
                printf("[node-mode] gain=%d OK\n", gain);
            } catch (ob::Error &e) {
                printf("[node-mode] PROPERTY QUERY FAILED: %s\n", e.getMessage());
            }
        }

        ob::Pipeline pipe(dev);
        std::shared_ptr<ob::Config> config = std::make_shared<ob::Config>();
        auto colorProfiles = pipe.getStreamProfileList(OB_SENSOR_COLOR);
        config->enableStream(colorProfiles->getVideoStreamProfile());
        auto depthProfiles = pipe.getStreamProfileList(OB_SENSOR_DEPTH);
        if (!node_mode) {
            config->enableStream(depthProfiles->getVideoStreamProfile());
        }
        if (node_mode) {
            // 复现 ROS 节点：同时开 IR 流 + launch 里的 Y11 深度格式 + 标定参数查询
            printf("[node-mode] also enabling IR stream...\n");
            try {
                auto irProfiles = pipe.getStreamProfileList(OB_SENSOR_IR);
                config->enableStream(irProfiles->getVideoStreamProfile());
            } catch (ob::Error &e) {
                printf("[node-mode] IR profile failed: %s\n", e.getMessage());
            }
            printf("[node-mode] requesting depth Y11 profile (launch config)...\n");
            try {
                auto dy11 = depthProfiles->getVideoStreamProfile(640, 480, OB_FORMAT_Y11, 30);
                config->enableStream(dy11);
            } catch (ob::Error &e) {
                printf("[node-mode] Y11 profile FAILED: %s\n", e.getMessage());
            }
            printf("[node-mode] getCalibrationCameraParamList...\n");
            try {
                auto params = dev->getCalibrationCameraParamList();
                printf("[node-mode] calibration params count=%d OK\n", params->count());
            } catch (ob::Error &e) {
                printf("[node-mode] CALIBRATION QUERY FAILED: %s\n", e.getMessage());
            }
        }
        pipe.start(config);
        printf("pipeline started\n");

        int got_color = 0, got_depth = 0;
        for (int i = 0; i < n_frames * 3 && (got_color < n_frames || got_depth < n_frames); i++) {
            auto frameSet = pipe.waitForFrames(2000);
            if (!frameSet) { printf("frameSet timeout\n"); continue; }
            auto color = frameSet->colorFrame();
            if (color && got_color < n_frames) {
                char path[256];
                if (color->format() == OB_FORMAT_MJPG) {
                    snprintf(path, sizeof(path), "%s/color_%02d.jpg", outdir.c_str(), got_color);
                    FILE *f = fopen(path, "wb");
                    fwrite(color->data(), 1, color->dataSize(), f);
                    fclose(f);
                } else if (color->format() == OB_FORMAT_YUYV) {
                    snprintf(path, sizeof(path), "%s/color_%02d_yuyv.pgm", outdir.c_str(), got_color);
                    save_yuyv(path, (const uint8_t *)color->data(), color->width(), color->height());
                } else {
                    snprintf(path, sizeof(path), "%s/color_%02d.raw", outdir.c_str(), got_color);
                    FILE *f = fopen(path, "wb");
                    fwrite(color->data(), 1, color->dataSize(), f);
                    fclose(f);
                }
                printf("color %d: %dx%d format=%d size=%u -> %s\n", got_color,
                       color->width(), color->height(), color->format(),
                       color->dataSize(), path);
                got_color++;
            }
            auto depth = frameSet->depthFrame();
            if (depth && got_depth < n_frames) {
                char path[256];
                snprintf(path, sizeof(path), "%s/depth_%02d.pgm", outdir.c_str(), got_depth);
                save_pgm16(path, (const uint16_t *)depth->data(), depth->width(), depth->height());
                printf("depth %d: %dx%d format=%d -> %s\n", got_depth,
                       depth->width(), depth->height(), depth->format(), path);
                got_depth++;
            }
        }
        pipe.stop();
        printf("DONE color=%d depth=%d\n", got_color, got_depth);
        return (got_color > 0 && got_depth > 0) ? 0 : 3;
    } catch (ob::Error &e) {
        fprintf(stderr, "FAIL: %s (%s)\n", e.getMessage(), e.getName());
        return 4;
    }
}
