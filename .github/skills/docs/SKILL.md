---
name: docs
description: "Use when: writing or updating documentation, design specs, devlog, README, requirements. Applies to docs/ and devlog/."
---

# Docs — 项目文档

> 约束来源：`docs/design-spec.md` §7.4

## 核心规则

1. **格式**：Markdown，UTF-8 编码
2. **devlog**：每天一个文件 `YYYY-MM-DD.md`，放在 `devlog/`
3. **术语统一**：见下方术语表
4. **禁止**：文档中写死 IP 地址、绝对路径、API Key

## 文档结构

```
docs/
├── requirements.md        # 产品需求规范（功能清单）
├── tech-spec.md           # 技术选型 + 架构 + 协议
├── design-spec.md         # UI 设计规范 + Skills 约束 (§7)
├── hardware-bom.md        # 硬件采购清单
├── driver-c20-800lrc.md   # 电机驱动器参考
└── development-plan.md    # 开发阶段与执行步骤

devlog/
└── YYYY-MM-DD.md          # 每日开发日志
```

## devlog 模板

```markdown
# 📝 开发日志 — YYYY-MM-DD

## ✅ 今日完成
| 事项 | 描述 |
|------|------|

## 🔜 待办事项
| 优先级 | 事项 |
|--------|------|

## ⚠️ 已解决问题
- 

## 📊 阶段状态
- Phase X: ✅ / 🔄 / ⬜
```

## 术语表

| 术语 | 说明 |
|------|------|
| App / App 端 | Android 前端程序 |
| 小车 / robot / 小车端 | 树莓派 + ROS 2 硬件系统 |
| BleProtocol / 蓝牙帧 | App↔小车 通信协议 [0xAA\|len\|cmd\|data\|checksum] |
| CANopen | 电机驱动器通信协议 |
| SQLite / DataStore | Android 本地持久化 |
| SLAM / Nav2 | 同步定位建图 + 导航框架 |

## 禁止事项

- ❌ 写出 IP 地址 → 用 "树莓派 IP" 代替
- ❌ 写出绝对路径 → 用 "项目根目录" 代替
- ❌ 写出 API Key / 密码
- ❌ 术语不一致（如一会儿叫"小车"，一会儿叫"机器人"）
