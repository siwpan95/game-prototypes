# 地牢冒险者 (Dungeon Delver)

> **G:\example + G:\alloy = 一个完整的、可以运行的游戏。**

把 `G:\example` 里 `procgen` 的程序化**世界生成**能力，
与 `G:\alloy` 的**游戏引擎**熔接成一个真正能玩的
**回合制 Roguelike 地牢探险游戏**。

- `procgen` 负责「造世界」：地牢/洞穴几何、怪物名字、宝箱掉落风味。
- `alloy` 负责「跑世界」：地图承载、实体模型、战斗、背包、AI、玩家状态。

## 引擎整合点（alloy 各层都被用到）

| 引擎模块 | 在游戏里的角色 |
| --- | --- |
| `world.map_data.MapData` | 地形字符网格（墙/地/楼梯） |
| `world.item.Item` + `create_weapon/create_armor/create_consumable` | 武器 / 护甲 / 药水 loot |
| `world.game_state.PlayerState` | 玩家 HP 等状态 |
| `systems.simple_combat` (`SimpleCombat`/`MobTemplate`/`MobLibrary`) | 三选一回合制战斗 |
| `systems.inventory.Inventory` | 背包 |
| `ai.decision.GenericStateMachine` | 怪物 idle/chase/attack 状态机 |
| `core.ecs.World`/`Entity`/`Component` | ECS 实体模型（玩家 + 怪物） |

## 自包含 / 零跨项目耦合

按「复制即复用」原则，本游戏把两个库**内联**进项目，
运行时不再依赖 `G:\alloy` 或 `G:\tools\procgen`：

```
G:\game\
├── alloy/     # 内联引擎源码（完整镜像：含 fonts/ 字体、example 脚本、.github CI）
├── procgen/         # 内联 procgen 包（含 cli.py / test_smoke.py / pyproject.toml 等完整外层）
├── entities.py      # ECS 组件 + 物品目录 + 怪物库
├── monster_ai.py    # 基于 GenericStateMachine 的怪物 AI
├── world_gen.py     # procgen 生成 → MapData + ECS 实体
├── game.py          # 游戏主循环 / 战斗 / 背包 / 渲染
├── run.py           # 启动入口
└── README.md
```

## 运行

依赖：Python 3.10+，以及 `numpy` + `Pillow`（procgen 需要）。
（引擎渲染/音频用到 pygame/scipy/asteval，但本控制台游戏不依赖它们。）

```bat
cd G:\game
python run.py                 REM 交互游玩
python run.py --seed 7       REM 换种子
python run.py --floors 8     REM 更多层
python run.py --auto         REM 无头自动演示（自检，无需键盘）
```

## 玩法

- **移动**：`W`/`A`/`S`/`D`（也支持 `H/J/K/L` 或 上/下/左/右）
- **拾取**：`G`　**装备**：`E`　**喝药**：`U`　**背包**：`I`
- **下层**：站在 `>` 楼梯上按 `>`　**帮助**：`?`　**退出**：`Q`
- **战斗**：撞向怪物即进入战斗 —— `1` 攻击 / `2` 防御 / `3` 逃跑 / `4` 特技（强击） / `U` 战中喝药
- **面板**：`C` 查看角色（等级 / 已选强化 / AI Director 实时状态）
- **目标**：向下探索，击败最终 Boss（巨龙），活着通关。

每层地牢由 procgen 程序化生成（房间地牢 / 元胞洞穴 / BSP 地窖 三种生成器轮换），
怪物名也由 procgen 的 `NameGenerator` 随机生成；越深的层怪物越多越强，掉落也越好。
最后一层是 Boss 层。踩中陷阱（⚠️ 尖刺 / 🌋 熔岩）会受伤，熔岩附带灼烧。

> 提示：武器「命中附加」词缀（燃烧/淬毒）与护甲「荆棘」词缀构成构筑核心；
> 升级时从 3 个随机强化（perk）里选 1，把成长变成有代理权的选择。

---

## 增强系统（联网调研驱动的全面升级）

在基础可玩版之上，结合现代 Roguelike 设计实践做了全面增强，分四大支柱。
每项改动都参考了具体来源（见各模块 docstring），且都接在既有引擎之上、不改动引擎类。

### 1. 成长系统 — 经验 / 等级 / 升级三选一（`progression.py`）

- 击败怪物获得经验，越深层经验加成越高（`combat.get_xp_reward` × 层深系数）。
- 升级时从 **3 个随机 perk 里选 1**（zooz《Designing Fair RNG》的「半随机层 /
  choosable luck」：成长应是玩家有代理权的选择，而非固定奖励）。
- 10 种 perk（力量/坚韧/精准/嗜血/再生/幸运/迅捷/专注/守护/强健体魄），
  数值可叠加形成构筑；`compute_perk_mods` 为纯函数，读档时重算不重复触发即时效果。

### 2. 装备稀有度与随机词缀（`affixes.py`）

- 五档稀有度：普通 / 魔法 / 稀有 / 史诗 / 传说（ANSI 配色，控制台可见）。
- 越深的层整体越偏向高稀有度；「幸运」perk / AI Director 幸运加成整体抬一档。
- 按稀有度掷出随机词缀（Roguetemple「tweak the lists」：扰动掉落组合保证可重玩性）：
  武器（锋利/精准/吸血/燃烧/淬毒/沉重）、护甲（坚固/荆棘/恢复/警觉/庇护）。
  词缀挂在 `Item.metadata`，计算有效属性时叠加，不改引擎类。

### 3. AI Director 动态难度（`director.py`）

- 参考《死亡细胞》AI Director（源自 L4D）：根据玩家近期表现「橡皮筋式」调节节奏。
- 玩家吃瘪（承伤/死亡）→ 少刷怪、降伤、减陷阱、多掉好货；碾压 → 反向加压。
- `Director` 为纯数据 + 轻量调节，不持有游戏对象，便于存档与单测。

### 4. 智能与程序化生成

- **程序化多样性**：房间地牢 / 元胞洞穴 / BSP 地窖 三种生成器按层轮换，
  并对房间数、洞穴填充率做参数扰动（Roguetemple「tweak the variables」）。
- **怪物智能**：远程怪（骷髅弓手 / 暗影法师）在视线+射程内发射箭/法术
  （`pathfinding.clear_los` 视线判定，墙后打不到）；群聚警觉（贴脸即全层警觉）；
  Boss 血量过半进入狂暴（伤害 ×1.5，行为树阶段切换）；Boss 首遇渲染 ASCII 立绘。
- **主题楼层 / 灾害**：生物群系（procgen `generate_world`）偏置怪物与陷阱类型，
  火山类地穴出现 🌋 熔岩陷阱（附带灼烧），其余为 ⚠️ 尖刺。
- **战斗深度**：暴击、特技（强击）、战中喝药、怪物中毒/灼烧状态结算、荆棘反弹、
  受击减伤、每回合再生。小地图（2×2 降采样）辅助导航。

### 5. 图形界面联动（`gui.py`，tkinter）

图形界面版在 `Game` 之上包一层，不改动游戏逻辑，现已同步展示全部增强系统：

- **稀有度配色**：地图与背包里的物品按五档稀有度着色（普通灰 → 传说金）。
- **主题陷阱**：🌋 熔岩 / ⚠️ 尖刺 在地图上以 `~` / `^` 区分渲染。
- **远程怪高亮**：远程怪（弓手 / 法师）以紫色标识，提示「会被放风筝」。
- **升级三选一**：有待升级时自动弹出 3 选 1 弹窗，点「选择」即套用 perk。
- **角色面板（C）**：显示等级 / 属性 / 已选 perk / AI Director 状态。
- **Boss 立绘**：首次遭遇 Boss 弹出 ASCII 立绘与名字。
- **小地图**：右侧实时 2×2 降采样已探索区域，辅助导航。
- 战斗面板新增 **特技(4)** 与 **喝药(U)** 按钮，键盘 `4` / `u` 同样可用。

### 存档

- 存档版本升到 v2，持久化：玩家状态、背包（含物品稀有度+词缀）、成长、AI Director、
  怪物特殊能力/状态（远程/Boss 狂暴等）。`--save` 开局即存，`--load` 读档续玩。

### 测试

```bat
cd G:\game
python -m unittest tests.test_enhancements tests.test_gui -v
```

覆盖：成长曲线 / perk 聚合 / 词缀格式化（回归修复）/ Director 橡皮筋与存档往返 /
生成集成（trap_types + 物品词缀 + 远程怪元数据）/ 多种子无头自动演示不崩 /
GUI 冒烟（构建 + 角色面板 + 升级三选一真实点击 + 深层远程怪与陷阱渲染；
无显示环境自动跳过）。

