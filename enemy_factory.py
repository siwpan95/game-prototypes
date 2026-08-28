"""Enemy factory — creates enemy entities from data or wave scaling."""

from __future__ import annotations
import random
from ecs import World
from components import (
    HealthComponent, AttackComponent, EnemyComponent,
    KeywordComponent, RenderComponent, MinionComponent,
)
from constants import (
    WAVE_ENEMY_BASE_HP, WAVE_ENEMY_HP_SCALE,
    WAVE_ENEMY_BASE_ATK, WAVE_ENEMY_ATK_SCALE,
    WAVE_BOSS_HP_MULTI, WAVE_BOSS_ATK_MULTI,
)


def create_enemy_from_data(world: World, data: dict, wave: int):
    """Create an enemy entity from a data dict (from JSON or Excel).

    Wave number is used for scaling.
    Returns the Entity.
    """
    entity = world.create_entity()

    # Scale stats by wave
    scale = max(1, wave - 1)
    hp = data.get("hp", WAVE_ENEMY_BASE_HP) + scale * WAVE_ENEMY_HP_SCALE
    atk = data.get("attack", WAVE_ENEMY_BASE_ATK) + scale * WAVE_ENEMY_ATK_SCALE
    is_boss = data.get("is_boss", False)

    if is_boss:
        hp = int(hp * WAVE_BOSS_HP_MULTI)
        atk = int(atk * WAVE_BOSS_ATK_MULTI)

    world.add_component(entity, HealthComponent(hp, hp))
    world.add_component(entity, AttackComponent(atk))
    world.add_component(entity, EnemyComponent(
        enemy_id=data["id"],
        name=data["name"],
        intent=data.get("intent", "attack"),
        intent_value=atk,
        is_boss=is_boss,
        intent_pattern=data.get("intent_pattern", "always_attack"),
    ))

    # Optional keywords
    kw_list = data.get("keywords", [])
    if kw_list:
        kw = KeywordComponent()
        for k in kw_list:
            k_lower = k.lower().replace(" ", "_")
            if k_lower == "taunt":
                kw.taunt = True
            elif k_lower == "divine_shield":
                kw.divine_shield = True
            elif k_lower == "lifesteal":
                kw.lifesteal = True
            elif k_lower == "poisonous":
                kw.poisonous = True
        world.add_component(entity, kw)

    # If enemy has taunt it acts as a minion too (for combat targeting)
    world.add_component(entity, MinionComponent(data["name"], "enemy"))
    world.add_component(entity, RenderComponent())
    return entity


def generate_wave_enemies(world: World, enemy_pool: list[dict], wave: int) -> list:
    """Generate a list of enemy entities for a given wave.

    Returns list of Entity IDs.
    """
    enemies = []

    # Determine enemy count
    if wave % 5 == 0:
        # Boss wave: 1 boss + 1-2 minions
        boss_data = _pick_boss(enemy_pool)
        if boss_data:
            boss = create_enemy_from_data(world, boss_data, wave)
            enemies.append(boss)
        # Add 1-2 regular enemies
        regulars = _pick_regulars(enemy_pool, min(2, 1 + wave // 10))
        for ed in regulars:
            e = create_enemy_from_data(world, ed, wave)
            enemies.append(e)
    else:
        # Regular wave: 1-3 enemies scaling with wave
        count = min(1 + wave // 2, 4)
        regulars = _pick_regulars(enemy_pool, count)
        for ed in regulars:
            e = create_enemy_from_data(world, ed, wave)
            enemies.append(e)

    return enemies


def choose_next_intent(enemy_comp: EnemyComponent, atk_comp: AttackComponent) -> None:
    """Decide what the enemy will do next turn."""
    pattern = enemy_comp.intent_pattern
    if pattern == "always_attack":
        enemy_comp.intent = "attack"
        enemy_comp.intent_value = atk_comp.attack
    elif pattern == "alternate":
        if enemy_comp.intent == "attack":
            enemy_comp.intent = "defend"
            enemy_comp.intent_value = 5
        else:
            enemy_comp.intent = "attack"
            enemy_comp.intent_value = atk_comp.attack
    elif pattern == "buff_then_attack":
        if enemy_comp.intent in ("defend", "buff"):
            enemy_comp.intent = "attack"
            enemy_comp.intent_value = atk_comp.attack
        else:
            enemy_comp.intent = "buff"
            enemy_comp.intent_value = 2  # +2 attack buff
    else:  # random
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
