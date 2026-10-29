"""
alloy 快速上手示例
=========================

演示统一引擎的核心用法：ECS架构、事件驱动、世界模型、战斗系统。
"""

import sys
import os
# 将 alloy 的父目录加入 sys.path，使 alloy 包可被导入
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, _PROJECT_ROOT)

from alloy import (
    # 核心
    GameEngine, World, Entity, Component, System, EventBus, EventTypes,

    # 世界模型
    GameState, PlayerState, MapData, Item, Character, Room, MapGraph, MapNode,

    # 系统
    Inventory, InventoryItem, Puzzle, PuzzleSystem, CommandParser, SaveLoadManager,
    ModManager, MapManager,

    # 战斗
    CombatState, CombatEngine, Card, CardDeck, CardLibrary,
    Enemy, EnemyInstance, Intent, IntentType, EnemyLibrary,

    # 渲染
    ConsoleRenderer, SolidColor, HSVFlowColor,

    # 工具
    JSONLoader, Logger, TextFormatter,
)


# ══════════════════════════════════════════════════════════
# 示例 1: ECS 架构 — 创建组件和系统
# ══════════════════════════════════════════════════════════

def example_ecs():
    """演示 ECS 架构的基本用法。"""
    print("=" * 50)
    print("示例 1: ECS 架构")

    # 定义组件
    class Position(Component):
        def __init__(self, x: int = 0, y: int = 0):
            self.x = x
            self.y = y

    class Velocity(Component):
        def __init__(self, vx: int = 0, vy: int = 0):
            self.vx = vx
            self.vy = vy

    class Health(Component):
        def __init__(self, hp: int = 100, max_hp: int = 100):
            self.hp = hp
            self.max_hp = max_hp

    # 定义系统
    class MovementSystem(System):
        priority = 50

        def update(self, world: World, dt: float) -> None:
            for entity in world.each(Position, Velocity):
                pos = entity.get(Position)
                vel = entity.get(Velocity)
                pos.x += vel.vx
                pos.y += vel.vy

    # 创建世界
    world = World()

    # 创建实体
    player = world.create_entity("player")
    player.add(Position(0, 0))
    player.add(Velocity(1, 0))
    player.add(Health(100))

    enemy = world.create_entity("enemy")
    enemy.add(Position(10, 5))
    enemy.add(Health(50))

    # 注册系统
    world.add_system(MovementSystem())

    # 运行一帧
    world.update(0.016)

    # 验证
    pos = player.get(Position)
    print(f"  玩家移动后位置: ({pos.x}, {pos.y})")  # -> (1, 0)

    # 查询所有有 Position + Health 的实体
    living = world.get_entities_with_components(Position, Health)
    print(f"  存活实体: {len(living)}")
    for e in living:
        pos = e.get(Position)
        hp = e.get(Health)
        print(f"    {e.eid or e.id}: pos={pos.x},{pos.y} hp={hp.hp}")


# ══════════════════════════════════════════════════════════
# 示例 2: 事件总线 — 系统间松耦合通信
# ══════════════════════════════════════════════════════════

def example_event_bus():
    """演示事件驱动的松耦合通信。"""
    print()
    print("=" * 50)
    print("示例 2: 事件总线")

    bus = EventBus(debug=True)

    events_received = []

    # 系统 A: 监听 ROOM_ENTER 事件
    @bus.subscribe(EventTypes.ROOM_ENTER)
    def on_room_enter(data):
        events_received.append(f"进入房间: {data}")

    # 系统 B: 监听 ITEM_PICKUP 事件
    @bus.subscribe(EventTypes.ITEM_TAKE)
    def on_item_take(data):
        events_received.append(f"拾取物品: {data}")

    # 模拟游戏流程
    bus.emit(EventTypes.ROOM_ENTER, {"room_id": "大厅", "name": "废弃的大厅"})

    # 一次性监听
    bus.once(EventTypes.ITEM_TAKE, lambda d: events_received.append(f"一次性: {d}"))
    bus.emit(EventTypes.ITEM_TAKE, {"item_id": "key_01", "name": "生锈的钥匙"})
    bus.emit(EventTypes.ITEM_TAKE, {"item_id": "potion_01", "name": "回复药"})  # 一次性已移除

    for evt in events_received:
        print(f"  {evt}")


# ══════════════════════════════════════════════════════════
# 示例 3: 世界模型 — 地图/物品/房间
# ══════════════════════════════════════════════════════════

def example_world():
    """演示世界模型的使用。"""
    print()
    print("=" * 50)
    print("示例 3: 世界模型")

    # 地图数据
    map_data = MapData.empty(cols=20, rows=15)
    map_data.set(5, 7, "@")       # 玩家
    map_data.set(10, 3, "E")      # 敌人
    map_data.set(8, 10, "K")      # 钥匙
    print(f"  地图大小: {map_data.cols}x{map_data.rows}")
    print(f"  玩家位置 (5,7): {map_data.get(5, 7)}")
    print(f"  敌人位置 (10,3): {map_data.get(10, 3)}")

    # 物品系统
    from alloy.world.item import create_weapon, create_consumable, create_key as make_key

    sword = create_weapon("iron_sword", "铁剑", stats={"atk": 5}, description="一把普通的铁剑")
    potion = create_consumable("heal_potion", "回复药", effects={"hp": 30})
    key = make_key("cellar_key", "地牢钥匙")
    print(f"  物品: {sword}, {potion}, {key}")

    # 房间系统
    room_hall = Room(room_id="hall", name="大厅", description="一个宽敞的大厅，石柱上刻着古老的符文。")
    room_hall.exits["north"] = "corridor"
    print(f"  房间: {room_hall.name}, 出口: {list(room_hall.exits.keys())}")

    # 节点图
    mg = MapGraph()
    mg.add_node(MapNode(node_id="start", name="起点"))
    mg.add_node(MapNode(node_id="forest", name="森林"))
    mg.add_node(MapNode(node_id="castle", name="城堡"))
    mg.nodes["start"].connections = ["forest"]
    mg.nodes["forest"].connections = ["start", "castle"]
    mg.nodes["castle"].connections = ["forest"]
    mg.current_node = "start"
    dests = mg.get_available_destinations()
    current_node = mg.nodes[mg.current_node]
    print(f"  当前位置: {current_node.name}, 可前往: {[d.name for d in dests]}")

    # 游戏状态
    gs = GameState()
    gs.player.adjust_hp(-20)
    gs.player.add_item("iron_sword")
    gs.player.set_flag("found_secret_door")
    print(f"  游戏状态: hp={gs.player.hp}, items={gs.player.items}, flag={gs.player.has_flag('found_secret_door')}")


# ══════════════════════════════════════════════════════════
# 示例 4: 背包 + 谜题 + 命令
# ══════════════════════════════════════════════════════════

def example_systems():
    """演示游戏系统。"""
    print()
    print("=" * 50)
    print("示例 4: 游戏系统（背包/谜题/命令）")

    # 背包
    inv = Inventory(capacity=10)
    inv.add(InventoryItem(item_id="sword", name="铁剑", item_type="weapon", quantity=1))
    inv.add(InventoryItem(item_id="potion", name="回复药", item_type="consumable", quantity=3))
    inv.add(InventoryItem(item_id="key", name="地牢钥匙", item_type="key", quantity=1))
    print(f"  背包: {len(list(inv.all_items))} 种物品")
    for it in inv.all_items:
        print(f"    {it.name} x{it.quantity}")

    # 谜题系统
    puzzle_sys = PuzzleSystem()
    puzzle_sys.register(Puzzle(
        puzzle_id="door_puzzle",
        title="封印之门",
        puzzle_type="riddle",
        question="什么东西越洗越脏？",
        answer=["水", "water"],
        hints=["和清洁有关", "无色无味"],
        rewards={"sanity": 10},
    ))
    result = puzzle_sys.verify_answer("door_puzzle", "水")
    print(f"  谜题: 回答'水' -> {'正确' if result.get('success') else '错误'}")

    # 命令解析
    cp = CommandParser()
    tests = [
        ("go north", "移动"),
        ("take key", "拾取"),
        ("use potion", "使用"),
        ("look", "查看"),
        ("q", "退出（别名）"),
    ]
    for inp, desc in tests:
        cmd, args = cp.parse(inp)
        print(f"  命令 '{inp}' -> {cmd} {args}  ({desc})")

    # 存档
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        sm = SaveLoadManager(save_dir=tmpdir)
        sm.save(gs := GameState(), slot=0)
        loaded = sm.load(slot=0)
        print(f"  存档: save={sm.get_slot_info(0) is not None}, load={'ok' if loaded else 'fail'}")


# ══════════════════════════════════════════════════════════
# 示例 5: 卡牌战斗
# ══════════════════════════════════════════════════════════

def example_combat():
    """演示卡牌战斗系统。"""
    print()
    print("=" * 50)
    print("示例 5: 卡牌战斗")

    # 构建卡组
    deck = CardDeck()
    deck.add(Card(id="slash", name="斩击", description="造成 6 点伤害", ap_cost=1, damage=6))
    deck.add(Card(id="slash", name="斩击", description="造成 6 点伤害", ap_cost=1, damage=6))
    deck.add(Card(id="slash", name="斩击", description="造成 6 点伤害", ap_cost=1, damage=6))
    deck.add(Card(id="block", name="防御", description="获得 5 点格挡", ap_cost=1, block=5))
    deck.add(Card(id="block", name="防御", description="获得 5 点格挡", ap_cost=1, block=5))
    deck.add(Card(id="heavy", name="重击", description="造成 12 点伤害", ap_cost=2, damage=12))

    # 创建敌人
    enemy_template = Enemy(
        id="goblin",
        name="哥布林",
        hp=30, max_hp=30,
        intents=[
            Intent(name="爪击", description="造成 5 点伤害", damage=5),
            Intent(name="蓄力重击", description="造成 10 点伤害", damage=10, effect_tag="HIGH_PRESS"),
            Intent(name="防御姿态", description="获得护甲", damage=0, effect_tag="BLOCK"),
        ]
    )

    # 创建战斗
    enemy_inst = EnemyInstance(enemy_template)
    combat_state = CombatState.new(
        hp=40, max_hp=40, nerve=100, max_nerve=100,
        enemy=enemy_inst, deck=deck.cards.copy(),
    )
    engine = CombatEngine(combat_state)

    print(f"  战斗开始: 玩家 {combat_state.player_hp}HP vs {enemy_inst.name} {enemy_inst.hp}HP")
    print(f"  手牌 ({len(combat_state.hand)}张): {[c.name for c in combat_state.hand]}")

    # 玩家回合: 使用第一张手牌
    if combat_state.hand:
        card = combat_state.hand[0]
        combat_state.play_card(0)
        print(f"  使用: {card.name} (AP剩余: {combat_state.ap})")

    # 回合结束 → 敌人行动
    combat_state.end_player_turn()
    enemy_intent = enemy_inst.peek_intent()
    if enemy_intent:
        print(f"  敌人意图: {enemy_intent.name} [{enemy_intent.description}]")

    # 敌人回合
    enemy_inst.choose_intent()
    enemy_intent = enemy_inst.peek_intent()
    if enemy_intent:
        damage = max(0, enemy_intent.damage - combat_state.player_block)
        combat_state.player_hp = max(0, combat_state.player_hp - damage)
        combat_state.player_block = 0
        print(f"  受到 {damage} 点伤害!")

    print(f"  战斗后: 玩家 {combat_state.player_hp}HP, 敌人 {enemy_inst.hp}HP")


# ══════════════════════════════════════════════════════════
# 示例 6: GameEngine 一键装配
# ══════════════════════════════════════════════════════════

def example_game_engine():
    """演示 GameEngine 装配器的使用。"""
    print()
    print("=" * 50)
    print("示例 6: GameEngine 一键装配")

    engine = GameEngine()
    engine.add_core()       # ECS + EventBus
    engine.add_world()      # GameState
    engine.add_systems()    # Inventory + Puzzles + Commands + SaveLoad

    # 验证装配结果
    print(f"  World: {type(engine.world).__name__}")
    print(f"  EventBus: {type(engine.bus).__name__}")
    print(f"  GameState: {type(engine.state).__name__}")

    inv = engine.get("inventory")
    inv.add(InventoryItem(item_id="lamp", name="提灯", item_type="tool"))
    print(f"  Inventory: {inv.item_count} items")

    # ECS 更新
    entity = engine.world.create_entity("test_entity")
    class Marker(Component): pass
    entity.add(Marker())
    print(f"  ECS: {engine.world.entity_count()} entities")

    print("  引擎装配完成!")


# ══════════════════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  alloy 统一引擎 — 快速上手示例")
    print("=" * 60 + "\n")

    example_ecs()
    example_event_bus()
    example_world()
    example_systems()
    example_combat()
    example_game_engine()

    print()
    print("=" * 60)
    print("  全部 6 个示例运行完毕!")
    print("=" * 60)
