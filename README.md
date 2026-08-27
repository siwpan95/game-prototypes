# Carimara

一款基于 pygame-ce 的卡牌游戏，含程序化音频合成工具。

## 语言 / 类型
- Python / pygame 图形界面卡牌游戏

## 目录要点
- `main.py` —— 入口
- `components/`、`core/`、`systems/` —— 游戏逻辑与 ECS 组件
- `assets/`、`data/`、`mods/`、`tools/`、`tests/` —— 资源、数据、模组与测试
- `faatt.py` —— 程序化音频（WAV）合成工具

## 运行方式与依赖
- 运行：`F:\Python314\python.exe main.py`
- 依赖（`requirements.txt`）：pygame-ce>=2.5.0；numpy、scipy（音频）；pytest（测试）

## 测试状态
- 核心 40 个 .py py_compile 通过
- `tests/_backup/test_card_system.py` 第 34 行缺右括号存在语法错误（备份文件，不影响运行）
- GUI 窗口游戏，未运行（仅编译）
