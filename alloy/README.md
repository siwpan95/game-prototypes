# alloy — 统一游戏引擎

从 D:\allin 下 100+ 个项目中提炼的通用 Python 游戏引擎，融合 ECS 架构、事件总线、世界模型、卡牌战斗、AI 叙事、音频合成等能力。

## 架构分层

```
core/      ECS + EventBus + Config + FixedTimestepLoop  ← 所有项目必用，零硬依赖
world/     世界模型 (状态/地图/物品/角色)      ← 游戏数据层，可序列化
systems/   游戏系统 (战斗/谜题/背包/存档/Mod)   ← 游戏逻辑层
render/    渲染 (终端/GUI/动画/公式引擎)       ← 表现层
audio/     音频 (合成/音乐/音效)              ← 依赖 numpy/scipy
fx/        粒子特效                          ← 依赖 numpy
ai/        智能 (叙事/对话/AI生成)            ← 可选 requests/ollama
ai/decision/ 决策范式 (状态机/行为树/决策树/差分引擎/ECS脑) ← 零依赖
test/      测试工具 (自定义框架)              ← 零依赖
utils/     通用工具 (JSON/日志/字体/文本)      ← 零依赖
```

## 安装

```bash
# 核心（零依赖，ECS + EventBus + World + Systems）
pip install -e .

# 渲染 + 音频
pip install -e ".[render,audio]"

# 全部功能
pip install -e ".[all]"
```

## 快速开始

```python
from alloy import GameEngine

# 一键装配
engine = GameEngine()
engine.add_core()       # ECS + EventBus
engine.add_world()      # GameState
engine.add_systems()    # Inventory + Puzzles + SaveLoad
engine.add_combat()     # 卡牌战斗
engine.add_audio()      # 音频系统

# 直接使用
world = engine.world
state = engine.state
inventory = engine.get("inventory")
```

```python
# 或按需导入
from alloy.core import World, Entity, Component, System, EventBus
from alloy.world import PlayerState, Room, Item, MapData, MapGraph
from alloy.systems import Inventory, PuzzleSystem, CommandParser
from alloy.systems.combat import CombatEngine, Card, CardDeck, Enemy
```

运行示例：
```bash
cd D:/allin && python alloy/example_quickstart.py
cd D:/allin && python alloy/example_decision_ai.py
```

运行测试（292 个）：
```bash
cd D:/allin && python -m alloy.test.run_all
```

## 决策 / 行为范式（状态机 · 行为树 · 决策树 · 差分引擎）

`alloy.ai.decision` 集成了源自 zhuangtaiji 项目的四种计算/决策范式，
覆盖游戏 AI 与状态管理的核心需求，并与本引擎的 ECS 世界循环、事件总线深度打通：

| 范式 | 适用场景 | 关键 API |
|------|----------|----------|
| 状态机 FSM / HSM | 明确的状态 + 事件转移；层次状态机支持嵌套子状态/历史/内部转移 | `GenericStateMachine` / `HierarchicalStateMachine` / `create_state_machine` |
| 行为树 BT | 每帧重新评估的响应式 AI 行为编排（根驱动 tick） | `BehaviorTree` / `Blackboard` / `build_behavior_tree` |
| 决策树 DT | 基于特征空间的一次性路由决策 | `DecisionTree` / `DecisionResult` / `build_decision_tree` |
| 差分引擎 | 巴贝奇有限差分（加法递推）+ 状态差量/响应式脏检查 | `FiniteDifference` / `StateDiff` / `ReactiveTracker` |

**接入 ECS 世界循环**（让 NPC 拥有可驱动的「大脑」）：

```python
from alloy import GameEngine, BrainComponent, BlackboardComponent
from alloy.ai.decision import build_brain_from_spec, default_brains_config

engine = GameEngine()
engine.add_core().add_ai_brain()          # 注册 BrainSystem 到世界主循环
cfg = default_brains_config()

npc = engine.world.create_entity("goblin")
npc.add(BlackboardComponent({"fault": False, "load": 30}))   # 实体级黑板
npc.add(BrainComponent(
    tree=build_brain_from_spec(cfg["behavior_trees"]["BT_SelfHeal"]),
    name="goblin_ai",
))
engine.world.update(0.016)   # BrainSystem 自动 tick 行为树，结果写回实体黑板
```

**固定时间步长主循环**（游戏循环架构最佳实践，参考 Gaffer "Fix Your Timestep"）：

```python
engine = GameEngine()
engine.add_core()             # 内部创建 self.loop = FixedTimestepLoop
engine.advance(0.05)         # 按 1/60 固定步长切分多次 world.update，钳制单帧时间
```

更完整的示例见 `example_decision_ai.py`。

## 核心模块

| 模块 | 说明 | 行数 |
|------|------|------|
| `core/ecs.py` | Entity-Component-System 架构，自增ID + 链式调用 + 类型安全 | 434 |
| `core/event_bus.py` | 松耦合事件总线，递归保护 + 一次性监听 + 装饰器模式 | 355 |
| `world/game_state.py` | 玩家状态 + 游戏状态 + 章节枚举 + to_dict/from_dict | 377 |
| `systems/combat/` | 回合制卡牌战斗：CombatState + 12种Buff + 敌人意图系统 | 1347 |
| `ai/generator.py` | Ollama/DeepSeek 双后端 + 中文模板降级 | 542 |
| `render/formula_engine.py` | 安全数学公式求值 (asteval优先，纯Python回退) | 363 |
| `fx/particle.py` | 高性能粒子系统：Particle + Emitter + ForceField | 949 |
| `core/game_loop.py` | 固定步长主循环 FixedTimestepLoop（累加器 + 单帧钳制防死亡螺旋 + 插值 alpha） | 新增 |
| `ai/decision/state_machine.py` | 通用/层次状态机 FSM/HSM：嵌套子状态/历史/内部转移 `#` | 移植 |
| `ai/decision/behavior_tree.py` | 行为树 BT：组合/装饰/条件/动作 + Blackboard + 声明式构造 | 移植 |
| `ai/decision/decision_tree.py` | 规则型决策树 DT：Condition/Switch/Action 路由 | 移植 |
| `ai/decision/difference_engine.py` | 差分引擎：有限差分递推 + StateDiff + ReactiveTracker 响应式 | 移植 |
| `ai/decision/brain.py` | ECS 粘合层：BlackboardComponent / BrainComponent / BrainSystem | 新增 |

## 本地字体加载

引擎支持从包内 `alloy/fonts/` 目录加载本地字体（随包分发，跨平台一致），
同时兼容 `ALLIN_FONT_PATH` 环境变量、系统字体与 pygame/tkinter 多重兜底。

目录结构：
```
alloy/
└── fonts/
    └── BaoCanMouHuiTingShouXieTi2.0-2.ttf   # 随包打包的手写体（默认本地字体）
```

Pygame 端：
```python
from alloy.utils.font import load_local_font, load_cjk_font

# 加载打包字体（默认取 fonts/ 中第一个发现的字体）
font = load_local_font(32, bold=True)
font.render("饱餐谋·文字冒险", True, (255, 255, 255))

# 按别名加载（别名 = 文件名 stem，大小写不敏感）
font = load_local_font(24, name="baocanmou")

# 让通用 CJK 加载器优先使用本地字体
font = load_cjk_font(16, local_first=True)
```

Tkinter 端（GUI 标题/按钮用手写体，正文保持系统等宽可读性）：
```python
from alloy.render.gui_base import get_default_fonts

fonts = get_default_fonts(local_font="baocanmou")  # title/heading/button 用手写体
```

常用 API：
| 函数 | 说明 |
|------|------|
| `discover_local_fonts()` | 扫描 `fonts/` 目录，返回 `[(别名, 路径), ...]` |
| `load_local_font(size, name, bold, face_index)` | 从本地加载 pygame 字体 |
| `load_local_tk_font(size, name, bold)` | 从本地加载 tkinter 字体 |
| `register_local_font(alias, path)` | 手动注册字体别名 |
| `get_default_local_font_name()` | 返回默认本地字体别名 |
| `get_fonts_dir()` | 返回本地字体目录（兼容开发/pip/PyInstaller） |

> 支持格式：`.ttf` `.otf` `.ttc`（多字脸用 `face_index`）`.woff` `.woff2`。
> 字体对象按 `(路径, 字号, 粗体, 字脸)` 缓存，重复加载大体积 TTF 不会重复开销。

## Python 版本

Python 3.10+

## 可选依赖

| 依赖 | 用途 | 安装组 |
|------|------|--------|
| numpy | 音频合成、公式引擎、粒子系统 | render, audio |
| scipy | 音频信号处理 | audio |
| pygame-ce | 音频播放、输入、字体 | pygame |
| asteval | 公式引擎安全求值 | render |
| requests | AI DeepSeek 后端 | ai |

## 许可

MIT
