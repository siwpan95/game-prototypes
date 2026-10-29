# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added（R3 · 2026-10-26 接入超级引擎）

- **可选接入超级引擎**（`superengine`）：新增 `dungeon_source` / `rules_kernel` 两条契约能力。
  `--engine super` 时用 worldbuilder 的**真实地牢生成**与**可解关卡图**（房间/走廊/锁钥，
  entrance→boss）替代随机网格；用 an-engine 的**骰系**（d20 / ndM）替代区间随机，
  并新增 **d20 命中检定层**（内置路径恒定命中）。
- `--status` 查看引擎可用性与当前来源；`--seed` / `--size` / `--rooms` / `--fast` 可调。
- 标准库自跑测试 `python -m tests.run_tests`（10 项）。

### Changed（R3 重构）

- 单文件拆为 `dungeon/` 包：`world.py`（世界源）/ `rules.py`（规则源）/ `game.py`（主循环）/
  `ui.py`（表现层）/ `engine.py`（可选依赖探测与降级）。主循环只认接口，换源不改代码。
- **默认路径保持纯标准库**：内置世界源 + 内置规则源，与旧版行为一致，
  因此"无第三方依赖 / 单文件发行"的承诺不被破坏。引擎缺失时自动回退（`--strict` 则明确报错）。

### Fixed（R3 顺带修掉的旧版 latent bug）

- **出生点可能被覆写成出口**：旧版在出口重掷循环里反复 `grid[exit] = EXIT`，
  一旦某次重掷又落回 `(0,0)`，就会把出生点写成出口，并留下**两个出口** ——
  与其自身注释「出生点设为空地，保证安全」相悖。新版按注释意图修正：
  重掷到不撞出生点为止、只落一次出口，出生点恒为空地。
  （200 个种子样本中有 2 个受旧版影响；其余 198 个与旧版**逐格一致**。）

### Changed

- R2 反向重构勘查（2026-08-27）：规则内核接入判定——本作区间随机不含 D&D/GURPS 骰系，alloy.trpg 无同构原语，按「只接同构原语」原则不接入（README 记账）；顺手清理打包产物并重写 .gitignore。
  > **已被 R3 取代**：超级引擎提供同构原语后改为「接入，但做成可选增强」，详见 README §R3。

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：Windows 可执行程序（PyInstaller，Python 3.14）。
- 发布面：gitee [siwpan/random-dungeon-](https://gitee.com/siwpan/random-dungeon-) release `v1.0.0`（随机地牢 v1.0.0）。