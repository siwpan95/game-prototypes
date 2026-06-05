"""Card factory — creates card entities from data dictionaries."""

from __future__ import annotations
import random
from ecs import World
from components import (
    CardComponent, KeywordComponent, AttackComponent,
    HealthComponent, MinionComponent, RenderComponent,
)


# ── 关键词中英文映射 ────────────────────────────────────────────────
KEYWORD_CN_MAP: dict[str, str] = {
    "taunt":           "嘲讽",
    "charge":          "冲锋",
    "rush":            "突袭",
    "divine_shield":   "圣盾",
    "poisonous":       "剧毒",
    "lifesteal":       "吸血",
    "windfury":        "风怒",
}

KEYWORD_CN_REVERSE: dict[str, str] = {v: k for k, v in KEYWORD_CN_MAP.items()}


def translate_keyword(kw: str) -> str:
    """将英文关键词转为中文显示名。"""
    return KEYWORD_CN_MAP.get(kw.lower().replace(" ", "_"), kw)


def translate_keywords(kw_list: list[str]) -> list[str]:
    """将关键词列表全部转为中文。"""
    return [translate_keyword(k) for k in kw_list]


def _status_desc(se: dict) -> str:
    """生成状态效果的中文描述片段。"""
    names = {
        "stun": "眩晕", "slow": "迟缓", "weaken": "虚弱",
        "freeze": "冰冻", "shaken": "动摇", "burn": "燃烧",
        "poison": "中毒", "shield_up": "护盾增强",
    }
    etype = se.get("type", "")
    turns = se.get("turns", 1)
    value = se.get("value", 0)
    name = names.get(etype, etype)
    if value > 0:
        return f"施加{name}({value}点,{turns}回合)"
    return f"施加{name}({turns}回合)"


def generate_card_description(data: dict) -> str:
    """根据卡牌数据字段，从玩家视角动态生成统一格式的中文描述。

    确保所有卡牌描述措辞一致，不会出现一会儿说"敌人"一会儿说"玩家"的情况。
    """
    parts: list[str] = []
    card_type = data.get("type", "attack")
    damage = data.get("damage", 0)
    shield = data.get("shield", 0)
    heal = data.get("heal", 0)
    target = data.get("target", "enemy")
    element = data.get("element", "none")
    battlecry = data.get("battlecry")
    deathrattle = data.get("deathrattle")
    keywords = data.get("keywords", [])
    status_effect = data.get("status_effect")

    # 元素名称映射
    elem_names = {
        "fire": "火焰", "ice": "冰霜", "lightning": "雷电",
        "wind": "风暴", "earth": "大地", "dark": "暗影", "light": "神圣",
    }

    def _target_enemy_desc(dmg: int) -> str:
        if target == "none":
            return f"对所有敌人造成{dmg}点伤害"
        elif target in ("enemy", "any_minion"):
            return f"对一个敌人造成{dmg}点伤害"
        else:
            return f"造成{dmg}点伤害"

    if card_type == "attack":
        if damage > 0:
            elem_prefix = ""
            if element and element != "none":
                elem_prefix = elem_names.get(element, "") 
            parts.append(f"{elem_prefix}{_target_enemy_desc(damage)}")
        if heal > 0:
            parts.append(f"回复{heal}点生命")
        if shield > 0:
            parts.append(f"获得{shield}点护盾")
        # ── 状态效果描述 ──
        if status_effect:
            se = status_effect
            parts.append(_status_desc(se))

    elif card_type == "skill":
        if shield > 0:
            parts.append(f"获得{shield}点护盾")
        if heal > 0:
            parts.append(f"回复{heal}点生命")
        if battlecry and battlecry.get("type") == "draw":
            parts.append("抽1张牌")
        if damage > 0:
            parts.append(_target_enemy_desc(damage))
        # ── 状态效果描述（技能卡通常影响自身或全体）──
        if status_effect:
            se = status_effect
            parts.append(_status_desc(se))

    elif card_type == "minion":
        # ── 战吼描述 ──
        bc_type = battlecry.get("type", "") if battlecry else ""
        bc_val = battlecry.get("value", 0) if battlecry else 0
        if damage > 0:
            parts.append(f"战吼：{_target_enemy_desc(damage)}")
        if shield > 0:
            parts.append(f"战吼：获得{shield}点护盾")
        if heal > 0:
            parts.append(f"战吼：回复{heal}点生命")
        if bc_type == "draw":
            parts.append(f"战吼：抽{bc_val}张牌")
        elif bc_type == "damage_self":
            parts.append(f"战吼：对自己造成{bc_val}点伤害")
        elif bc_type == "freeze":
            parts.append(f"战吼：自身冰冻{bc_val}回合")
        elif bc_type == "damage_equal_attack":
            parts.append("战吼：造成等于攻击力的伤害")
        elif bc_type == "buff_attack":
            parts.append(f"战吼：攻击力+{bc_val}")
        elif bc_type == "buff_health_per_card":
            parts.append(f"战吼：生命值+{bc_val}")
        elif bc_type == "set_stats":
            parts.append(f"战吼：攻击力和生命值变为{bc_val}")
        # ── 亡语描述 ──
        dr_type = deathrattle.get("type", "") if deathrattle else ""
        dr_val = deathrattle.get("value", 0) if deathrattle else 0
        if dr_type == "damage":
            parts.append(f"亡语：对所有敌人造成{dr_val}点伤害")
        elif dr_type == "damage_target":
            parts.append(f"亡语：对一个敌人造成{dr_val}点伤害")
        elif dr_type == "draw":
            parts.append(f"亡语：抽{dr_val}张牌")
        elif dr_type == "heal":
            parts.append(f"亡语：回复{dr_val}点生命")
        # 仅有关键词无其他效果时，用关键词作为描述
        if not parts and keywords:
            kw_cn = [translate_keyword(k) for k in keywords]
            parts = kw_cn

    if parts:
        result = "，".join(parts)
        # 确保以句号结尾
        if not result.endswith("。"):
            result += "。"
        return result

    # 兜底：使用原始描述
    return data.get("description", "")


def create_card_entity(world: World, data: dict):
    """Create a card entity from a data dict (from JSON or Excel).

    Returns the Entity.
    """
    entity = world.create_entity()

    # 自动生成统一视角的描述文字
    auto_desc = generate_card_description(data)
    # 优先使用自动生成的描述；如果为空则回退到 Excel 中的原始描述
    description = auto_desc if auto_desc else data.get("description", "")

    card = CardComponent(
        card_id=data["id"],
        name=data["name"],
        cost=data.get("cost", 1),
        card_type=data.get("type", "attack"),
        description=description,
        rarity=data.get("rarity", "common"),
        attack=data.get("attack", 0),
        health=data.get("health", 0),
        target_type=data.get("target", "enemy"),
        keywords=data.get("keywords", []),
        battlecry=data.get("battlecry"),
        deathrattle=data.get("deathrattle"),
        damage=data.get("damage", 0),
        shield=data.get("shield", 0),
        heal=data.get("heal", 0),
        pool=data.get("pool", "B"),
        element=data.get("element", "none"),
        status_effect=data.get("status_effect"),
    )
    world.add_component(entity, card)
    world.add_component(entity, RenderComponent())
    return entity


def create_minion_from_card(world: World, card_entity) -> object:
    """Given a card entity with CardComponent, spawn a minion entity on the board.

    Returns the new minion Entity.
    """
    card = world.get_component(card_entity, CardComponent)
    if card is None:
        return None

    minion_ent = world.create_entity()

    # Health
    world.add_component(minion_ent, HealthComponent(card.health, card.health))

    # Attack
    atk_comp = AttackComponent(card.attack)
    world.add_component(minion_ent, atk_comp)

    # Minion marker
    world.add_component(minion_ent, MinionComponent(card.name, "player"))

    # Keywords
    kw = _parse_keywords(card.keywords)
    world.add_component(minion_ent, kw)

    # Store battlecry / deathrattle references on the minion too
    if card.battlecry or card.deathrattle:
        # We keep a second CardComponent-like reference on the minion
        # so keyword_system can find effects
        world.add_component(minion_ent, CardComponent(
            card_id=card.card_id,
            name=card.name,
            cost=card.cost,
            card_type=card.card_type,
            description=card.description,
            rarity=card.rarity,
            attack=card.attack,
            health=card.health,
            target_type=card.target_type,
            keywords=card.keywords,
            battlecry=card.battlecry,
            deathrattle=card.deathrattle,
            damage=card.damage,
            shield=card.shield,
            heal=card.heal,
        ))

    world.add_component(minion_ent, RenderComponent())

    # If Charge — can attack immediately
    if kw.charge:
        atk_comp.attacks_this_turn = 0  # Can attack right now
    # If Windfury — can attack twice per turn
    if kw.windfury:
        atk_comp.max_attacks = 2

    return minion_ent


def _parse_keywords(kw_list: list[str]) -> KeywordComponent:
    """Convert a list of keyword strings into a KeywordComponent."""
    kw = KeywordComponent()
    for k in (kw_list or []):
        k_lower = k.lower().replace(" ", "_")
        if k_lower == "taunt":
            kw.taunt = True
        elif k_lower == "charge":
            kw.charge = True
        elif k_lower == "rush":
            kw.rush = True
        elif k_lower == "divine_shield":
            kw.divine_shield = True
        elif k_lower == "poisonous":
            kw.poisonous = True
        elif k_lower == "lifesteal":
            kw.lifesteal = True
        elif k_lower == "windfury":
            kw.windfury = True
            kw.__dict__["_windfury_set"] = True  # Will set max_attacks=2 later
    if kw.windfury:
        pass  # handled in combat system
    return kw


def pick_reward_cards(card_pool: list[dict], count: int = 3) -> list[dict]:
    """Pick N reward cards from the pool using weighted rarity.

    Returns list of card data dicts.
    """
    weights = {"common": 65, "rare": 28, "epic": 7}
    weighted = []
    for c in card_pool:
        w = weights.get(c.get("rarity", "common"), 65)
        weighted.append((c, w))

    chosen = []
    pool = weighted[:]
    for _ in range(min(count, len(pool))):
        entries, ws = zip(*pool) if pool else ([], [])
        pick = random.choices(list(entries), weights=list(ws), k=1)[0]
        chosen.append(pick)
        # Remove picked to avoid duplicates
        pool = [(c, w) for c, w in pool if c["id"] != pick["id"]]
    return chosen


def pick_reward_cards_elite(card_pool: list[dict], count: int = 4) -> list[dict]:
    """Pick reward cards for elite battles — higher rarity weighting."""
    weights = {"common": 40, "rare": 35, "epic": 20, "legendary": 5}
    weighted = []
    for c in card_pool:
        w = weights.get(c.get("rarity", "common"), 40)
        weighted.append((c, w))

    chosen = []
    pool = weighted[:]
    for _ in range(min(count, len(pool))):
        entries, ws = zip(*pool) if pool else ([], [])
        pick = random.choices(list(entries), weights=list(ws), k=1)[0]
        chosen.append(pick)
        pool = [(c, w) for c, w in pool if c["id"] != pick["id"]]
    return chosen


def upgrade_card(card_component: CardComponent) -> str:
    """Upgrade a card component in-place. Returns the upgrade description.

    Upgrade effects vary by card type:
    - Attack cards: +3 damage, cost may decrease
    - Skill cards: +3 shield/heal, cost may decrease
    - Minion cards: +2/+2 stats
    - Cost minimum is 1 (can't go to 0 from upgrade alone)
    """
    if card_component.upgraded:
        return "已升级过了！"

    card_component.upgraded = True
    old_name = card_component.name
    card_component.name = card_component.name + "+"
    changes = []

    if card_component.card_type == "attack":
        card_component.damage += 3
        changes.append(f"伤害 +3")
    elif card_component.card_type == "skill":
        card_component.shield += 3
        card_component.heal += 3
        changes.append(f"效果 +3")
    elif card_component.card_type == "minion":
        card_component.attack += 2
        card_component.health += 2
        changes.append(f"攻击/生命 +2")

    # Cost reduction (50% chance, min 1)
    if card_component.cost > 1 and random.random() < 0.5:
        card_component.cost -= 1
        changes.append(f"费用 -1")

    return f"{old_name} → {card_component.name}: {', '.join(changes) if changes else '已升级'}"
