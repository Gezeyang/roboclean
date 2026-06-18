# 🚀 部署指南 — 树莓派小车端

> 从零开始，把树莓派变成一台能跑的推料机器人。

---

## 一、硬件准备

| 序号 | 硬件 | 检查项 |
|------|------|--------|
| 1 | 树莓派 4B (4GB+) | 正常点亮，TF 卡 ≥ 32GB |
| 2 | CAN HAT (MCP2515) | 已插到 GPIO 排针，短接 120Ω 终端电阻 |
| 3 | CAN 双绞线 | 连接 CAN HAT → 三台驱动器的 CANH/CANL |
| 4 | 48V→5V DC-DC | 给树莓派供电，输出 ≥ 3A |
| 5 | 网线 / WiFi | 树莓派有网络（安装依赖用） |
| 6 | 镭神 N10P LiDAR | USB 连接 |
| 7 | 蓝牙适配器 | 树莓派 4B 板载蓝牙即可 |
| 8 | 安全触边 / 急停 / 超声波 | GPIO 按 `safety_sensor.py` 引脚接好 |

---

## 二、烧录系统

### 2.1 下载 Ubuntu Server 22.04

用 Raspberry Pi Imager 烧录：
- OS: `Ubuntu Server 22.04 LTS (64-bit)`
- 烧录前在 Imager 里设置 WiFi + SSH

### 2.2 首次登录

```bash
# 插卡开机，通过路由器后台找到 IP，或直接接显示器
ssh ubuntu@<树莓派IP>
# 默认密码: ubuntu（首次登录会要求改密码）
```

### 2.3 基础配置

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 设置时区
sudo timedatectl set-timezone Asia/Shanghai

# 设置主机名（可选）
sudo hostnamectl set-hostname roboclean
```

---

## 三、CAN 接口配置

### 3.1 启用 SPI + MCP2515

```bash
# 编辑 /boot/firmware/config.txt  (Ubuntu) 或 /boot/config.txt (Raspberry Pi OS)
sudo nano /boot/firmware/config.txt
```

添加以下行：

```
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
dtoverlay=spi-bcm2835
```

### 3.2 配置 CAN 接口

```bash
# 重启后生效
sudo reboot

# 验证 CAN 接口存在
ip link show can0

# 设置 500kbps 并启用
sudo ip link set can0 type can bitrate 500000
sudo ip link set up can0

# 测试: 自发自收
# 终端1:
candump can0
# 终端2:
cansend can0 123#DEADBEEF
```

### 3.3 开机自动启用 CAN

```bash
sudo nano /etc/systemd/network/can0.network
```

```
[Match]
Name=can0

[CAN]
BitRate=500K
```

```bash
sudo systemctl enable systemd-networkd
```

---

## 四、安装 ROS 2 Humble

```bash
# 添加 ROS 2 源
sudo apt install software-properties-common -y
sudo add-apt-repository universe -y
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update

# 安装 ROS 2 Humble 桌面版（含 RViz2）
sudo apt install ros-humble-desktop -y
# 或最小安装: sudo apt install ros-humble-ros-base -y
```

```bash
# 在 ~/.bashrc 中添加 ROS 2 环境
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

验证：
```bash
ros2 run demo_nodes_cpp talker   # 终端1
ros2 run demo_nodes_cpp listener # 终端2
```

---

## 五、安装项目依赖

### 5.1 Python 包

```bash
pip3 install --upgrade pip
pip3 install python-can canopen numpy    # CANopen 驱动
pip3 install pybluez                      # 蓝牙 SPP
# PyBluez 需要系统库:
sudo apt install libbluetooth-dev -y
```

### 5.2 ROS 2 导航包

```bash
sudo apt install ros-humble-nav2-bringup -y
sudo apt install ros-humble-slam-toolbox -y
sudo apt install ros-humble-tf2-ros -y
```

### 5.3 镭神 N10P LiDAR 驱动

```bash
# 在 ~/ros2_ws/src 下克隆
cd ~/ros2_ws/src
git clone https://github.com/RoboSense-LiDAR/lslidar_ros2.git
cd ~/ros2_ws
colcon build --packages-select lslidar_driver
```

### 5.4 测试工具

```bash
sudo apt install can-utils -y      # candump / cansend
sudo apt install bluetooth -y       # bluetoothctl
sudo apt install bluez -y
```

---

## 六、部署项目代码

### 6.1 拉取代码

```bash
mkdir -p ~/roboclean_ws/src
cd ~/roboclean_ws/src

# git clone（需要先配好 GitHub SSH Key 或用 HTTPS）
git clone https://github.com/Gezeyang/roboclean.git roboclean

# 或用 SSH:
# git clone git@github.com:Gezeyang/roboclean.git roboclean
```

### 6.2 建立 ROS 2 workspace 软链接

项目代码在 `src/robot/` 下，ROS 2 需要把它链接到 workspace：

```bash
cd ~/roboclean_ws
ln -s ~/roboclean_ws/src/roboclean/src/robot/src/* src/
```

或者更直接地——直接在 robot 目录里 build：

```bash
cd ~/roboclean_ws/src/roboclean/src/robot
colcon build --symlink-install
```

### 6.3 编译

```bash
cd ~/roboclean_ws
colcon build --symlink-install
source install/setup.bash
```

`--symlink-install` 意味着修改 Python 源码后**不需要重新编译**，重启节点即可生效。

---

## 七、运行

### 7.1 启动全部节点

```bash
source /opt/ros/humble/setup.bash
source ~/roboclean_ws/install/setup.bash
ros2 launch roboclean_bringup bringup.launch.py can_channel:=can0
```

### 7.2 仅启动核心（无真实硬件时测试）

```bash
ros2 launch roboclean_bringup bringup.launch.py use_hardware:=false
```

### 7.3 检查节点状态

```bash
ros2 node list          # 列出所有运行中的节点
ros2 topic list         # 列出所有 Topic
ros2 topic echo /motor/status  # 查看电机状态
ros2 topic echo /battery/voltage  # 查看电池电压
```

### 7.4 手动控制测试

```bash
# 前进 0.2 m/s
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2}, angular: {z: 0.0}}" -1

# 停止
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}, angular: {z: 0.0}}" -1
```

---

## 八、开机自启（Systemd）

### 8.1 创建服务文件

```bash
sudo nano /etc/systemd/system/roboclean.service
```

```ini
[Unit]
Description=RoboClean Robot Bringup
After=network.target can0.device
Wants=can0.device

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/roboclean_ws
Environment="ROS_DOMAIN_ID=0"
ExecStartPre=/bin/sleep 5
ExecStart=/bin/bash -c 'source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch roboclean_bringup bringup.launch.py'
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 8.2 启用

```bash
sudo systemctl daemon-reload
sudo systemctl enable roboclean.service
sudo systemctl start roboclean.service

# 查看日志
sudo journalctl -u roboclean.service -f
```

---

## 九、蓝牙配对（App 连接）

```bash
# 进入蓝牙控制台
sudo bluetoothctl

# 在 bluetoothctl 中:
power on
discoverable on
pairable on
agent on
default-agent

# 给小车蓝牙命名
system-alias RoboClean-001

# 等待 App 端搜索并配对
# 配对后 App 端用 SPP UUID 00001101-0000-1000-8000-00805F9B34FB 连接
```

---

## 十、故障排查

### CAN 不通

```bash
# 检查接口是否存在
ip link show can0

# 检查是否有终端电阻（CAN H/L 间应约 60Ω）
# 检查 MCP2515 overlay 是否生效
dmesg | grep -i can
dmesg | grep -i mcp

# 手动加载
sudo modprobe mcp251x
sudo ip link set can0 type can bitrate 500000
sudo ip link set up can0
```

### 蓝牙连不上

```bash
# 检查蓝牙服务状态
sudo systemctl status bluetooth

# 重启蓝牙
sudo systemctl restart bluetooth

# 查看日志
sudo journalctl -u bluetooth -f
```

### LiDAR 无数据

```bash
# 检查 USB 设备
ls /dev/ttyUSB*
lsusb | grep -i cp210  # N10P 一般用 CP210x USB 串口

# 检查串口权限
sudo chmod 666 /dev/ttyUSB0

# 手动启动 LiDAR 驱动测试
ros2 run lslidar_driver lslidar_driver_node --ros-args -p serial_port:=/dev/ttyUSB0
```

### 驱动器不响应

```bash
# 检查 CAN 通信
candump can0

# 检查驱动器上电（48V 接入）
# 检查 Node ID 是否正确（出厂默认 1/2/3）
# 用 SDO 读取寄存器测试:
python3 -c "
import canopen
net = canopen.Network()
net.connect(channel='can0', bustype='socketcan')
node = net.add_node(1, object_dictionary={})
print('Fault code:', node.sdo[0x2102].raw)
net.disconnect()
"
```

---

## 十一、日常更新代码

```bash
cd ~/roboclean_ws/src/roboclean
git pull

# Python 代码改了不需要重新编译（--symlink-install 生效）
# 只需要重启节点:
ros2 daemon stop
ros2 launch roboclean_bringup bringup.launch.py
```

---

> 📌 最后更新：2026-06-18
