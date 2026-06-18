---
name: frontend
description: "Use when: working on Android App, Kotlin, Jetpack Compose, Material 3 UI, Bluetooth SPP, DataStore. Applies to src/app/."
---

# Frontend — Android App (Kotlin / Compose)

> 约束来源：`docs/design-spec.md` §7.2 + `docs/tech-spec.md` §3

## 核心规则

1. **只用 Kotlin**，禁止 Java 代码
2. **UI 只能用 Jetpack Compose + Material 3**，禁止 XML layout
3. **配色严格使用 `Color.kt`** 中的预定义色值（Blue 系列 + Success/Warning/Error）
4. **数据持久化用 DataStore Preferences**，禁止 Room
5. **蓝牙帧格式不可改**，必须与 `BleProtocol.kt` 和 `docs/tech-spec.md` §3 严格一致

## 代码结构

```
src/app/app/src/main/java/com/roboclean/app/
├── MainActivity.kt          # 唯一 Activity，setContent { RoboCleanTheme { MainApp() } }
├── ui/
│   ├── theme/Color.kt       # 色彩系统（禁止直接写 #RRGGBB）
│   ├── theme/Theme.kt       # MaterialTheme 配置
│   ├── navigation/Screen.kt # 底部导航 4 个 Tab
│   └── screens/*.kt         # Dashboard / Route / Schedule / Bluetooth
├── bluetooth/
│   ├── BleProtocol.kt       # 帧格式 [0xAA|len|cmd|data|checksum]
│   ├── BluetoothService.kt  # SPP 连接 + 收发
│   └── RobotStatus.kt       # 状态数据类
└── data/
    └── *.kt                 # Repository + DataStore
```

## 组件约束

- 可复用组件（`BatteryRing`、`InfoCard`、`StatusCard`、`DeviceCard`、`WaypointItem`、`TimeSlotItem`）不得内联重写
- 新组件遵循 `docs/design-spec.md` §6 的组件库命名

## 禁止事项

- ❌ 直接写 `#RRGGBB` 色值 → 用 `Color.kt`
- ❌ 修改 `BleProtocol` 帧格式 → 必须先改 `docs/tech-spec.md`
- ❌ 硬编码中文字符串 → 用 `res/values/strings.xml`
- ❌ 引入新依赖 → 需在 `build.gradle.kts` 注释说明原因
