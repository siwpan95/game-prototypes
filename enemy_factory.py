"""Enemy factory — creates enemy entities with DifficultyManager scaling.

Stats use non-linear tier-based curves instead of flat linear scaling.
AI patterns, keywords, card pool quality all scale with room progression.
"""

from __future__ import annotations
import random
from ecs import World
from components import (
    HealthComponent, AttackComponent, EnemyComponent,
    KeywordComponent, RenderComponent, MinionComponent,
    DeckComponent, HandComponent, CardComponent,
)
from constants import FLOAT_DAMAGE
from systems.difficulty_system import get_difficulty, DifficultyManager
from debug_probes import probe


# ── Enemy Creation ────────────────────────────────────────────────────────

def create_enemy_from_data(world: World, data: dict, room_number: int,
                            is_elite: bool = False, dm: DifficultyManager | None = None):
    """Create an enemy entity from a data dict (from JSON or Excel).

    Uses DifficultyManager for tier-based stat scaling, AI patterns,
    keyword assignment, and shield bonuses.

    Args:
        world: ECS World
        data: Enemy data dict (id, name, hp, attack, is_boss, keywords, etc.)
        room_number: Current room number for difficulty scaling
        is_elite: Apply elite multipliers
        dm: DifficultyManager singleton (auto-fetched if None)

    Returns the enemy Entity.
    """
    if dm is None:
        dm = get_difficulty()

    entity = world.create_entity()
    is_boss = data.get("is_boss", False)
    base_hp = data.get("hp", 12)
    base_atk = data.get("attack", 4)

    # ── Tier-based non-linear stat scaling ──────────────────────────
    hp = dm.scale_enemy_hp(base_hp, room_number, is_boss=is_boss)
    atk = dm.scale_enemy_atk(base_atk, room_number, is_boss=is_boss)

    # Elite modifier (stacks)
    if is_elite:
        elite = dm.elite_stat_multiplier()
        hp = int(hp * elite["hp_mult"])
        atk = int(atk * elite["atk_mult"])

    h_comp = HealthComponent(hp, hp)

    # ── Ascension initial shield ────────────────────────────────────
    init_shield = dm.get_initial_shield(room_number)
    if init_shield > 0:
        h_comp.shield = init_shield

    world.add_component(entity, h_comp)
    world.add_component(entity, AttackComponent(atk))

    # ── AI pattern from difficulty tier ─────────────────────────────
    ai_pattern = dm.get_ai_pattern(room_number, is_boss=is_boss)
    # Boss buff value scales with tier
    buff_value = 1 + dm.get_tier(room_number).level

    world.add_component(entity, EnemyComponent(
        enemy_id=data["id"],
        name=data["name"],
        intent=data.get("intent", "attack"),
        intent_value=atk,
        is_boss=is_boss,
        intent_pattern=data.get("intent_pattern", ai_pattern),
    ))

    # ── Difficulty-based keyword assignment ─────────────────────────
    # Merge data keywords with difficulty-assigned keywords
    data_kw = list(data.get("keywords", []))
    diff_kw = dm.pick_keywords(room_number, is_boss=is_boss)
    all_kw = list(set(data_kw + diff_kw))  # dedupe

    if all_kw:
        kw = KeywordComponent()
        for k in all_kw:
            k_lower = k.lower().replace(" ", "_")
            if k_lower == "taunt":
                kw.taunt = True
            elif k_lower == "divine_shield":
                kw.divine_shield = True
            elif k_lower == "lifesteal":
                kw.lifesteal = True
            elif k_lower == "poisonous":
                kw.poisonous = True
            elif k_lower == "rush":
                kw.rush = True
            elif k_lower == "windfury":
                kw.windfury = True
        world.add_component(entity, kw)

    world.add_component(entity, MinionComponent(data["name"], "enemy"))
    world.add_component(entity, RenderComponent())

    # Store buff value for AI use
    entity._dm_buff_value = buff_value

    probe("enemy::create", f"生成: {data['name']}",
          {"room": room_number, "hp": hp, "atk": atk,
           "boss": str(is_boss), "elite": str(is_elite),
           "tier": dm.get_tier(room_number).name,
           "ai": ai_pattern, "kw": all_kw}, module="enemy")

    return entity


def generate_wave_enemies(world: World, enemy_pool: list[dict], room_number: int,
                          is_elite: bool = False) -> list:
    """Generate enemies for a room, using DifficultyManager for count and scaling.

    Args:
        world: ECS World
        enemy_pool: List of enemy data dicts
        room_number: Current room number
        is_elite: Apply elite multipliers

    Returns list of enemy Entity IDs.
    """
    dm = get_difficulty()
    enemies = []

    if room_number % 5 == 0:
        # ── Boss wave: 1 boss + minions ─────────────────────────────
        boss_data = _pick_boss(enemy_pool)
        if boss_data:
            boss = create_enemy_from_data(world, boss_data, room_number, is_elite, dm)
            enemies.append(boss)

        # Minion count scales with tier
        tier = dm.get_tier(room_number)
        minion_count = max(1, min(tier.level, 3))
        regulars = _pick_regulars(enemy_pool, minion_count)
        for ed in regulars:
            e = create_enemy_from_data(world, ed, room_number, is_elite, dm)
            enemies.append(e)
    else:
        # ── Regular room: count from DifficultyManager ──────────────
        count = dm.scale_enemy_count(room_number)
        regulars = _pick_regulars(enemy_pool, count)
        for ed in regulars:
            e = create_enemy_from_data(world, ed, room_number, is_elite, dm)
            enemies.append(e)

    return enemies


# ── AI Intent Selection ───────────────────────────────────────────────────

def choose_next_intent(enemy_comp: EnemyComponent, atk_comp: AttackComponent,
                        hp_comp: HealthComponent | None = None) -> None:
    """Decide what the enemy will do next turn.

    AI patterns:
      - always_attack: mindlessly attack every turn
      - alternate: attack/defend alternating
      - buff_then_attack: buff self first, then attack hard
      - tactical: defend when low HP, attack otherwise
      - aggressive: always attack, occasionally buff
    """
    pattern = enemy_comp.intent_pattern
    buff_val = 2  # default buff value

    if pattern == "always_attack":
        enemy_comp.intent = "attack"
        enemy_comp.intent_value = atk_comp.attack

    elif pattern == "alternate":
        if enemy_comp.intent == "attack":
            enemy_comp.intent = "defend"
            enemy_comp.intent_value = 5 + atk_comp.attack // 3
        else:
            enemy_comp.intent = "attack"
            enemy_comp.intent_value = atk_comp.attack

    elif pattern == "buff_then_attack":
        if enemy_comp.intent in ("defend", "buff"):
            enemy_comp.intent = "attack"
            enemy_comp.intent_value = atk_comp.attack
        else:
            enemy_comp.intent = "buff"
            enemy_comp.intent_value = buff_val

    elif pattern == "tactical":
        # Defend when below 30% HP; buff then attack otherwise
        if hp_comp and hp_comp.hp < hp_comp.max_hp * 0.3:
            enemy_comp.intent = "defend"
            enemy_comp.intent_value = 8 + atk_comp.attack // 2
        elif enemy_comp.intent in ("defend", "buff"):
            enemy_comp.intent = "attack"
            enemy_comp.intent_value = atk_comp.attack
        else:
            enemy_comp.intent = "buff"
            enemy_comp.intent_value = buff_val

    elif pattern == "aggressive":
        # 80% attack, 20% buff
        if random.random() < 0.2 and enemy_comp.intent != "buff":
            enemy_comp.intent = "buff"
            enemy_comp.intent_value = 3
        else:
            enemy_comp.intent = "attack"
            enemy_comp.intent_value = atk_comp.attack

    else:  # random fallback
        choice = random.choice(["attack", "attack", "defend"])
        if choice == "attack":
            enemy_comp.intent = "attack"
            enemy_comp.intent_value = atk_comp.attack
        else:
            enemy_comp.intent = "defend"
            enemy_comp.intent_value = 5


def _pick_boss(pool: list[dict]) -> dict | None:
    bosses = [e for e in pool if e.get("is_boss", False)]
    return random.choice(bosses) if bosses else None


def _pick_regulars(pool: list[dict], count: int) -> list[dict]:
    regulars = [e for e in pool if not e.get("is_boss", False)]
    if not regulars:
        return []
    return random.choices(regulars, k=min(count, len(regulars)))


# ── Enemy Card System ───────────────────────────────────────────────────────

def create_enemy_deck_entities(world: World, card_pool_b: list[dict],
                                card_pool_c: list[dict], room_number: int,
                                is_elite: bool = False) -> tuple:
    """Create enemy deck/hand entities for a room.

    Deck size and card quality scale with difficulty tier.
    Higher tiers unlock rarer cards.

    Returns (deck_entity, hand_entity).
    """
    from card_factory import create_card_entity
    dm = get_difficulty()

    # Filter card pool by tier-based rarity cap
    filtered_c = dm.filter_card_pool(card_pool_c, room_number)
    combined = list(card_pool_b) + filtered_c
    if not combined:
        return (None, None)

    # Deck size: 3 + tier * 2 (more cards at higher tiers)
    tier = dm.get_tier(room_number)
    deck_size = min(3 + tier.level * 2 + (2 if is_elite else 0), 20)

    deck_ent = world.create_entity()
    deck_comp = DeckComponent(owner="enemy")

    # Weight towards higher rarity at higher tiers
    chosen = _weighted_card_pick(combined, deck_size, room_number)
    for cdata in chosen:
        c_ent = create_card_entity(world, cdata)
        deck_comp.cards.append(c_ent)
    random.shuffle(deck_comp.cards)

    world.add_component(deck_ent, deck_comp)

    hand_ent = world.create_entity()
    world.add_component(hand_ent, HandComponent(owner="enemy"))

    return (deck_ent, hand_ent)


def _weighted_card_pick(pool: list[dict], count: int, room_number: int) -> list[dict]:
    """Pick cards with weights biased toward higher rarity at higher tiers."""
    dm = get_difficulty()
    tier = dm.get_tier(room_number)

    # Base weights
    rarity_weights = {"common": 60, "rare": 25, "epic": 10, "legendary": 5}

    # Tier adjustments: increase rare/epic weight
    rarity_weights["common"] = max(10, 60 - tier.level * 10)
    rarity_weights["rare"] = min(40, 25 + tier.level * 4)
    rarity_weights["epic"] = min(35, 10 + tier.level * 6)

    def _weight(card: dict) -> int:
        return rarity_weights.get(card.get("rarity", "common"), 10)

    # Weighted sampling
    weights = [_weight(c) for c in pool]
    total = sum(weights)
    if total <= 0:
        return random.choices(pool, k=min(count, len(pool)))

    # Normalize and pick
    chosen = random.choices(pool, weights=weights, k=min(count, len(pool)))
    return chosen


# ── Enemy Card Play ──────────────────────────────────────────────────────

def enemy_draw_card(world: World) -> bool:
    """Draw 1 card from enemy deck to enemy hand. Returns True if drawn."""
    deck_comp = _get_enemy_deck(world)
    hand_comp = _get_enemy_hand(world)
    if not deck_comp or not hand_comp:
        return False
    if len(hand_comp.cards) >= 5:  # Enemy hand max
        return False
    card = deck_comp.draw_one()
    if card:
        hand_comp.cards.append(card)
        return True
    return False


def enemy_play_card(world: World, combat_sys) -> str | None:
    """Enemy plays 1 random card from hand. Returns description string or None."""
    hand_comp = _get_enemy_hand(world)
    if not hand_comp or not hand_comp.cards:
        return None

    # Pick a random card from hand
    card_ent = random.choice(hand_comp.cards)
    hand_comp.cards.remove(card_ent)

    card = world.get_component(card_ent, CardComponent)
    if not card:
        world.destroy_entity(card_ent)
        return None

    # Resolve card based on type
    result = _enemy_resolve_card(world, card_ent, card, combat_sys)

    # Discard the card (enemy doesn't recycle discard)
    world.destroy_entity(card_ent)
    return result


def _enemy_resolve_card(world: World, card_ent, card: CardComponent, combat_sys) -> str:
    """Resolve a card played by the enemy."""
    import random as _random

    if card.card_type == "attack":
        dmg = card.damage or 0
        if dmg > 0:
            actual_target = combat_sys._resolve_taunt(world, None, attacker_owner="enemy")
            if actual_target is not None:
                target_h = world.get_component(actual_target, HealthComponent)
                if target_h:
                    absorbed = min(target_h.shield, dmg)
                    target_h.shield -= absorbed
                    remaining = dmg - absorbed
                    target_h.hp -= remaining
                    combat_sys._spawn_float(world, actual_target, f"-{dmg} (嘲讽)", FLOAT_DAMAGE)
                    combat_sys._check_death(world, actual_target)
                    return f"敌人使用 {card.name}，被嘲讽随从挡下 {dmg} 伤害！"

            player_h = combat_sys._get_player_health(world)
            if player_h:
                absorbed = min(player_h.shield, dmg)
                player_h.shield -= absorbed
                remaining = dmg - absorbed
                player_h.hp -= remaining
                if player_h.hp <= 0:
                    from game_state import Phase
                    combat_sys.gs.phase = Phase.GAME_OVER
                return f"敌人使用 {card.name}，造成 {dmg} 伤害！"
        return f"敌人使用 {card.name}。"

    elif card.card_type == "skill":
        enemy_ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
        if enemy_ents and card.shield > 0:
            target = _random.choice(enemy_ents)
            h = world.get_component(target, HealthComponent)
            if h:
                h.shield += card.shield
                return f"敌人使用 {card.name}，获得 {card.shield} 护盾！"
        return f"敌人使用 {card.name}。"

    elif card.card_type == "minion":
        enemy_minions = [e for e in world.get_entities_with(MinionComponent, HealthComponent)
                        if world.get_component(e, MinionComponent)
                        and world.get_component(e, MinionComponent).owner == "enemy"
                        and not world.get_component(e, EnemyComponent)
                        and world.get_component(e, HealthComponent).alive]
        if len(enemy_minions) >= 5:
            return f"敌人试图召唤 {card.name}，但战场已满！"

        minion_ent = _create_enemy_minion(world, card)
        if minion_ent:
            return f"敌人召唤了 {card.name}！"
        return f"敌人使用 {card.name}。"

    return f"敌人使用 {card.name}。"


def _create_enemy_minion(world: World, card: CardComponent):
    """Create an enemy minion entity from a card."""
    from card_factory import _parse_keywords

    minion_ent = world.create_entity()
    world.add_component(minion_ent, HealthComponent(card.health, card.health))
    atk_comp = AttackComponent(card.attack)
    world.add_component(minion_ent, atk_comp)
    world.add_component(minion_ent, MinionComponent(card.name, "enemy"))
    kw = _parse_keywords(card.keywords)
    world.add_component(minion_ent, kw)
    if kw.charge:
        atk_comp.attacks_this_turn = 0

    if card.battlecry or card.deathrattle:
        world.add_component(minion_ent, CardComponent(
            card_id=card.card_id, name=card.name, cost=card.cost,
            card_type=card.card_type, description=card.description,
            rarity=card.rarity, attack=card.attack, health=card.health,
            target_type=card.target_type, keywords=card.keywords,
            battlecry=card.battlecry, deathrattle=card.deathrattle,
            damage=card.damage, shield=card.shield, heal=card.heal,
            element=card.element, status_effect=card.status_effect,
        ))

    world.add_component(minion_ent, RenderComponent())

    if card.battlecry:
        bt = card.battlecry.get("type", "")
        if bt == "damage_equal_attack":
            player_h = _enemy_get_player_health(world)
            if player_h:
                player_h.take_damage(atk_comp.attack)

    return minion_ent


def _enemy_get_player_health(world: World):
    """Get player health component."""
    from components import PlayerComponent, HealthComponent
    for e in world.entities:
        h = world.get_component(e, HealthComponent)
        p = world.get_component(e, PlayerComponent)
        if h and p:
            return h
    return None


# ── Enemy Turn Integration ─────────────────────────────────────────────────

def enemy_process_turn_ai(world: World, enemy_ent, combat_sys) -> None:
    """Enhanced enemy turn processing with difficulty-aware AI.

    Called from main.py _process_enemy_turn to replace the old linear
    intent processing. Uses HP context for tactical decisions.
    """
    enemy_comp = world.get_component(enemy_ent, EnemyComponent)
    atk_comp = world.get_component(enemy_ent, AttackComponent)
    h_comp = world.get_component(enemy_ent, HealthComponent)

    if not enemy_comp or not h_comp or not h_comp.alive:
        return

    # Execute intent
    if enemy_comp.intent == "attack":
        combat_sys.enemy_attack_player(world, enemy_ent)
    elif enemy_comp.intent == "defend":
        if h_comp:
            h_comp.shield += enemy_comp.intent_value
    elif enemy_comp.intent == "buff":
        if atk_comp:
            atk_comp.attack += enemy_comp.intent_value

    # Choose next intent with HP awareness
    choose_next_intent(enemy_comp, atk_comp, h_comp)


# ── Helpers ────────────────────────────────────────────────────────────────

_combat_sys = None


def enemy_set_combat_sys(cs) -> None:
    global _combat_sys
    _combat_sys = cs


def enemy_get_combat_sys():
    return _combat_sys


def _get_enemy_deck(world: World) -> DeckComponent | None:
    for e in world.get_entities_with(DeckComponent):
        d = world.get_component(e, DeckComponent)
        if d and d.owner == "enemy":
            return d
    return None


def _get_enemy_hand(world: World) -> HandComponent | None:
    for e in world.get_entities_with(HandComponent):
        h = world.get_component(e, HandComponent)
        if h and h.owner == "enemy":
            return h
    return None


def cleanup_enemy_card_entities(world: World) -> None:
    """Destroy enemy deck/hand entities, all their card entities, and enemy minions."""
    for e in list(world.get_entities_with(DeckComponent)):
        d = world.get_component(e, DeckComponent)
        if d and d.owner == "enemy":
            for c_ent in d.cards + d.discard:
                world.destroy_entity(c_ent)
            world.destroy_entity(e)
    for e in list(world.get_entities_with(HandComponent)):
        h = world.get_component(e, HandComponent)
        if h and h.owner == "enemy":
            for c_ent in h.cards:
                world.destroy_entity(c_ent)
            world.destroy_entity(e)
    for e in list(world.get_entities_with(MinionComponent)):
        m = world.get_component(e, MinionComponent)
        if m and m.owner == "enemy" and not world.get_component(e, EnemyComponent):
            world.destroy_entity(e)
