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
