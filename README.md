# russia

Russian Roulette —— 俄罗斯轮盘赌（ECS 版）。

## 简介
基于 pygame(-ce) 的俄罗斯轮盘赌游戏，采用 ECS 架构，包含 3D6 骰子系统、成就系统、ASCII 艺术角色、中英文国际化（i18n）与多种子弹类型（橡皮弹、燃烧弹等）。

## 语言 / 类型
- 语言：Python
- 类型：桌面 GUI 游戏（pygame）

## 目录要点
- `main.py`：主入口（游戏循环与 pygame 初始化）
- `ecs.py`、`components.py`、`systems.py`：ECS 框架与系统
- `dice.py`、`achievements.py`、`ascii_art.py`、`lang.py`：骰子、成就、ASCII 画、国际化
- `build/`、`dist/`：PyInstaller 打包产物；`*.spec`：打包配置

## 运行方式与依赖
```
python main.py
```
- 依赖：`pygame`（或 `pygame-ce`，当前环境已安装 pygame）。

## 测试状态
- `py_compile` 语法检查：通过（8 个 .py）。
- 运行：GUI 窗口游戏，未实际启动（避免卡住）。
