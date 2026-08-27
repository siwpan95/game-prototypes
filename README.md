# 诡秘之主 · 序列途径模拟系统

> 基于小说《诡秘之主》世界观的「序列魔药体系」模拟器 —— 数据驱动、含 CLI 演示与 tkinter 图形界面。
>
> 版本：v2.1（Canvas Edition · GUI 图形界面）｜ **P0–P2 增强路线图（E1–E11）已全部落地**

一个纯 Python（仅标准库）的模拟器，完整实现了小说中「亵渎石板」记载的 **22 条神之途径**、序列 9 → 序列 0 的晋升机制，以及扮演法、人性之锚、精神污染、唯一性、晋升仪式、途径切换、性别转换等核心设定；并在此之上叠加了材料收集、连续 SAN、事件、存档、阵营社交、AI 对手、成就图鉴、沉浸包装等增强模块。

---

## ✨ 功能特性

### 核心体系（原始规则引擎）
- **22 条神之途径**：黑暗、暴君、愚者、错误、门、母亲、月亮、红祭司、混沌魔女……全部内置数据。
- **10 级序列体系**：序列 9（最低）→ 序列 0（真神），数据驱动的序列定义。
- **扮演法（Acting Method）**：按序列名称进行扮演、累积「消化度」，消化完成方可晋升。
- **人性之锚（Anchor）**：人性值 + 羁绊 + 信徒/传说传承，对抗失控的最后防线；不同序列等级有最低锚强度要求。
- **精神污染 / SAN（Pollution）**：清醒 → 低语 → 幻觉 → 失控 → 神殒 五级模型（连续值），含污染来源追踪与净化。
- **魔药与仪式（Potion / Ritual）**：序列 5 起晋升需要仪式；`Potion` 类封装主材料与辅助材料。
- **途径切换（Pathway Switch）**：同一「权柄体系（途径组）」内、达到互换等级后可同级切换（如诡秘之主组：愚者 ⇄ 错误 ⇄ 门）。
- **性别转换**：部分途径在晋升到特定序列时强制变性（红祭司、混沌魔女、母亲、月亮等）。
- **唯一性（Uniqueness）**：每条途径仅一个序列 0 唯一性，序列 1 非凡特性仅三份，含线程安全的全局注册表。
- **旧日 / 四支柱**：途径组聚合为旧日位格，含支柱级旧日的晋升条件计算。
- **GUI 图形界面**：基于 `tkinter.Canvas` 自绘的深色神秘学主题（暗金 + 紫罗兰），内嵌 Noto Sans SC 字体，无需系统字体依赖；含 10 个视图（角色 / 途径 / 途径组 / 行动 / 日志 / 酿造 / 事件 / 阵营 / 对手 / 图鉴）。
- **CLI 演示**：**10 种**内置演示模式 + `all` 总览，开箱即用。

### 增强模块（P0 / P1 / P2 — 详细设计见 `docs/ENHANCEMENT_RESEARCH.md`）
- **E1 魔药材料收集**：每条途径配方 + `Inventory` 库存，晋升前校验材料（`brewing_panel`）。
- **E2 连续 SAN 理智**：污染改为连续值（0–100），阈值严格映射五级。
- **E3 数据驱动事件**：`data/events.json` 主题事件 + 选择结算，与材料 / SAN / 锚 / 阵营联动。
- **E4 存档 / 读档**：`GameSession` 多字段序列化 + 多槽位。
- **E5 扮演质量维度**：主动 / 被动 / 背离 影响消化加权。
- **E6 能力效果化**：能力在事件 / 扮演中产生 SAN 安抚 / 额外材料 / 隐秘线索。
- **E7 阵营 / 塔罗会社交**：声望 + 社交动作（交换 / 净化 / 锚）。
- **E8 AI 对手非凡者**：`RivalSystem` 多对手在其它途径推进、争夺唯一性 / 序列 1 槽位（复用全局 owner 模型）。
- **E9 成就 / 图鉴 / 多结局**：10 项成就 + 序列 / 能力图鉴进度 + 因路线而异的 5 种结局。
- **E10 主题沉浸包装**：序列考据 tooltip、灰雾之上·源堡叙事、可选环境音效。
- **E11 CLI↔GUI 共享核心**：`GameSession` 统一引擎；`journey` demo 演示完整养成循环 + 存读档往返。

---

## 📁 目录结构

```
G:\project_root\
├── README.md                  # 本文件
├── requirements.txt           # 依赖说明（纯标准库，无第三方包）
├── run_gui.bat                # Windows 一键启动 GUI（UTF-8 编码）
├── main.py                    # CLI 入口：10 种演示模式 + world 概览
├── gui_app.py                 # 薄启动器：from gui.app import LordOfMysteriesGUI; .run()
│
├── sequences.py               # 序列核心：BaseSequence / Sequence / make_sequence
├── ascension.py               # 晋升系统：Potion / ascend / switch_pathway / AscensionManager
├── anchor.py                  # 人性之锚系统：强度计算、羁绊、信徒、传承
├── pollution.py               # 污染系统：PollutionLevel / 异常 / PollutionManager（连续 SAN）
├── uniqueness.py              # 唯一性与序列 1 非凡特性（线程安全全局注册表）
├── pathway_groups.py          # 途径组、旧日等级、互换验证、序列等级描述、封印物等级
├── pathways_data.py           # 22 条途径的完整数据（序列、能力、仪式、性别转换）
├── role_playing.py            # 扮演循环模拟、仪式校验、单途径/切换演示
│
├── inventory.py               # 材料库存（E1）
├── events.py                  # 数据驱动事件（E3）
├── factions.py                # 阵营 / 塔罗会声望与社交动作（E7）
├── abilities.py               # 能力效果化（E6）
├── rivals.py                  # AI 对手（E8）
├── achievements.py            # 成就 / 图鉴 / 结局（E9）
├── lore.py                    # 序列考据 / 沉浸文案（E10）
├── save_load.py               # GameSession 存档/读档与序列化（E4 / E11）
│
├── gui/                       # tkinter Canvas GUI 包
│   ├── app.py                 # LordOfMysteriesGUI 主类 + 入口
│   ├── controllers.py         # 控制器（动作处理 + 各面板回调）
│   ├── state.py               # GUIState（含 achievements / codex / rival_system 等）
│   ├── theme.py / drawing.py / helpers.py
│   └── panels/                # 10 个自由函数面板 draw_*(canvas, state, callbacks)
│       ├── character_view / pathways_view / groups_view / action_panel
│       ├── log_panel / brewing_panel / event_panel / factions_view
│       └── rivals_view / codex_view
│
├── data/
│   └── events.json            # 主题事件数据（E3）
│
└── tests/                     # 单元 / 面板 / 控制器测试（无头 + 需 tkinter）
    ├── _panel_harness.py      # FakeCanvas + CallbackRecorder 脚手架
    ├── test_all.py            # 纯逻辑总套件（沙箱 Python 即可）
    ├── test_panels_suite.py   # 面板自由函数套件（需 F:\Python314 带 tkinter）
    └── test_e* / test_panel_* / test_controller_*
```

---

## 🔧 环境要求

| 项目        | 要求                                   |
| ----------- | -------------------------------------- |
| Python      | **≥ 3.10**（使用了 `X \| None` 联合类型标注） |
| 第三方依赖  | **无**（仅标准库：tkinter / enum / threading / typing / random / math / os / sys） |
| 操作系统    | Windows / macOS / Linux（GUI 需支持 tkinter 的桌面环境） |

> 注：GUI 使用的 `NotoSansSC-*.otf` 字体已随项目附带，无需额外安装字体。代码中未使用 `from __future__ import annotations`，因此 `int | None` 等标注会在导入时求值，必须使用 Python 3.10+。
>
> **测试环境分工**：纯逻辑与 `test_all.py` 可在任意 Python（含沙箱）运行；面板 / 控制器测试需在**带 tkinter 的 Python（如 `F:\Python314\python.exe`）**下运行 `tests/test_panels_suite.py`，否则会因缺 tkinter 跳过（非代码问题）。

---

## 🚀 安装与运行

### 方式一：图形界面（推荐）

**Windows** —— 双击 `run_gui.bat` 即可（已设置为 UTF-8 代码页）。

**通用（命令行）**：

```bash
cd G:\project_root
python gui_app.py          # 薄启动器，等价于 python -m gui.app
```

### 方式二：命令行演示

```bash
cd G:\project_root
python main.py                      # 默认运行 full 完整旅程
python main.py --demo basic         # 基础演示：偷盗者 → 诈骗师
python main.py --demo multi         # 多途径展示：6 条途径序列 9 → 8
python main.py --demo switch        # 途径切换：诡秘之主组序列 3 互换
python main.py --demo full          # 完整旅程：错误途径序列 9 → 6
python main.py --demo gender        # 性别转换途径展示
python main.py --demo world         # 世界观全览：22 条途径汇总
python main.py --demo uniqueness    # 唯一性争夺：序列 0 权柄之争
python main.py --demo old_one       # 旧日晋升：诡秘之主（支柱级）
python main.py --demo sealed        # 封印物等级映射
python main.py --demo journey       # 共享核心：完整养成循环 + 存档/读档（E11）
python main.py --demo all           # 运行以上全部演示
```

也可直接把模式名当参数：`python main.py basic` / `python main.py journey` 等。

---

## 🧠 核心概念

| 概念       | 说明 |
| ---------- | ---- |
| **途径 (Pathway)** | 一条从序列 9 到序列 0 的晋升路线，对应一种「权柄」。共 22 条。 |
| **序列 (Sequence)** | 途径中的某个等级（9 最低，0 为真神）。名称决定扮演方式。 |
| **扮演法 (Acting)** | 按序列名称「扮演」该角色并累积消化度；`digestion_ratio` 达到 100% 才能晋升。扮演质量（主动/被动/背离）影响加权消化（E5）。 |
| **魔药 (Potion)** | 服用对应序列的「非凡特性」触发晋升，封装主材料与辅助材料（E1 需先备齐材料）。 |
| **仪式 (Ritual)** | 序列 5 及以上晋升所需的仪式，未通过校验无法晋升。 |
| **人性之锚 (Anchor)** | 人性值 + 羁绊 + 信徒/传承 组成的强度值；高序列无锚即失控。 |
| **污染 / SAN (Pollution)** | 使用力量累积的精神污染，连续值 0–100，分 5 级；超过阈值触发 `InsanityError` 失控。 |
| **唯一性 (Uniqueness)** | 每条途径仅一个序列 0 根源；集齐三份序列 1 特性 + 唯一性 = 可成神。AI 对手也会争夺空闲槽位（E8）。 |
| **途径组 (Group)** | 共享同一权柄体系的途径集合（如诡秘之主组：愚者/错误/门），高序列可互换。 |
| **性别转换** | 部分途径在晋升到特定序列时强制改变性别（设定还原）。 |
| **成就 / 图鉴 / 结局** | 10 项成就、序列与能力图鉴进度、5 种结局走向（E9）。 |

**非凡体系三大定律**：① 非凡特性不灭；② 同序列内非凡特性守恒；③ 相近途径非凡特性聚合。

---

## 💡 编程使用示例

```python
import sys
sys.path.insert(0, "G:/project_root")  # 或在本目录运行

from sequences import make_sequence
from anchor import Anchor
from ascension import Potion, ascend, switch_pathway
from role_playing import role_playing_loop
from save_load import GameSession

# 1. 创建一名「错误途径」序列 9 偷盗者，并绑定人性之锚
klein = make_sequence("error", 9)
klein.anchor = Anchor(humanity=85, connections=7, name="克莱恩的日常锚")

# 2. 扮演消化
klein.perform_action("偷窃")
klein.perform_action("潜入")
print(klein.digestion_ratio)   # 1.0 → 消化完成

# 3. 服用魔药晋升到序列 8 诈骗师
potion = Potion("error", 8, "诈骗师非凡特性", ["灵性之血", "迷幻花粉末"])
klein = potion.consume(klein)

# 4. 进入诡秘之主途径组序列 3 后，同级切换到「门」途径
scholar = make_sequence("fool", 3)
scholar = switch_pathway(scholar, "door")   # 需先通过 PathwaySwitchValidator 校验

# 5. 模拟 30 天污染积累
survived, lost, pollution = role_playing_loop(klein, days=30, verbose=False)

# 6. 用 GameSession 存档 / 读档（CLI 与 GUI 共用同一引擎）
sess = GameSession(character=klein.to_dict(), view_mode="character")
sess.save("klein_save")
sess2 = GameSession.load("klein_save")
klein2 = Sequence.from_dict(sess2.character)
```

---

## 🧩 模块说明

| 模块 | 职责 |
| ---- | ---- |
| `sequences.py` | `BaseSequence` 抽象基类、`Sequence` 数据驱动实例、`make_sequence` 工厂；含扮演消化、理智心跳、污染疯癫注入。 |
| `ascension.py` | `AscensionManager` 晋升核心（消化/锚/仪式/切换/性别检查）、`Potion` 魔药类、`ascend` / `switch_pathway` 便捷函数、`fall` 堕落降级。 |
| `anchor.py` | `Anchor` 人性之锚：强度计算、羁绊、信徒、传说传承、各等级最低锚要求。 |
| `pollution.py` | `PollutionLevel` 枚举、异常体系（`InsanityError` / `AnchorBreakError` / `SequenceError` 等）、`PollutionSource` 来源、`PollutionManager` 连续 SAN 管理。 |
| `uniqueness.py` | `Uniqueness` 唯一性（线程安全全局注册表）、`SequenceOneCharacteristic` 序列 1 特性（每途径三份）。 |
| `role_playing.py` | `role_playing_loop` 多日扮演/污染模拟、`ritual_check_pass` 仪式校验、单途径与切换演示。 |
| `pathway_groups.py` | `PathwaySwitchValidator` 互换验证、`OldOnePath` 旧日条件计算、`FOUR_PILLARS` 四支柱、`get_level_description` 等级描述、封印物等级。 |
| `pathways_data.py` | 22 条途径的完整数据：名称、塔罗牌、所属途径组、性别转换等级、各序列的能力/扮演行为/仪式/诅咒/特殊说明。 |
| `inventory.py` | `Inventory` 材料库存（持有 / 配方匹配），支撑 E1 酿造前置校验。 |
| `events.py` | `pick_event` / `resolve_choice` 数据驱动事件（纯逻辑，不依赖 tkinter），`data/events.json` 为内容源。 |
| `factions.py` | `FactionSystem` 阵营声望与社交动作（tarot_exchange / church_purify / secret_anchor）。 |
| `abilities.py` | `ABILITY_EFFECTS` 能力效果注册表 + `apply_ability_effects`，在事件/扮演中产生 SAN 安抚等效果。 |
| `rivals.py` | `Rival` / `RivalSystem`：AI 对手在其它途径推进、消化、晋升、争抢唯一性/序列 1 槽位。 |
| `achievements.py` | `AchievementSystem`（10 成就）、`CodexSystem`（图鉴进度）、`evaluate_ending`（5 结局）、`record_codex` / `evaluate_achievements`。 |
| `lore.py` | `PATHWAY_LORE` / `GROUP_LORE` 序列考据与沉浸文案（纯数据，不依赖 tkinter）。 |
| `save_load.py` | `GameSession` 多字段序列化（character / inventory / factions / rival_system / achievements / codex / …）+ 多槽位存读档。 |
| `gui/` | `app.py`（`LordOfMysteriesGUI` 主类）、`controllers.py`、`state.py`、`theme.py` / `drawing.py` / `helpers.py`，以及 `panels/` 下 10 个自由函数面板。 |

---

## ⚠️ 已知限制 / 技术债

- `BaseSequence` 自身被注释为「系统中最好用的技术债」：运行时通过 `types.MethodType` 注入疯癫行为，属有意设计的「污染致疯」模拟，但破坏了纯数据驱动结构。
- 污染模拟的每日增量、幻觉级额外污染概率等为演示用常量，非严格按原著数值。
- 部分序列 5+ 的 `ritual` 仅作占位/示例，未覆盖全部 22 途径的真实仪式文本。
- GUI 当前为单角色单窗口交互，未实现「多角色并行」。**存档/读档（E4）与多槽位已支持**；AI 对手（E8）、成就图鉴（E9）、沉浸音效（E10）等增强均已在 GUI 中暴露入口。

---

## 📄 许可证

本项目为《诡秘之主》粉丝向模拟器，仅供学习与原著推演使用。原著角色、途径设定版权归作者 **爱潜水的乌贼** 及出品方所有。代码以 MIT 风格开源，使用即表示你已了解此用途限制。
