---
name: ui-design
description: "Use when: designing or modifying App UI, creating new Screens/Components, styling, handling interaction states. Applies to src/app/."
---

# UI Design — 界面设计规范

> 约束来源：`docs/design-spec.md` + `docs/tech-spec.md` §3
> 配合：[[frontend]] [[coding-standards]]

## 核心原则

1. **一致性 > 创意**：同一类元素在整个 App 中长得一样、用起来一样
2. **反馈必有**：每个用户操作必须有视觉反馈（加载/成功/失败/禁用）
3. **数据驱动**：UI 是状态的函数 —— `UI = f(State)`
4. **可访问性**：触控区域 ≥ 48dp，颜色对比度达标

---

## 一、设计系统引用

所有 UI 元素必须使用项目设计系统，禁止 ad-hoc 样式。

### 1.1 色彩 — `Color.kt`

```kotlin
// ✅ 正确
color = MaterialTheme.colorScheme.primary
color = Blue500
color = Success

// ❌ 禁止
color = Color(0xFF2196F3)     // 硬编码色值
color = Color.Blue             // 用项目 Blue 系列
```

| 用途 | 色值来源 |
|------|---------|
| 主色 | `Blue500` / `Blue600` |
| 背景 | `Blue50` / `Blue100` / `Surface` |
| 文字 | `onPrimary` / `onSurface` / `onBackground` |
| 功能色 | `Success`（绿）/ `Warning`（黄）/ `Error`（红） |
| 电池指示 | `BatteryRingColors` 预定义梯度 |

### 1.2 字体 — `Theme.kt`

- 使用 `MaterialTheme.typography`，禁止直接设 `fontSize`
- 层级：`headlineLarge → titleLarge → bodyLarge → bodyMedium → labelSmall`
- 中文字符串统一走 `res/values/strings.xml`，禁止硬编码

---

## 二、组件复用规则

### 2.1 已有可复用组件（不可重复定义）

| 组件 | 文件 | 用途 |
|------|------|------|
| `BatteryRing` | DashboardScreen.kt | 电量环形指示器 |
| `InfoCard` | DashboardScreen.kt | 信息卡片（电压/里程/温度） |
| `StatusCard` | DashboardScreen.kt | 工作状态卡片 |
| `DeviceCard` | BluetoothScreen.kt | 设备列表卡片 |
| `WaypointItem` | RouteScreen.kt | 途经点条目 |
| `TimeSlotItem` | ScheduleScreen.kt | 时间段条目 |

### 2.2 何时抽取新组件

满足以下 **≥ 2 项**就应抽取为可复用组件：

- 在 ≥ 2 个 Screen 中出现
- 逻辑独立可单测
- 有独立的状态（加载/空/错误/正常）
- 超过 50 行 Composable 代码

### 2.3 组件命名约定

```kotlin
// Composable 组件：名词，描述"是什么"
@Composable
fun BatteryRing(percent: Int, modifier: Modifier = Modifier)

// 事件回调：on + 动作（过去式或原形）
onClick / onDelete / onToggle / onValueChange

// 组件文件命名
XxxCard.kt   → 信息卡片类
XxxItem.kt   → 列表条目类
XxxSheet.kt  → 底部弹出
XxxDialog.kt → 对话框
```

---

## 三、布局规范

### 3.1 间距系统

| Token | 值 | 用途 |
|-------|-----|------|
| `xs` | 4.dp | 图标与文字间距 |
| `sm` | 8.dp | 同类元素间距 |
| `md` | 16.dp | 组件间标准间距 |
| `lg` | 24.dp | 段落/区块间距 |
| `xl` | 32.dp | 页面级间距 |

```kotlin
// ✅ 使用 MaterialTheme 或统一的 PaddingValues
contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp)

// ❌ 随意的间距
Modifier.padding(7.dp)
```

### 3.2 列表与网格

- 使用 `LazyColumn` / `LazyRow`，禁止 `Column` + `forEach` 渲染大量条目
- 每个列表项必须有 `key` 参数：
  ```kotlin
  LazyColumn {
      items(devices, key = { it.address }) { device ->
          DeviceCard(device)
      }
  }
  ```

### 3.3 触控规范

- 最小触控区域：48dp × 48dp
- 图标按钮用 `IconButton`（自带最小触控区域）
- 列表项点击使用 `clickable` 而非 `combinedClickable`（除非需要长按）
- 重要操作按钮突出（filled），次要按钮弱化（outlined/text）

---

## 四、交互状态规范

每个有数据加载的组件必须覆盖 4 种状态：

```kotlin
sealed class UiState<out T> {
    object Loading : UiState<Nothing>()       // 加载中 → CircularProgressIndicator
    data class Success<T>(val data: T) : UiState<T>()  // 成功 → 数据展示
    data class Error(val message: String) : UiState<Nothing>()  // 失败 → 错误提示 + 重试按钮
    object Empty : UiState<Nothing>()         // 空数据 → 空状态插图 + 引导文案
}
```

### 4.1 加载态

```
- 用 CircularProgressIndicator（主题色）
- 禁止空白页面等加载 → 必须有 loading 指示器
- > 3 秒的加载 → 显示进度文字
```

### 4.2 错误态

```
- 显示用户可理解的错误信息（不是 stack trace）
- 提供"重试"按钮
- 蓝牙连接失败等可恢复错误 → Snackbar
- 致命错误 → 全屏错误 + 返回按钮
```

### 4.3 空态

```
- 首次使用（无数据）→ 插图 + "点击 + 号添加途经点" 等引导
- 搜索无结果 → "未找到匹配的设备" + 搜索建议
```

### 4.4 操作反馈

| 场景 | 反馈方式 |
|------|---------|
| 按钮点击 | 按钮状态变化（enabled → disabled）+ ripple 效果 |
| 异步操作成功 | Snackbar（绿色）+ 自动消失 |
| 异步操作失败 | Snackbar（红色）+ 错误信息 + 操作按钮 |
| 危险操作（急停/删除） | AlertDialog 确认，不可撤销 |
| 后台状态变化 | 页面自动刷新（StateFlow 驱动） |

---

## 五、蓝牙设备 UI 专项

```
设备扫描列表：
  - 已配对设备：显示信号强度、连接按钮
  - 新设备：显示"未配对"标签
  - 扫描中：列表顶部显示脉冲动画指示器

连接状态：
  - 连接中 → 设备卡片显示 CircularProgressIndicator
  - 已连接 → 设备卡片高亮 + 绿色连接指示灯
  - 断连 → Snackbar 提示 + 自动回退到扫描页
```

---

## 六、Preview 规范

```kotlin
@Preview(name = "Default", showBackground = true)
@Preview(name = "Dark Mode", uiMode = UI_NIGHT_MODE, showBackground = true)
@Preview(name = "Large Font", fontScale = 1.5f)

// 每种 UiState 都需要 Preview：
@Preview(name = "Loading")
@Composable
private fun DashboardLoadingPreview()

@Preview(name = "Error")
@Composable
private fun DashboardErrorPreview()

@Preview(name = "Empty")
@Composable
private fun DashboardEmptyPreview()
```

---

## 七、设计审查清单

提交 UI 代码前自查：

| # | 检查项 | ✓ |
|---|--------|---|
| 1 | 颜色全部来自 `Color.kt`，无 `#RRGGBB` | ☐ |
| 2 | 间距使用统一 token（xs/sm/md/lg/xl） | ☐ |
| 3 | 触控区域 ≥ 48dp | ☐ |
| 4 | 4 种状态（Loading/Success/Error/Empty）都有处理 | ☐ |
| 5 | 长文本有截断策略（`maxLines` + `TextOverflow.Ellipsis`） | ☐ |
| 6 | 中文字符串在 `strings.xml` 中 | ☐ |
| 7 | 列表项有 `key` | ☐ |
| 8 | 每个 Screen/组件有 `@Preview` | ☐ |
| 9 | 暗色模式 Preview 正常 | ☐ |
| 10 | 无内联重复的组件（已抽取） | ☐ |

---

## 禁止事项

- ❌ 硬编码色值（`#RRGGBB` / `Color.Red` 等）
- ❌ 硬编码中文字符串
- ❌ `Column` + `forEach` 代替 `LazyColumn`
- ❌ 空白页面等待加载（必须有 loading 指示器）
- ❌ 忽略错误状态（蓝牙断连、数据加载失败）
- ❌ 触控区域 < 48dp
- ❌ 直接使用系统默认字体大小（绕过 Typography token）
- ❌ 重复定义已有可复用组件
- ❌ 引入新依赖实现已有的 UI 能力
