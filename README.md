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
