# 🔧 技术选型与架构规范

> 本文档定义项目的技术栈、系统架构、通信协议和开发规范。

---

## 1. 技术栈总览

```
┌──────────────────────────────────────────────────────┐
│                    安卓 App                           │
│    Kotlin + Jetpack Compose + Material 3              │
│    MVVM: Screen → ViewModel → Repository/Service      │
│    地图: osmdroid (OpenStreetMap, 免费无 API Key)      │
│    持久化: DataStore Preferences                      │
│    蓝牙: 经典蓝牙 RFCOMM (SPP UUID)                    │
└──────────────────────┬───────────────────────────────┘
                       │ 蓝牙 SPP (RFCOMM)
                       │ 帧协议: [0xAA|len|cmd|payload|checksum]
┌──────────────────────┴───────────────────────────────┐
│                 小车端（树莓派 4B）                    │
│     OS: Ubuntu Server 22.04 + ROS 2 Humble           │
│     导航: Nav2 / 通道中线跟随 / 示教-复现              │
│     调度: 离线任务调度器 (TaskScheduler)               │
│     语言: Python 3.10+                                │
│     CANopen 单例: 多节点共享一个 Network               │
└──────────────────────┬───────────────────────────────┘
                       │ CAN Bus 500kbps
┌──────────────────────┴───────────────────────────────┐
│                   硬件层                               │
│    驱动器 ×3: ZBLD.C20-800LRC (Node ID 1/2/3)        │
│    LiDAR: 镭神 N10P (25m, 0.28deg)                   │
│    超声波 ×4 / 安全触边 ×2 / 急停按钮                  │
│    48V 60Ah 铅酸 → DC-DC → 树莓派 5V                  │
│    绝对值编码器 (17-bit, 131072 ppr)                   │
└──────────────────────────────────────────────────────┘
```

| 层面 | 选型 | 理由 |
|------|------|------|
| **App 语言** | Kotlin 2.0+ | Android 官方首选，现代化、安全 |
| **App UI** | Jetpack Compose 1.6+ + Material 3 | 声明式 UI，5 个 Tab 导航 |
| **App 架构** | MVVM (Screen→ViewModel→Repository/Service) | 关注点分离，可单测 |
| **App 地图** | osmdroid 6.1 (OpenStreetMap) | 免费，离线瓦片缓存 |
| **App 持久化** | DataStore Preferences | Key-Value，轻量可靠 |
| **App 蓝牙** | 经典蓝牙 RFCOMM (SPP) | 双向流，稳定可靠 |
| **小车 OS** | Ubuntu Server 22.04 (64-bit) | 树莓派 4B 兼容 |
| **机器人框架** | ROS 2 Humble | 行业标准，SLAM/导航生态成熟 |
| **SLAM** | slam_toolbox | 2D 雷达 SLAM |
| **导航** | Nav2 (A* + DWB) + 围栏跟随 v2 + 路径回放 | 三模互补 |
| **App↔车通信** | 蓝牙 SPP 帧协议 | 8 条指令，每 2s 轮询 |
| **电机控制** | CANopen (SocketCAN + canopen 库) | ZBLD.C20-800LRC 原生支持 |
| **路径录制** | PathRecorder × 10Hz odometry | 示教-复现模式 |
| **供电系统** | 48V 铅酸 60Ah | 直接驱动 500W×2 + 200W |
| **编码器** | 绝对值编码器 (17-bit) | 断电不失位置，精度高 |
| **测试** | pytest (Python) + JUnit + MockK (Kotlin) | 108 个自动化用例 |
| **版本控制** | Git + pre-commit (ruff + ktlint) | 提交前自动检查 |
| **CI/CD** | GitHub Actions | push 自动跑测试 + lint |

---

## 2. 系统架构

### 2.1 整体架构图

```
                       用户
                        │
        ┌───────────────┴───────────────┐
        │           App (Android)        │
        │                                │
        │  ┌──────┐ ┌──────┐ ┌──────┐   │
        │  │仪表盘 │ │ 路线  │ │ 时间  │   │
        │  │电量环│ │地图选点│ │周表  │   │
        │  └──┬───┘ └──┬───┘ └──┬───┘   │
        │     │        │        │       │
        │  ┌──┴───┐ ┌──┴───┐ ┌──┴───┐   │
        │  │ 操控  │ │ 蓝牙  │ │      │   │
        │  │方向键│ │设备扫描│ │      │   │
        │  │录制回放││连接管理│ │      │   │
        │  └──┬───┘ └──┬───┘ └──────┘   │
        │     │        │                │
        │  ┌──┴────────┴─────────────┐  │
        │  │      MVVM 层             │  │
        │  │  Screen → ViewModel     │  │
        │  │       → Repository      │  │
        │  │       → BluetoothService│  │
        │  └───────────┬─────────────┘  │
        └──────────────┼────────────────┘
                       │ 蓝牙 SPP (RFCOMM)
                       │ 帧: [0xAA|len|cmd|payload|checksum]
        ┌──────────────┼────────────────┐
        │      车端 (树莓派 4B)          │
        │              │                 │
        │  ┌───────────┴───────────┐    │
        │  │     bt_server         │    │
        │  │  SPP Server + 帧解析   │    │
        │  └───────┬───────┬───────┘    │
        │          │       │             │
        │  ┌───────┴─┐ ┌───┴────────┐  │
        │  │/bt/command│ │/bt/status  │  │
        │  └──┬───┬───┘ └────────────┘  │
        │     │   │                      │
        │     ▼   ▼                      │
        │  ┌──────────────┐             │
        │  │task_scheduler│ ← 定时触发   │
        │  │  (离线调度)   │             │
        │  └──┬───────┬───┘             │
        │     │/task  │/task            │
        │     │/start │/stop            │
        │     ▼       ▼                 │
        │  ┌──────────────────┐        │
        │  │ fence_follower   │ 20Hz   │
        │  │ (通道中线跟随 v2) │← /scan │
        │  │ LiDAR → 中线 →PID│        │
        │  └────────┬─────────┘        │
        │           │ /cmd_vel          │
        │  ┌────────┴─────────┐        │
        │  │ waypoint_navigator│← /route│
        │  │ (Nav2 途经点导航) │        │
        │  └────────┬─────────┘        │
        │           │ /nav/active       │
        │  ┌────────┴─────────┐        │
        │  │ path_player      │ 20Hz   │
        │  │ (路径回放 PP追踪) │← /task │
        │  │ path_recorder    │ 10Hz   │
        │  │ (录制 /odom)     │        │
        │  └────────┬─────────┘        │
        │           │ /cmd_vel          │
        │  ┌────────┴─────────┐        │
        │  │ motor_controller │ 10Hz   │
        │  │ Twist→RPM→CANopen│← /safety│
        │  └────────┬─────────┘        │
        │           │ CAN Bus 500kbps   │
        │  ┌────────┼─────────┐        │
        │  │   DriveSystem    │        │
        │  │ 左(1)右(2)刷(3)  │        │
        │  └──────────────────┘        │
        │                              │
        │  ┌──────────┐ ┌──────────┐  │
        │  │encoder   │ │ safety   │  │
        │  │_odom 50Hz│ │_sensor   │  │
        │  │打滑检测   │ │GPIO监测  │  │
        │  └──────────┘ └──────────┘  │
        │                              │
        │  ┌──────────┐ ┌──────────┐  │
        │  │charging  │ │ LiDAR    │  │
        │  │_dock     │ │ N10P     │  │
        │  │低电→回充  │ │ slam     │  │
        │  └──────────┘ └──────────┘  │
        └──────────────────────────────┘
```

### 2.2 App 内部架构（MVVM）

#### 2.2.1 分层职责

```
┌─────────────────────────────────────────────┐
│  Screen (Composable)          ← 只负责 UI    │
│  5 个 Tab: Dashboard / Route / Schedule     │
│            Control / Bluetooth              │
│                                             │
│  职责: 渲染界面，用户交互 → 调用 ViewModel     │
│  不知道: 蓝牙协议、数据存储、业务逻辑          │
├─────────────────────────────────────────────┤
│  ViewModel                     ← 业务逻辑    │
│  DashboardVM / RouteVM / ScheduleVM         │
│  ControlVM / BluetoothVM                    │
│                                             │
│  职责: 持有 StateFlow 状态，协调 Repository    │
│  不知道: Context、Activity、UI 细节           │
├─────────────────────────────────────────────┤
│  Repository / Service          ← 数据层      │
│  RouteRepository (DataStore)                │
│  BluetoothService (蓝牙 SPP)                 │
│  BleProtocol (帧构造/解析)                    │
│                                             │
│  职责: 数据存取、通信封装                     │
│  不知道: UI、ViewModel 的存在                │
└─────────────────────────────────────────────┘
```

#### 2.2.2 5 个 Screen 与其 ViewModel

| Screen | ViewModel | 关键数据 | 关键操作 |
|--------|-----------|---------|---------|
| **DashboardScreen** | DashboardViewModel | robotStatus, isConnected, estimatedHours | emergencyStop, returnToCharge |
| **RouteScreen** | RouteViewModel | waypoints (List + map), uiState | addWaypoint, deleteWaypoint, sendToRobot |
| **ScheduleScreen** | ScheduleViewModel | timeSlots, groupedByDay, uiState | addTimeSlot, toggleSlot, sendToRobot |
| **ControlScreen** | ControlViewModel | speedLevel, brushOn, isRecording, isPlaying | move四方向, toggleBrush, startRecording, startPlayback |
| **BluetoothScreen** | BluetoothViewModel | pairedDevices, discoveredDevices, connectedDevice | startScan, connect, disconnect |

#### 2.2.3 数据流示例 — 急停

```
用户点 [急停]
  → ControlScreen: viewModel.emergencyStop()
    → ControlViewModel: btService.emergencyStop()
      → BluetoothService: send(BleProtocol.buildFrame(0x04, empty))
        → 蓝牙: [0xAA][0x03][0x04][0xA8]
          → bt_server: /bt/command {"cmd":"emergency_stop"}
            → motor_controller: drives.emergency_stop()
              → CANopen: CMD_EMG_STOP (0x0006) → 三台驱动器立即断电
```

#### 2.2.4 数据流示例 — 状态查询 (每 2 秒)

```
BluetoothService.queryLoop() 每 2s:
  → send(CMD_QUERY_STATUS 0x01)
    → 蓝牙: [0xAA][0x03][0x01][0xA8]
      → bt_server: _send_status()
        → 蓝牙: [0xAA][0x0E][0x11][78%][52.0V][12.8km][工作中][35degC][CK]
          → BluetoothService.parseResponse()
            → _robotStatus.value = RobotStatus(78, 52.0, 12.8, true, 35)
              → DashboardVM.robotStatus (StateFlow)
                → DashboardScreen: BatteryRing(78), InfoCard("12.8 km")
```

### 2.3 车端节点图 (ROS 2)

#### 2.3.1 全部 9 个节点

| 节点 | 包 | 频率 | 职责 |
|------|-----|------|------|
| **bt_server** | roboclean_bt | 1Hz | 蓝牙 SPP 服务端 + 帧解析 + 协议转发 |
| **motor_controller** | roboclean_driver | 10Hz | Twist→RPM→CANopen + 手动操控 + 看门狗 |
| **encoder_odom** | roboclean_driver | 50Hz | 编码器→/odom + TF + 3层打滑检测 |
| **safety_sensor** | roboclean_sensors | 20Hz | GPIO 监测触边/急停 + 超声波非阻塞状态机 |
| **fence_follower** | roboclean_navigation | 20Hz | 两侧通道中线追踪 + PID + 拐角降速 |
| **waypoint_navigator** | roboclean_navigation | — | Nav2 途经点序列导航 |
| **charging_dock** | roboclean_navigation | 10Hz | 低电→Nav2→泊入→充电状态机 |
| **task_scheduler** | roboclean_navigation | 1Hz | 离线定时调度 + JSON 持久化 |
| **path_recorder** | roboclean_navigation | 10Hz | 录制 /odom 位置 + 刷子动作 |
| **path_player** | roboclean_navigation | 20Hz | Pure Pursuit 路径跟踪回放 |

#### 2.3.2 完整 Topic 索引

| Topic | 类型 | 发布者 | 订阅者 | 说明 |
|-------|------|--------|--------|------|
| `/cmd_vel` | Twist | fence_follower / waypoint_navigator / path_player | motor_controller | 速度指令 (仲裁优先级: nav > path > fence) |
| `/safety/stop` | Bool | safety_sensor | motor_controller | 急停信号 |
| `/odom` | Odometry | encoder_odom | Nav2 / path_recorder / path_player / bt_server | 里程计 |
| `/scan` | LaserScan | lslidar (N10P) | fence_follower / slam_toolbox | 激光点云 |
| `/ultrasonic/fence` | Float32 | safety_sensor | fence_follower | 超声波辅助 |
| `/battery/voltage` | Float32 | motor_controller | bt_server / charging_dock | 电池电压 |
| `/total_distance` | Float32 | encoder_odom | bt_server | 累计里程 |
| `/motor/status` | String | motor_controller | bt_server | 电机状态字符串 |
| `/drum/run` | Bool | fence_follower / waypoint_navigator | path_recorder (记录) | 推料刷控制 |
| `/brush/run` | Bool | waypoint_navigator | (CANopen) | 途经点模式下刷子控制 |
| `/nav/active` | Bool | waypoint_navigator | fence_follower | 导航仲裁: 导航期间暂停围栏跟随 |
| `/task/start` | Bool | task_scheduler | fence_follower / path_player | 定时任务启动 |
| `/task/stop` | Bool | task_scheduler | fence_follower / path_player | 定时任务停止 |
| `/task/status` | String | task_scheduler | (日志/调试) | 任务状态 |
| `/route/waypoints` | String | bt_server (from App) | waypoint_navigator | App 下发的途经点 JSON |
| `/route/status` | String | waypoint_navigator | bt_server | 导航进度反馈 |
| `/bt/command` | String | bt_server | motor_controller / task_scheduler / charging_dock / path_recorder / path_player | App 指令转发 |
| `/bt/status` | String | bt_server | (日志/调试) | 蓝牙连接状态 |
| `/path/status` | String | path_recorder / path_player | bt_server | 路径录制/回放状态 |
| `/fence/status` | String | fence_follower | (日志/调试) | 围栏跟随状态 |
| `/charging/status` | String | charging_dock | bt_server | 回充状态 |
| `/diagnostics/motor` | String | motor_controller | (日志/调试) | 电机诊断 |
| `/diagnostics/odom` | String | encoder_odom | (日志/调试) | 里程计诊断 |
| `/tf` | TransformStamped | encoder_odom | Nav2 / slam_toolbox | 坐标变换 |

#### 2.3.3 /cmd_vel 仲裁规则

三个节点都可能发布 `/cmd_vel`，优先级：

```
waypoint_navigator (Nav2 导航) → 最高优先级
  │ 发布 /nav/active=true → fence_follower 收到后暂停控制
  │
path_player (路径回放) → 中等优先级
  │ 由 task_scheduler 触发, 回放期间 fence_follower 不启动
  │
fence_follower (围栏跟随) → 最低优先级
  │ 仅在 /nav_active=false 且 /task_enabled=true 时工作
  │
motor_controller 的手动操控 → 旁路
  │ 直接订阅 /bt/command, 不经过 /cmd_vel
  │ App 手动操控按钮 → 直接写入 CANopen
```

---

## 3. 蓝牙通信协议

### 3.1 数据帧格式

```
┌──────┬──────┬──────┬──────────┬──────┐
│ 帧头  │ 长度  │ 指令  │   数据    │ 校验  │
│ 0xAA │ 1Byte│ 1Byte│  N Byte  │1Byte │
└──────┴──────┴──────┴──────────┴──────┘

长度 = 3 + payload.size
校验 = 0xAA XOR 长度 XOR 指令 XOR payload[0] XOR ... XOR payload[N-1]
```

### 3.2 指令定义 (v2 实现版)

| 指令 | 方向 | 名称 | Payload | 说明 |
|------|------|------|---------|------|
| `0x01` | App→车 | CMD_QUERY_STATUS | 无 | 查询状态，车端立即返回 0x11 |
| `0x02` | App→车 | CMD_SET_SCHEDULE | UTF-8 JSON | 设置工作时间表 |
| `0x03` | App→车 | CMD_SET_ROUTE | UTF-8 JSON | 设置路线途经点 |
| `0x04` | App→车 | CMD_EMERGENCY | 无 | 紧急停止 |
| `0x05` | App→车 | CMD_START_STOP | [0x01]=启动 / [0x00]=停止 | 启动/停止工作 |
| `0x06` | App→车 | CMD_MANUAL_CTRL | UTF-8 JSON | 手动操控指令 |
| `0x11` | 车→App | RSP_STATUS | 11 bytes 结构体 | 返回状态数据 |
| `0x12` | 车→App | RSP_ACK | [0x01]=成功 / [0x00]=失败 | 确认收到指令 |

### 3.3 状态 payload (0x11) 结构

```
[电池% u8][电压 f32 LE][总里程 f32 LE][工作中 u8][温度 u8]
   1B       4B           4B             1B       1B  = 11 bytes

示例:
  [0x4E] [0x00 0x00 0x50 0x42] [0xCD 0xCC 0x4C 0x41] [0x01] [0x23]
   78%         52.0V              12.8km              工作中    35°C
```

### 3.4 手动操控 payload (0x06) 格式

```json
// 方向控制
{"action": "move", "direction": "forward", "speed": 0.25}
{"action": "stop"}

// 刷子
{"action": "brush", "on": true}

// 路径录制
{"action": "record_start", "name": "示教路径"}
{"action": "record_stop"}

// 路径回放
{"action": "playback_start", "file": ""}
{"action": "playback_stop"}
```

### 3.5 工作时间表 payload (0x02) 格式

```json
{
  "slots": [
    {"id":1, "dayOfWeek":"周一", "startHour":8, "startMinute":0,
     "endHour":9, "endMinute":30, "enabled":true},
    {"id":2, "dayOfWeek":"周一", "startHour":14, "startMinute":0,
     "endHour":16, "endMinute":0, "enabled":true}
  ]
}
```

### 3.6 路线途经点 payload (0x03) 格式

```json
{
  "waypoints": [
    {"id":1, "name":"通道入口", "lat":39.9042, "lon":116.4074, "yaw":0.0},
    {"id":2, "name":"通道中点", "lat":39.9050, "lon":116.4080, "yaw":0.1},
    {"id":3, "name":"通道出口", "lat":39.9060, "lon":116.4088, "yaw":0.0}
  ]
}
```

### 3.7 修改协议流程

1. 更新本文件 §3
2. App 端修改 `BleProtocol.kt` + `BluetoothService.kt`
3. 车端修改 `bt_server.py` 的常量和 `_parse_frame()`
4. 两端各自更新单元测试 (BleProtocolTest.kt + test_bt_protocol.py)
5. 集成测试确认互通 (帧构造 → 发送 → 接收 → 解析)

---

## 4. CANopen 电机控制协议

### 4.1 CAN 总线拓扑

```
树莓派 (CANopen Master)
  │ CAN HAT (MCP2515)
  │
  ╧══════════════════ CAN Bus (双绞屏蔽线, 500kbps) ══════════════════
  │                    │                    │
  ├─ 终端电阻 120Ω     │                    ├─ 终端电阻 120Ω
  │                    │                    │
                 ┌─────┴─────┐        ┌─────┴─────┐        ┌─────┴─────┐
                 │  驱动器1   │        │  驱动器2   │        │ 清洁驱动  │
                 │ Node ID: 1 │        │ Node ID: 2 │        │ Node ID: 3 │
                 │ 左轮 500W  │        │ 右轮 500W  │        │ 刷子 200W  │
                 └───────────┘        └───────────┘        └───────────┘
```

### 4.2 CANopen 通信机制

| 机制 | 说明 |
|------|------|
| **NMT** | 网络管理：控制驱动器上/下线、复位 |
| **SDO** | 服务数据对象：配置驱动器参数（加速、减速、PID） |
| **PDO** | 过程数据对象：实时传输速度指令 / 位置反馈（高优先级） |
| **Heartbeat** | 心跳：驱动器定时发送状态，监控在线 |

### 4.3 期望的 PDO 映射（需与驱动器手册核对）

| PDO | 方向 | 内容 |
|-----|------|------|
| TPDO1 | 驱动器→主机 | 当前位置（绝对值编码器）+ 当前速度 + 状态字 |
| RPDO1 | 主机→驱动器 | 目标速度 + 控制字（使能/启停/模式） |

### 4.4 驱动器关键寄存器（ZBLD.C20-800LRC）

> 详见 [`docs/driver-c20-800lrc.md`](driver-c20-800lrc.md)

| 地址 | 含义 | R/W | 说明 |
|------|------|-----|------|
| `2000h` | 控制命令 | W/R | 0001h=正转, 0002h=反转, 0005h=停机, 0006h=紧停 |
| `2001h` | 设定速度 | W/R | 单位 RPM |
| `2004h` | 实际速度 | R | 单位 RPM |
| `2005h` | 实际电流 | R | 单位 0.1A |
| `2006h` | 母线电压 | R | 单位 0.1V（可用于监测电池） |
| `2007h` | 故障代码 | R | 0=正常 |
| `200Bh` | 状态字 | R | Bit0=运行, Bit1=正转, Bit3=故障 |

### 4.5 软件实现

```
motor_controller 节点:
  /cmd_vel (Twist) → 差速运动学 → RPM
    v_left = v - w×sep/2, v_right = v + w×sep/2
    RPM = v / (2π×radius) × 60 × gear_ratio
    限幅 ±1500 RPM

  → CANopen SDO 写:
    REG_SPEED_SET (0x2001) ← RPM
    REG_CONTROL (0x2000)   ← CMD_FWD_RUN / CMD_REV_RUN

encoder_odom 节点:
  CANopen SDO 读 REG_ENCODER (0x2104) ← 编码器原始值
  → 弧度 = raw / resolution × 2π / gear_ratio
  → /odom (Odometry) + TF (base_link→odom)

CANopen 共享单例 (解决多节点连接冲突):
  get_shared_network(channel='can0')  ← 全局唯一 canopen.Network
  C20Driver(1, network=shared)         ← encoder_odom 用共享网络
  DriveSystem(1,2,3, channel=can0)    ← motor_controller 用共享网络
```

---

## 5. 供电系统

### 5.1 供电架构

| 电压 | 来源 | 供给 |
|------|------|------|
| 48V DC | 铅酸电池 60Ah | 三路驱动器 ZBLD.C20-800LRC (48V 800W)、接触器线圈 |
| 5V DC | 48V→5V DC-DC 隔离模块 (10A) | 树莓派 4B (~3A)、镭神 N10P |
| 3.3V | 树莓派板载 | CAN HAT (MCP2515)、GPIO 传感器 |

### 5.2 安全回路

```
电池(+) → 总保险 100A → 急停按钮(常闭) → 接触器线圈 → 电池(-)
                                                  │
                                  接触器主触点(三路) → 各驱动器电源
```

- 按下急停 → 接触器断开 → 所有驱动器物理断电 (<10ms)
- 安全触边触发 → GPIO LOW → /safety/stop → 软件急停 (<50ms)
- cmd_watchdog: 0.5s 无指令自动停车 → CANopen CMD_STOP
- 断线保护: GPIO 上拉 (PUD_UP) → 断线时 HIGH → 不误触发

---

## 6. 开发规范

### 6.1 代码规范

| 项目 | 规范 |
|------|------|
| App 代码风格 | Kotlin 官方代码规范 + ktlint 检查 |
| 小车代码风格 | Python: PEP8 + ruff 检查 |
| 注释语言 | 中文（方便项目成员理解） |
| Git 提交信息 | `[类型] 简短描述`，类型: feat/fix/docs/tooling/ci/refactor/test |
| Lint 工具 | 提交前: ruff (Python) + ktlint (Kotlin) + 通用检查 (pre-commit) |
| CI | GitHub Actions: push 自动跑 pytest + ktlintCheck + testDebugUnitTest |

### 6.2 文件命名

| 类型 | 命名规则 | 示例 |
|------|----------|------|
| App 页面 | `XxxScreen.kt` | `DashboardScreen.kt` |
| App ViewModel | `XxxViewModel.kt` | `RouteViewModel.kt` |
| App 组件 | `XxxCard.kt` / `XxxItem.kt` | `DeviceCard` / `WaypointItem` |
| App 主题 | `Xxx.kt` | `Color.kt` / `Theme.kt` |
| 小车节点 | `xxx_xxx.py` (snake_case) | `motor_controller.py` |
| 小车启动 | `xxx.launch.py` | `bringup.launch.py` |
| 小车配置 | `xxx_params.yaml` | `robot_params.yaml` |
| 小车测试 | `test_xxx.py` | `test_bt_protocol.py` |

### 6.3 Skills 约束

详见 [`.github/skills/`](../.github/skills/)，开发时遵循 7 个 skill 约束:

- `frontend`: Android/Kotlin/Compose 技术约束
- `backend`: ROS 2/Python/CANopen 技术约束
- `coding-standards`: 代码书写规范 (命名、注释、CR 清单)
- `architecture`: 架构设计规范 (MVVM/分层/ADR)
- `testing`: 测试规范 (覆盖率/金字塔)
- `ui-design`: UI 设计规范 (组件复用/交互状态)
- `docs`: 文档规范 (格式/术语/devlog)

---

## 7. 路径模式 (示教-复现)

### 7.1 工作流程

```
第一次到现场 (示教 — 只需做一次):
  1. 机器人推到通道起点，开机
  2. App 连接蓝牙 → 操控页 → 点 [开始录制]
  3. 手动驾驶沿完整路线走一遍
  4. 点 [停止录制] → 路径保存为 ~/roboclean_paths/path_YYYYMMDD_HHMMSS.json

之后每天 (自动):
  1. 到设定时间 → task_scheduler 触发 /task/start
  2. path_player 加载最新路径 → Pure Pursuit 跟踪回放
  3. 录制时启停刷子的位置自动复现
  4. 回放结束 → 停车
  5. 低电量时 → charging_dock 自动回充
  6. 完全不需要 App 在线
```

### 7.2 路径文件格式

```json
{
  "version": 1,
  "created": "2026-06-20T14:30:00",
  "duration_s": 180.5,
  "points": 1800,
  "path": [
    {"type":"pose", "x":0.0, "y":0.0, "yaw":0.0, "brush":false, "t":0.0},
    {"type":"pose", "x":0.025, "y":0.001, "yaw":0.001, "brush":false, "t":0.1},
    ...
    {"type":"action", "action":"brush", "on":true, "t":12.5},
    ...
  ]
}
```

### 7.3 Pure Pursuit 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| lookahead_distance | 0.8m | 前视距离，越大路径越平滑 |
| max_speed | 0.25 m/s | 回放最大速度 |
| goal_tolerance | 0.3m | 终点容忍度，到达即停止 |
| max_angular | 0.6 rad/s | 最大角速度 |

---

## 8. 依赖版本

| 依赖 | 版本 |
|------|------|
| Android minSdk | 26 (Android 8.0) |
| Android targetSdk | 34 |
| Kotlin | 2.0+ |
| Jetpack Compose | 1.6+ (BOM 2024.06) |
| Navigation Compose | 2.7.7 |
| Lifecycle ViewModel | 2.8.2 |
| DataStore Preferences | 1.1.1 |
| osmdroid | 6.1.18 |
| Kotlin Serialization | 1.7.1 |
| MockK (test) | 1.13.12 |
| ROS 2 | Humble |
| Ubuntu | 22.04 Server (64-bit) |
| Python | 3.10+ |
| canopen | ≥ 2.2 |
| python-can | ≥ 4.0 |
| numpy | ≥ 1.24 |
| pytest | ≥ 7.0 |
| PyBluez | ≥ 0.23 |
| slam_toolbox | ROS 2 Humble |
| nav2-bringup | ROS 2 Humble |

---

> 📌 最后更新：2026-06-18 — v2 架构全面修订 (MVVM + 示教复现 + 通道中线 + 离线调度)
