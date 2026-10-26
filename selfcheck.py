"""Headless self-check for 「文字传奇」 logic layers.

Imports only the tkinter-free layers: ecs/ (ECS), mvvm/model.py, mvc/ and
skills/.  The Tkinter views (mvvm/view.py, mvc/view_task.py, common/fonts.py)
and main.py are never imported, so no window is created.

Run from the project root:  .venv\\Scripts\\python.exe selfcheck.py
"""
import os
import sys
from unittest import mock

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# The project prints Chinese diagnostics while loading game_data.xlsx; keep them
# readable when stdout is a pipe with a legacy code page.
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ecs.components import (
    ExpComponent,
    HPComponent,
    MonsterComponent,
    NameComponent,
    RespawnComponent,
)
from ecs.entities import create_monster, create_player
from ecs.systems import _check_level_up, combat_system, respawn_system
from ecs.world import World
from mvc.controller_task import TaskController
from mvc.model_task import Task, TaskModel
from mvvm.model import GameModel
from skills.skill_components import SkillSlotComponent
from skills.skill_defs import get_skill_defs
from skills.skill_vm import SkillViewModel


def _check(condition, message):
    if not condition:
        raise AssertionError(message)


def check_world():
    """ECS World: entity lifecycle and component queries."""
    world = World()
    eid = world.create_entity()
    _check(isinstance(eid, int) and eid >= 1, "entity id is not a positive int")
    _check(world.entity_exists(eid), "new entity not registered")

    hp = HPComponent(hp=10)
    world.add_component(eid, hp)
    _check(world.get_component(eid, HPComponent) is hp, "component not stored")
    _check(world.has_component(eid, HPComponent), "has_component disagrees")

    other = world.create_entity()
    world.add_component(other, NameComponent("other"))
    rows = world.get_components(HPComponent)
    _check(len(rows) == 1 and rows[0][0] == eid,
           f"get_components(HPComponent) wrong: {rows}")
    _check(world.get_entities_with(NameComponent) == [other],
           "get_entities_with(NameComponent) wrong")
    _check(world.get_components(HPComponent, NameComponent) == [],
           "query matched an entity missing one component")

    world.remove_component(eid, HPComponent)
    _check(not world.has_component(eid, HPComponent), "component not removed")
    world.destroy_entity(other)
    _check(not world.entity_exists(other), "entity not destroyed")


def check_combat():
    """Combat: deterministic damage, crit, dodge and kill accounting."""
    world = World()
    player = create_player(world)
    monster = create_monster(world, name="训练假人", level=1, affix_id="")
    mon_hp = world.get_component(monster, HPComponent)
    player_hp = world.get_component(player, HPComponent)
    start = mon_hp.hp

    logs = []
    with mock.patch("ecs.systems.random.randint", return_value=11), \
            mock.patch("ecs.systems.random.random", return_value=0.99):
        combat_system(world, 0.0, player, monster, logs.append)
    _check(mon_hp.hp == start - 11,
           f"normal hit dealt {start - mon_hp.hp} instead of 11")
    _check(player_hp.hp == player_hp.max_hp - 11,
           f"counter-attack dealt {player_hp.max_hp - player_hp.hp}")

    # Crit path: random()==0.0 triggers crit, and also the player's dodge.
    world2 = World()
    player2 = create_player(world2)
    monster2 = create_monster(world2, name="暴击假人", level=1, affix_id="")
    mon2_hp = world2.get_component(monster2, HPComponent)
    player2_hp = world2.get_component(player2, HPComponent)
    start2 = mon2_hp.hp
    with mock.patch("ecs.systems.random.randint", return_value=11), \
            mock.patch("ecs.systems.random.random", return_value=0.0):
        combat_system(world2, 0.0, player2, monster2, logs.append)
    _check(mon2_hp.hp == start2 - 22,
           f"crit dealt {start2 - mon2_hp.hp} instead of 22")
    _check(player2_hp.hp == player2_hp.max_hp,
           "dodged counter-attack still hurt the player")

    # Kill -> exp reward -> respawn countdown.
    world3 = World()
    player3 = create_player(world3)
    monster3 = create_monster(world3, name="脆皮假人", level=1, affix_id="")
    mon3_hp = world3.get_component(monster3, HPComponent)
    exp3 = world3.get_component(player3, ExpComponent)
    mon3_hp.hp = 1
    with mock.patch("ecs.systems.random.randint", return_value=11), \
            mock.patch("ecs.systems.random.random", return_value=0.99):
        combat_system(world3, 0.0, player3, monster3, logs.append)
    _check(mon3_hp.hp == 0 and not mon3_hp.alive, "monster did not die at 0 HP")
    reward = world3.get_component(monster3, MonsterComponent).exp_reward
    _check(exp3.exp == reward, f"kill gave {exp3.exp} exp, expected {reward}")
    resp = world3.get_component(monster3, RespawnComponent)
    _check(resp.respawn_timer == resp.respawn_time > 0,
           "respawn timer not started on death")
    for _ in range(resp.respawn_time):
        respawn_system(world3, 1.0, logs.append)
    _check(mon3_hp.alive and mon3_hp.hp == mon3_hp.max_hp,
           "monster did not respawn")
    _check(resp.respawn_timer == 0, "respawn timer not reset")


def check_level_progression():
    """Level-up: overflow exp flows into the exp pool, max HP grows."""
    world = World()
    player = create_player(world)
    exp_c = world.get_component(player, ExpComponent)
    hp_c = world.get_component(player, HPComponent)
    _check(exp_c.level == 1 and exp_c.threshold() == 30,
           f"unexpected level threshold {exp_c.threshold()}")
    exp_c.exp = 35
    hp_c.hp = 40
    logs = []
    _check_level_up(world, player, logs.append)
    _check(exp_c.level == 2, f"level is {exp_c.level}, expected 2")
    _check(exp_c.exp == 0, f"exp not reset: {exp_c.exp}")
    _check(exp_c.exp_pool == 5, f"overflow pool is {exp_c.exp_pool}, expected 5")
    _check(hp_c.max_hp == 120 and hp_c.hp == 120,
           f"max HP not grown: {hp_c.max_hp}/{hp_c.hp}")
    _check(any("Lv.2" in line for line in logs), "no level-up log line")


def check_tasks():
    """MVC task system: progress, completion and one-shot reward claim."""
    model = TaskModel()
    kill = Task(id="k1", name="击杀 x2", desc="", target_value=2,
                reward_exp=20, event_type="kill", monster_name="*")
    level = Task(id="l1", name="升到 Lv.3", desc="", target_value=3,
                 reward_exp=25, event_type="level_up")
    model.add_task(kill)
    model.add_task(level)
    controller = TaskController(model)

    controller.on_monster_killed("任意怪")
    _check(kill.current_value == 1 and not kill.done, "kill progress not 1/2")
    controller.on_monster_killed("任意怪")
    _check(kill.done and kill.current_value == 2, "kill task did not complete")

    controller.on_level_up(2)
    _check(not level.done, "level task completed too early")
    controller.on_level_up(3)
    _check(level.done, "level task did not complete at Lv.3")

    _check(model.claim_reward("k1") == 20, "reward not granted")
    _check(model.claim_reward("k1") == 0, "reward granted twice")
    _check(kill.claimed and kill.name.endswith("✅"), "claim not recorded")
    _check(model.claim_reward("l1") == 25, "second reward not granted")
    _check(model.claim_reward("missing") == 0, "unknown task paid a reward")


def check_skills():
    """Skills: unlock rule, exp-pool cost, cooldown lock and ticking."""
    world = World()
    player = create_player(world)
    monster = create_monster(world, name="木桩", level=1, affix_id="")
    _check(world.get_component(player, SkillSlotComponent) is None,
           "player already had a skill slot")

    vm = SkillViewModel(world, player)
    slot = world.get_component(player, SkillSlotComponent)
    _check(slot.skill_ids == ["flame_slash"],
           f"starter skills wrong: {slot.skill_ids}")
    defs = get_skill_defs()
    flame = defs["flame_slash"]
    _check(callable(flame.get("effect")), "flame_slash has no effect function")
    cost = flame["cost_exp_pool"]
    cooldown = flame["cooldown"]
    _check(cooldown > 0, "flame_slash cooldown is 0")

    exp_c = world.get_component(player, ExpComponent)
    exp_c.exp_pool = cost * 3
    mon_hp = world.get_component(monster, HPComponent)
    start = mon_hp.hp
    logs = []

    _check(vm.cmd_use_skill("flame_slash", monster, logs.append) is True,
           "flame_slash cast failed")
    _check(mon_hp.hp == start - 19,
           f"flame_slash dealt {start - mon_hp.hp} instead of 19 (1.5*ATK)")
    _check(exp_c.exp_pool == cost * 2, "exp pool not charged")
    _check(slot.cooldowns["flame_slash"] == cooldown, "cooldown not set")

    _check(vm.cmd_use_skill("flame_slash", monster, logs.append) is False,
           "skill cast while on cooldown")
    _check(exp_c.exp_pool == cost * 2, "cooldown-locked cast still charged exp")
    cooling = vm.get_skill_states()
    _check(any(s["id"] == "flame_slash" and not s["ready"] for s in cooling),
           "flame_slash reported ready while cooling down")

    vm.tick_cooldowns(cooldown)
    _check(slot.cooldowns["flame_slash"] <= 0, "cooldown did not tick down")

    exp_c.exp_pool = 0
    _check(vm.cmd_use_skill("flame_slash", monster, logs.append) is False,
           "cast succeeded with an empty exp pool")
    _check(vm.cmd_use_skill("blood_rage", monster, logs.append) is False,
           "locked skill was castable")

    vm.check_level_unlocks(3, logs.append)
    _check("heal" in slot.skill_ids, "heal not unlocked at Lv.3")
    states = vm.get_skill_states()
    _check(len(states) == len(slot.skill_ids), "skill state list mismatch")
    _check(any(s["id"] == "flame_slash" and s["ready"] for s in states),
           "flame_slash still cooling down after the tick")


def check_game_model():
    """GameModel (MVVM model): state accessors and safe out-of-range input."""
    model = GameModel()
    state = model.get_player_state()
    _check(state.get("level") == 1, f"player level wrong: {state.get('level')}")
    _check(state.get("hp") == 100 and state.get("max_hp") == 100,
           f"player HP wrong: {state.get('hp')}/{state.get('max_hp')}")
    _check(state.get("atk") == 13, f"player ATK wrong: {state.get('atk')}")
    _check(state.get("equipment") == [], "player starts equipped")
    monsters = model.get_monster_states()
    _check(len(monsters) == 6, f"expected 6 monsters, got {len(monsters)}")
    _check(all(m["alive"] for m in monsters), "monsters start dead")
    _check(model.is_player_dead() is False, "player starts dead")
    model.attack_monster(999)
    model.attack_monster(-1)
    _check(model.is_player_dead() is False, "out-of-range attack hurt the player")


CHECKS = (
    ("ECS world", check_world),
    ("combat", check_combat),
    ("level progression", check_level_progression),
    ("task system", check_tasks),
    ("skill system", check_skills),
    ("game model", check_game_model),
)


def main():
    passed = []
    for name, func in CHECKS:
        try:
            func()
        except AssertionError as exc:
            print(f"FAIL: {name}: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001 - report any unexpected error
            print(f"FAIL: {name}: {type(exc).__name__}: {exc}")
            return 1
        passed.append(name)
    print("selfcheck ok: " + ", ".join(passed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
