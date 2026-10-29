"""
插件协议与标准预设（preset）
=============================

插件协议（与 Cordis 插件同构，鸭子类型）：

    name  : str                 插件标识
    inject: list[str]           依赖的服务 key（装配期校验，决定加载顺序）
    outer(ctx) -> None|disposer  可选：可重用外作用域，每个父上下文只执行一次
                                 （共享状态/一次性注册；副作用挂父上下文）
    apply(ctx, config) -> None | disposer    注册能力；返回可调用对象则作为统一 disposer

fork 双作用域：ctx.fork_install(plugin) 会把 outer 留在父作用域、
apply 落进每次新建的 fork——同一插件多实例并存、逐实例独立回收。

标准预设（preset）把引擎现有的 add_* 装配改为同一套注册原语：

    preset_core(ctx, update_cb=None)     World + EventBus + 固定步长循环   （对应 add_core）
    preset_world(ctx)                    GameState                          （对应 add_world）
    preset_systems(ctx)                  背包/谜题/命令/存档                 （对应 add_systems）
    preset_combat(ctx)                   卡牌战斗                            （对应 add_combat）
    preset_audio(ctx, backend)           音频系统                            （对应 add_audio）
    preset_ai_brain(ctx, bus=None)       决策大脑（挂入 World 主循环）        （对应 add_ai_brain）
    preset_trpg(ctx)                     TRPG 规则内核（自 D20 并入）          （D&D-GURPS 角色构建）

预设之间用依赖声明组织：preset_world 缺 "world" 时自动先装 preset_core，
依此类推——加载顺序由依赖决定，不再需要手工链式守卫。
所有预设幂等：已装则复用。
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from alloy.core.context import Context

__all__ = [
    "preset_core",
    "preset_world",
    "preset_systems",
    "preset_combat",
    "preset_audio",
    "preset_ai_brain",
    "preset_trpg",
    "STANDARD_PRESETS",
]


def _shutdown_disposer(obj: Any) -> Optional[Callable[[], Any]]:
    """系统若有 shutdown() 则作为 disposer，否则为 None（销毁时无动作）。"""
    shutdown = getattr(obj, "shutdown", None)
    return shutdown if callable(shutdown) else None


def preset_core(ctx: Context, update_cb: Optional[Callable[[float], None]] = None) -> Context:
    """核心层：World + EventBus + FixedTimestepLoop + WorldLog。幂等：已装则复用。"""
    if ctx.has("world") and ctx.has("bus") and ctx.has("loop") and ctx.has("log"):
        return ctx
    from alloy.core.ecs import World
    from alloy.core.event_bus import EventBus
    from alloy.core.game_loop import FixedTimestepLoop
    from alloy.core.world_log import WorldLog

    if not ctx.has("world"):
        ctx.provide("world", World())
    if not ctx.has("bus"):
        ctx.provide("bus", EventBus())
    if not ctx.has("loop"):
        ctx.provide("loop", FixedTimestepLoop(update_cb, None, fixed_dt=1.0 / 60.0))
    if not ctx.has("log"):
        ctx.provide("log", WorldLog())
    return ctx


def preset_world(ctx: Context) -> Context:
    """世界模型层：GameState。缺 core 时自动先装。"""
    if not ctx.has("world"):
        preset_core(ctx)
    if ctx.has("state"):
        return ctx
    from alloy.world import GameState
    ctx.provide("state", GameState())
    return ctx


def preset_systems(ctx: Context) -> Context:
    """通用系统层：背包/谜题/命令/存档。缺 core/world 时自动先装。"""
    if not ctx.has("world"):
        preset_core(ctx)
    if not ctx.has("state"):
        preset_world(ctx)
    if ctx.has("inventory") and ctx.has("puzzles") and ctx.has("commands") and ctx.has("saves"):
        return ctx
    from alloy.systems import Inventory, PuzzleSystem, CommandHandler, SaveLoadManager
    from alloy.core.paths import get_save_dir

    bus = ctx.get("bus")
    inventory = Inventory()
    puzzles = PuzzleSystem(event_bus=bus)
    commands = CommandHandler()
    saves = SaveLoadManager(save_dir=get_save_dir())
    ctx.provide("inventory", inventory, dispose=_shutdown_disposer(inventory))
    ctx.provide("puzzles", puzzles, dispose=_shutdown_disposer(puzzles))
    ctx.provide("commands", commands, dispose=_shutdown_disposer(commands))
    ctx.provide("saves", saves, dispose=_shutdown_disposer(saves))
    return ctx


def preset_combat(ctx: Context) -> Context:
    """卡牌战斗层。缺 core/world 时自动先装。"""
    if not ctx.has("world"):
        preset_core(ctx)
    if not ctx.has("state"):
        preset_world(ctx)
    if ctx.has("card_library") and ctx.has("enemy_library") and ctx.has("combat"):
        return ctx
    from alloy.systems.combat import CardLibrary, EnemyLibrary, CombatEngine

    card_library = CardLibrary()
    enemy_library = EnemyLibrary()
    combat = CombatEngine()
    ctx.provide("card_library", card_library, dispose=_shutdown_disposer(card_library))
    ctx.provide("enemy_library", enemy_library, dispose=_shutdown_disposer(enemy_library))
    ctx.provide("combat", combat, dispose=_shutdown_disposer(combat))
    return ctx


def preset_audio(ctx: Context, backend: str = "pygame") -> Context:
    """音频系统。backend: 'pygame' | 'bloodmusic'。"""
    if ctx.has("audio"):
        return ctx
    from alloy.audio import AudioSystem

    audio = AudioSystem(backend=backend)
    ctx.provide("audio", audio, dispose=_shutdown_disposer(audio))
    return ctx


def preset_ai_brain(ctx: Context, event_bus: Any = None) -> Context:
    """决策/行为大脑：BrainSystem 挂入 World 主循环。缺 core 时自动先装。"""
    if not ctx.has("world"):
        preset_core(ctx)
    if ctx.has("brain"):
        return ctx
    from alloy.ai import BrainSystem

    bus = event_bus if event_bus is not None else ctx.get("bus")
    brain = BrainSystem(event_bus=bus)
    ctx.get("world").add_system(brain)
    ctx.provide("brain", brain, dispose=_shutdown_disposer(brain))
    return ctx


def preset_trpg(ctx: Context) -> Context:
    """TRPG 规则内核层（自 D20 并入，R2）：D&D-GURPS 变体角色构建内核。

    14 个子系统（属性/装备/优缺点/天赋/技术/种族/背景/专长/技能/骰子/衍生/
    法术位/休整/战斗宏/角色卡）+ 数据中枢。缺 'bus' 时提供独立 EventBus；
    'trpg' 服务 = TrpgContext 适配器，其 effect 栈挂宿主（注册即回滚）。
    幂等：已装且存活则复用。装配实现见 alloy.trpg.preset。
    """
    from alloy.trpg import preset_trpg as _preset

    return _preset(ctx)


#: 标准预设索引（供 --dump-profile 与 preset 装配使用）
STANDARD_PRESETS = {
    "core": preset_core,
    "world": preset_world,
    "systems": preset_systems,
    "combat": preset_combat,
    "audio": preset_audio,
    "ai_brain": preset_ai_brain,
    "trpg": preset_trpg,
}
