---
name: backend
description: "Use when: working on ROS 2, Python, robot driver, CANopen, SLAM, Nav2, sensor, motor control. Applies to src/robot/."
---

# Backend — 小车端 (Python / ROS 2 Humble)

> 约束来源：`docs/design-spec.md` §7.3 + `docs/tech-spec.md` §2-4

## 核心规则

1. **语言**：Python 3.10+，非性能瓶颈不用 C++
2. **框架**：ROS 2 Humble，禁止 ROS 1 语法
3. **CANopen**：严格遵循 `docs/tech-spec.md` §4 和 `docs/driver-c20-800lrc.md`
4. **蓝牙协议**：与 App 端 `BleProtocol` 帧格式一致，禁止单方面修改
5. **日志**：用 `rclpy` logger，禁止 `print()`

## 代码结构

```
src/robot/
├── roboclean_bringup/     # Launch 文件 + 参数配置
├── roboclean_bt/          # 蓝牙 SPP 服务端 + 协议
├── roboclean_driver/      # CANopen Master + 电机控制 + 编码器里程计
├── roboclean_navigation/  # SLAM (slam_toolbox) + Nav2 + 途经点执行
└── roboclean_sensors/     # RPLidar A1M8 + 安全触边 + 超声波 + 电量检测
```

## ROS 2 规范

| 事项 | 规范 |
|------|------|
| Topic 命名 | `snake_case`，按模块前缀：`/motor/cmd_vel`、`/sensor/laser`、`/nav/waypoint` |
| Node 命名 | `snake_case`，与包名对应：`motor_driver`、`bt_server`、`slam_node` |
| Launch | 所有节点统一通过 Launch 文件启动，禁止手动 ros2 run |
| 参数 | 敏感参数放 `config/` YAML，禁止硬编码 |
| QOS | 传感器数据用 `SENSOR_DATA`，指令用 `SYSTEM_DEFAULT` |

## 安全约束

- 急停、触边、超声波独立节点，互不阻塞
- 安全传感器优先级高于导航指令
- 低电量（<20%）自动触发回充，App 同步告警

## 禁止事项

- ❌ 修改 CANopen Node ID / 波特率 → 必须先改 `docs/tech-spec.md`
- ❌ 蓝牙帧格式单方面改动 → 两端必须同步
- ❌ `print()` 调试 → 用 `self.get_logger().info()`
- ❌ 硬编码 IP / 端口 / 路径
