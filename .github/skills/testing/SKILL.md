---
name: testing
description: "Use when: writing unit/integration/HIL tests, setting up test frameworks, defining test strategy, mocking dependencies. Applies to src/."
---

# Testing — 测试规范

> 约束来源：`docs/tech-spec.md` §6 + `docs/development-plan.md`
> 配合：[[coding-standards]] [[architecture]] [[frontend]] [[backend]]

## 核心原则

1. **可测试性是设计出来的**：代码写完了才想"怎么测"就晚了
2. **测试是文档**：看测试代码应该能理解模块的行为契约
3. **快速反馈**：单元测试毫秒级，集成测试秒级，端到端测试按需
4. **独立性**：每个测试不依赖其他测试的执行顺序

---

## 一、测试金字塔

```
         ╱  E2E / 硬件在环（HIL）  ╲
        ╱    少量，验证完整链路      ╲
       ╱─────────────────────────────╲
      ╱       集成测试                ╱
     ╱    模块间接口、Topic 通信      ╱
    ╱───────────────────────────────╱
   ╱        单元测试                ╱
  ╱   函数/方法级，覆盖所有逻辑分支  ╱
 ╱─────────────────────────────────╱
```

| 层级 | App 端 | Robot 端 | 目标数量 |
|------|--------|----------|---------|
| **单元测试** | ViewModel / Repository / BleProtocol | 每个 Node 的核心方法、协议解析 | 大量（每函数 ≥1） |
| **集成测试** | BluetoothService + 协议 | Topic 发布/订阅链路、CANopen 通信 | 适中（每个模块间接口 ≥1） |
| **E2E / HIL** | App ↔ Robot 蓝牙通信 | 完整 bringup + 传感器 + 电机 | 少量（核心流程） |

---

## 二、单元测试规范

### 2.1 测试文件组织

```
App 端:
src/app/app/src/test/java/com/roboclean/app/
├── bluetooth/
│   ├── BleProtocolTest.kt       ← 协议帧构造/解析
│   └── BluetoothServiceTest.kt  ← 连接/收发逻辑
├── data/
│   ├── RouteRepositoryTest.kt
│   └── ScheduleRepositoryTest.kt
└── ui/
    ├── DashboardViewModelTest.kt
    ├── BluetoothViewModelTest.kt
    ├── RouteViewModelTest.kt
    └── ScheduleViewModelTest.kt

Robot 端:
src/robot/src/<package>/test/
├── test_canopen_driver.py
├── test_motor_controller.py
├── test_encoder_odom.py
├── test_bt_protocol.py          ← 帧解析与车端协议
├── test_fence_follower.py
└── test_safety_sensor.py
```

### 2.2 测试命名

```kotlin
// Kotlin — Given/When/Then
@Test
fun `given empty battery when query status then return low battery warning`()
```

```python
# Python
def test_parse_status_payload_returns_correct_battery_percentage():
```

### 2.3 每个测试只测一件事

```
✅ 好：
  test_emergency_stop_publishes_safety_stop_message()
  test_emergency_stop_when_already_stopped_is_noop()

❌ 差：
  test_emergency_stop_all_scenarios()  ← 测太多，失败时不知道哪步挂了
```

### 2.4 Mock 与 Stub 规则

| 场景 | 做法 |
|------|------|
| ViewModel 测试 | Mock Repository，验证状态变化 |
| Repository 测试 | Mock DataStore / BluetoothService |
| ROS Node 测试 | Mock Publisher/Subscription，验证消息内容 |
| CANopen 驱动测试 | Mock python-can Network，验证发送的命令帧 |
| 蓝牙协议测试 | **不要 Mock**，协议解析是纯函数 |

- Mock 只应用于外部边界（网络、硬件、数据库、文件系统）
- 纯业务逻辑不要 Mock → 直接测

---

## 三、集成测试规范

### 3.1 App 端集成测试

| 测试目标 | 方法 |
|---------|------|
| BluetoothService + BleProtocol | 在真机/模拟器上连接蓝牙串口模块，收发完整帧 |
| Repository + DataStore | 读写真实 DataStore，验证持久化 |
| ViewModel + Repository | 不 Mock Repository，用 Fake 数据源 |

### 3.2 Robot 端集成测试

| 测试目标 | 方法 |
|---------|------|
| Topic 通信链路 | 启动 2 个 Node，验证消息正确收发 |
| CANopen 通信 | 挂真实驱动器（不接电机），SDO 读参数 + PDO 收发 |
| 传感器读取 | 超声波/安全触边 GPIO 信号模拟 |
| Launch 文件 | `ros2 launch` 启动后 `ros2 topic list` 验证所有 Topic 就绪 |

### 3.3 集成测试的运行

```bash
# App 端
./gradlew :app:testDebugUnitTest        # 单元测试
./gradlew :app:connectedAndroidTest     # 集成测试（需设备）

# Robot 端
colcon test --packages-select roboclean_driver roboclean_sensors
colcon test-result --verbose
```

---

## 四、硬件在环测试（HIL）

### 4.1 何时进行

- 电机控制逻辑修改后
- 安全传感器逻辑修改后
- 导航/循栏算法修改后
- 蓝牙通信协议修改后
- 发布前（每次 release 前跑一次完整 HIL）

### 4.2 HIL 测试清单

| 测试项 | 通过标准 |
|--------|---------|
| 急停按钮按下 → 所有电机断电 | 接触器断开，`/safety/stop` 为 True |
| 安全触边触发 → 电机停机 | 软件急停 + 接触器断开 |
| 超声波检测到障碍物 → 减速/停止 | `/cmd_vel` 速度归零 |
| 电池低电量 → 自动回充 | 触发 charging_dock 状态机 |
| App 发送 0x01 → 返回状态帧 | 11 字节 payload 解析正确 |
| App 发送 0x05 → 急停 | 电机停机 |
| 循栏模式：直栏杆 → 平行行驶 | 横向偏差 ≤ 5cm |
| 循栏模式：拐角 → 跟随转弯 | 不撞栏、不丢栏 |
| 自动回充：对接充电桩 | 触点接触，开始充电 |
| 编码器里程计：直行 10m | 累计误差 ≤ 5% |

---

## 五、测试覆盖率要求

| 模块 | 行覆盖率 | 分支覆盖率 |
|------|---------|-----------|
| 协议层（BleProtocol / bt_server 协议部分） | ≥ 90% | ≥ 85% |
| ViewModel / Repository | ≥ 80% | ≥ 70% |
| 安全相关代码（safety_sensor, 急停逻辑） | ≥ 90% | ≥ 85% |
| 导航/控制算法（fence_follower, charging_dock） | ≥ 75% | ≥ 65% |
| 电机驱动（CANopen 命令构造） | ≥ 80% | ≥ 70% |
| UI Composable（纯渲染） | Preview 覆盖即可 | — |

---

## 六、测试先行原则（推荐流程）

```
1. 明确需求 → 写测试用例（只写签名，不实现）
2. 运行测试 → 全部失败（红色）
3. 实现功能 → 测试逐步通过（绿色）
4. 重构优化 → 测试保持绿色
5. Review → 测试即说明书
```

不强求严格 TDD，但写代码前先想清楚"这段代码怎么测"。

---

## 禁止事项

- ❌ 提交未通过的测试（`@Ignore` / `@Disabled` 需注释原因+日期）
- ❌ 测试依赖外部状态（网络、真实硬件）→ 用 Mock/Fake
- ❌ 测试之间有执行顺序依赖（每个测试独立 setUp/tearDown）
- ❌ 用 `Thread.sleep()` / `time.sleep()` 等异步结果 → 用 await / `runTest`
- ❌ 只测 happy path → 必须覆盖边界条件、错误路径
- ❌ 生产代码因为"不好测"而降低质量 → 重构代码让它好测
