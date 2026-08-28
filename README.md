# 随机地牢 · 终端文字地牢探险

> 独立仓 siwpan/random-dungeon-（本地 G:\repos\random-dungeon-）。纯 Python 标准库实现的终端文字地牢探险游戏。

## 玩法

- 逐房间探索随机生成的地牢：每间房随机为 **空地 / 怪物 / 宝藏 / 陷阱 / 出口**。
- 遇到怪物即战斗（随机骰点），宝藏获得收益，陷阱受伤；找到出口通关。
- 慢速打字机式输出（`slow_print`），经典终端文字冒险质感。

## 运行

```bash
python 随机地牢.py
```

依赖：Python 3（纯标准库，无第三方依赖）。

## 测试与打包

- 打包：`随机地牢.spec`（PyInstaller，onedir）。
- 发行面：gitee release `v1.0.0`（Windows 可执行程序）。

## 谱系（2026-08-27 统一治理）

- 本仓为体面留存：本地开发副本已归档至 `G:\archive\trash\随机地牢`（勿删）；仓库为唯一活跃留存。

## 许可

MIT · Copyright (c) 2026 siwpan

## 规则内核接入判定（R2 · 2026-08-27）

勘查结论：本作数值均为玩法区间随机（`randint` 范围 / `random.choice`），不含
D&D/GURPS 骰系（d20/3d6/难度表）；alloy.trpg（D&D 三宝书 + GURPS Basic Set）无同构
原语可接。按「只接同构原语、绝不破坏行为契约」原则**不接入**（记账声明）。
将来若引入检定/属性规则：`from alloy.trpg import roll_3d6, gurps_success_chance`
（接入模式参照 running-group-simulator 的 `core/dice.py`）。