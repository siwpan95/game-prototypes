# rider

Line Rider Pro —— 画线骑行物理模拟游戏。

## 简介
基于 Tkinter Canvas 的 Line Rider 类游戏：玩家绘制贝塞尔轨道，小人沿轨道滑行，包含混沌物理、相机跟随、材质、音效合成与粒子/回声特效。

## 语言 / 类型
- 语言：Python（仅标准库 tkinter，无第三方依赖）
- 类型：桌面 GUI 游戏（物理模拟）

## 目录要点
- `main.py`：主入口与 `App` 应用整合
- `rider.py`、`rider_entity.py`：骑手实体与渲染
- `track.py`：轨道与贝塞尔曲线
- `physics.py`：混沌物理与步进
- `camera.py`、`audio.py`、`effects.py`、`config.py`：相机、音效合成、特效、配置

## 运行方式与依赖
```
python main.py
```
- 依赖：Python 标准库（tkinter、math、time、random）。

## 测试状态
- `py_compile` 语法检查：通过（9 个 .py）。
- 运行：GUI 窗口游戏，未实际启动（避免卡住）。
