# 四颜色 RGB-D 分拣决策 Demo

这个适配版只检测目标并输出分拣建议，不控制底盘、机械臂、舵机或夹爪。它支持
红、黄、绿、蓝四种颜色，并将结果保存为 JSON、发布为 `std_msgs/String`：

```sh
/data/robot-host/student/demo/color_sorting/run-color-sorting-demo.sh
```

固定覆盖输出：

```text
/data/robot-host/student/output/color-sorting/latest-color-sorting.jpg
/data/robot-host/student/output/color-sorting/latest-color-sorting-depth-preview.jpg
/data/robot-host/student/output/color-sorting/latest-color-sorting.json
```

一次运行期间还会在 `/student/color_sorting/decision` 发布同一份 JSON。配置文件
`color_sorting_config.json` 只保存颜色到语义收纳区的映射，不保存抓取或放置坐标。

`recommendation_ready=true` 仅表示颜色分拣建议可用。`pick_ready` 在本 Demo 中恒为
`false`：相机光学坐标必须经过当前实车手眼标定转换到 `base_link`，再做 IK、工作
空间和碰撞检查，才允许由单独的动作层执行抓取。
