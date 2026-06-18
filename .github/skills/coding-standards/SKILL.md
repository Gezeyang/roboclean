---
name: coding-standards
description: "Use when: writing any code (Kotlin/Python), reviewing PRs, refactoring, setting up lint/format tools. Applies to src/."
---

# Coding Standards — 代码书写规范

> 约束来源：`docs/tech-spec.md` §6 + `docs/design-spec.md` §7
> 配合：[[frontend]] [[backend]] [[architecture]]

## 核心规则

1. **可读性优先**：代码首先是给人读的，机器执行只是副产品
2. **一致性**：整个项目内同一种写法只用一种方式
3. **最小化**：函数/类/文件尽量短小，单一职责
4. **显式优于隐式**：类型声明、参数命名、错误处理都要显式

---

## 一、通用规范（前后端通用）

### 1.1 命名

| 元素 | Kotlin (App) | Python (Robot) |
|------|-------------|----------------|
| 类/接口 | `UpperCamelCase` | `UpperCamelCase` |
| 函数/方法 | `lowerCamelCase` | `snake_case` |
| 变量/参数 | `lowerCamelCase` | `snake_case` |
| 常量 | `UPPER_SNAKE_CASE` | `UPPER_SNAKE_CASE` |
| 文件 | `UpperCamelCase.kt` | `snake_case.py` |
| ROS Topic | — | `snake_case`，如 `/motor/cmd_vel` |
| ROS Node | — | `snake_case`，如 `motor_controller` |

### 1.2 函数/方法

- **单一职责**：一个函数只做一件事，名字能完整描述其行为
- **参数数量**：≤ 4 个。超过时考虑封装为数据类/dataclass
- **函数长度**：尽量 ≤ 40 行（不含注释和空行）。超过时分拆
- **纯函数优先**：无副作用、相同输入总是相同输出的函数最易测试

### 1.3 注释

- **公共 API 必须有文档注释**（KDoc / docstring）
- **"为什么" 优于 "是什么"**：代码本身说明"做什么"，注释解释"为什么这样做"
- **TODO/FIXME/HACK** 必须附带日期和责任人：
  ```kotlin
  // TODO(2026-06-18): 接入真实地图组件后移除占位
  ```
  ```python
  # FIXME(2026-06-18): register 0x2104 未在驱动手册中确认
  ```
- **禁止**：注释掉的代码块直接提交 → 删除，Git 历史可以找回

### 1.4 错误处理

- **不要吞异常**：每个 catch 块必须有日志输出或向上抛
- **错误信息要有上下文**：不只是 "failed"，要说 "failed to connect motor driver on CAN bus, node_id=1"
- **App 端**：用户可见的错误用 `Snackbar` / `Toast`，技术细节记 logcat
- **Robot 端**：用 `self.get_logger().error()` 而非 `print()`

### 1.5 文件组织

```
每个模块文件从上到下的顺序：
1. 包声明 / import
2. 模块级常量
3. 类型定义（data class / dataclass / enum）
4. 接口/抽象类（如有）
5. 主要实现类
6. 私有辅助类型/函数
```

---

## 二、Kotlin 专项规范（App 端）

### 2.1 Compose

- **Composable 函数**用 `UpperCamelCase`，返回 `Unit`
- **每个 Composable 必须有一个 `Modifier` 参数**（默认值 `Modifier`），方便调用方控制布局
- **Stateless**：Composable 只管渲染，状态通过参数传入、回调传出
- **Preview**：每个 Screen 和可复用组件必须有 `@Preview`（至少一个）

### 2.2 状态管理

- **单一数据源**：每个页面一个 ViewModel，通过 `StateFlow` 暴露状态
- **禁止在 Composable 中直接调用 suspend 函数** → 走 `LaunchedEffect` 或 `rememberCoroutineScope`
- **禁止**：`mutableStateOf` 用于跨 Composable 共享状态 → 用 ViewModel

### 2.3 DataStore

- 每个 Repository 注入 `DataStore<Preferences>`
- Key 定义在 Repository 文件顶部，命名：`KEY_<PURPOSE>`
- 读写操作必须有 `try-catch`，失败时返回默认值而非崩溃

---

## 三、Python 专项规范（Robot 端）

### 3.1 ROS 2 Node

- 每个 Node 类继承 `rclpy.node.Node`，`__init__` 末尾调用 `super().__init__('node_name')`
- Publisher/Subscriber/Service/Timer 全部在 `__init__` 中创建
- **禁止**在回调中做重计算 → 仅更新内部状态，重计算放 `timer_callback`

### 3.2 类型注解

- 所有公开方法必须有类型注解：
  ```python
  def set_speed(self, rpm: int, direction: str = 'forward') -> bool:
  ```
- 用 `from __future__ import annotations`（Python 3.10+）

### 3.3 参数管理

- 所有可调参数从 YAML 配置文件加载，不得硬编码
- Node 内通过 `self.declare_parameter()` 声明，`self.get_parameter()` 读取
- 修改参数 → 先改 `config/` 下的 YAML，再改代码中默认值

### 3.4 CANopen

- 所有寄存器地址定义为模块级常量，如 `REG_CONTROL_CMD = 0x2000`
- SDO 读写操作封装为独立方法，附带超时和重试
- PDO 映射在代码中显式注释其 COB-ID 对应关系

---

## 四、Code Review 清单

提交代码前自查：

| # | 检查项 | ✓ |
|---|--------|---|
| 1 | 无 `print()` / `Log.d()` 调试残留 | ☐ |
| 2 | 无注释掉的死代码 | ☐ |
| 3 | 所有 TODO/FIXME 有日期和责任人 | ☐ |
| 4 | 硬编码值已提取为常量或配置 | ☐ |
| 5 | 异常被正确处理（有日志，非空 catch） | ☐ |
| 6 | 命名符合本规范名称表 | ☐ |
| 7 | 函数 ≤ 40 行，参数 ≤ 4 个 | ☐ |
| 8 | 公共 API 有文档注释 | ☐ |
| 9 | 没有引入未声明的依赖 | ☐ |
| 10 | 两端蓝牙协议帧格式一致 | ☐ |

---

## 五、常见反模式

| 反模式 | 错误示例 | 正确做法 |
|--------|---------|---------|
| **上帝类** | 单个 Node/ViewModel 处理所有逻辑 | 按职责拆分为多个 Node/ViewModel |
| **魔法数字** | `if battery < 20:` | `if battery < LOW_BATTERY_THRESHOLD:` |
| **空 catch** | `catch (e: Exception) {}` | 至少 `Log.w(TAG, "msg", e)` |
| **回调地狱** | 3 层嵌套 `LaunchedEffect` | 提取到 ViewModel 的 suspend 方法 |
| **固件耦合** | App 直接依赖驱动器寄存器地址 | 通过蓝牙协议抽象，车端转换 |
| **假数据残留** | 提交包含硬编码的假设备列表 | 假数据仅用于 Preview，生产代码走 Service |

---

## 禁止事项

- ❌ 绕过 lint/formatter 提交代码
- ❌ 复制粘贴超过 3 行的代码块（提取为函数/方法）
- ❌ 魔法数字（-1 除外）
- ❌ 空 catch 块
- ❌ 注释掉的代码保留在提交中
- ❌ `print()` / `println()` 用于生产日志
- ❌ 硬编码配置值（阈值、超时时间、IP、端口）
