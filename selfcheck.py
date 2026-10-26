"""Headless self-check for KARD.

Drives the pygame-free core: ECS bookkeeping, JSON data + card/enemy factories,
combat resolution, keyword rules, turn/deck state progression and room
generation. pygame, input_system, render_system and main.py are never imported,
so no window or display is needed.

Usage: python selfcheck.py
"""

import os
import random
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class Checker:
    """Collects failures so every check runs before exiting."""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passed: list[str] = []

    def check(self, label: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passed.append(label)
            print(f"  ok   {label}")
        else:
            message = f"{label}: {detail}" if detail else label
            self.failures.append(message)
            print(f"  FAIL {message}")

    def section(self, title: str) -> None:
        print(f"[{title}]")


def make_player(world, mods, hp=50, max_hp=80):
    """Create the player entity the combat helpers look for."""
    components = mods["components"]
    player = world.create_entity()
    world.add_component(player, components.PlayerComponent())
    world.add_component(player, components.HealthComponent(hp, max_hp))
    world.add_component(player, components.EnergyComponent(3, 3))
    world.add_component(player, components.DeckComponent([]))
    world.add_component(player, components.HandComponent())
    world.add_component(player, components.BoardComponent())
    return player


def check_ecs(c: Checker, mods: dict) -> None:
    """The ECS must add/query/remove/destroy components consistently."""
    c.section("ecs")
    World = mods["World"]
    components = mods["components"]

    world = World()
    e1 = world.create_entity()
    e2 = world.create_entity()
    c.check("entities get unique ids", e1 != e2 and e1.id != e2.id)

    world.add_component(e1, components.HealthComponent(10, 10))
    world.add_component(e1, components.AttackComponent(3))
    world.add_component(e2, components.HealthComponent(5, 5))
    c.check(
        "components are retrievable per entity",
        world.get_component(e1, components.HealthComponent).hp == 10
        and world.get_component(e2, components.HealthComponent).hp == 5
        and world.get_component(e2, components.AttackComponent) is None,
        "component lookup mismatch",
    )
    c.check(
        "get_entities_with intersects component sets",
        world.get_entities_with(components.HealthComponent) == {e1, e2}
        and world.get_entities_with(components.HealthComponent,
                                    components.AttackComponent) == {e1}
        and world.get_entities_with() == set(),
        "component intersection wrong",
    )
    world.destroy_entity(e2)
    c.check(
        "destroy_entity removes the entity and all its components",
        e2 not in world.entities
        and not world.has_component(e2, components.HealthComponent)
        and world.get_entities_with(components.HealthComponent) == {e1},
        "entity not fully destroyed",
    )
    world.clear()
    c.check(
        "clear() empties entities and component tables",
        not world.entities and not world.get_entities_with(
            components.HealthComponent),
        "clear() left state behind",
    )


def check_components_math(c: Checker, mods: dict) -> None:
    """Health/attack/energy/deck components must obey their contracts."""
    c.section("components")
    components = mods["components"]

    h = components.HealthComponent(10, 10)
    h.shield = 4
    dealt = h.take_damage(6)
    c.check(
        "damage is absorbed by shield before HP",
        h.shield == 0 and h.hp == 8 and dealt == 2 and h.alive,
        f"shield={h.shield} hp={h.hp} dealt={dealt}",
    )
    h.heal(100)
    c.check("heal caps at max HP", h.hp == 10 and h.alive, f"hp={h.hp}")
    h.take_damage(50)
    c.check(
        "HP reaching zero marks the entity dead",
        h.hp <= 0 and not h.alive,
        f"hp={h.hp}",
    )

    a = components.AttackComponent(5)
    a.temp_attack_buff = 2
    a.attacks_this_turn = 1
    c.check(
        "attack exposes effective attack and attack budget",
        a.effective_attack == 7 and not a.can_attack,
        f"eff={a.effective_attack} can={a.can_attack}",
    )
    a.max_attacks = 2
    c.check("windfury budget allows a second attack", a.can_attack)

    energy = components.EnergyComponent(1, 3)
    c.check(
        "energy spends only what is available and refreshes",
        energy.spend(2) is False and energy.current == 1
        and energy.spend(1) is True and energy.current == 0
        and (energy.refresh() or energy.current == 3),
        f"current={energy.current}",
    )

    deck = components.DeckComponent(cards=[1, 2, 3])
    first = deck.draw_one()
    deck.add_to_discard(first)
    second = deck.draw_one()
    c.check(
        "deck pops cards and recycles the discard pile when empty",
        first == 3 and second == 2 and deck.cards == [1]
        and deck.discard == [3],
        f"cards={deck.cards} discard={deck.discard}",
    )
    deck.cards = []
    refilled = deck.draw_one()
    c.check(
        "an empty deck reshuffles its discard pile",
        refilled == 3 and deck.cards == [] and deck.discard == [],
        f"drew={refilled} cards={deck.cards} discard={deck.discard}",
    )

    board = components.BoardComponent(max_minions=2)
    board.minions = [1, 2]
    c.check("board reports when it is full", board.is_full)


def check_data_and_factories(c: Checker, mods: dict) -> None:
    """JSON data must load and drive the card/enemy factories."""
    c.section("data + factories")
    World = mods["World"]
    components = mods["components"]
    create_card_entity = mods["create_card_entity"]
    create_minion_from_card = mods["create_minion_from_card"]
    pick_reward_cards = mods["pick_reward_cards"]
    create_enemy_from_data = mods["create_enemy_from_data"]
    generate_wave_enemies = mods["generate_wave_enemies"]
    choose_next_intent = mods["choose_next_intent"]
    load_cards_from_json = mods["load_cards_from_json"]
    load_enemies_from_json = mods["load_enemies_from_json"]
    load_cards = mods["load_cards"]
    load_enemies = mods["load_enemies"]

    data_dir = os.path.join(ROOT, "data")
    config_dir = os.path.join(ROOT, "config")
    cards = load_cards_from_json(os.path.join(data_dir, "cards.json"))
    enemies = load_enemies_from_json(os.path.join(data_dir, "enemies.json"))

    c.check(
        "cards.json loads a valid card pool",
        len(cards) >= 20 and all(c.get("id") and c.get("name") and c.get("type")
                                 for c in cards),
        f"cards={len(cards)}",
    )
    c.check(
        "enemies.json loads bosses and regulars",
        len(enemies) >= 10 and any(e.get("is_boss") for e in enemies),
        f"enemies={len(enemies)}",
    )
    c.check(
        "the Excel-or-JSON loader returns card/enemy pools",
        len(load_cards(config_dir, data_dir)) > 0
        and len(load_enemies(config_dir, data_dir)) > 0,
        "loader returned an empty pool",
    )

    world = World()
    strike = next(c for c in cards if c["id"] == "strike")
    ent = create_card_entity(world, strike)
    comp = world.get_component(ent, components.CardComponent)
    c.check(
        "create_card_entity copies id/type/damage",
        comp is not None and comp.card_id == "strike" and comp.card_type == "attack"
        and comp.damage == 6 and comp.cost == strike["cost"],
        f"got {comp!r}",
    )

    minion_card = next(c for c in cards if c["id"] == "shield_bearer")
    minion_ent = create_minion_from_card(world, create_card_entity(world, minion_card))
    c.check(
        "a minion card spawns attack/health/minion/keyword components",
        minion_ent is not None
        and world.get_component(minion_ent, components.HealthComponent).hp == minion_card["health"]
        and world.get_component(minion_ent, components.AttackComponent) is not None
        and world.get_component(minion_ent, components.MinionComponent) is not None
        and world.get_component(minion_ent, components.KeywordComponent).taunt,
        "minion components incomplete",
    )

    charge_card = next(c for c in cards if "Charge" in (c.get("keywords") or []))
    charge_minion = create_minion_from_card(world, create_card_entity(world, charge_card))
    charge_kw = world.get_component(charge_minion, components.KeywordComponent)
    c.check(
        "the Charge keyword is parsed onto the minion",
        charge_kw is not None and charge_kw.charge
        and charge_kw.active_keywords == ["charge"],
        f"keywords={getattr(charge_kw, 'active_keywords', None)}",
    )

    picks = pick_reward_cards(cards, 3)
    c.check(
        "reward picks are distinct and from the pool",
        len(picks) == 3 and len({p["id"] for p in picks}) == 3
        and all(p in cards for p in picks),
        f"picks={[p['id'] for p in picks]}",
    )

    slime = next(e for e in enemies if e["id"] == "slime")
    enemy_ent = create_enemy_from_data(world, slime, wave=3)
    eh = world.get_component(enemy_ent, components.HealthComponent)
    ea = world.get_component(enemy_ent, components.AttackComponent)
    c.check(
        "enemy stats scale with the wave number",
        eh.hp == 12 + 2 * 5 and ea.attack == 4 + 2 * 1,
        f"hp={eh.hp} atk={ea.attack}",
    )
    boss = next(e for e in enemies if e["is_boss"])
    boss_ent = create_enemy_from_data(world, boss, wave=5)
    bh = world.get_component(boss_ent, components.HealthComponent)
    ba = world.get_component(boss_ent, components.AttackComponent)
    c.check(
        "bosses get the HP/ATK multipliers",
        bh.max_hp == int((boss["hp"] + 4 * 5) * 4)
        and ba.attack == int((boss["attack"] + 4 * 1) * 2),
        f"hp={bh.max_hp} atk={ba.attack}",
    )

    wave5 = generate_wave_enemies(world, enemies, wave=5)
    c.check(
        "wave 5 spawns a boss plus support",
        len(wave5) >= 2 and any(
            world.get_component(e, components.EnemyComponent).is_boss for e in wave5
        ),
        f"spawned={len(wave5)}",
    )

    comp_a = components.EnemyComponent("x", "X", intent="attack",
                                       intent_pattern="always_attack")
    atk_a = components.AttackComponent(7)
    choose_next_intent(comp_a, atk_a)
    c.check(
        "always_attack keeps the enemy on attack",
        comp_a.intent == "attack" and comp_a.intent_value == 7,
        f"{comp_a.intent}/{comp_a.intent_value}",
    )
    comp_b = components.EnemyComponent("y", "Y", intent="attack",
                                       intent_pattern="alternate")
    atk_b = components.AttackComponent(4)
    choose_next_intent(comp_b, atk_b)
    first_intent = (comp_b.intent, comp_b.intent_value)
    choose_next_intent(comp_b, atk_b)
    c.check(
        "alternate swaps attack and defend intents",
        first_intent == ("defend", 5)
        and comp_b.intent == "attack" and comp_b.intent_value == 4,
        f"first={first_intent} second={comp_b.intent}",
    )
    comp_c = components.EnemyComponent("z", "Z", intent="attack",
                                       intent_pattern="buff_then_attack")
    choose_next_intent(comp_c, components.AttackComponent(5))
    buff = (comp_c.intent, comp_c.intent_value)
    choose_next_intent(comp_c, components.AttackComponent(5))
    c.check(
        "buff_then_attack buffs before attacking",
        buff == ("buff", 2) and comp_c.intent == "attack",
        f"buff={buff} next={comp_c.intent}",
    )


def check_combat(c: Checker, mods: dict) -> None:
    """Card, minion and enemy attacks must resolve damage correctly."""
    c.section("combat")
    World = mods["World"]
    components = mods["components"]
    GameState = mods["GameState"]
    Phase = mods["Phase"]
    CombatSystem = mods["CombatSystem"]
    create_card_entity = mods["create_card_entity"]
    create_minion_from_card = mods["create_minion_from_card"]

    world = World()
    gs = GameState()
    combat = CombatSystem(gs)
    player = make_player(world, mods)
    ph = world.get_component(player, components.HealthComponent)

    enemy = world.create_entity()
    world.add_component(enemy, components.HealthComponent(30, 30))
    world.add_component(enemy, components.AttackComponent(5))
    world.add_component(enemy, components.EnemyComponent("dummy", "Dummy"))

    strike = {"id": "strike", "name": "Strike", "cost": 1, "type": "attack",
              "damage": 6, "target": "enemy"}
    combat.resolve_card(world, create_card_entity(world, strike), enemy)
    c.check(
        "an attack card damages its target and counts as a card played",
        world.get_component(enemy, components.HealthComponent).hp == 24
        and world.get_component(player, components.PlayerComponent).cards_played == 1,
        f"hp={world.get_component(enemy, components.HealthComponent).hp}",
    )

    defend = {"id": "defend", "name": "Defend", "cost": 1, "type": "skill",
              "shield": 5, "target": "self"}
    combat.resolve_card(world, create_card_entity(world, defend))
    c.check("a shield skill card adds shield to the player", ph.shield == 5,
            f"shield={ph.shield}")

    ph.hp = 40
    vampiric = {"id": "vampiric_touch", "name": "Vampiric Touch", "cost": 1,
                "type": "attack", "damage": 4, "keywords": ["Lifesteal"],
                "target": "enemy"}
    combat.resolve_card(world, create_card_entity(world, vampiric), enemy)
    c.check(
        "lifesteal heals the player for the damage dealt",
        ph.hp == 44 and ph.shield == 5,
        f"hp={ph.hp} shield={ph.shield}",
    )

    minion_card = {"id": "mk", "name": "Test Minion", "cost": 1, "type": "minion",
                   "attack": 3, "health": 4, "keywords": ["Taunt"], "target": "none"}
    combat.resolve_card(world, create_card_entity(world, minion_card))
    board = world.get_component(player, components.BoardComponent)
    c.check(
        "a minion card puts a minion on the board",
        len(board.minions) == 1
        and world.get_component(board.minions[0], components.HealthComponent).hp == 4
        and world.get_component(board.minions[0], components.AttackComponent).attack == 3,
        f"board={len(board.minions)}",
    )

    # Minion vs minion in a clean world (no taunt minions to redirect to).
    duel = World()
    duel_gs = GameState()
    duel_combat = CombatSystem(duel_gs)
    make_player(duel, mods)
    plain = dict(minion_card, id="plain", name="Plain", keywords=[])
    attacker = create_minion_from_card(duel, create_card_entity(duel, plain))
    target = duel.create_entity()
    duel.add_component(target, components.HealthComponent(10, 10))
    duel.add_component(target, components.AttackComponent(2))
    duel_combat.minion_attack(duel, attacker, target)
    c.check(
        "a minion attack damages both sides",
        duel.get_component(target, components.HealthComponent).hp == 7
        and duel.get_component(attacker, components.HealthComponent).hp == 2
        and duel.get_component(attacker, components.AttackComponent).attacks_this_turn == 1,
        f"target_hp={duel.get_component(target, components.HealthComponent).hp} "
        f"attacker_hp={duel.get_component(attacker, components.HealthComponent).hp}",
    )

    # Taunt redirects a minion attack to the taunter.
    taunt_world = World()
    taunt_gs = GameState()
    taunt_combat = CombatSystem(taunt_gs)
    taunt_player = make_player(taunt_world, mods)
    taunter = create_minion_from_card(
        taunt_world, create_card_entity(taunt_world, minion_card))
    other = create_minion_from_card(
        taunt_world,
        create_card_entity(taunt_world, dict(minion_card, id="mk2", name="Other",
                                             keywords=[])))
    scout = create_minion_from_card(
        taunt_world, create_card_entity(taunt_world, dict(minion_card, id="mk3",
                                                          name="Scout", attack=3,
                                                          keywords=[])))
    taunt_combat.minion_attack(taunt_world, scout, other)
    c.check(
        "taunt redirects the attack away from the intended target",
        taunt_world.get_component(other, components.HealthComponent).hp == 4
        and taunt_world.get_component(taunter, components.HealthComponent).hp == 1,
        f"other={taunt_world.get_component(other, components.HealthComponent).hp} "
        f"taunt={taunt_world.get_component(taunter, components.HealthComponent).hp}",
    )
    c.check(
        "taunt world player stayed untouched",
        taunt_world.get_component(taunt_player, components.HealthComponent).hp == 50,
    )

    # Enemy attacks player through shield, then kills -> GAME_OVER.
    ph.hp, ph.max_hp, ph.shield = 5, 80, 4
    combat.enemy_attack_player(world, enemy)
    c.check(
        "an enemy attack is soaked by shield first",
        ph.hp == 4 and ph.shield == 0 and gs.phase is not Phase.GAME_OVER,
        f"hp={ph.hp} shield={ph.shield}",
    )
    world.get_component(enemy, components.AttackComponent).attack = 10
    combat.enemy_attack_player(world, enemy)
    c.check(
        "a lethal enemy attack drops HP to 0 or below and sets GAME_OVER",
        ph.hp <= 0 and gs.phase is Phase.GAME_OVER,
        f"hp={ph.hp} phase={gs.phase}",
    )

    # Poisonous kills the defender and dead entities leave the ECS.
    poison_world = World()
    poison_gs = GameState()
    poison_combat = CombatSystem(poison_gs)
    make_player(poison_world, mods)
    poisoner = create_minion_from_card(
        poison_world,
        create_card_entity(poison_world, dict(minion_card, id="poisoner",
                                              name="Poisoner", keywords=[])))
    poison_world.get_component(poisoner, components.KeywordComponent).poisonous = True
    victim = poison_world.create_entity()
    poison_world.add_component(victim, components.HealthComponent(30, 30))
    poison_world.add_component(victim, components.AttackComponent(0))
    poison_combat.minion_attack(poison_world, poisoner, victim)
    c.check(
        "poisonous kills through any amount of HP and cleans the entity up",
        poison_world.get_component(victim, components.HealthComponent) is None
        and victim not in poison_world.entities,
        "victim survived poison or was not destroyed",
    )


def check_keywords(c: Checker, mods: dict) -> None:
    """Keyword rules must shield, gate attacks and honour taunt."""
    c.section("keywords")
    World = mods["World"]
    components = mods["components"]
    GameState = mods["GameState"]
    KeywordSystem = mods["KeywordSystem"]

    world = World()
    ks = KeywordSystem(GameState())

    shielded = world.create_entity()
    world.add_component(shielded, components.KeywordComponent(divine_shield=True))
    world.add_component(shielded, components.RenderComponent())
    c.check(
        "divine shield absorbs one hit and is consumed",
        ks.on_damage_pre(world, shielded, 9) == 0
        and not world.get_component(shielded, components.KeywordComponent).divine_shield
        and ks.on_damage_pre(world, shielded, 9) == 9,
        "divine shield did not absorb exactly one hit",
    )

    fresh = world.create_entity()
    world.add_component(fresh, components.MinionComponent("Fresh", "player"))
    world.add_component(fresh, components.AttackComponent(2))
    world.add_component(fresh, components.KeywordComponent())
    charged = world.create_entity()
    world.add_component(charged, components.MinionComponent("Charged", "player"))
    world.add_component(charged, components.AttackComponent(2))
    world.add_component(charged, components.KeywordComponent(charge=True))
    rushing = world.create_entity()
    world.add_component(rushing, components.MinionComponent("Rushing", "player"))
    world.add_component(rushing, components.AttackComponent(2))
    world.add_component(rushing, components.KeywordComponent(rush=True))
    c.check(
        "charge/rush bypass the just-played summoning lock",
        ks.can_minion_attack(world, fresh) is False
        and ks.can_minion_attack(world, charged) is True
        and ks.can_minion_attack(world, rushing) is True,
        "summoning lock wrong for charge/rush",
    )

    taunter = world.create_entity()
    world.add_component(taunter, components.MinionComponent("Taunt", "enemy"))
    world.add_component(taunter, components.HealthComponent(9, 9))
    world.add_component(taunter, components.KeywordComponent(taunt=True))
    targets = ks.get_valid_attack_targets(world, "player")
    c.check(
        "taunt restricts the valid attack targets to the taunter",
        targets == [taunter],
        f"targets={targets}",
    )
    world.get_component(taunter, components.KeywordComponent).taunt = False
    c.check(
        "without taunt the enemy face is a legal target (empty list)",
        ks.get_valid_attack_targets(world, "player") == [],
    )

    poison_attacker = world.create_entity()
    world.add_component(poison_attacker, components.KeywordComponent(poisonous=True))
    victim = world.create_entity()
    world.add_component(victim, components.HealthComponent(20, 20))
    ks.on_after_combat(world, poison_attacker, victim)
    c.check(
        "poisonous combat sets the defender to 0 HP",
        world.get_component(victim, components.HealthComponent).hp == 0,
    )


def check_turn_flow(c: Checker, mods: dict) -> None:
    """End-of-turn must refresh energy, draw a card and switch phase."""
    c.section("turn flow")
    World = mods["World"]
    components = mods["components"]
    GameState = mods["GameState"]
    Phase = mods["Phase"]
    CombatSystem = mods["CombatSystem"]

    world = World()
    gs = GameState()
    gs.phase = Phase.PLAYER_TURN
    gs.selected_card_entity = object()
    combat = CombatSystem(gs)
    player = make_player(world, mods)
    energy = world.get_component(player, components.EnergyComponent)
    energy.current = 1
    hand = world.get_component(player, components.HandComponent)
    deck = world.get_component(player, components.DeckComponent)
    deck.cards = [11, 12, 13]

    minion = world.create_entity()
    world.add_component(minion, components.HealthComponent(5, 5))
    world.add_component(minion, components.AttackComponent(2))
    world.add_component(minion, components.MinionComponent("M", "player"))
    world.get_component(minion, components.AttackComponent).attacks_this_turn = 1

    combat.end_player_turn(world)

    c.check(
        "end_player_turn switches to the enemy turn and clears selection",
        gs.phase is Phase.ENEMY_TURN and gs.selected_card_entity is None,
        f"phase={gs.phase}",
    )
    c.check(
        "end_player_turn refreshes energy and draws exactly one card",
        energy.current == energy.max_energy and len(hand.cards) == 1
        and len(deck.cards) == 2,
        f"energy={energy.current} hand={len(hand.cards)} deck={len(deck.cards)}",
    )
    c.check(
        "end_player_turn resets minion attack budgets and played flags",
        world.get_component(minion, components.AttackComponent).attacks_this_turn == 0
        and world.get_component(minion, components.MinionComponent).just_played is False,
        "minion turn state not reset",
    )


def check_rooms(c: Checker, mods: dict) -> None:
    """Room generation constraints must hold regardless of RNG."""
    c.section("rooms")
    random.seed(20261026)
    generate_next_room = mods["generate_next_room"]
    RoomType = mods["RoomType"]
    battle_gold_reward = mods["battle_gold_reward"]
    merchant_card_price = mods["merchant_card_price"]
    merchant_remove_price = mods["merchant_remove_price"]

    c.check(
        "the first room is always a battle",
        all(generate_next_room(None, 1).room_type is RoomType.BATTLE
            for _ in range(20)),
        "first room varies",
    )
    c.check(
        "every fifth room is an elite",
        all(generate_next_room(RoomType.BATTLE, n).room_type is RoomType.ELITE
            for n in (5, 10, 15, 20)),
        "elite milestone missing",
    )
    rooms = [generate_next_room(RoomType.BATTLE, 3).room_type for _ in range(60)]
    c.check(
        "the weighted pool only produces known room types",
        all(r in set(RoomType) for r in rooms),
        f"types={set(rooms)}",
    )
    c.check(
        "a merchant is never followed by another merchant",
        all(generate_next_room(RoomType.MERCHANT, 3).room_type is not RoomType.MERCHANT
            for _ in range(60)),
        "consecutive merchant generated",
    )
    c.check(
        "a campfire is never followed by another campfire",
        all(generate_next_room(RoomType.CAMPFIRE, 3).room_type is not RoomType.CAMPFIRE
            for _ in range(60)),
        "consecutive campfire generated",
    )
    c.check(
        "battle gold stays inside the normal/elite brackets",
        all(12 <= battle_gold_reward(False) <= 25 for _ in range(40))
        and all(30 <= battle_gold_reward(True) <= 50 for _ in range(40)),
        "gold reward out of range",
    )
    c.check(
        "merchant prices increase with rarity",
        all(25 <= merchant_card_price("common") <= 35 for _ in range(20))
        and all(85 <= merchant_card_price("epic") <= 120 for _ in range(20))
        and merchant_remove_price() == 50,
        "merchant pricing wrong",
    )


def main() -> int:
    c = Checker()
    try:
        import components
        from card_factory import (
            create_card_entity, create_minion_from_card, pick_reward_cards,
        )
        from ecs import World
        from enemy_factory import (
            choose_next_intent, create_enemy_from_data, generate_wave_enemies,
        )
        from excel_loader import (
            load_cards, load_cards_from_json, load_enemies, load_enemies_from_json,
        )
        from game_state import GameState, Phase
        from rooms.room_system import (
            RoomType, battle_gold_reward, generate_next_room,
            merchant_card_price, merchant_remove_price,
        )
        from systems.combat_system import CombatSystem
        from systems.keyword_system import KeywordSystem

        mods = {
            "World": World,
            "components": components,
            "GameState": GameState,
            "Phase": Phase,
            "CombatSystem": CombatSystem,
            "KeywordSystem": KeywordSystem,
            "create_card_entity": create_card_entity,
            "create_minion_from_card": create_minion_from_card,
            "pick_reward_cards": pick_reward_cards,
            "create_enemy_from_data": create_enemy_from_data,
            "generate_wave_enemies": generate_wave_enemies,
            "choose_next_intent": choose_next_intent,
            "load_cards_from_json": load_cards_from_json,
            "load_enemies_from_json": load_enemies_from_json,
            "load_cards": load_cards,
            "load_enemies": load_enemies,
            "generate_next_room": generate_next_room,
            "RoomType": RoomType,
            "battle_gold_reward": battle_gold_reward,
            "merchant_card_price": merchant_card_price,
            "merchant_remove_price": merchant_remove_price,
        }

        check_ecs(c, mods)
        check_components_math(c, mods)
        check_data_and_factories(c, mods)
        check_combat(c, mods)
        check_keywords(c, mods)
        check_turn_flow(c, mods)
        check_rooms(c, mods)
    except Exception as exc:  # noqa: BLE001 - report any crash as a failure
        print(f"FAIL unexpected {type(exc).__name__}: {exc}")
        return 1

    if c.failures:
        print(f"FAIL {len(c.failures)} check(s) failed: {c.failures[0]}")
        return 1

    print(
        f"selfcheck ok: {len(c.passed)} checks - ECS lifecycle, component maths, "
        "JSON/Excel card+enemy factories and wave scaling, card/minion/enemy combat, "
        "keyword rules, turn-deck-energy flow and room-generation constraints"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
