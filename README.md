# Life Reset Simulator

人生重开模拟器：MBTI 风格出身选择 + 王权决策树，采用“本体 + JSON 内容库 + 决策树模块”设计的桌面模拟游戏。

## 语言/类型
Python 3（tkinter），桌面 GUI 游戏，纯标准库。

## 目录要点
- `main.py`：入口（命令行/引导）；`game_gui.py`：tkinter 图形界面
- `core/`：核心逻辑与常量；`content/`：内容与 JSON 数据
- `decision_tree.py`：决策树；`backgrounds.json` / `decision_cards.json` / `events.json` / `profile.json`：内容与存档数据
- `saves/`：存档；`docs/` `tools/`：文档与工具

## 运行方式与依赖
```
python main.py
```
依赖：Python 标准库（tkinter、json、random 等），无需第三方包。GUI 窗口游戏，运行后会阻塞等待交互。

## 测试状态
`py_compile` 语法检查 25 个 `.py` 全部通过；GUI（tkinter）未做自动运行。
