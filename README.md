# 🚗 智能清洁小车 — 项目总指引

## 项目简介

一款可在室内+室外混合环境下自主行驶的智能清洁小车，配合安卓 App 实现远程设置与管理。

---

## 📁 项目结构

```
robo/
├── README.md                  ← 你在这里（项目总指引）
├── docs/                      ← 📚 项目文档中心
│   ├── development-plan.md    ← 开发阶段与执行步骤
│   ├── requirements.md        ← 产品需求规范
│   ├── tech-spec.md           ← 技术选型与架构规范
│   ├── design-spec.md         ← UI/UX 设计规范
│   ├── hardware-bom.md        ← 硬件采购清单
│   └── driver-c20-800lrc.md   ← 驱动器参考手册
├── devlog/                    ← 📝 开发日志（每日自动记录）
│   └── YYYY-MM-DD.md
└── src/                       ← 💻 源代码
    ├── robot/                 ← 小车端（树莓派 / ROS）
    └── app/                   ← 安卓 App 端
```

---

## 🗺️ 文档导航

| 我想了解… | 去看这个 |
|-----------|----------|
| 整体怎么做，分几步？ | [`docs/development-plan.md`](docs/development-plan.md) |
| 具体要做什么功能？ | [`docs/requirements.md`](docs/requirements.md) |
| 用什么技术栈？ | [`docs/tech-spec.md`](docs/tech-spec.md) |
| UI 长什么样？ | [`docs/design-spec.md`](docs/design-spec.md) |
| 需要买什么硬件？ | [`docs/hardware-bom.md`](docs/hardware-bom.md) *(待生成)* |
| 今天做了什么？ | [`devlog/`](devlog/) |

---

## ⚡ 快速开始

1. **先读** → [`docs/development-plan.md`](docs/development-plan.md) 了解整体节奏
2. **再看** → [`docs/requirements.md`](docs/requirements.md) 明确功能边界
3. **开发时** → 严格遵循 [`docs/tech-spec.md`](docs/tech-spec.md) 和 [`docs/design-spec.md`](docs/design-spec.md)

---

## 🔄 开发规则

- ✅ **一次只做一步**，完成并验证后再进入下一步
- ✅ **每天更新开发日志**，记录完成事项和待办事项
- ✅ **所有决定先记入文档**，再动手写代码
- ✅ **遇到不确定的点**，先停下来讨论，不要盲目推进

---

## 🧠 Skills（AI 开发约束）

| Skill | 适用范围 | 说明 |
|-------|---------|------|
| [`frontend`](.github/skills/frontend/SKILL.md) | `src/app/` | Android App：Kotlin / Compose / BLE 协议 / DataStore |
| [`backend`](.github/skills/backend/SKILL.md) | `src/robot/` | 小车端：ROS 2 Humble / Python / CANopen / 传感器 |
| [`coding-standards`](.github/skills/coding-standards/SKILL.md) | `src/` 全局 | 命名、注释、错误处理、Code Review 清单 |
| [`architecture`](.github/skills/architecture/SKILL.md) | `src/` 全局 | MVVM / ROS 2 Node 分层、模块边界、ADR 决策记录 |
| [`testing`](.github/skills/testing/SKILL.md) | `src/` 全局 | 单元/集成/HIL 测试策略、Mock 规范、覆盖率要求 |
| [`ui-design`](.github/skills/ui-design/SKILL.md) | `src/app/` | Compose 组件复用、交互状态、Preview 规范、设计审查 |
| [`docs`](.github/skills/docs/SKILL.md) | `docs/` `devlog/` | 文档格式、术语表、devlog 模板 |

---

> 📌 最后更新：2026-06-17
