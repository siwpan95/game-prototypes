# Progress Quest Multiverse

一个 Progress Quest 的复刻版，结合多个流行游戏的世界观、角色、装备和怪物，打造一个庞大的多元宇宙自动 RPG 游戏。

## 项目愿景

创建一个零玩家游戏，玩家创建角色后，游戏完全自动进行。结合多个流行游戏的内容，打造一个多元化的游戏体验。

## 核心概念

- **零玩家游戏**：玩家创建角色后，游戏完全自动进行
- **多元宇宙**：结合多个流行游戏的世界观和内容
- **进度可视化**：通过进度条、日志、统计等方式展示角色成长
- **收集与成就**：收集装备、怪物图鉴、成就等

## 目录结构

```
pq_multiverse/
├── main.py      主入口（带主题选择界面）
├── run_pq_ui.py      PQ 架构版 UI 入口
├── src/
│   ├── core/        核心引擎（GameEngine、PQ 架构、主题引擎）
│   ├── data/        中文资源数据
│   ├── themes/      主题系统（theme_loader + JSON 数据）
│   │   └── data/    各主题 JSON 数据（warcraft/diablo/genshin/pokemon/lol/final_fantasy/warhammer_40k/warhammer_fantasy/zelda）
│   └── ui/          Tkinter UI（开始界面 + 两个主窗口）
├── scripts/     修复/分析脚本（fix_*.py / analyze_*.py）
├── tests/       单元测试
├── docs/         设计文档和报告
└── saves/        游戏存档
```

## 快速开始

### 运行主程序（推荐）
```bash
# 显示开始界面，选择主题后进入游戏（默认：主题版引擎）
python main.py

# 使用 PQ 架构版引擎（集成队列系统/Tick引擎/确定随机数）
python main.py --pq

# 跳过开始界面，直接进入指定主题
python main.py --theme warcraft

# PQ 架构版 + 指定主题
python main.py --pq --theme diablo

# 查看可用主题
python main.py --list
```

## 技术架构

### 技术栈
- **编程语言**：Python 3.11+
- **GUI 框架**：Tkinter
- **游戏逻辑**：Python
- **数据存储**：JSON（主题数据）+ pickle（存档）
- **多媒体**：pygame-ce（可选）

### 模块划分
1. **`src/core/`** — 核心引擎
   - `game_engine_v2.py` — 基础游戏引擎（角色/装备/战斗/任务）
   - `themed_engine.py` — 主题化引擎（继承 GameEngine，加载 JSON 主题）
   - `themed_engine_pq.py` — PQ 架构版引擎（集成队列系统/Tick 引擎/确定随机数）
   - `queue_system.py` — 行动队列系统
   - `tick_engine.py` — Tick 驱动游戏循环
   - `deterministic_rng.py` — 确定随机数（可重复对局）
   - `equipment_generator.py` — 装备生成器
   - `monster_task_generator.py` — 怪物/任务生成器

2. **`src/themes/`** — 主题系统
   - `theme_loader.py` — 自动发现并加载 `themes/data/` 下的 JSON 主题
   - `theme_base.py` — 主题数据类定义
   - `data/<主题名>/` — 各主题 JSON 数据（races/classes/equipment/monsters/quests/spells/tasks/meta）

3. **`src/ui/`** — UI
   - `start_screen.py` — 开始界面（主题/角色选择）
   - `tkinter_ui_themed.py` — 主题版主窗口（基于 ThemedGameEngine）
   - `tkinter_ui_pq.py` — PQ 架构版主窗口（基于 PQThemedGameEngine）

4. **`scripts/`** — 开发工具
   - `fix_*.py` — 数据修复脚本
   - `analyze_theme_balance.py` — 主题平衡性分析

5. **`tests/`** — 单元测试

## 已支持主题

| 主题 | 显示名称 | 状态 |
|------|---------|------|
| warcraft | 魔兽世界 | ✅ |
| genshin | 原神 | ✅ |
| diablo | 暗黑破坏神 | ✅ |
| pokemon | 宝可梦 | ✅ |
| lol | 英雄联盟 | ✅ |
| final_fantasy | 最终幻想 | ✅ |
| warhammer_40k | 战锤40K | ✅ |
| warhammer_fantasy | 战锤幻想 | ✅ |
| zelda | 塞尔达传说 | ✅ |

新增主题只需在 `src/themes/data/` 下放入 JSON 文件，无需修改代码。

## 项目状态

### 已完成
- [x] 研究 Progress Quest 核心机制
- [x] 设计多主题架构（theme_loader 自动发现）
- [x] 实现基础游戏引擎（GameEngine V2）
- [x] 实现主题化引擎（ThemedGameEngine）
- [x] 实现 PQ 架构版引擎（PQThemedGameEngine，集成队列/Tick/RNG）
- [x] 实现 Tkinter UI（开始界面 + 主题版 + PQ 版）
- [x] 完成 9 个主题数据（warcraft/diablo/genshin/pokemon/lol/ff/40k/fantasy/zelda）
- [x] 项目目录结构整理（scripts/tests/docs 归档完成）

### 待完成
- [ ] 优化 UI 表现（进度条动画、战斗日志滚动）
- [ ] 实现存档/读档界面
- [ ] 实现主题切换（游戏中切换主题）
- [ ] 打包为可执行文件（PyInstaller）
- [ ] 编写用户手册

## 如何贡献

1. Fork 项目
2. 创建分支
3. 提交代码
4. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

## 联系方式

如有任何问题或建议，请通过以下方式联系：
- 创建 GitHub Issue
- 发送邮件至：[your-email@example.com]

## 致谢

- Progress Quest 原作者 Eric Fredericksen
- 所有为本项目做出贡献的开发者

## 更新日志

### 2026-06-30
- 整理项目目录结构：`src/` 散落文件归档到 `scripts/`、`tests/`、`docs/`
- `themed_engine.py` / `themed_engine_pq.py` 移入 `src/core/`
- `run_pq_ui.py` 移至根目录
- 更新 `main.py` 和 `run_pq_ui.py` 的 import 路径
- 更新 README.md 目录结构说明

### 2026-06-29
- 创建项目
- 完成项目设计文档
- 完成技术架构设计文档
- 完成开发指南文档
- 创建原型代码
- 实现 PQ 架构版引擎（队列系统/Tick 引擎/确定随机数）
- 完成 9 个主题数据
