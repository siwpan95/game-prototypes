# -*- coding: utf-8 -*-
"""test_m5_save — M5 存档 / 读档往返（headless，全绿）。

验收：
  - save -> load 往返：world 网格逐格一致（含所有 z 层）。
  - player 的 fx/fy/hp/max_hp/alive/inventory 还原一致。
  - daynight.t 一致；survival 的 spawn_x/y 与 hp 一致。
  - creatures 还原后 kind/hp/state/count 与存档一致。
  - 用不同 registry 实例 load 也能工作（注册表隔离）。
  - 损坏 / 缺失路径的容错行为符合定义。
"""

from __future__ import annotations

import os
import tempfile

from mcclone.core.block_registry import BlockRegistry, STONE, DIRT, GRASS, WATER, SAND
from mcclone.core.block_world import BlockWorld
from mcclone.core.daynight import DayNight
from mcclone.player.player import Player
from mcclone.systems.survival import SurvivalConfig, SurvivalSystem
from mcclone.creatures.entity import AIState, CreatureKind
from mcclone.creatures.system import CreatureSystem

from mcclone.world.savegame import SaveGame, save_game, load_game


# ── 构造小世界的工具 ──
def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def _small_world(reg, w=12, h=12, depth=3):
    """手工确定性小世界：底层实心 + 表层草 + 水洼 + 各 z 层标记。"""
    world = BlockWorld(w, h, depth)
    for x in range(w):
        for y in range(4):                      # 底 4 行石头
            world.set(x, y, 0, STONE)
        world.set(x, 4, 0, DIRT)
        world.set(x, 5, 0, GRASS)               # 地表
    # 一处水洼（z=0）
    for x in range(2, 5):
        world.set(x, 0, 0, WATER)
    # z=1 / z=2 层放不同方块，验证多层还原
    for x in range(w):
        world.set(x, 0, 1, DIRT)
        world.set(x, 0, 2, STONE)
    world.set(3, 3, 2, GRASS)
    return world


def _make_state(reg, world, seed=42):
    """组装一套运行期游戏对象（含被改过的状态），用于往返测试。"""
    player = Player(5.0, 6.0, reg)
    player.hp = 7.0
    player.max_hp = 20.0
    player.alive = True
    player.facing = -1
    player.vx = 1.5
    player.vy = -2.0
    player.on_ground = True
    player.selected_slot = 2
    player.hotbar = [GRASS, DIRT, STONE, WATER, SAND, 0]
    # 改背包：第 1 槽放 10 个 stone，第 3 槽放 5 个 grass
    player.inventory._items[1] = (STONE, 10)
    player.inventory._items[3] = (GRASS, 5)
    player.inventory._selected = player.selected_slot
    player.held_id = player.hotbar[player.selected_slot]
    player._sync_aabb()

    survival = SurvivalSystem(player, SurvivalConfig())
    survival.set_spawn(5.0, 6.0)
    # survival 经 player 写 hp/hunger：再手动偏离以验证还原
    player.hunger = 11.0
    player.max_hunger = 20.0

    daynight = DayNight(600.0)
    daynight.update(123.0)          # 推进时间，得到非 0 的 t

    creatures = CreatureSystem(world, reg, None, None, seed=seed)
    creatures.spawn(CreatureKind.COW, 2.0, 5.0)
    creatures.spawn(CreatureKind.PIG, 7.0, 5.0)
    z = creatures.spawn(CreatureKind.ZOMBIE, 9.0, 5.0)
    z.hp = 12.0
    z.state = AIState.ATTACK
    return {
        "world": world, "player": player, "survival": survival,
        "daynight": daynight, "creatures": creatures, "seed": seed,
    }


def _tmp_path():
    fd, path = tempfile.mkstemp(suffix=".json", prefix="m5_save_")
    os.close(fd)
    os.remove(path)                 # 仅借用路径，文件稍后创建
    return path


# ─────────────────────────────────────────────────────────────────────────
# 往返测试
# ─────────────────────────────────────────────────────────────────────────

def test_world_grid_roundtrip_exact_per_cell():
    reg = _reg()
    world = _small_world(reg)
    st = _make_state(reg, world)
    path = _tmp_path()
    try:
        save_game(path, **st, registry=reg, saved_at="T0")
        loaded = load_game(path, reg)
        lw = loaded["world"]
        assert lw.width == world.width and lw.height == world.height and lw.depth == world.depth
        for z in range(world.depth):
            for y in range(world.height):
                for x in range(world.width):
                    assert lw.get(x, y, z) == world.get(x, y, z)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_player_coordinates_restored():
    reg = _reg()
    world = _small_world(reg)
    st = _make_state(reg, world)
    path = _tmp_path()
    try:
        save_game(path, **st, registry=reg, saved_at="T0")
        loaded = load_game(path, reg)
        p = loaded["player"]
        assert p.fx == 5.0
        assert p.fy == 6.0
        assert p.vx == 1.5
        assert p.vy == -2.0
        assert p.facing == -1
        assert p.on_ground is True
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_player_survival_state_restored():
    reg = _reg()
    world = _small_world(reg)
    st = _make_state(reg, world)
    path = _tmp_path()
    try:
        save_game(path, **st, registry=reg, saved_at="T0")
        loaded = load_game(path, reg)
        p = loaded["player"]
        assert p.hp == 7.0
        assert p.max_hp == 20.0
        assert p.alive is True
        assert p.hunger == 11.0
        assert p.max_hunger == 20.0
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_player_inventory_restored():
    reg = _reg()
    world = _small_world(reg)
    st = _make_state(reg, world)
    path = _tmp_path()
    try:
        save_game(path, **st, registry=reg, saved_at="T0")
        loaded = load_game(path, reg)
        p = loaded["player"]
        # 背包逐槽还原一致（与存档前对象完全相等）
        assert p.inventory.as_list() == st["player"].inventory.as_list()
        # stone / grass 总数与存档前一致（含构造期预填）
        assert p.inventory.count(STONE) == st["player"].inventory.count(STONE)
        assert p.inventory.count(GRASS) == st["player"].inventory.count(GRASS)
        # 选中槽与手持 id 一致
        assert p.selected_slot == 2
        assert p.held_id == p.hotbar[p.selected_slot]
        # 槽位字典逐一一致（直接比对还原的 _items）
        assert p.inventory.slot(1) == (STONE, 10)
        assert p.inventory.slot(3) == (GRASS, 5)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_daynight_t_restored():
    reg = _reg()
    world = _small_world(reg)
    st = _make_state(reg, world)
    saved_t = st["daynight"].t()
    path = _tmp_path()
    try:
        save_game(path, **st, registry=reg, saved_at="T0")
        loaded = load_game(path, reg)
        assert abs(loaded["daynight"].t() - saved_t) < 1e-9
        assert loaded["daynight"].day_length_sec == 600.0
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_survival_spawn_and_hp_restored():
    reg = _reg()
    world = _small_world(reg)
    st = _make_state(reg, world)
    path = _tmp_path()
    try:
        save_game(path, **st, registry=reg, saved_at="T0")
        loaded = load_game(path, reg)
        sv = loaded["survival"]
        assert sv._spawn_x == 5.0
        assert sv._spawn_y == 6.0
        # hp 经 player 还原
        assert loaded["player"].hp == 7.0
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_creatures_kind_hp_state_count_restored():
    reg = _reg()
    world = _small_world(reg)
    st = _make_state(reg, world)
    path = _tmp_path()
    try:
        save_game(path, **st, registry=reg, saved_at="T0")
        loaded = load_game(path, reg)
        cs = loaded["creatures"]
        assert cs.count() == 3
        kinds = {c.kind for c in cs.creatures}
        assert CreatureKind.COW in kinds
        assert CreatureKind.PIG in kinds
        assert CreatureKind.ZOMBIE in kinds
        # 僵尸被改过的 hp/state 应还原
        z = [c for c in cs.creatures if c.kind == CreatureKind.ZOMBIE][0]
        assert z.hp == 12.0
        assert z.state == AIState.ATTACK
        # 被动生物默认满血满 state
        cow = [c for c in cs.creatures if c.kind == CreatureKind.COW][0]
        assert cow.hp == cow.max_hp
        assert cow.fx == 2.0 and cow.fy == 5.0
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_load_with_different_registry_instance():
    """注册表隔离：用新 registry 实例 load 也应成功（生物种类不依赖 registry）。"""
    reg_a = _reg()
    world = _small_world(reg_a)
    st = _make_state(reg_a, world)
    path = _tmp_path()
    try:
        save_game(path, **st, registry=reg_a, saved_at="T0")
        reg_b = BlockRegistry()
        reg_b.load_defaults()       # 全新实例，与 reg_a 内存隔离
        loaded = load_game(path, reg_b)
        assert loaded["world"].get(3, 3, 2) == GRASS
        assert loaded["creatures"].count() == 3
        assert loaded["player"].inventory.as_list() == st["player"].inventory.as_list()
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_savegame_dataclass_roundtrip():
    """SaveGame（Serializable dataclass）自身 to_dict/from_dict 往返一致。"""
    sg = SaveGame(version=1, seed=7, saved_at="TS",
                  world={"width": 1, "blocks": {}},
                  daynight={"t": 0.25, "day_length_sec": 600.0},
                  player={"fx": 1.0, "hp": 5.0},
                  survival={"spawn_x": 1.0, "spawn_y": 2.0},
                  creatures=[{"kind": "COW", "x": 1.0, "y": 2.0}])
    d = sg.to_dict()
    back = SaveGame.from_dict(d)
    assert back.seed == 7
    assert back.saved_at == "TS"
    assert back.world == {"width": 1, "blocks": {}}
    assert back.creatures[0]["kind"] == "COW"
    # 写盘与读盘
    path = _tmp_path()
    try:
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        again = SaveGame.from_dict(data)
        assert again.seed == 7
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_missing_path_raises_file_not_found():
    reg = _reg()
    path = os.path.join(tempfile.gettempdir(), "m5_nonexistent_xyz.json")
    if os.path.exists(path):
        os.remove(path)
    try:
        load_game(path, reg)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("缺失路径应抛 FileNotFoundError")


def test_corrupt_file_raises_value_error():
    reg = _reg()
    path = _tmp_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ this is not valid json ")
        try:
            load_game(path, reg)
        except ValueError:
            pass
        else:
            raise AssertionError("损坏文件应抛 ValueError")
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_meta_and_seed_present():
    reg = _reg()
    world = _small_world(reg)
    st = _make_state(reg, world, seed=99)
    path = _tmp_path()
    try:
        save_game(path, **st, registry=reg, saved_at="T_META")
        loaded = load_game(path, reg)
        assert loaded["seed"] == 99
        assert loaded["meta"]["version"] == 1
        assert loaded["meta"]["saved_at"] == "T_META"
        assert loaded["meta"]["seed"] == 99
        assert os.path.abspath(path) == loaded["meta"]["path"]
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_tolerant_missing_optional_fields():
    """存档缺可选字段（如 survival 无 hunger、player 无 vx）应兜底默认值。"""
    reg = _reg()
    world = _small_world(reg)
    st = _make_state(reg, world)
    path = _tmp_path()
    try:
        save_game(path, **st, registry=reg, saved_at="T0")
        # 手动删掉若干可选字段再写回
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["survival"].pop("hunger", None)
        data["player"].pop("vx", None)
        data["creatures"][0].pop("state", None)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        loaded = load_game(path, reg)        # 不应抛异常
        assert loaded["player"].vx == 0.0
        assert loaded["survival"].player.hunger == loaded["player"].max_hunger
        first = loaded["creatures"].creatures[0]
        assert first.state in (AIState.IDLE, AIState.WANDER,
                               AIState.FLEE, AIState.ATTACK)
    finally:
        if os.path.exists(path):
            os.remove(path)
