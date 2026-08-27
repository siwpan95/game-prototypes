# Endless Highway

一款基于 ECS 架构的无尽高速公路驾驶游戏，含漂移玩法与电子风音频。

## 语言 / 类型
- Python / pygame 图形界面驾驶游戏（ECS 架构）

## 目录要点
- `main.py` —— 入口（创建 World、生成实体、运行游戏循环）
- `ecs/` —— 组件与系统（输入、漂移、碰撞、渲染、HUD、装饰物）
- `audio/` —— 音频系统与音频管理器
- `faatt.py` —— 程序化音频合成
- `config.json` —— 窗口、道路、玩家、漂移等配置

## 运行方式与依赖
- 运行：`F:\Python314\python.exe main.py`
- 依赖：pygame（项目未提供 requirements.txt）；音频合成可能需 numpy/scipy

## 测试状态
- py_compile 语法检查通过（11 个 .py）
- GUI 窗口游戏，未运行（仅编译）
