"""Card factory — creates card entities from data dictionaries."""

from __future__ import annotations
import random
from ecs import World
from components import (
    CardComponent, KeywordComponent, AttackComponent,
    HealthComponent, MinionComponent, RenderComponent,
)


def create_card_entity(world: World, data: dict):
    """Create a card entity from a data dict (from JSON or Excel).

    Returns the Entity.
    """
    entity = world.create_entity()

    card = CardComponent(
        card_id=data["id"],
        name=data["name"],
        cost=data.get("cost", 1),
        card_type=data.get("type", "attack"),
        description=data.get("description", ""),
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
