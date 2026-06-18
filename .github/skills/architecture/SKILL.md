---
name: architecture
description: "Use when: designing new modules, defining interfaces between App/Robot, making architectural decisions, adding new subsystems. Applies to src/."
---

# Architecture — 架构设计规范

> 约束来源：`docs/tech-spec.md` §2 + `docs/design-spec.md` §7
> 配合：[[coding-standards]] [[frontend]] [[backend]]

## 核心原则

1. **单一职责**：每个模块只有一个理由去修改它
2. **依赖倒置**：高层不依赖低层，两者都依赖抽象（接口/协议）
3. **开闭原则**：对扩展开放，对修改闭合
4. **边界清晰**：模块间的通信协议是"宪法"，不能单方面修改
5. **先文档后代码**：架构变更先更新 `docs/tech-spec.md`，再写代码

---

## 一、系统分层

```
┌─────────────────────────────────────────┐
│  App 层 (Android)                        │
│  Screen → ViewModel → Repository → ...  │
├─────────────────────────────────────────┤
│  通信层 (Bluetooth SPP)                  │
│  BleProtocol ← 两端必须一致 → bt_server  │
├─────────────────────────────────────────┤
│  Robot 层 (ROS 2 Humble)                 │
│  bt_server / navigator / driver / sensor │
├─────────────────────────────────────────┤
│  硬件抽象层 (HAL)                        │
│  CANopen Driver / GPIO / LiDAR           │
└─────────────────────────────────────────┘
```

**关键规则**：
- 上层不能跳过中间层直接访问底层（App 不能直接发 CANopen 指令）
- 跨层的通信协议改变 → 先改文档，两端同步实施

---

## 二、App 端架构（MVVM）

### 2.1 分层职责

| 层 | 职责 | 不负责 |
|----|------|--------|
| **Screen (View)** | 渲染 UI，响应用户交互，把事件转给 ViewModel | 业务逻辑、数据转换、直接调用 BluetoothService |
| **ViewModel** | 持有 UI 状态（StateFlow），处理业务逻辑，调用 Repository | UI 细节、Context、蓝牙连接细节 |
| **Repository** | 数据存取（DataStore / 蓝牙），协调数据源 | UI、生命周期 |
| **Service** | 蓝牙 SPP 连接管理、帧收发 | 数据解析、业务逻辑 |

### 2.2 依赖方向

```
Screen ──depends on──▶ ViewModel ──depends on──▶ Repository ──depends on──▶ Service
                                                                         ▶ DataStore
```

- **Screen 不知道 Repository/Service 存在**
- **ViewModel 不知道 Context/Activity 存在**
- **Repository 封装 DataStore + BluetoothService 的调用细节**

### 2.3 ViewModel 契约

每个 Screen 对应一个 ViewModel：

```kotlin
class XxxViewModel(
    private val repository: XxxRepository  // 构造注入
) : ViewModel() {

    // 用 StateFlow 暴露 UI 状态（不是 LiveData）
    val uiState: StateFlow<XxxUiState>

    // 公开方法：用户动作的入口
    fun onAction(action: XxxAction)
}
```

- UiState 是 data class，包含页面所需的所有数据
- Action 是 sealed class/interface，枚举所有用户操作
- ViewModel 内部用 `viewModelScope.launch` 执行异步

### 2.4 导航与状态共享

- **Single Activity**：`MainActivity` 是唯一 Activity
- **NavHost** 管理 4 个 Tab 页面切换
- **共享数据**通过 Activity 级 ViewModel 或 `CompositionLocal` 传递（蓝牙连接状态、机器人状态）
- 页面间不要通过 bundle 传复杂对象 → 用共享 ViewModel

---

## 三、Robot 端架构（ROS 2 Node）

### 3.1 节点图

```
                    ┌──────────────┐
                    │  bt_server   │  ← 蓝牙通信
                    └──────┬───────┘
                           │ /cmd_xxx , /route/waypoints
              ┌────────────┼────────────┐
              ▼            ▼            ▼
    ┌─────────────┐ ┌───────────┐ ┌───────────┐
    │  charging_  │ │ waypoint_ │ │  fence_   │
    │    dock     │ │ navigator │ │ follower  │
    └──────┬──────┘ └─────┬─────┘ └─────┬─────┘
           │              │             │
           └──────────────┼─────────────┘
                          │ /cmd_vel
                   ┌──────┴──────┐
                   │   motor_    │  ← CANopen 电机控制
                   │ controller  │
                   └──────┬──────┘
                          │ CAN Bus
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

### 3.2 Topic 设计规则

| 规则 | 说明 |
|------|------|
| **单向数据流** | 指令 Topic（/cmd_xxx）与状态 Topic（/xxx/status）分开 |
| **命名空间** | 按功能模块分组：`/motor/` `/safety/` `/nav/` `/route/` |
| **一个发布者** | 每个 Topic 只有一个节点发布，多节点订阅 |
| **QoS 匹配** | 传感器数据用 `SENSOR_DATA`，指令用 `SYSTEM_DEFAULT` |

### 3.3 节点职责边界

```
motor_controller  → 接收 /cmd_vel，翻译为 CANopen 指令，发布 /motor/status
encoder_odom      → 读取编码器，发布 /odom + TF + /total_distance
safety_sensor     → 监控 GPIO（触边/急停/超声波），发布 /safety/stop
fence_follower    → 订阅 /scan + /ultrasonic/fence，发布 /cmd_vel（循栏）
waypoint_navigator→ 订阅 /route/waypoints，调用 Nav2，发布 /cmd_vel
charging_dock     → 订阅 /battery/voltage，调用 Nav2 + 对接逻辑
bt_server         → 蓝牙收发，协议解析，发布/订阅各路 Topic
```

### 3.4 Launch 文件规范

- 所有节点通过 launch 文件启动，禁止 `ros2 run` 手动启
- `bringup.launch.py` 是总入口，包含所有子节点
- 复杂启动拆分为子 launch 文件，`bringup` 用 `IncludeLaunchDescription` 组合

---

## 四、通信边界

### 4.1 App ↔ Robot 蓝牙协议

```
协议定义源：
  App 端：BleProtocol.kt（帧格式、指令码、解析逻辑）
  Robot 端：bt_server.py（帧格式、指令码、解析逻辑）

修改流程：
  1. 在 docs/tech-spec.md §3 更新协议定义
  2. 两端同步修改 BleProtocol.kt 和 bt_server.py
  3. 两端独立单元测试验证
  4. 集成测试确认互通
```

### 4.2 Robot 内部 Topic 接口

- 新增 Topic 必须先定义消息类型、发布者、订阅者、QoS
- 修改已有 Topic 的数据结构 → 检查所有订阅者是否兼容

---

## 五、架构决策记录（ADR）

重大架构决策必须记录在对应模块的注释中。格式：

```
ADR: <标题>
日期: YYYY-MM-DD
背景: <为什么需要做这个决策>
决策: <选择了什么>
替代方案: <考虑过但没选的方案及其理由>
影响: <哪些模块受影响>
```

常见决策场景：
- 新增依赖（为什么选这个库而不是别的）
- 协议变更（为什么加新指令而不是复用旧指令）
- 模块拆分/合并（为什么两个 Node 要合并/分拆）

---

## 六、新增模块的检查清单

开发新模块前，确认：

| # | 检查项 | ✓ |
|---|--------|---|
| 1 | 模块职责一句话能说清楚 | ☐ |
| 2 | 与其他模块的边界（Topic/接口）已定义 | ☐ |
| 3 | 依赖方向符合分层架构 | ☐ |
| 4 | 通信协议（蓝牙帧/Topic 消息）已文档化 | ☐ |
| 5 | 不重复实现已有模块的功能 | ☐ |
| 6 | 测试策略已考虑（怎么单测、怎么集成测） | ☐ |
| 7 | docs/tech-spec.md 相关章节已更新 | ☐ |

---

## 禁止事项

- ❌ 跨层直接访问（App Screen 直接调 BluetoothService）
- ❌ 单方面修改蓝牙帧协议
- ❌ 循环依赖（模块 A 依赖 B，B 也依赖 A）
- ❌ God Node：一个 ROS Node 做超过 3 件不相关的事
- ❌ 跳过文档直接写架构代码
- ❌ 追加功能时破坏已有接口契约
