"""
allin_engine — 统一游戏引擎
============================

从本地工作区 100+ 个项目中提炼的通用游戏引擎，融合了以下精华：

核心能力：
    - ECS 架构        → core/ecs.py          (融合 carimara_py + pywallpaper)
    - 事件总线        → core/event_bus.py     (融合 carimara_py + hell below)
    - 世界模型        → world/               (房间/地图/物品/角色/游戏状态)
    - 战斗系统        → systems/combat/      (卡牌战斗引擎)
    - 谜题/存档/背包  → systems/             (通用游戏系统)
    - 渲染            → render/              (控制台/Tkinter/Pygame 多后端)
    - 音频            → audio/               (bloodmusic 合成引擎)
    - 粒子特效        → fx/                  (tools/particle)
    - AI 叙事与对话   → ai/                  (easy-ai + ollama_generator)
    - 测试工具        → test/                (py_test_runner)

架构分层：
    ┌─────────────────────────────────────────┐
    │  core/      ECS + EventBus + Config      │  ← 所有项目必用
    ├─────────────────────────────────────────┤
    │  world/     世界模型 (状态/地图/物品)      │  ← 游戏数据层
    ├─────────────────────────────────────────┤
    │  systems/   游戏系统 (战斗/谜题/背包/存档)  │  ← 游戏逻辑层
    ├─────────────────────────────────────────┤
    │  render/    渲染 (终端/GUI/动画/公式)      │  ← 表现层
    │  audio/     音频 (合成/音乐/音效)          │
    │  fx/        特效 (粒子系统)               │
    ├─────────────────────────────────────────┤
    │  ai/        人工智能 (叙事/对话/生成)      │  ← 智能层
    │  test/      测试工具                      │
    │  utils/     通用工具                      │
    └─────────────────────────────────────────┘

快速开始：
    # 方式1: 使用 GameEngine 一键装配
    from allin_engine import GameEngine
    
    engine = GameEngine()
    engine.add_core()      # ECS + EventBus
    engine.add_world()     # 游戏状态 + 地图
    engine.add_systems()   # 背包 + 谜题 + 存档
    world = engine.world
    
    # 方式2: 按需导入
    from allin_engine.core import World, Entity, Component, System, EventBus
    from allin_engine.world import PlayerState, Room, Item, MapData
    from allin_engine.systems import Inventory, PuzzleSystem, SaveLoadManager

需求依赖：
    Python 3.10+
    - numpy       (音频合成/粒子系统/公式引擎)
    - scipy       (音频合成，可选)
    - pygame-ce   (pygame渲染/音频播放，可选)
    - requests    (AI生成器 DeepSeek 后端，可选)
    - asteval>=1.0 (公式引擎安全求值，可选；缺失时退化为受限 exec 回退)

版本: 1.0.0
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "全哥"

# ── 核心层 ────────────────────────────────────────────
# 核心模块无硬依赖，直接导入
from allin_engine.core import (
    Entity,
    Component,
    System,
    World,
    SerializableWorld,
    Snapshotable,
    is_component,
    EventBus,
    EventTypes,
    EventHandler,
    FixedTimestepLoop,
    GameLoopStats,
    MissingDependencyError,
    feature_flags,
    has,
    require,
    report,
    Context,
    DuplicateServiceError,
    WorldLog,
)

# ── 标准预设（preset：与 Cordis bundle 对应的装配原语） ──
from allin_engine.core.plugins import (
    preset_core,
    preset_world,
    preset_systems,
    preset_combat,
    preset_audio,
    preset_ai_brain,
)

# ── 配置 ──────────────────────────────────────────────
from allin_engine.core.config import (
    CELL, COLS, ROWS, WINDOW_W, WINDOW_H, FPS,
    FILL_CHAR, BLOCKED_CHARS, PORTAL_CHARS, DEBUG,
)
from allin_engine.core.paths import (
    ROOT, ENGINE_DIR, CORE_DIR,
    get_resource_root, get_data_dir, get_assets_dir, get_config_dir,
    get_fonts_dir, get_save_dir, get_logs_dir, ensure_dirs,
)

# ── 世界模型 ──────────────────────────────────────────
# 世界模型无硬依赖，直接导入
from allin_engine.world import (
    GameState,
    PlayerState,
    ImageryNetwork,
    ImageryNode,
    MapData,
    Room,
    Portal,
    Mechanism,
    MechanismAction,
    Item,
    Character,
    MapNode,
    MapGraph,
    GraphPathFinder,
    grid_astar,
)

# ── 游戏系统 ──────────────────────────────────────────
# 系统层无硬依赖（TkinterInputSource 仅运行时需要 tkinter）
from allin_engine.systems import (
    InputManager,
    CommandParser,
    CommandHandler,
    CommandResult,
    Puzzle,
    PuzzleSystem,
    Inventory,
    InventoryItem,
    StackableInventory,
    EquipmentSlots,
    ItemRegistry,
    CraftingSystem,
    Recipe,
    SaveLoadManager,
    SaveSlotInfo,
    ModManager,
    MapManager,
    ModManifest,
    MapDef,
    PortalDef,
    MechanismDef,
    SimpleCombat,
    MobTemplate,
    CombatResult,
    MobLibrary,
)

# ── 战斗系统 ──────────────────────────────────────────
# 战斗系统无硬依赖，直接导入
from allin_engine.systems.combat import (
    CombatState,
    CombatEngine,
    Card,
    CardDeck,
    CardLibrary,
    Enemy,
    EnemyInstance,
    Intent,
    IntentType,
    EnemyLibrary,
)

# ── 渲染 ──────────────────────────────────────────────
# 渲染层：gui_base 需要 tkinter（可选），render/__init__.py 已做条件导入
# 若 tkinter 不可用，BaseWindow / StatusPanel / Styles 将为 None
from allin_engine.render import (
    ConsoleRenderer,
    BaseWindow,
    StatusPanel,
    Styles,
    ColorGenerator,
    SolidColor,
    HSVFlowColor,
    EnergyColor,
    RainbowColor,
    FormulaEngine,
    Animation,
    GameLogPanel,
    StatusBar,
    QuickCommandBar,
    GameInputBar,
    GameWindow,
    GameTheme,
)

# ── 音频 ──────────────────────────────────────────────
# 音频层：pygame 为可选依赖，audio_system 在运行时检测
from allin_engine.audio import (
    SynthVoice,
    synthesize_voice,
    OscType,
    EnvShape,
    ADSRParams,
    MusicPattern,
    generate_music_wav,
    AudioSystem,
)

# ── 特效 ──────────────────────────────────────────────
# 特效层无硬依赖，直接导入
from allin_engine.fx import (
    Particle,
    Emitter,
    ForceField,
    ParticleSystem,
    NumpyParticleSystem,
)

# ── AI ────────────────────────────────────────────────
# AI 层：requests（DeepSeek 后端）为可选依赖，generator 在运行时检测
from allin_engine.ai import (
    NarrativeEngine,
    DialogueEngine,
    ContentGenerator,
)

# ── 决策 / 行为范式（集成自 zhuangtaiji）──────────────
# 状态机 / 层次状态机 / 行为树 / 决策树 / 差分引擎 / ECS 脑
from allin_engine.ai import (
    GenericStateMachine,
    create_state_machine,
    HierarchicalStateMachine,
    BehaviorTree,
    Blackboard,
    DecisionTree,
    FiniteDifference,
    StateDiff,
    ReactiveTracker,
    BrainComponent,
    BlackboardComponent,
    BrainSystem,
    default_brains_config,
    load_decision_config,
    build_brain_from_spec,
)

# ── 测试 ──────────────────────────────────────────────
# 测试层无硬依赖，直接导入
from allin_engine.test import (
    TestRunner,
    TestResult,
    Probe,
    ProbeManager,
)

# ── 工具 ──────────────────────────────────────────────
# 工具层无硬依赖，直接导入
from allin_engine.utils import (
    JSONLoader,
    Logger,
    TextFormatter,
    load_cjk_font,
    load_cjk_tk_font,
    load_local_font,
    load_local_tk_font,
    discover_local_fonts,
    register_local_font,
    get_local_fonts_dir,
    get_default_local_font_name,
    list_local_fonts,
    clear_font_cache,
)


# ══════════════════════════════════════════════════════════
#  游戏引擎装配器
# ══════════════════════════════════════════════════════════

_MISSING = object()  # get() 方法 default 参数的哨兵


class GameEngine:
    """
    游戏引擎装配器 —— 一键组装核心模块。

    用法::

        engine = GameEngine()
        engine.add_core()       # ECS + EventBus
        engine.add_world()      # 游戏状态
        engine.add_systems()    # 背包/谜题/存档

        # 直接使用
        world = engine.world
        bus = engine.bus

        # 运行主循环
        engine.run(dt=0.016)
    """

    def __init__(self):
        # 可逆装配内核：所有服务注册进 ctx，卸载/销毁自动回滚（注册即回滚）
        self.ctx: Context = Context()
        self.world: World | None = None
        self.bus: EventBus | None = None
        self.state: GameState | None = None
        self.log: WorldLog | None = None
        self._systems: dict[str, object] = {}
        self.running: bool = False
        self.loop: FixedTimestepLoop | None = None

    # ── 装配方法（内部走 preset，已装则复用） ────────

    def add_core(self) -> "GameEngine":
        """装配核心层：ECS World + EventBus + 固定步长循环。

        内部调用 preset_core，注册进 self.ctx；重复调用幂等（复用已装服务）。
        """
        preset_core(self.ctx, update_cb=self.update)
        self.world = self.ctx.get("world")
        self.bus = self.ctx.get("bus")
        self.loop = self.ctx.get("loop")
        self.log = self.ctx.get("log")
        return self

    def add_world(self) -> "GameEngine":
        """装配世界模型：GameState。缺 core 时自动先装。重复调用幂等。"""
        if self.world is None:
            self.add_core()
        preset_world(self.ctx)
        self.state = self.ctx.get("state")
        return self

    def add_systems(self) -> "GameEngine":
        """装配通用系统：背包/谜题/命令/存档。重复调用幂等。"""
        if self.state is None:
            self.add_world()
        preset_systems(self.ctx)
        for key in ("inventory", "puzzles", "commands", "saves"):
            self._systems[key] = self.ctx.get(key)
        return self

    def add_combat(self) -> "GameEngine":
        """装配战斗系统。重复调用幂等。"""
        if self.state is None:
            self.add_world()
        preset_combat(self.ctx)
        for key in ("card_library", "enemy_library", "combat"):
            self._systems[key] = self.ctx.get(key)
        return self

    def add_audio(self, backend: str = "pygame") -> "GameEngine":
        """装配音频系统。backend: 'pygame' | 'bloodmusic'。重复调用幂等。"""
        preset_audio(self.ctx, backend=backend)
        self._systems["audio"] = self.ctx.get("audio")
        return self

    def add_ai_brain(self, event_bus: EventBus | None = None) -> "GameEngine":
        """装配决策/行为脑系统：把行为树/状态机挂到 ECS 实体上由主循环驱动。

        用法（先创建带 BrainComponent 的实体）：
            engine.add_core().add_ai_brain()
            npc = engine.world.create_entity("goblin")
            npc.add(BlackboardComponent({"hp": 30}))
            npc.add(BrainComponent(tree=build_behavior_tree(spec)))
            engine.world.update(0.016)   # BrainSystem 自动 tick 行为树
        """
        if self.world is None:
            self.add_core()
        preset_ai_brain(self.ctx, event_bus=event_bus)
        brain = self.ctx.get("brain")
        self._systems["brain"] = brain
        return self

    # ── 查询方法 ────────────────────────────────────

    def get(self, name: str, default: object = _MISSING):
        """获取已装配的子系统。

        用法::

            inventory = engine.get("inventory")          # 未装配时返回 None
            inventory = engine.get("inventory", default=None)  # 等价写法
            inventory = engine.get("inventory", default=[])   # 自定义默认值

        参数：
            name: 子系统名称（如 "inventory", "combat", "audio"）
            default: 未装配时返回的默认值（默认 None）

        返回：
            子系统实例，或 default
        """
        if name in self._systems:
            return self._systems[name]
        if self.ctx.has(name):
            return self.ctx.get(name)
        if default is _MISSING:
            return None
        return default

    def has(self, name: str) -> bool:
        return name in self._systems or self.ctx.has(name)

    def mount(self, plugin, config: object = None) -> "GameEngine":
        """装配第三方插件（name/inject/apply 协议），注册进 self.ctx。

        inject 声明的依赖缺失时在装配期报错；apply 返回可调用对象
        则作为插件统一 disposer，随 shutdown()/unload() 自动执行。
        """
        self.ctx.install(plugin, config)
        return self

    def unload(self, key: str) -> bool:
        """卸载指定服务：自动执行其 disposer 并从 ctx 移除。

        key 为 "world"/"bus"/"loop"/"state" 时同步清理引擎镜像属性；
        key 为子系统名时同步清理 self._systems 条目。
        """
        ok = self.ctx.unload(key)
        if key in self._systems:
            del self._systems[key]
        if key == "world":
            self.world = None
        elif key == "bus":
            self.bus = None
        elif key == "loop":
            self.loop = None
        elif key == "state":
            self.state = None
        elif key == "log":
            self.log = None
        return ok

    # ── 生命周期 ────────────────────────────────────

    def start(self) -> None:
        """启动引擎"""
        self.running = True

    def stop(self) -> None:
        """停止引擎"""
        self.running = False

    def update(self, dt: float) -> None:
        """主循环更新：驱动 ECS World"""
        if self.world is not None:
            self.world.update(dt)

    def run(self, dt: float = 0.016) -> None:
        """单次更新"""
        self.update(dt)

    def advance(self, real_dt: float) -> None:
        """以固定步长推进真实时间片段 real_dt（秒）。

        依赖 add_core() 创建的 self.loop（FixedTimestepLoop）：内部按固定步长
        切分多次 world.update，并钳制单帧最大时间，避免「死亡螺旋」。
        """
        if self.loop is not None:
            self.loop.advance(real_dt)
        else:
            self.update(real_dt)

    def shutdown(self) -> None:
        """清理资源：按注册逆序回滚全部 disposer（注册即回滚），引擎可重新装配。

        与旧版区别：旧版逐系统调用 shutdown 但保留状态；新版通过 ctx.dispose()
        统一回滚，随后换上新 Context，engine.add_* 可再次装配。
        """
        self.running = False
        self.ctx.dispose()
        self._systems.clear()
        self.world = None
        self.bus = None
        self.state = None
        self.log = None
        self.loop = None
        self.ctx = Context()


# ══════════════════════════════════════════════════════════
#  公共接口
# ══════════════════════════════════════════════════════════

__all__ = [
    # ── 元信息 ──
    "__version__",
    "GameEngine",

    # ── 核心层 ──
    "Entity", "Component", "System", "World", "SerializableWorld", "Snapshotable", "is_component",
    "EventBus", "EventTypes", "EventHandler",
    "FixedTimestepLoop", "GameLoopStats",
    "MissingDependencyError", "feature_flags", "has", "require", "report",
    "Context", "DuplicateServiceError", "WorldLog",
    "preset_core", "preset_world", "preset_systems",
    "preset_combat", "preset_audio", "preset_ai_brain",

    # ── 配置 ──
    "CELL", "COLS", "ROWS", "WINDOW_W", "WINDOW_H", "FPS",
    "FILL_CHAR", "BLOCKED_CHARS", "PORTAL_CHARS", "DEBUG",
    "ROOT", "ENGINE_DIR", "CORE_DIR",
    "get_resource_root", "get_data_dir", "get_assets_dir", "get_config_dir",
    "get_fonts_dir", "get_save_dir", "get_logs_dir", "ensure_dirs",

    # ── 世界模型 ──
    "GameState", "PlayerState", "ImageryNetwork", "ImageryNode",
    "MapData", "Room", "Portal", "Mechanism", "MechanismAction",
    "Item", "Character", "MapNode", "MapGraph",

    # ── 游戏系统 ──
    "InputManager",
    "CommandParser", "CommandHandler", "CommandResult",
    "Puzzle", "PuzzleSystem",
    "Inventory", "InventoryItem",
    "StackableInventory", "EquipmentSlots", "ItemRegistry",
    "CraftingSystem", "Recipe",
    "SaveLoadManager", "SaveSlotInfo",
    "ModManager", "MapManager", "ModManifest", "MapDef", "PortalDef", "MechanismDef",

    # ── 战斗系统 ──
    "CombatState", "CombatEngine",
    "Card", "CardDeck", "CardLibrary",
    "Enemy", "EnemyInstance", "Intent", "IntentType", "EnemyLibrary",
    "SimpleCombat", "MobTemplate", "CombatResult", "MobLibrary",

    # ── 渲染 ──
    "ConsoleRenderer", "BaseWindow", "StatusPanel", "Styles",
    "ColorGenerator", "SolidColor", "HSVFlowColor", "EnergyColor", "RainbowColor",
    "FormulaEngine", "Animation",
    "GameLogPanel", "StatusBar", "QuickCommandBar", "GameInputBar",
    "GameWindow", "GameTheme",

    # ── 音频 ──
    "SynthVoice", "synthesize_voice", "OscType", "EnvShape", "ADSRParams",
    "MusicPattern", "generate_music_wav", "AudioSystem",

    # ── 特效 ──
    "Particle", "Emitter", "ForceField", "ParticleSystem", "NumpyParticleSystem",

    # ── AI ──
    "NarrativeEngine", "DialogueEngine", "ContentGenerator",

    # ── 决策/行为范式（状态机/行为树/决策树/差分引擎/脑）──
    "GenericStateMachine", "create_state_machine", "HierarchicalStateMachine",
    "BehaviorTree", "Blackboard", "DecisionTree",
    "FiniteDifference", "StateDiff", "ReactiveTracker",
    "BrainComponent", "BlackboardComponent", "BrainSystem",
    "default_brains_config", "load_decision_config", "build_brain_from_spec",

    # ── 测试 ──
    "TestRunner", "TestResult", "Probe", "ProbeManager",

    # ── 工具 ──
    "JSONLoader", "Logger", "TextFormatter", "load_cjk_font",
    "load_cjk_tk_font", "load_local_font", "load_local_tk_font",
    "discover_local_fonts", "register_local_font", "get_local_fonts_dir",
    "get_default_local_font_name", "list_local_fonts", "clear_font_cache",
]

