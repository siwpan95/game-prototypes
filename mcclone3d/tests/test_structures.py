# -*- coding: utf-8 -*-
"""Phase 2-C 村庄与结构单测（纯逻辑，零 GL）。

覆盖：选址硬判据（平坦 / 不在水边 / 不在雪线上 / 世界太小时不出村）、
整平（地基那层铺满、上方没有残留的树）、四栋房（**门洞通**、屋里有火把、
屋顶不透）、农田（作物长在土上、水渠是水）、**结构不进存档增量**（走 `set_generated`）、
同种子逐格相同、**老档读回来村庄还在原位**（结构由种子重算 ⇒ 不依赖存档）、
村民只在村里刷（村外刷不出）、**村里僵尸刷不出来**（火把光照 ⇒ Phase 2-A × 2-C 联动）。

跑：`python -m tests.test_structures`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d import structures as S
from mcclone3d.world import ChunkedWorld, surface_height

test, main = make_suite('ALL_STRUCTURES_TESTS_PASSED', '村庄与结构')

#: 256 世界才有足够地方放村庄（`structures.village_sites` 的 margin ≈ 26）
SEED, SIZE, HEIGHT = 20261014, 256, 64


def _village_world(seed=SEED):
    w = ChunkedWorld(seed, SIZE, HEIGHT)
    w.generate()
    w.decorate()
    return w


def _one_village(seed=SEED):
    """返回 `(world, (vx, vy, vz))` —— 保证至少有一个村庄（没有就炸，别静默跳过）。"""
    w = _village_world(seed)
    assert w.villages, f'seed={seed} 的世界里一个村庄都没有（选址判据是不是太严了？）'
    return w, w.villages[0]


# ==================================================================== 选址
@test('选址：村庄存在、中心在世界内、地基在水面之上且不在雪线之上')
def t_sites_valid():
    w = _village_world()
    assert w.villages, '256 世界该至少有一个村庄'
    margin = S.VILLAGE_R + S.HOUSE_OFF + S.HOUSE_HW + 2
    for (vx, vy, vz) in w.villages:
        assert margin <= vx <= SIZE - margin, f'村庄中心 x={vx} 太靠边'
        assert margin <= vz <= SIZE - margin, f'村庄中心 z={vz} 太靠边'
        assert vy > w.sea_level + 1, f'({vx},{vz}) 地基 {vy} 在水下'
        assert vy < w.snow_line - 2, f'({vx},{vz}) 地基 {vy} 在雪线上'


@test('选址：整张地图范围内的地表极差 ≤ FLAT_TOL（"平坦"是前提不是事后补救）')
def t_sites_flat():
    w = _village_world()
    for (vx, vy, vz) in w.villages:
        hs = [surface_height(x, z, w.seed, HEIGHT)
              for x in range(vx - S.VILLAGE_R, vx + S.VILLAGE_R + 1, 2)
              for z in range(vz - S.VILLAGE_R, vz + S.VILLAGE_R + 1, 2)]
        assert max(hs) - min(hs) <= S.FLAT_TOL, \
            f'村庄 ({vx},{vz}) 选址不平：极差 {max(hs) - min(hs)}'


@test('选址：世界太小时返回空表（不许越界去盖房）')
def t_sites_too_small():
    for size in (16, 32, 48):
        assert S.village_sites(7, size, size, 6, 20) == [], \
            f'size={size} 的世界放不下村庄（margin ≈ 26），该返回空表'


@test('选址：确定性（同种子一致；换种子不同的位置）')
def t_sites_deterministic():
    a = S.village_sites(SEED, SIZE, HEIGHT, 30, 44)
    b = S.village_sites(SEED, SIZE, HEIGHT, 30, 44)
    assert a == b, '同种子两次选址不一致'
    other = S.village_sites(777, SIZE, HEIGHT, 30, 44)
    assert a != other, '换种子选址完全一样（哈希没用上？）'


@test('选址：相邻村庄不会叠在一起（占地不重叠）')
def t_sites_no_overlap():
    w = _village_world()
    reach = S.VILLAGE_R + 1
    for i, (ax, _ay, az) in enumerate(w.villages):
        for (bx, _by, bz) in w.villages[i + 1:]:
            assert abs(ax - bx) > reach or abs(az - bz) > reach, \
                f'村庄 ({ax},{az}) 与 ({bx},{bz}) 占地重叠'


# ==================================================================== 整平
@test('整平：村庄地基那层没有空气（不许出现"塌陷的地面"）')
def t_ground_solid():
    w, (vx, vy, vz) = _one_village()
    hole = []
    for x in range(vx - S.VILLAGE_R, vx + S.VILLAGE_R + 1):
        for z in range(vz - S.VILLAGE_R, vz + S.VILLAGE_R + 1):
            if w.get(x, vy, z) == B.AIR:
                hole.append((x, z))
    assert not hole, f'村庄地基上有 {len(hole)} 格空气，例如 {hole[:4]}'


@test('整平：村庄上方没有残留的树（清空高度 ≥ 树冠高度）')
def t_clear_trees():
    w, (vx, vy, vz) = _one_village()
    leftover = []
    for x in range(vx - S.VILLAGE_R, vx + S.VILLAGE_R + 1):
        for z in range(vz - S.VILLAGE_R, vz + S.VILLAGE_R + 1):
            for dy in range(1, 4):
                if w.get(x, vy + dy, z) in (B.LOG, B.LEAVES):
                    leftover.append((x, vy + dy, z))
    assert not leftover, f'村庄里还留着 {len(leftover)} 格树，例如 {leftover[:4]}'


@test('整平：地基材质是草地（不是原始地形的一地杂色）')
def t_ground_material():
    w, (vx, vy, vz) = _one_village()
    ok = {B.GRASS, B.GRAVEL, B.PLANKS, B.WATER, B.COBBLE, B.DIRT, B.CROP}
    bad = [(x, z, B.name_of(w.get(x, vy, z)))
           for x in range(vx - S.VILLAGE_R, vx + S.VILLAGE_R + 1)
           for z in range(vz - S.VILLAGE_R, vz + S.VILLAGE_R + 1)
           if w.get(x, vy, z) not in ok]
    assert not bad, f'地基上有 {len(bad)} 格杂色，例如 {bad[:4]}'


# ==================================================================== 建筑
@test('四栋房：四面墙都在、屋顶不透（下雨不会漏进屋里）')
def t_houses_intact():
    w, (vx, vy, vz) = _one_village()
    for (sx, sz) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        hx, hz = vx + sx * S.HOUSE_OFF, vz + sz * S.HOUSE_OFF
        # 屋顶：最上面那层（half = HOUSE_HW）整片是实体
        top = vy + S.HOUSE_WALL + 2
        for x in range(hx - S.HOUSE_HW, hx + S.HOUSE_HW + 1):
            for z in range(hz - S.HOUSE_HW, hz + S.HOUSE_HW + 1):
                assert w.get(x, top, z) != B.AIR, \
                    f'房子({sx:+d},{sz:+d}) 屋顶漏在 ({x},{z})'
        # 四角有柱子（墙不是断的）
        for dx in (-S.HOUSE_HW, S.HOUSE_HW):
            for dz in (-S.HOUSE_HW, S.HOUSE_HW):
                assert w.get(hx + dx, vy + 1, hz + dz) != B.AIR, \
                    f'房子({sx:+d},{sz:+d}) 缺角柱 ({dx},{dz})'


@test('四栋房：门洞通（2 格高）且**朝村庄中心**，出门不会被墙挡死')
def t_doors_open():
    w, (vx, vy, vz) = _one_village()
    for (sx, sz) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        hx, hz = vx + sx * S.HOUSE_OFF, vz + sz * S.HOUSE_OFF
        dx, dz = -sx, -sz                        # 门朝中心
        if dx:
            door = [(hx + dx * S.HOUSE_HW, vy + dy, hz) for dy in (1, 2)]
            outside = (hx + dx * (S.HOUSE_HW + 1), vy + 1, hz)
        else:
            door = [(hx, vy + dy, hz + dz * S.HOUSE_HW) for dy in (1, 2)]
            outside = (hx, vy + 1, hz + dz * (S.HOUSE_HW + 1))
        for (x, y, z) in door:
            assert w.get(x, y, z) == B.AIR, f'房子({sx:+d},{sz:+d}) 门洞被堵在 ({x},{y},{z})'
        # 门前那一格也必须是通的（否则出门撞墙，等于没门）
        assert w.get(*outside) == B.AIR, \
            f'房子({sx:+d},{sz:+d}) 门口外面是 {B.name_of(w.get(*outside))}，出不去'


@test('四栋房：屋里有火把（屋内的光只来自它）')
def t_house_torches():
    w, (vx, vy, vz) = _one_village()
    for (sx, sz) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        hx, hz = vx + sx * S.HOUSE_OFF, vz + sz * S.HOUSE_OFF
        found = any(w.get(x, y, z) == B.TORCH
                    for x in range(hx - S.HOUSE_HW, hx + S.HOUSE_HW + 1)
                    for y in range(vy + 1, vy + S.HOUSE_WALL + 1)
                    for z in range(hz - S.HOUSE_HW, hz + S.HOUSE_HW + 1))
        assert found, f'房子({sx:+d},{sz:+d}) 屋里没有火把'


@test('农田：作物长在土上，中间有水渠，田埂把田围起来（留一个缺口）')
def t_farms():
    w, (vx, vy, vz) = _one_village()
    for az in (vz - S.HOUSE_OFF, vz + S.HOUSE_OFF):
        crops = [(x, z) for x in range(vx - 2, vx + 3) for z in range(az - 2, az + 3)
                 if w.get(x, vy + 1, z) == B.CROP]
        assert crops, f'({vx},{az}) 这块田里一株作物都没有'
        for (x, z) in crops:
            assert w.get(x, vy, z) == B.DIRT, \
                f'({x},{z}) 的作物下面不是泥土，是 {B.name_of(w.get(x, vy, z))}'
        # 水渠：田中间那一行（`z == az`）在田土那层是水
        assert w.get(vx, vy, az) == B.WATER, f'({vx},{az}) 田里没有水渠'
        # 田埂：上/下边缘是圆石（`z == az ± 2` 且不是缺口）
        assert w.get(vx, vy + 1, az - 2) == B.COBBLE or w.get(vx, vy + 1, az + 2) == B.COBBLE, \
            f'({vx},{az}) 这块田没有田埂'


# ==================================================================== 纪律
@test('纪律：结构与树都不进存档增量（走 set_generated ⇒ 老档不用升级）')
def t_not_in_edits():
    w = _village_world()
    assert len(w.edits) == 0, f'装修留下 {len(w.edits)} 条增量（树/村庄都不该记）'
    dumped = w.dump()                              # 世界存档：`{version, seed, size, height, edits}`
    names = {row[3] for row in dumped['edits']}
    assert names == set(), f'存档里出现了装修方块：{sorted(names)[:6]}'


@test('确定性：同种子两次生成逐格相同（位置/朝向/屋顶材质都定得住）')
def t_deterministic():
    a, b = _village_world(), _village_world()
    assert a.villages == b.villages, '两次生成的村庄位置不同'
    pr = S.VILLAGE_R
    for (vx, vy, vz) in a.villages[:2]:
        for x in range(vx - pr, vx + pr + 1, 3):
            for y in range(vy, vy + 8):
                for z in range(vz - pr, vz + pr + 1, 3):
                    assert a.get(x, y, z) == b.get(x, y, z), \
                        f'({x},{y},{z}) 两次生成不同：{a.get(x, y, z)} vs {b.get(x, y, z)}'


@test('老档读回来村庄还在原位（结构由种子重算，不依赖存档）')
def t_reload_same_village():
    w = _village_world()
    data = w.dump()
    w2 = ChunkedWorld(SEED, SIZE, HEIGHT)
    w2.load(data)                                  # load 里 replant=True ⇒ decorate()
    assert w2.villages == w.villages, \
        f'读档后村庄位置变了：{w2.villages} vs {w.villages}'
    pr = S.VILLAGE_R
    for (vx, vy, vz) in w.villages[:1]:
        for (x, y, z) in ((vx, vy, vz), (vx + 1, vy + 1, vz), (vx - 3, vy + 2, vz - 3)):
            assert w2.get(x, y, z) == w.get(x, y, z), f'({x},{y},{z}) 读档后不一样'


@test('玩法闭环：打掉作物掉小麦（`recipes.drops_for`）')
def t_crop_drops_wheat():
    from mcclone3d import items as I
    from mcclone3d import recipes as R
    drops = R.drops_for(B.CROP)
    assert drops, '作物不掉落（农田就没有意义了）'
    names = {I.ITEMS[i].name for (i, _n) in drops}
    assert names == {'wheat'}, f'作物该掉小麦，实际掉 {sorted(names)}'
    # 面（麦子）本身不是"能拿在手里的方块"
    assert R.as_item(B.CROP) is None, '作物不该有方块物品（同煤/铁矿）'


# ==================================================================== 刷怪联动
@test('村民只在村里刷：村外随机刷怪不出村民（village_only）')
def t_villager_village_only():
    from mcclone3d import mobs as MB
    vk = MB.mob_kind('villager')
    assert vk.village_only, '村民必须标 village_only（否则荒野会冒村民）'
    assert not vk.hostile, '村民是被动生物'
    assert all(not k.village_only for k in MB.all_kinds() if k.name != 'villager'), \
        'village_only 只有村民该有'


@test('村里僵尸刷不出来（火把光照 ⇒ Phase 2-A 的暗处判据天然生效）')
def t_village_is_safe():
    from mcclone3d import mobs as MB
    from mcclone3d.kernel import make_offline
    k = make_offline({'seed': SEED, 'size': 128, 'height': 64, 'light': True})
    assert k.world.villages, '这个尺寸下该有村庄'
    vx, vy, vz = k.world.villages[0]
    k.light.column_pass_all()
    for cx in range(k.size // 16):
        for cy in range(k.height // 16):
            for cz in range(k.size // 16):
                k.light.relight_chunk(cx, cy, cz)
    limit = MB.mob_kind('zombie').spawn_light_max
    # 村庄中心 5×5 的地面：方块光必须高于僵尸的刷新阈值
    dark = []
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            if k.light.block(vx + dx, vy + 1, vz + dz) <= limit:
                dark.append((dx, dz))
    assert not dark, f'村中心还有 {len(dark)} 格暗到能刷僵尸：{dark[:4]}'


@test('村民通道：村里能刷出村民、且不会刷到村外，人口有上限')
def t_villager_spawns():
    from mcclone3d.kernel import make_offline, VILLAGE_POP
    k = make_offline({'seed': SEED, 'size': 128, 'height': 64, 'light': True})
    vx, vy, vz = k.world.villages[0]
    k.pos = [vx + 0.5, float(vy + 1), vz + 0.5]
    k.light.column_pass_all()
    for cx in range(k.size // 16):
        for cy in range(k.height // 16):
            for cz in range(k.size // 16):
                k.light.relight_chunk(cx, cy, cz)
    for _ in range(30):
        k._try_spawn_villager()
    vs = [m for m in k.mobs if m.kind.name == 'villager']
    assert vs, '在村里连刷 30 次都没有村民'
    cap = len(k.world.villages) * VILLAGE_POP
    assert len(vs) <= cap, f'村民 {len(vs)} 只超过上限 {cap}'
    span = S.VILLAGE_R + 4
    for m in vs:
        assert abs(m.pos[0] - vx) <= span and abs(m.pos[2] - vz) <= span, \
            f'村民刷到村外了：({m.pos[0]:.1f},{m.pos[2]:.1f}) vs 村 ({vx},{vz})'


if __name__ == '__main__':
    sys.exit(main())
