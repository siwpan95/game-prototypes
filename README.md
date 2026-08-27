# text_adventure

文字冒险解谜游戏（英文 + 中文双版本）。

## 简介
基于 pygame 的文字冒险/解谜游戏，整合多种小谜题（数学、谜语、填字、数独、猜数字、扫雷、数织、2048 等），由引擎驱动谜题生命周期与计分。含英文版 `text_adventure/` 与中文版 `text_adventure_zh/` 两个并行实现。

## 语言 / 类型
- 语言：Python
- 类型：桌面 GUI 游戏（pygame 文字解谜）

## 目录要点
- `text_adventure/`：英文版（`main.py` 入口）
- `text_adventure_zh/`：中文版（`main.py` 入口）
- 各版本内：`engine.py`（引擎）、`ui.py`（pygame 界面）、`events.py`（事件总线）、`domain.py`（状态）、`gameplay_pool/`（谜题库）

## 运行方式与依赖
```
python text_adventure/main.py          # 英文版
python text_adventure_zh/main.py       # 中文版
```
- 依赖：`pygame`（或 `pygame-ce`，当前环境已安装 pygame）。

## 测试状态
- `py_compile` 语法检查：通过（44 个 .py）。
- 运行：GUI 窗口游戏，未实际启动（避免卡住）。
