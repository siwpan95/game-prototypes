# 表格挂机 · Progress Quest v2 风格挂机桌游

> 独立仓 siwpan/table-hanging-machine（本地 G:\repos\table-hanging-machine）。全自动挂机桌游：Excel 配置驱动 + 自动角色成长（tkinter GUI）。

## 玩法

- **全自动角色创建**：无存档时随机生成角色，开局即挂机。
- **PQ 风格内容**：Progress Quest 风格的法术 / 装备 / 特殊宝物，按等级自动生成怪物（无章节限怪）。
- **章节 = 纯进度标记**：挂机推进即进度。
- 存档：`save.json`（自动保存）；配置：`config.xlsx`（Excel 驱动数值与内容）。

## 运行

```bash
python main.pyw
```

依赖：Python 3（tkinter + openpyxl，见 requirements）。

## 结构要点

- `main.pyw`：主入口 + 游戏循环（tkinter GUI）。
- `game_engine.py`：核心挂机引擎（成长/战斗/掉落）。
- `create_cards.py` / `excel_writer.py` / `gen_conf.py` / `progress_tracker.py`：内容生成与 Excel 配置工具链。

## 测试与打包

- 打包：`table-hanging-machine.spec`（PyInstaller，onedir）。
- 发行面：gitee release `v1.0.0`（表格挂机 v1.0.0）。

## 谱系（2026-08-27 统一治理）

- 挂机族谱系：与 Idle / stay / pq-multiverse / bee / Life Reset 同族；本仓为独立留存（本地无副本，勿删）。

## 许可

MIT · Copyright (c) 2026 siwpan
