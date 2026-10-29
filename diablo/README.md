# Diablo: Cataclysm Era

> 仓库：<https://gitee.com/siwpan/diablo> ｜ 许可：MIT-0（MIT No Attribution）（见 [LICENSE](LICENSE)）

一款暗黑破坏神风格的图形界面 RPG 游戏。

## 语言 / 类型
- Python / tkinter 图形界面 RPG

## 目录要点
- `main.py` —— 入口（启动 `GameGUI`）
- `gui.py` —— 主界面（Graphical UI）
- `models.py`、`data.py`、`storage.py` —— 数据模型、预设数据与存档
- `game_fsm.py`、`statemachine/` —— 状态机逻辑
- `i18n.py`、`autoplay.py`、`idle_brain.py` —— 国际化、自动挂机与闲置 AI
- `test_game_fsm.py` —— 状态机测试

## 运行方式与依赖
- 运行：`python main.py`
- 依赖：无（标准库 tkinter）

## 测试状态
- py_compile 语法检查通过（14 个 .py）
- GUI 窗口游戏，未运行（仅编译）
