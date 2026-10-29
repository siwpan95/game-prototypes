# text_fps

文字 FPS 战术战斗游戏（英文 + 中文双版本）。

## 简介
基于 pygame(-ce) 的文字 FPS 战术战斗游戏，含战斗、移动、背包、潜行等系统，玩家/敌人回合制战斗。含英文版 `text_fps/` 与中文版 `text_fps_zh/`（后者另有独立 README、RUNBOOK 与代码评审报告）。

## 语言 / 类型
- 语言：Python
- 类型：桌面 GUI 游戏（pygame 文字 FPS）

## 目录要点
- `text_fps/`：英文版（入口 `main.py`）
- `text_fps_zh/`：中文版（入口 `main.py`，含 `README.md`、`RUNBOOK.md`、`CODE_REVIEW_REPORT.md`）
- 各版本内：`core/`（事件总线、游戏状态、常量）、`systems/`（战斗/移动/背包/潜行）、`models/`、`data/`、`ui/`、`save/`、`tests/`

## 运行方式与依赖
```
python text_fps/main.py          # 英文版
python text_fps_zh/main.py       # 中文版
```
- 依赖：`pygame-ce`（无则回退 `pygame`，当前环境已安装 pygame）。

## 测试状态
- `py_compile` 语法检查：通过（81 个 .py）。
- 运行：GUI 窗口游戏，未实际启动（避免卡住）。
