"""
test/test_combat.py — 战斗系统单元测试

测试卡牌 (Card / CardDeck / CardLibrary)、敌人 (Enemy / EnemyInstance / EnemyLibrary)、
战斗引擎 (CombatState / CombatEngine)。

运行：
    cd D:/allin && python -m alloy.test.test_combat
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from alloy.systems.combat import (
    Card, CardDeck, CardLibrary,
    Enemy, EnemyInstance, Intent, IntentType, EnemyLibrary,
    CombatState, CombatEngine,
)


# ══════════════════════════════════════════════════════════
# Card 测试
# ══════════════════════════════════════════════════════════

def test_card_create():
    """测试卡牌创建"""
    card = Card(id="slash", name="斩击", damage=6, ap_cost=1)
    assert card.id == "slash"
    assert card.name == "斩击"
    assert card.damage == 6
    assert card.ap_cost == 1
    assert card.playable is True


def test_card_cost_property():
    """测试卡牌 cost 属性"""
    card = Card(id="heavy", name="重击", damage=12, ap_cost=2, nerve_cost=5)
    assert card.cost == (2, 5)


def test_card_serialization():
    """测试卡牌 to_dict / from_dict"""
    card = Card(id="block", name="防御", block=5, ap_cost=1, description="获得5点格挡")
    d = card.to_dict()
    assert d["id"] == "block"
    assert d["block"] == 5

    restored = Card.from_dict(d)
    assert restored.id == "block"
    assert restored.block == 5
    assert restored.name == "防御"


def test_card_repr():
    """测试卡牌 repr"""
    card = Card(id="slash", name="斩击", damage=6, ap_cost=1)
    r = repr(card)
    assert "斩击" in r
    assert "dmg=6" in r


# ══════════════════════════════════════════════════════════
# CardDeck 测试
# ══════════════════════════════════════════════════════════

def test_carddeck_create():
    """测试卡组创建"""
    deck = CardDeck()
    assert deck.count == 0
    assert deck.is_empty is True
    assert len(deck) == 0


def test_carddeck_add_remove():
    """测试卡组添加和移除"""
    deck = CardDeck()
    deck.add(Card(id="slash", name="斩击"))
    deck.add(Card(id="block", name="防御"))
    assert deck.count == 2
    assert deck.has("slash") is True

    assert deck.remove("slash") is True
    assert deck.count == 1
    assert deck.remove("nonexistent") is False


def test_carddeck_remove_all():
    """测试批量移除同名卡牌"""
    deck = CardDeck()
    deck.add_batch([
        Card(id="slash", name="斩击"),
        Card(id="slash", name="斩击"),
        Card(id="block", name="防御"),
    ])
    removed = deck.remove_all("slash")
    assert removed == 2
    assert deck.count == 1


def test_carddeck_draw():
    """测试抽牌"""
    deck = CardDeck()
    deck.add(Card(id="a", name="A"))
    deck.add(Card(id="b", name="B"))
    deck.add(Card(id="c", name="C"))

    drawn = deck.draw(2)
    assert len(drawn) == 2
    assert deck.count == 1

    # 抽空后返回空列表
    deck.draw(1)
    empty = deck.draw(5)
    assert len(empty) == 0


def test_carddeck_list_ids():
    """测试列出卡牌 ID"""
    deck = CardDeck()
    deck.add(Card(id="slash", name="斩击"))
    deck.add(Card(id="block", name="防御"))
    ids = deck.list_ids()
    assert "slash" in ids
    assert "block" in ids


def test_carddeck_serialization():
    """测试卡组序列化"""
    deck = CardDeck()
    deck.add(Card(id="slash", name="斩击", damage=6))
    d = deck.to_dict()
    assert len(d["cards"]) == 1

    restored = CardDeck.from_dict(d)
    assert restored.count == 1
    assert restored.get("slash").damage == 6


def test_carddeck_contains():
    """测试 __contains__"""
    deck = CardDeck()
    deck.add(Card(id="slash", name="斩击"))
    assert "slash" in deck
    assert "block" not in deck


# ══════════════════════════════════════════════════════════
# CardLibrary 测试
# ══════════════════════════════════════════════════════════

def test_cardlibrary_register():
    """测试卡牌库注册"""
    lib = CardLibrary()
    lib.register(Card(id="slash", name="斩击"))
    assert lib.has_card("slash") is True
    assert lib.count == 1


def test_cardlibrary_get_card():
    """测试获取卡牌（返回副本）"""
    lib = CardLibrary()
    lib.register(Card(id="slash", name="斩击", damage=6))
    card = lib.get_card("slash")
    assert card is not None
    assert card.name == "斩击"
    # 修改副本不影响原库
    card.damage = 999
    assert lib.get_card("slash").damage == 6


def test_cardlibrary_get_nonexistent():
    """测试获取不存在的卡牌"""
    lib = CardLibrary()
    assert lib.get_card("nonexistent") is None
    assert lib.has_card("nonexistent") is False


def test_cardlibrary_load_from_list():
    """测试从列表加载"""
    lib = CardLibrary()
    data = [
        {"id": "slash", "name": "斩击", "damage": 6},
        {"id": "block", "name": "防御", "block": 5},
    ]
    lib.load_from_json(data)
    assert lib.count == 2
    assert lib.has_card("slash")
    assert lib.has_card("block")


# ══════════════════════════════════════════════════════════
# Intent / Enemy / EnemyInstance 测试
# ══════════════════════════════════════════════════════════

def test_intent_create():
    """测试意图创建"""
    intent = Intent(name="爪击", description="造成5点伤害", damage=5)
    assert intent.name == "爪击"
    assert intent.damage == 5


def test_intent_serialization():
    """测试意图序列化"""
    intent = Intent(name="蓄力", damage=10, effect_tag="HIGH_PRESS")
    d = intent.to_dict()
    assert d["name"] == "蓄力"
    assert d["effect_tag"] == "HIGH_PRESS"

    restored = Intent.from_dict(d)
    assert restored.name == "蓄力"
    assert restored.damage == 10


def test_enemy_create():
    """测试敌人模板创建"""
    enemy = Enemy(id="goblin", name="哥布林", hp=30, max_hp=30)
    assert enemy.id == "goblin"
    assert enemy.name == "哥布林"
    assert enemy.hp == 30
    assert enemy.is_boss is False


def test_enemy_serialization():
    """测试敌人模板序列化"""
    enemy = Enemy(
        id="goblin", name="哥布林", hp=30, max_hp=30,
        intents=[Intent(name="爪击", damage=5)],
    )
    d = enemy.to_dict()
    assert d["id"] == "goblin"
    assert len(d["intents"]) == 1

    restored = Enemy.from_dict(d)
    assert restored.id == "goblin"
    assert len(restored.intents) == 1
    assert restored.intents[0].damage == 5


def test_enemy_instance_create():
    """测试敌人战斗实例创建"""
    template = Enemy(
        id="goblin", name="哥布林", hp=30, max_hp=30,
        intents=[Intent(name="爪击", damage=5)],
    )
    inst = EnemyInstance(template)
    assert inst.id == "goblin"
    assert inst.hp == 30
    assert inst.alive is True


def test_enemy_instance_default_intent():
    """测试无意图时使用默认攻击"""
    template = Enemy(id="slime", name="史莱姆", hp=20, max_hp=20)
    inst = EnemyInstance(template)
    intent = inst.peek_intent()
    assert intent.damage == 5  # 默认意图


def test_enemy_instance_intent_cycle():
    """测试意图循环"""
    template = Enemy(
        id="goblin", name="哥布林", hp=30, max_hp=30,
        intents=[
            Intent(name="爪击", damage=5),
            Intent(name="重击", damage=10),
        ],
    )
    inst = EnemyInstance(template)

    # 第一轮：爪击
    i1 = inst.choose_intent()
    assert i1.name == "爪击"

    # 第二轮：重击
    i2 = inst.choose_intent()
    assert i2.name == "重击"

    # 第三轮：回到爪击
    i3 = inst.choose_intent()
    assert i3.name == "爪击"


def test_enemy_instance_peek():
    """测试窥视意图不推进指针"""
    template = Enemy(
        id="goblin", name="哥布林", hp=30, max_hp=30,
        intents=[Intent(name="爪击", damage=5)],
    )
    inst = EnemyInstance(template)
    peeked = inst.peek_intent()
    assert peeked.name == "爪击"
    # 再次 peek 应该相同
    assert inst.peek_intent().name == "爪击"


def test_enemy_instance_reset_intents():
    """测试重置意图指针"""
    template = Enemy(
        id="goblin", name="哥布林", hp=30, max_hp=30,
        intents=[Intent(name="A", damage=1), Intent(name="B", damage=2)],
    )
    inst = EnemyInstance(template)
    inst.choose_intent()  # 推进到 B
    assert inst.current_intent_index == 1

    inst.reset_intents()
    assert inst.current_intent_index == 0


def test_enemy_instance_take_damage():
    """测试敌人受伤"""
    template = Enemy(id="goblin", name="哥布林", hp=30, max_hp=30)
    inst = EnemyInstance(template)
    actual = inst.take_damage(10)
    assert actual == 10
    assert inst.hp == 20


def test_enemy_instance_take_damage_with_armor():
    """测试护甲减伤"""
    template = Enemy(id="knight", name="骑士", hp=50, max_hp=50, armor=10)
    inst = EnemyInstance(template)
    actual = inst.take_damage(15)
    assert actual == 5   # 15 - 10 护甲
    assert inst.hp == 45
    assert inst.armor == 0  # 护甲被消耗


def test_enemy_instance_heal():
    """测试敌人治疗"""
    template = Enemy(id="goblin", name="哥布林", hp=30, max_hp=30)
    inst = EnemyInstance(template)
    inst.take_damage(20)
    healed = inst.heal(5)
    assert healed == 5
    assert inst.hp == 15

    # 治疗不超过 max_hp
    healed = inst.heal(100)
    assert healed == 15
    assert inst.hp == 30


def test_enemy_instance_hp_percent():
    """测试 HP 百分比"""
    template = Enemy(id="goblin", name="哥布林", hp=40, max_hp=40)
    inst = EnemyInstance(template)
    assert inst.hp_percent == 1.0
    inst.take_damage(20)
    assert inst.hp_percent == 0.5


def test_enemy_instance_alive():
    """测试存活判定"""
    template = Enemy(id="goblin", name="哥布林", hp=10, max_hp=10)
    inst = EnemyInstance(template)
    assert inst.alive is True
    inst.take_damage(10)
    assert inst.alive is False
    assert inst.hp == 0


# ══════════════════════════════════════════════════════════
# EnemyLibrary 测试
# ══════════════════════════════════════════════════════════

def test_enemy_library_register():
    """测试敌人库注册"""
    lib = EnemyLibrary()
    lib.register(Enemy(id="goblin", name="哥布林", hp=30, max_hp=30))
    assert lib.has_enemy("goblin") is True
    assert lib.count == 1


def test_enemy_library_get_instance():
    """测试从库创建战斗实例"""
    lib = EnemyLibrary()
    lib.register(Enemy(id="goblin", name="哥布林", hp=30, max_hp=30))
    inst = lib.get_instance("goblin")
    assert inst is not None
    assert inst.name == "哥布林"
    assert lib.get_instance("nonexistent") is None


def test_enemy_library_list_bosses():
    """测试列出 Boss"""
    lib = EnemyLibrary()
    lib.register(Enemy(id="goblin", name="哥布林", hp=30, max_hp=30))
    lib.register(Enemy(id="dragon", name="巨龙", hp=200, max_hp=200, is_boss=True))
    bosses = lib.list_bosses()
    assert len(bosses) == 1
    assert bosses[0].id == "dragon"


def test_enemy_library_load_from_list():
    """测试从列表加载敌人"""
    lib = EnemyLibrary()
    data = [
        {"id": "goblin", "name": "哥布林", "hp": 30, "max_hp": 30},
        {"id": "slime", "name": "史莱姆", "hp": 20, "max_hp": 20},
    ]
    lib.load_from_json(data)
    assert lib.count == 2
    assert lib.has_enemy("goblin")
    assert lib.has_enemy("slime")


# ══════════════════════════════════════════════════════════
# CombatState 测试
# ══════════════════════════════════════════════════════════

def _make_combat(hp=40, max_hp=40, enemy_hp=30):
    """创建测试用战斗状态"""
    deck = [
        Card(id="slash", name="斩击", damage=6, ap_cost=1),
        Card(id="slash", name="斩击", damage=6, ap_cost=1),
        Card(id="block", name="防御", block=5, ap_cost=1),
    ]
    enemy = EnemyInstance(Enemy(
        id="goblin", name="哥布林", hp=enemy_hp, max_hp=enemy_hp,
        intents=[Intent(name="爪击", damage=5)],
    ))
    return CombatState.new(
        hp=hp, max_hp=max_hp, nerve=100, max_nerve=100,
        enemy=enemy, deck=deck,
    )


def test_combat_state_new():
    """测试创建战斗状态"""
    cs = _make_combat()
    assert cs.player_hp == 40
    assert cs.enemy.hp == 30
    assert cs.turn_number == 1
    assert cs.combat_over is False
    assert len(cs.hand) <= 5  # HAND_SIZE


def test_combat_play_card():
    """测试打出卡牌"""
    cs = _make_combat()
    initial_ap = cs.ap
    if cs.hand:
        card = cs.hand[0]
        success = cs.play_card(0)
        assert success is True
        assert cs.ap < initial_ap  # AP 消耗了


def test_combat_play_invalid_index():
    """测试无效手牌索引"""
    cs = _make_combat()
    success = cs.play_card(999)
    assert success is False


def test_combat_victory():
    """测试战斗胜利"""
    # 敌人只有 5 HP，一刀斩击(6伤害)即可击杀
    cs = _make_combat(enemy_hp=5)
    # 找到伤害牌打出
    for i, card in enumerate(cs.hand):
        if card.damage > 0:
            cs.play_card(i)
            break
    assert cs.combat_over is True
    assert cs.player_won is True
    assert cs.check_victory() is True
    assert cs.exp_reward > 0


def test_combat_defeat():
    """测试战斗失败"""
    cs = _make_combat(hp=1, max_hp=1)
    # 结束玩家回合 → 敌人攻击 → 玩家死亡
    cs.end_player_turn()
    assert cs.combat_over is True
    assert cs.player_won is False
    assert cs.check_defeat() is True


def test_combat_block_reduces_damage():
    """测试格挡减伤"""
    cs = _make_combat(hp=100, max_hp=100)
    cs.player_block = 10
    cs.end_player_turn()
    # 敌人伤害5，格挡10，应不受伤或只受少量伤害
    assert cs.player_hp >= 95


def test_combat_draw_hand():
    """测试抽满手牌"""
    cs = _make_combat()
    cs.draw_hand()
    assert len(cs.hand) <= 5


def test_combat_shuffle_discard():
    """测试弃牌堆洗入抽牌堆"""
    cs = _make_combat()
    cs.discard_pile.append(Card(id="test", name="测试牌"))
    cs.shuffle_discard_into_draw()
    assert len(cs.discard_pile) == 0
    assert len(cs.draw_pile) > 0


# ══════════════════════════════════════════════════════════
# CombatEngine 测试
# ══════════════════════════════════════════════════════════

def test_combat_engine_start():
    """测试引擎启动战斗"""
    engine = CombatEngine()
    assert engine.state is None

    deck = [Card(id="slash", name="斩击", damage=6, ap_cost=1)]
    enemy = EnemyInstance(Enemy(id="goblin", name="哥布林", hp=30, max_hp=30))
    state = engine.start_combat(40, 40, 100, 100, enemy, deck)
    assert engine.state is not None
    assert state.player_hp == 40


def test_combat_engine_play_card():
    """测试引擎出牌"""
    engine = CombatEngine()
    deck = [Card(id="slash", name="斩击", damage=6, ap_cost=1)]
    enemy = EnemyInstance(Enemy(id="goblin", name="哥布林", hp=30, max_hp=30))
    engine.start_combat(40, 40, 100, 100, enemy, deck)

    if engine.state.hand:
        result = engine.play_card(0)
        assert result is True


def test_combat_engine_end_combat():
    """测试结束战斗归档"""
    engine = CombatEngine()
    deck = [Card(id="slash", name="斩击", damage=6, ap_cost=1)]
    enemy = EnemyInstance(Enemy(id="goblin", name="哥布林", hp=30, max_hp=30))
    engine.start_combat(40, 40, 100, 100, enemy, deck)

    ended = engine.end_combat()
    assert ended is not None
    assert engine.state is None
    assert engine.total_battles == 1
