# 🤖 RoboClean — 小车端代码

> 树莓派 4B + ROS 2 Humble + CANopen
> 推料机器人，120kg+，48V 60Ah，500W×2 + 200W

---

## 工作区结构

```
src/robot/
├── src/
│   ├── roboclean_bringup/          # 启动文件 + 参数配置
│   │   ├── launch/
│   │   │   └── bringup.launch.py   # 全节点主启动
│   │   └── config/
│   │       └── robot_params.yaml   # 全局参数
│   ├── roboclean_driver/           # CANopen 驱动 + 电机控制
│   │   └── roboclean_driver/
│   │       ├── canopen_driver.py   # C20-800LRC 底层驱动
│   │       ├── motor_controller.py # ROS 2 电机控制节点
│   │       └── encoder_odom.py     # 编码器里程计 (3层打滑检测)
│   ├── roboclean_sensors/          # 安全传感器
│   │   └── roboclean_sensors/
│   │       └── safety_sensor.py    # 安全触边 + 急停 + 超声波×4
│   ├── roboclean_navigation/       # 导航 (推料核心)
│   │   ├── launch/
│   │   │   └── navigation.launch.py
│   │   ├── config/
│   │   │   ├── nav2_params.yaml    # Nav2 参数 (DWB + A*)
│   │   │   └── slam_params.yaml    # slam_toolbox 参数
│   │   └── roboclean_navigation/
│   │       ├── fence_follower.py   # 围栏跟随 (RANSAC + PCA + PID)
│   │       ├── waypoint_navigator.py # 途经点导航 (App 路线模式)
│   │       └── charging_dock.py    # 自动回充控制器
│   └── roboclean_bt/               # 蓝牙通信
│       └── roboclean_bt/
│           └── bt_server.py        # SPP 服务端 + 协议解析
```

## 编译

```bash
cd src/robot
colcon build --symlink-install
source install/setup.bash
```

## 启动

```bash
# 完整启动 (所有节点)
ros2 launch roboclean_bringup bringup.launch.py can_channel:=can0

# 仅电机 + 里程计 + 安全
ros2 launch roboclean_bringup bringup.launch.py use_hardware:=false

# 单独启动各模块
ros2 run roboclean_driver motor_controller
ros2 run roboclean_driver encoder_odom
ros2 run roboclean_sensors safety_sensor
ros2 run roboclean_navigation fence_follower
ros2 run roboclean_navigation waypoint_navigator
ros2 run roboclean_navigation charging_dock
ros2 run roboclean_bt bt_server
```

## 控制小车

```bash
# 前进 0.3 m/s
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.3}, angular: {z: 0.0}}" -1

# 停止
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}, angular: {z: 0.0}}" -1
```

## 节点通信图

```
                 ┌──────────────┐
                 │  bt_server   │  ← 蓝牙 SPP (App↔车)
                 └──────┬───────┘
                        │ /bt/command
           ┌────────────┼────────────┐
           ▼            ▼            ▼
 ┌─────────────┐ ┌───────────┐ ┌───────────┐
 │  charging_  │ │ waypoint_ │ │  fence_   │
 │    dock     │ │ navigator │ │ follower  │
 └──────┬──────┘ └─────┬─────┘ └─────┬─────┘
        │              │   /nav/active │
        └──────────────┼───────────────┘
                       │ /cmd_vel
                ┌──────┴──────┐
                │   motor_    │  ← CANopen
                │ controller  │
                └──────┬──────┘
                       │ CAN Bus (500kbps)
           ┌───────────┼───────────┐
           ▼           ▼           ▼
      ┌────────┐ ┌────────┐ ┌────────┐
      │Driver 1│ │Driver 2│ │Driver 3│
      │Left 500W│ │Right 500W│ │Brush 200W│
      └────────┘ └────────┘ └────────┘

 ┌──────────┐  ┌───────────┐  ┌──────────┐
 │ encoder_ │  │  safety_  │  │   slam_  │
 │   odom   │  │  sensor   │  │  toolbox │
 └──────────┘  └───────────┘  └──────────┘
```

## Topic 索引

| Topic | 类型 | 发布者 | 订阅者 |
|-------|------|-------|--------|
| `/cmd_vel` | Twist | fence_follower / waypoint_navigator | motor_controller |
| `/safety/stop` | Bool | safety_sensor | motor_controller |
| `/odom` | Odometry | encoder_odom | Nav2 / slam_toolbox |
| `/scan` | LaserScan | lslidar (N10P) | fence_follower / slam_toolbox |
| `/ultrasonic/fence` | Float32 | safety_sensor | fence_follower |
| `/battery/voltage` | Float32 | motor_controller | bt_server / charging_dock |
| `/total_distance` | Float32 | encoder_odom | bt_server |
| `/nav/active` | Bool | waypoint_navigator | fence_follower (仲裁) |
| `/drum/run` | Bool | fence_follower | (CANopen → brush) |
| `/brush/run` | Bool | waypoint_navigator | (CANopen → brush) |
| `/route/waypoints` | String | bt_server (from App) | waypoint_navigator |
| `/bt/command` | String | bt_server | (日志/调试) |

## 前置依赖

```bash
# CANopen 驱动
pip3 install python-can canopen numpy

# CAN 接口配置
sudo ip link set can0 type can bitrate 500000
sudo ip link set up can0

# Nav2 (需要 ROS 2 Humble)
sudo apt install ros-humble-nav2-bringup ros-humble-slam-toolbox

# 蓝牙 (PyBluez)
sudo apt install libbluetooth-dev
pip3 install pybluez

# LiDAR (镭神 N10P)
# 安装 lslidar_driver ROS 2 包
```
