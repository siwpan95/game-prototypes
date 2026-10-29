# sixone

六一零食大闯关 · 无尽模式。

## 简介
基于 Tkinter + ECS 架构的贪吃蛇式游戏：自由移动收集零食、蛇身增长、躲避追逐幽灵，含力量糖果、分数与重生机制；内置音频合成管理器。

## 语言 / 类型
- 语言：Python（tkinter GUI，ECS 架构）
- 类型：桌面 GUI 游戏（贪吃蛇 / 追逐）

## 目录要点
- `main.py`：主入口（`Game` 类，Tkinter 主循环）
- `ecs.py`、`components.py`、`systems.py`、`entities.py`：ECS 框架与游戏逻辑
- `data_loader.py`、`snacks.xlsx`：零食数据加载与表格
- `audio_manager.py`、`faatt.py`：音频合成（运行时生成音效）
- `1.txt`、`2.txt`：说明/数据文本

## 运行方式与依赖
```
python main.py
```
- 依赖：Python 标准库（tkinter）；音频可选 `numpy` / `sounddevice` / `scipy`（缺失时静默降级为无声）。

## 测试状态
- `py_compile` 语法检查：通过（9 个 .py）。
- 运行：GUI 窗口游戏，未实际启动（避免卡住）。
