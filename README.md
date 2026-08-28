# 地狱之下（Hell Below）

一款 tkinter 游戏启动器平台，聚合多个已本地化的小游戏。

## 语言 / 类型
- Python / tkinter 图形界面游戏启动器

## 目录要点
- `launcher/main.py` —— 入口（Tkinter 主窗口，MVC 结构）
- `launcher/src/` —— controllers、views、models、core、utils
- `shared_core/`、`expand_shared/` —— 共享核心与扩展
- 多个 `*_zh` / `*_CN` 子目录 —— 各本地化小游戏
- `_test_*.py` —— 启动、按钮、E2E 等测试脚本

## 运行方式与依赖
- 运行：`F:\Python314\python.exe launcher/main.py`
- 依赖：无（仅标准库 tkinter）

## 测试状态
- py_compile 语法检查通过（73 个 .py）
- GUI 窗口程序，未运行（仅编译）

## 规则内核接入判定（R2 · 2026-08-27）

勘查结论：本作战斗为卡牌驱动（AP/格挡/神经值，无骰系判定），alloy.trpg（D&D 三宝书
+ GURPS Basic Set）无同构原语可接——按「只接同构原语、绝不破坏行为契约」原则
**不接入**（记账声明）。将来若引入 d20/3d6 检定：
`from alloy.trpg import roll_3d6, gurps_success_chance`（接入模式参照
running-group-simulator 的 `core/dice.py`）。

附带修复（同批）：开发探针 `_test_*.py` 硬编码旧桌面路径（Desktop\\stay\\hell below）
已改仓根相对；`_test_all_games.py` 原文件整体 s→y 字符污染且 src/ 导入路径失效，
已重写（Phase 1 文件/语法检查 11/11 通过；Phase 2 启动探针需弹窗，本会话未运行）。