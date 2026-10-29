# 随机地牢 · 终端文字地牢探险

> 仓库：<https://gitee.com/siwpan/random-dungeon-> ｜ 许可：MIT-0（MIT No Attribution）（见 [LICENSE](LICENSE)）
> 注：文中 <PATH> 为路径占位符，请替换为你本机实际的目录 / 可执行文件路径。

> 独立仓 siwpan/random-dungeon-（本地 <PATH>）。纯 Python 标准库实现的终端文字地牢探险游戏。

## 玩法

- 逐房间探索随机生成的地牢：每间房随机为 **空地 / 怪物 / 宝藏 / 陷阱 / 出口**。
- 遇到怪物即战斗（随机骰点），宝藏获得收益，陷阱受伤；找到出口通关。
- 慢速打字机式输出（`slow_print`），经典终端文字冒险质感。

## 运行

```bash
python 随机地牢.py                  # 默认：内置（纯标准库，与旧版一致）
python 随机地牢.py --engine super   # 接超级引擎（真实地牢图 + 骰系规则）
python 随机地牢.py --status         # 看引擎可用性与当前来源
python 随机地牢.py --seed 7 --fast  # 固定种子、关闭打字机延迟
```

依赖：Python 3。**默认路径纯标准库、无第三方依赖**；只有 `--engine super` 才需要
超级引擎（缺则自动回退内置）。

## 测试

```bash
python -m tests.run_tests
```

覆盖：内置路径与旧版逐格一致的回归、旧版 latent bug 的修正、同种子可复现、
规则区间一致、引擎缺失回退、`strict` 报错可行动、脚本化输入完整通关。

## 测试与打包

- 打包：`随机地牢.spec`（PyInstaller，onedir）。
- 发行面：gitee release `v1.0.0`（Windows 可执行程序）。

## 谱系（2026-08-27 统一治理）

- 本仓为体面留存：本地开发副本已归档至 `<PATH>`（勿删）；仓库为唯一活跃留存。

## 许可

MIT · Copyright (c) 2026 siwpan

## 规则内核接入判定（R3 · 2026-10-26，取代 R2 的结论）

**R2（2026-08-27）曾判定不接入**，理由是：本作数值均为「区间随机」（`randint` / `random.choice`），
不含 d20/3d6 骰系，`alloy.trpg` 无同构原语可接，按「只接同构原语、绝不破坏行为契约」原则不接入。

**R3 重新判定：接入，但做成可选增强。** 变化在于——超级引擎（superengine）把三仓能力按契约暴露出来后，
同构原语**已经存在**了：

| 需要的原语 | R2 时 | R3（超级引擎提供） |
|---|---|---|
| 地牢生成 | 无 | worldbuilder `generate_dungeon` + `dungeon_graph`（房间/走廊/锁钥，`dungeon_source` 契约） |
| 骰系 | 无 | an-engine `trpg.dice`（d20 / ndM / 3d6，`rules_kernel` 契约） |

**不破坏发行承诺的方式**：默认路径仍是纯标准库（内置世界源 + 内置规则源），
超级引擎只是**可选增强**（`--engine super`）。引擎缺失时自动回退内置，绝不崩溃。
因此「纯 Python 标准库、无第三方依赖」对普通用户依旧成立。

**行为契约如何守住**：
* 内置路径与旧版**逐格一致**（200 个种子里 198 个逐格相同；另 2 个是旧版自身 bug，见 CHANGELOG）；
* 引擎规则的骰系区间**刻意与内置区间重合**（怪物生命 3~8、怪物伤害 2~5、陷阱/治疗 5~10），
  换规则源不会让难度失衡；
* 引擎侧新增的是 d20 **命中检定层**（内置路径恒定命中）——这是接入规则内核的主要收益，
  也是唯一会改变体感的地方。

## 架构（R3 重构后）

单文件已拆为包，世界与规则都是**可替换源**：

```
随机地牢.py        CLI 入口（--engine / --status / --seed / --size / --rooms / --fast）
dungeon/
  engine.py        超级引擎探测与降级（可选依赖的唯一收口处）
  world.py         世界源：BuiltinWorldSource（网格随机）／ SuperEngineWorldSource（真实地牢图）
  rules.py         规则源：BuiltinRules（区间随机）／ SuperEngineRules（骰系 + d20 检定）
  game.py          主循环（只认三个接口，不知道背后是哪个实现）
  ui.py            表现层（打字机输出 + 输入，可注入替身便于测试）
tests/             标准库自跑的测试
```

**两条路径对比**

| | 内置（默认） | 超级引擎 |
|---|---|---|
| 依赖 | 纯标准库 | cordis + numpy + PyYAML + watchdog + 三仓源码 |
| 地牢 | `size×size` 随机网格，四方向移动 | 真实房间 + 走廊的**可解关卡图**，按连通关系移动 |
| 战斗 | 区间随机，恒定命中 | 骰系伤害 + **d20 命中检定**（会失手） |
| 缺失时 | — | 自动回退内置（`--strict` 则明确报错并给修复指令） |