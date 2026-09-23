# 六一快乐 · 六一零食大闯关（无尽模式）

> 仓库：<https://gitee.com/siwpan/happy-childrens-day> ｜ 许可：MIT-0（MIT No Attribution）（见 [LICENSE](LICENSE)）

> 独立仓 siwpan/happy-childrens-day（一仓一目录）。六一礼物：零食收集闯关小游戏（tkinter + 自研 ECS）。
> 发布面：gitee release `v1.0.0`（Windows 可执行程序，PyInstaller）。

## 玩法

- **自由移动 → 收集零食 → 蛇身增长 → 躲避幽灵 → 不死不休**（无尽模式）。
- 贪吃蛇式身体成长 + 吃豆人式追逐敌人：收集场上的零食让身体变长，同时躲避游荡的幽灵。
- 操作：方向键 / WASD 移动，空格键重开。

## 架构

- `ecs.py` / `components.py` / `entities.py` / `systems.py`：自研 ECS（实体组件系统）。
- `main.py`：tkinter 图形界面入口（游戏主循环）。
- `data_loader.py` + `snacks.xlsx`：零食数据（数据驱动，Excel 加载）。
- `audio_manager.py`：音效管理。
- `_verify_maze.py`：迷宫/地图自检脚本。

## 运行

```bash
python main.py
```

依赖：标准库 tkinter（Windows 官方 Python 自带）。

## 测试与打包

- `python _verify_maze.py`：地图生成自检。
- 打包：`happy-childrens-day.spec`（PyInstaller，onedir）；调试版 `happy-childrens-day-dbg.spec`。

## 许可

MIT · Copyright (c) 2026 siwpan
