# Bee（蜜蜂挂机 RPG / 无尽的进度条）

> 仓库：<https://gitee.com/siwpan/bee> ｜ 许可：MIT（见 [LICENSE](LICENSE)）

一款蜜蜂主题的挂机 RPG（放置进度条）游戏，支持系统托盘与实时音频。

## 语言 / 类型
- Python / tkinter 图形界面挂机游戏（含系统托盘）

## 目录要点
- `main.pyw` —— 窗口入口
- `src/` —— app、config、sim_core、resources 等模块
- `data/`、`docs/`、`tests/`、`godot/`（Godot 相关资源）
- `build_exe.py`、`BeeIdleRPG.spec` —— 打包脚本；`excel_to_json.py`、`gen_new_excels.py` 等数据工具
- `无尽的进度条3.0.exe` —— 已打包可执行文件

## 运行方式与依赖
- 运行：`python main.pyw`
- 依赖（`requirements.txt`）：numpy、scipy（音频合成，必需）；pystray、Pillow、openpyxl、sounddevice（可选）

## 主题包（异界 DLC）
- `SimCore(theme="warcraft")` 切换主题：`src/resources/themes/<id>/` 下的 JSON 优先于默认数据，缺失自动回退
- 已内置 10 个主题：魔兽/暗黑/原神/宝可梦/英雄联盟/最终幻想/战锤40K/中古战锤/塞尔达（来自 pq_multiverse）+ 经典 Progress Quest（来自 progress_quest）
- 重新导入：`python tools/import_pq_themes.py` / `python tools/import_pq_classic.py`
  数据源根目录解析顺序（不写死本机路径）：命令行参数 → 环境变量
  `PQ_MULTIVERSE_SRC` / `PQ_CLASSIC_SRC` → 由本仓位置推导的同级候选 → 报错并点名该设哪个变量
- 详见 `docs/architecture/merge-plan.md`（引擎并入计划，历史文档）

## 测试状态
- py_compile 语法检查通过（全部 .py）
- pytest：`python -m pytest tests`（7 个用例全绿，含黄金基准、IPC 桥接；基准生成器 `tests/test_sim_reference.py`）
- 冒烟测试：`python smoke_test.py [对局数]`（DDA 战斗模拟，词缀/稀有度/Boss 全覆盖）
- 回归脚本：`python test_refactor.py`（DDA 语义）、`python test_tag_system.py`（标签系统）
- 无头引擎 1 小时长时模拟通过（0 阵亡；主题模式/损坏存档容错/死亡螺旋修复均已验证）
- GUI 窗口游戏：未运行（无显示环境，仅无头验证）

## 健壮性
- 存档容错：损坏存档自动备份为 `save.json.corrupt-<ts>` 并新建游戏（字段缺失仅告警）
- DDA 反馈：阵亡上报回血抑制且跨世继承；稀有度按等级门控（Lv<5 仅普通，传说 Lv≥20）

## PQ 致敬特性（v3 借鉴 Progress Quest）
- 戏谑前缀池：107 个物品前缀兼敌人词缀（含「双倍伍基人的」「巫毒公主的」「非酋的」等 PQ 风格梗，同步 Excel 前缀表）
- 精炼叙事：环境氛围每场战斗只播报一次，吸血状态不再逐帧刷屏，战斗日志密度向 PQ 靠拢（黄金基准 145 行 → 17 行）
- 本地名人堂：阵亡自动结算生涯战绩至存档旁 `hall_of_fame.json`（最高等级/击杀/金币/最长存活，跨重开累积并播报新纪录）
