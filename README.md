# kard

> 仓库：<https://gitee.com/siwpan/kard> ｜ 许可：MIT-0（MIT No Attribution）（见 [LICENSE](LICENSE)）

KARD：一款类《吸血鬼幸存者》+《杀戮尖塔》关键字玩法的无尽模式卡牌动作游戏（英文版）。

## 语言/类型
Python 3（pygame-ce），ECS 架构，鼠标驱动的桌面 GUI 游戏。

## 目录要点
- `main.py`：入口（GUI 游戏循环）
- `ecs.py` / `components.py`：实体组件系统与组件定义
- `card_factory.py` / `enemy_factory.py`：卡牌与敌人工厂
- `game_state.py` / `constants.py` / `excel_loader.py`：游戏状态、常量与 Excel 数据加载
- `config/` `data/` `systems/`：配置、数据与各功能系统
- `venv/`：本地虚拟环境；`requirements.txt`：依赖清单

## 运行方式与依赖
```
python main.py
```
依赖：`pygame-ce>=2.3.0`、`openpyxl>=3.1.0`（见 `requirements.txt`）。GUI 窗口游戏，运行后会阻塞等待交互。

## 测试状态
`py_compile` 语法检查 13 个 `.py` 全部通过；GUI（pygame）未做自动运行。
