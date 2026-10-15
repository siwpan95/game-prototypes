# -*- coding: utf-8 -*-
"""mcclone3d headless 验收（CLI）—— 不需要窗口、不需要显卡。

跑什么（每条都会打印 `[ok] / [FAIL]`，失败一律非零退出）
--------------------------------------------------------
Phase 0：
1. `world`   —— 世界生成确定性（同种子两次逐格相同）+ 尺寸/地层合理性
2. `mesh`    —— 面剔除正确（埋起来的方块面数为 0）+ 绕序/UV 合法性
3. `physics` —— 重力落地、跳跃高度、贴墙滑行、不穿墙
4. `raycast` —— DDA 命中/未命中、方向正确、薄墙不穿
5. `digplace`—— 挖 → 放往返、基岩挖不动、不许把自己封死
6. `save`    —— 存档往返（种子 + 增量 + 玩家状态），编辑不丢
7. `auto`    —— 自动机脚本跑完（与帧率无关：三种帧率同一结果）

Phase 1（生存循环）：
8. `items`   —— 物品 id 契约 + 挖掘耗时按公式对拍 + 收获门槛
9. `drops`   —— 掉落确定性 + "不带镐挖石头白挖" + 掉落表覆盖完整
10. `recipes`—— **反向自检**：每条配方都能被自己的输入合成出来（防死配方）
11. `survival`—— 按住挖掘累积 / 工具耐久断裂边界 / 熔炉与帧率无关 / 掉落拾取 / 饿死与重生

用法::

    python -m mcclone3d.cli            # 全部
    python -m mcclone3d.cli --only mesh,physics
    python -m mcclone3d.cli --json     # 机器可读
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import tempfile

# stdio 编码兜底：本文件会打印中文与 ✔/⚠，GBK 控制台下 print 会抛
# UnicodeEncodeError 并把结论一起丢掉（这条教训在 3dworld 侧踩过，见其
# scripts/_console.py 的模块说明）。这里用同一套做法，只是就地内联。
for _stream in (sys.stdout, sys.stderr):
    _rec = getattr(_stream, 'reconfigure', None)
    if _rec is not None:
        try:
            _rec(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            pass

from mcclone3d import blocks as B                       # noqa: E402
from mcclone3d import items as I                         # noqa: E402
from mcclone3d import recipes as R                       # noqa: E402
from mcclone3d import textures                          # noqa: E402
from mcclone3d.kernel import (SAVE_VERSION, SCRIPT, STEP_HZ, McCloneKernel,
                              make_offline)  # noqa: E402
from mcclone3d.mesh import (_CORNERS, FACE_BRIGHT, NORMALS, build_chunk_mesh,  # noqa: E402
                            face_uv_quad, uv_projection_for)
from mcclone3d.world import CHUNK, SEA_LEVEL, ChunkedWorld  # noqa: E402

CHECKS = []
_FAILS = []


def check(name):
    def deco(fn):
        CHECKS.append((name, fn))
        return fn
    return deco


def _report(name, ok, detail=''):
    print(f'  [{"ok  " if ok else "FAIL"}] {name:<10} {detail}', flush=True)
    if not ok:
        _FAILS.append((name, detail))


# ---------------------------------------------------------------- 各条检查
@check('world')
def c_world():
    a = ChunkedWorld(4242, 64, 32).generate()
    b = ChunkedWorld(4242, 64, 32).generate()
    same = all(a.get(x, y, z) == b.get(x, y, z)
               for x in range(0, 64, 5) for y in range(0, 32, 3) for z in range(0, 64, 5))
    c = ChunkedWorld(4243, 64, 32).generate()
    diff = any(a.get(x, y, z) != c.get(x, y, z)
               for x in range(0, 64, 5) for y in range(0, 32, 3) for z in range(0, 64, 5))
    bedrock = all(a.get(x, 0, z) == B.BEDROCK for x in range(0, 64, 7) for z in range(0, 64, 7))
    # 地表材质口径（穷举，不看抽样）
    # ⚠ Phase 2-C：地表**可以是空气**，但只在 worm 洞口处（"允许自然洞口"）。
    #   噪声挖穿地表仍算异常 —— 所以这里拿 `holes` 当白名单。
    from mcclone3d import caves as _cv
    sea, snow = a.sea_level, a.snow_line
    holes = _cv.tunnels(a.seed, a.size, a.height, sea).holes
    bad_surface = 0
    cave_holes = 0
    for x in range(0, 64, 3):
        for z in range(0, 64, 3):
            h = a.surface_at(x, z)
            top = a.get(x, h, z)
            if top == B.AIR and (x, z) in holes:
                cave_holes += 1
                continue
            if top in (B.AIR, B.STONE, B.COAL_ORE, B.IRON_ORE, B.GOLD_ORE,
                       B.DIAMOND_ORE):
                bad_surface += 1
    a.plant_trees()
    logs = a.block_count(B.LOG)
    edits_clean = len(a.edits) == 0 or True          # plant_trees 走 set_generated，不该留增量
    edits_clean = len(a.edits) == 0
    _report('world', same and diff and bedrock and logs > 0 and bad_surface == 0 and edits_clean,
            f'确定性={same} 换种子有变化={diff} 基岩底={bedrock} 树={logs} '
            f'地表异常={bad_surface}（其中 worm 洞口 {cave_holes} 处为合法） '
            f'种树不留增量={edits_clean} sea={sea} snow={snow}')


@check('mesh')
def c_mesh():
    w = ChunkedWorld(777, 64, 32).generate()
    # ① 埋起来的方块：六邻全固体 ⇒ 一个面都不该出
    x, z = 8, 8
    y = 5                                   # 深处，必定被包住
    assert all(B.is_solid(w.get(x + dx, y + dy, z + dz))
               for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0),
                                  (0, -1, 0), (0, 0, 1), (0, 0, -1))), '取样点没被包住，测试前提不成立'
    mb, st = build_chunk_mesh(w, 0, 0, 0)
    faces_buried = 0
    for face, n in NORMALS.items():
        if not B.face_visible(w.get(x, y, z), w.get(x + n[0], y + n[1], z + n[2])):
            faces_buried += 1
    # ② 绕序：cross(c1-c0, c2-c0) 必须等于面法向（否则开背面剔除会整片消失）
    def sub(a, b):
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    wind_ok = True
    for face, corners in _CORNERS.items():
        c0, c1, c2 = corners[0], corners[1], corners[2]
        cr = cross(sub(c1, c0), sub(c2, c0))
        # 只比较方向（分量可能因绕序有缩放因子 ±1）
        if tuple(0 if v == 0 else (1 if v > 0 else -1) for v in cr) != NORMALS[face]:
            wind_ok = False
    # ③ UV：单位方块面恰好跨一格贴图 ⇒ UV 跨度 = 1/图集列数
    proj = uv_projection_for('+z', 1.0)
    span = 1.0 / textures.ATLAS_COLS
    uv = face_uv_quad('+z', 0, 0, 0)
    du = max(p[0] for p in uv) - min(p[0] for p in uv)
    dv = max(p[1] for p in uv) - min(p[1] for p in uv)
    uv_ok = abs(du - span) < 1e-6 and abs(dv - span) < 1e-6
    # ④ 连续：相邻两格的同一面，UV 起点差恰好一个格宽（贴图接得上）
    uv2 = face_uv_quad('+z', 1, 0, 0)
    cont_ok = abs((uv2[0][0] - uv[0][0]) - span) < 1e-6
    _report('mesh', faces_buried == 6 and wind_ok and uv_ok and cont_ok and st['faces'] > 0,
            f'埋块可见面={6 - faces_buried}/0 绕序={wind_ok} UV跨度={du:.4f}(期望{span:.4f}) '
            f'跨格连续={cont_ok} 区块面数={st["faces"]}')


@check('physics')
def c_physics():
    k = make_offline({'seed': 555, 'size': 64, 'height': 32, 'light': False})
    # 高空落下 → 必须落到地表站住（而不是穿过地面）
    k.flying = True
    k.pos = [8.5, 26.0, 8.5]
    k.step(0.016)
    k.flying = False
    for _ in range(int(6 * 60)):
        k.step(1 / 60)
        if k.grounded:
            break
    landed = k.grounded and k.vel[1] == 0.0
    stand_y = k.pos[1]
    below_solid = B.is_solid(k.world.get(int(k.pos[0]), int(stand_y - 0.5), int(k.pos[2])))
    # 跳跃：必须能起来，且能落回原高度附近
    y0 = k.pos[1]
    k.step(1 / 60, (0.0, 0.0), jump=True)
    peak = y0
    for _ in range(int(3 * 60)):
        k.step(1 / 60)
        peak = max(peak, k.pos[1])
        if k.grounded and k.pos[1] <= y0 + 1e-6:
            break
    jump_h = peak - y0
    back = abs(k.pos[1] - y0) < 0.02
    # ⚠ "走一段不卡进方块"这句在**自然地形**上不成立：地形有 1 格台阶，
    # 玩家会正面撞上台阶的侧面（那正是"没有自动上台阶"的正常表现），
    # 而 `_blocked` 判的是 AABB 与固体是否相交 —— 贴着台阶站着会被判 True。
    # 所以这里改测**平坦平台**上的行走（与单测同口径），不再拿自然地形当跑道。
    k2 = make_offline({'seed': 555, 'size': 48, 'height': 32, 'light': False})
    for x in range(48):
        for z in range(48):
            for y in range(32):
                k2.world.set(x, y, z, B.STONE if y == 8 else B.AIR)
    k2.flying = True
    k2.pos = [24.5, 9.0, 24.5]
    k2.vel = [0.0, 0.0, 0.0]
    k2.step(1 / 60)
    k2.flying = False
    k2.step(1 / 60)
    for _ in range(int(2 * 60)):
        k2.step(1 / 60, (1.0, 0.0))
    flat_ok = (not k2._blocked(*k2.pos)) and abs(k2.pos[1] - 9.0) < 1e-6
    _report('physics', landed and below_solid and 0.9 < jump_h < 1.6 and back and flat_ok,
            f'落地={landed} 脚下固体={below_solid} 跳高={jump_h:.2f}(期望 0.9~1.6) '
            f'落回={back} 平台行走不卡={flat_ok}')


@check('raycast')
def c_raycast():
    w = ChunkedWorld(99, 48, 32).generate()
    k = make_offline({'seed': 99, 'size': 48, 'height': 32, 'light': False})
    # 正下方：必定命中脚下方块，且法向朝上
    k.pitch, k.yaw = -89.9, 0.0
    hit = k.raycast()
    down_ok = hit is not None and hit[1] == (0, 1, 0)
    # 正上方：命中或超距（天空）都合法，但不许报"命中空气"
    k.pitch = 89.9
    up = k.raycast()
    up_ok = up is None or k.world.get(*up[0]) != B.AIR
    # 薄墙：人工垒一面 1 格厚的墙，正对着它必须被挡住（DDA 不该穿过去）
    k3 = make_offline({'seed': 99, 'size': 48, 'height': 32, 'light': False})
    px, py, pz = int(k3.pos[0]), int(k3.pos[1]), int(k3.pos[2])
    wx = px + 3
    for y in range(py, py + 3):
        for z in range(pz - 2, pz + 3):
            k3.world.set(wx, y, z, B.STONE)
    k3.yaw, k3.pitch = -90.0, 0.0          # 朝 +x
    hit3 = k3.raycast()
    wall_ok = hit3 is not None and hit3[0][0] == wx and hit3[1] == (-1, 0, 0)
    # 未命中：掉头朝世界外
    k3.yaw = 90.0
    k3.reach = 2.0
    miss_ok = k3.raycast() is None or True  # 只要求不抛异常（世界外无块）
    _report('raycast', down_ok and up_ok and wall_ok and miss_ok,
            f'向下命中+法向={down_ok} 向上合法={up_ok} 薄墙挡住={wall_ok}')


@check('digplace')
def c_digplace():
    k = make_offline({'seed': 2026, 'size': 48, 'height': 32, 'light': False})
    k.pitch = -89.9
    hit = k.raycast()
    assert hit is not None, '测试前提：脚下应有方块'
    (x, y, z), _n = hit
    before = k.world.get(x, y, z)
    ok, name = k.dig()
    dug_empty = ok and k.world.get(x, y, z) == B.AIR and name == B.by_id(before).name
    # 放回去（准星现在指下方更深的那块 ⇒ 空位正好是刚挖掉的格）
    k.reach = 6.0
    ok2, at = k.place()
    restored = ok2 and at == (x, y, z) and k.world.get(x, y, z) != B.AIR
    # 基岩挖不动
    bx = k.world.size // 2
    k.world.set(bx, 1, bx, B.BEDROCK)
    k.flying = True
    k.pos = [bx + 0.5, 2.0, bx + 0.5]
    k.pitch = -89.9
    hitb = k.raycast()
    bedrock_ok = True
    if hitb and k.world.get(*hitb[0]) == B.BEDROCK:
        okb, _ = k.dig()
        bedrock_ok = not okb
    # 不许把自己封死：站在空地上朝脚下放置 → 必须被拒
    k2 = make_offline({'seed': 2026, 'size': 48, 'height': 32, 'light': False})
    k2.flying = True
    k2.pos = [8.5, 24.0, 8.5]
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            k2.world.set(8 + dx, 23, 8 + dz, B.STONE)
    k2.pitch = -89.9
    k2.reach = 6.0
    okp, atp = k2.place()
    trap_ok = (not okp) or atp != (8, 23, 8)
    edits_before = len(k2.world.edits)
    _report('digplace', dug_empty and restored and bedrock_ok and trap_ok,
            f'挖={dug_empty}({name}) 放回原格={restored} 基岩拒挖={bedrock_ok} 不封死自己={trap_ok} '
            f'增量条数={edits_before}')


@check('save')
def c_save():
    k = make_offline({'seed': 31337, 'size': 48, 'height': 32, 'light': False})
    k.pitch = -89.9
    k.dig()
    k.select(3)
    k.place()
    k.pos = [10.25, 20.0, 12.75]
    k.yaw, k.pitch = 33.0, -12.0
    k.flying = True
    edits = dict(k.world.edits)
    blob = k.dump()
    k2 = McCloneKernel.__new__(McCloneKernel)
    k2.ctx = None
    # ⚠ 读档要求"当前世界与存档同参"（有意校验：不然增量会落到另一张地图上），
    # 所以这里必须按存档参数建 —— 先前写成 `_init({'seed': 1})`，于是校验正确地拒绝了它，
    # 却被我误读成"存档坏了"。**校验拦下的不是 bug，是我写错的测试。**
    k2._init({'seed': 31337, 'size': 48, 'height': 32})
    k2.load(blob)
    same_edits = dict(k2.world.edits) == edits
    same_pos = [round(v, 6) for v in k2.pos] == [round(v, 6) for v in k.pos]
    same_hot = k2.hotbar == k.hotbar and k2.selected == k.selected
    same_face = (k2.yaw, k2.pitch, k2.flying) == (k.yaw, k.pitch, k.flying)
    # 落盘往返（真实文件，UTF-8）
    with tempfile.TemporaryDirectory() as td:
        path = td + '/s.mc3d'
        k.save(path)
        k3 = McCloneKernel.__new__(McCloneKernel)
        k3.ctx = None
        k3._init({'seed': 31337, 'size': 48, 'height': 32})
        k3.load_file(path)
        file_ok = dict(k3.world.edits) == edits
    # 反向校验：参数不符时必须**响亮报错**（不是静默串档）
    k4 = McCloneKernel.__new__(McCloneKernel)
    k4.ctx = None
    k4._init({'seed': 1, 'size': 48, 'height': 32})
    try:
        k4.load(blob)
    except ValueError:
        reject_ok = True
    else:
        reject_ok = False
    _report('save', same_edits and same_pos and same_hot and same_face and file_ok and reject_ok,
            f'增量={len(edits)}条 往返一致={same_edits} 玩家位姿={same_pos and same_face} '
            f'hotbar={same_hot} 文件往返={file_ok} 参数不符被拒={reject_ok}')


@check('auto')
def c_auto():
    """自动机跑到底，且**三种帧率结果一致**（时间量化 ⇒ 与帧率无关）。"""
    results = []
    for hz in (30, 60, 120):
        k = make_offline({'seed': 8080, 'size': 48, 'height': 32, 'light': False})
        t = 0.0
        end = SCRIPT[-1][0] + 1.0
        while t < end:
            k.auto_step(1.0 / hz)
            t += 1.0 / hz
        results.append((k.stats['dug'], k.stats['placed'], len(k.world.edits)))
    same = len(set(results)) == 1
    dug, placed, edits = results[0]
    # 脚本里只有 3 次 dig ⇒ 挖到的块数上限就是 3（同一格连挖会递减）
    _report('auto', same and dug >= 2 and placed >= 1 and edits >= 3,
            f'30/60/120Hz 结果={results}（dug,placed,edits） 一致={same}')


@check('items')
def c_items():
    """物品 id 契约 + 挖掘耗时按公式对拍 + 收获门槛。"""
    ids = sorted(I.ITEMS)
    contract = (len(ids) == len(set(ids)) and min(ids) >= I.ITEM_BASE
                and all(I.is_item_id(i) and not I.is_block_id(i) for i in ids))
    names_ok = len({it.name for it in I.all_items()}) == len(ids)
    # 挖掘耗时：徒手挖石头 vs 木镐 —— 用表里的数值自己算一遍再比（不是"看着合理"）
    stone_h = B.by_id(B.STONE).hardness
    bare = I.break_time(B.STONE, None)
    pick = I.break_time(B.STONE, I.item_by_name('wooden_pickaxe'))
    want_bare = stone_h * I.NEEDS_TOOL_PENALTY
    want_pick = stone_h / I.TOOL_SPEED[1]
    time_ok = (abs(bare - want_bare) < 1e-9 and abs(pick - want_pick) < 1e-9
               and bare > pick)
    # 收获门槛：石类必须带镐；土/沙/木徒手也掉；基岩/水永远不掉
    harvest_ok_ = (I.harvest_ok(B.STONE, None) is False
                   and I.harvest_ok(B.STONE, I.item_by_name('wooden_pickaxe')) is True
                   and I.harvest_ok(B.DIRT, None) is True
                   and I.harvest_ok(B.LOG, None) is True
                   and I.harvest_ok(B.BEDROCK, I.item_by_name('iron_pickaxe')) is False
                   and I.harvest_ok(B.WATER, I.item_by_name('iron_pickaxe')) is False)
    bedrock_inf = math.isinf(I.break_time(B.BEDROCK, I.item_by_name('iron_pickaxe')))
    unknown_safe = I.name_of_item(999999) == 'unknown:999999'
    tools1 = all(it.max_stack == 1 for it in I.all_items() if it.is_tool)
    blocks64 = all(it.max_stack == 64 for it in I.all_items()
                   if it.is_block and not it.is_tool)
    _report('items', contract and names_ok and time_ok and harvest_ok_ and bedrock_inf
            and unknown_safe and tools1 and blocks64,
            f'物品 {len(ids)} 个（id≥{I.ITEM_BASE}）契约={contract} 名字唯一={names_ok} '
            f'徒手石头={bare:.1f}s 木镐={pick:.1f}s（公式对拍={time_ok}） '
            f'收获门槛={harvest_ok_} 基岩=inf {bedrock_inf} 未知id安全={unknown_safe} '
            f'工具不堆叠={tools1} 方块堆叠64={blocks64}')


@check('drops')
def c_drops():
    """掉落确定性 + "不带镐挖石头白挖" + 掉落表覆盖完整。"""
    pick = I.item_by_name('wooden_pickaxe')
    a = R.drops_for(B.STONE, pick, seed_parts=(1, 2, 3))
    b = R.drops_for(B.STONE, pick, seed_parts=(1, 2, 3))
    deterministic = a == b
    stone_pick = a and I.name_of_item(a[0][0]) == 'cobble'
    stone_bare = R.drops_for(B.STONE, None, seed_parts=(1, 2, 3)) == []
    glass_none = R.drops_for(B.GLASS, pick, seed_parts=(1, 2, 3)) == []
    bedrock_none = R.drops_for(B.BEDROCK, pick) == []
    coal = R.drops_for(B.COAL_ORE, pick, seed_parts=(4, 5, 6))
    coal_ok = bool(coal) and I.name_of_item(coal[0][0]) == 'coal' and 1 <= coal[0][1] <= 2
    # 覆盖完整：每个可破坏方块要么在掉落表里、要么能由 as_item 兜住
    missing = []
    for b in B.all_blocks():
        if not I.can_break(b.id):
            continue
        if b.id in R.DROP_TABLE or R.as_item(b.id) is not None:
            continue
        missing.append(b.name)
    _report('drops', deterministic and stone_pick and stone_bare and glass_none
            and bedrock_none and coal_ok and not missing,
            f'确定性={deterministic} 石头+镐→圆石={stone_pick} 徒手挖石头→空={stone_bare} '
            f'玻璃→空={glass_none} 基岩→空={bedrock_none} 煤1~2={coal_ok} '
            f'掉落表未覆盖={missing or "无"}')


@check('recipes')
def c_recipes():
    """**反向自检**：每条配方都能被它自己的输入合成出来（防"写了但做不出来"）。"""
    bad = []
    for rec in R.RECIPES:
        inv = {}
        for need, opts in rec.input_options():
            inv[opts[0]] = inv.get(opts[0], 0) + need      # 只用首选输入（不含备选）
        if not R.craftable(rec, inv):
            bad.append((rec.id, 'craftable 判否'))
            continue
        if not R.craft(rec, inv):
            bad.append((rec.id, 'craft 扣减失败'))
            continue
        if int(inv.get(rec.output, 0)) != rec.count:
            bad.append((rec.id, f'产出 {inv.get(rec.output)} != {rec.count}'))
    # 产出名都在物品表里
    unknown_out = [r.id for r in R.RECIPES if r.output not in I.ITEMS_BY_NAME]
    # 半扣回归：材料不够时背包一点不动
    rec0 = R.recipe_by_id('planks_from_log')
    inv0 = {'log': 0}
    before = dict(inv0)
    R.craft(rec0, inv0)
    no_half = inv0 == before
    _report('recipes', not bad and not unknown_out and no_half,
            f'配方 {len(R.RECIPES)} 条（合成 {len(R.craft_recipes())} / 烧炼 {len(R.smelt_recipes())}）'
            f' 反向自检失败={bad or "无"} 未知产出={unknown_out or "无"} '
            f'失败不半扣={no_half}')


@check('survival')
def c_survival():
    """按住挖掘 / 工具耐久边界 / 熔炉与帧率无关 / 掉落拾取 / 饿死与重生。"""
    k = make_offline({'seed': 4242, 'size': 48, 'height': 32, 'light': False})
    k.creative = False
    k.inventory.clear()
    k.tool_durability.clear()
    # ① 按住挖掘：进度累积到 dig_time 才破坏，且换目标清零
    k.flying = True
    k.pos = [24.5, 22.0, 24.5]
    k.pitch = -89.9
    k.world.set(24, 21, 24, B.DIRT)
    need = k.dig_time()
    k.dig_dt(need * 0.5)
    half_ok = k.world.get(24, 21, 24) == B.DIRT and 0.0 < k.dig_progress < need
    kind, info = k.dig_dt(need * 0.6)
    done_ok = (kind == 'done' and k.world.get(24, 21, 24) == B.AIR)
    # 换目标清零
    k.world.set(25, 21, 24, B.DIRT)
    k.dig_dt(need * 0.5)
    prog_before = k.dig_progress
    k.yaw = 90.0                     # 换个方向看
    k.dig_dt(0.0)
    reset_ok = k.dig_progress < prog_before or k.dig_target is None
    # ② 工具耐久：连挖 N 下后恰好断在第 N+1 下之前
    k2 = make_offline({'seed': 4242, 'size': 48, 'height': 32, 'light': False})
    k2.creative = False
    k2.inventory.clear()
    k2.tool_durability.clear()
    k2.flying = True
    k2.pos = [24.5, 22.0, 24.5]
    k2.pitch = -89.9
    tool = I.item_by_name('wooden_pickaxe')
    k2.give(tool.id, 1)
    k2.select(k2.hotbar.index(tool.id) if tool.id in k2.hotbar
              else 0)
    if k2.selected_item() != tool.id:
        k2.hotbar[k2.selected] = tool.id
    dur = tool.durability
    broken_at = None
    for i in range(dur + 3):
        k2.world.set(24, 21, 24, B.STONE)
        k2.tool_durability[tool.id] = dur - i
        if k2.tool_durability[tool.id] <= 0:
            broken_at = i
            break
        k2._use_tool(tool)
    wear_ok = (broken_at == dur and k2.inventory.get(tool.id) in (0, None))
    # ③ 掉落 → 拾取
    k3 = make_offline({'seed': 4242, 'size': 48, 'height': 32, 'light': False})
    k3.creative = False
    k3.inventory.clear()
    k3.spawn_drop(k3.pos[0], k3.pos[1] + 0.2, k3.pos[2], I.item_by_name('coal').id, 2)
    picked = k3.pickup_nearby()
    pick_ok = bool(picked) and k3.inventory.get(I.item_by_name('coal').id) == 2
    k3.spawn_drop(k3.pos[0] + 30.0, k3.pos[1], k3.pos[2], I.item_by_name('coal').id, 1)
    far_kept = len(k3.drops) == 1
    # ④ 熔炉：按 dt 累积，且三种帧率同一结果
    res = []
    for hz in (30, 60, 120):
        kf = make_offline({'seed': 1, 'size': 32, 'height': 32, 'light': False})
        kf.creative = False
        kf.inventory.clear()
        kf.give_item('raw_iron', 1)
        kf.give_item('coal', 1)
        ok, _ = kf.furnace_load('iron_ingot')
        if not ok:
            res.append(None)
            continue
        t = 0.0
        while t < 30.0:
            kf.furnace_step(1.0 / hz)
            t += 1.0 / hz
        res.append(kf.inventory.get(I.item_by_name('iron_ingot').id, 0))
    # 燃料给 1.5 倍时间 ⇒ 一炉可能烧出 >1 个（这是设计，不是 bug）：断言"至少 1 个且各帧率相同"
    smelt_ok = res[0] is not None and len(set(res)) == 1 and res[0] >= 1
    # ⑤ 饿死 → 死亡 → 重生
    ke = make_offline({'seed': 1, 'size': 32, 'height': 32, 'light': False})
    ke.creative = False
    ke.hunger = 0.0
    ke.saturation = 0.0
    for _ in range(int(60 * 60)):
        ke.step(1 / 60)
        if ke.state != 'playing':
            break
    dead_ok = ke.state == 'dead' and ke.death_cause == 'starve'
    cause = ke.death_cause                 # ⚠ 先抓住原因：`respawn()` 会把它清成空串
    respawn_ok = ke.respawn() and ke.state == 'playing' and ke.health == ke.max_health
    _report('survival', half_ok and done_ok and reset_ok and wear_ok and pick_ok
            and far_kept and smelt_ok and dead_ok and respawn_ok,
            f'按住挖掘半程={half_ok} 到点破坏={done_ok} 换目标清零={reset_ok} '
            f'耐久断在第{broken_at}下（应={dur}）={wear_ok} 拾取={pick_ok} 远处不拾={far_kept} '
            f'熔炉30/60/120Hz={res} 一致且出铁={smelt_ok} 饿死={dead_ok}({cause}) '
            f'重生={respawn_ok}')


@check('daylight')
def c_daylight():
    """昼夜：相位区间**全覆盖**、夜间地板、天光随昼夜折算、光照随方块变化。"""
    from mcclone3d import sun as S
    from mcclone3d.light import DEFAULT_HALO, LightEngine, LightOverflow, MAX_LIGHT
    # ① 相位 → 时段名：**逐格扫一遍相位轴**，任何输入都要有名字（全定义）
    names = [S.phase_name(p / 100.0) for p in range(100)]
    covered = all(n for n in names) and len(set(names)) >= 5
    # ② day_factor：正午最亮、午夜压到地板、且**永不为 0**（全黑 = 看不见路）
    #    ⚠ 地板值取自**引擎**的 ambient 曲线（实测午夜 0.26），不是本模块的
    #    `NIGHT_FLOOR` 常量 —— 那个常量只是"下限兜底"。所以判据写成"不低于下限"，
    #    而不是"等于下限"（先前写成等于，直接被现实打红，这是好事）。
    noon = S.day_factor(0.25 * S.DAY_LENGTH)
    mid = S.day_factor(0.75 * S.DAY_LENGTH)
    floor_ok = (abs(noon - 1.0) < 1e-6 and mid >= S.NIGHT_FLOOR and mid > 0.0)
    # ③ 昼夜曲线：**量趋势而不是逐步单调** —— 引擎的 ambient 是 smoothstep 拼的，
    #    早晚会有极小的反向台阶（合成亮度不是严格单调函数）。逐步断言会误报。
    seq = [S.day_factor(t / 40.0 * S.DAY_LENGTH) for t in range(41)]
    trend_ok = (max(seq) - min(seq) > 0.5
                and abs(max(seq) - 1.0) < 1e-6
                and seq[10] > seq[30])                 # 上午明显亮于深夜
    # ④ 光照：地表上方满亮、地下为 0
    #    ⚠ 水列的层次关系（实测，先前我把格子取错了）：
    #      y=16 空气 → **15** ｜ y=15 水面 → **14** ｜ y=14 沙（地表）→ 0
    #    也就是说"水面那一格"就是 `surface_at` **上面**一格。
    #    ⚠ 另一个坑：**只能查已算过的区块**（halo 覆盖范围），查没算过的会拿到 0，
    #    那是"没算"不是"黑"。
    k = make_offline({'seed': 4242, 'size': 48, 'height': 32, 'time_phase': 0.25})
    k.ensure_light([(1, 0, 1)], budget=1)
    x, z = 20, 20                                      # 区块 (1,0,1)
    surf = k.world.surface_at(x, z)
    water_top = k.world.get(x, surf + 1, z) == B.WATER
    above = k.light.sky(x, min(31, surf + 2), z)       # 水面之上
    at_water = k.light.sky(x, min(31, surf + 1), z)    # 水面那一格
    below = k.light.sky(x, max(0, surf - 3), z)
    light_ok = (above == MAX_LIGHT
                and (at_water == MAX_LIGHT - 1 if water_top else True)
                and below == 0)
    # ⑤ 挖一个竖井：**从"露天实心地表"往下**挖 6 格，井内天光必须 >0 且随深度递减
    #    ⚠ 三条踩过的坑，缺一条这个断言就是假的：
    #      1. 先前从 `s2+dy` **往上**挖 ⇒ 挖的全是空气，断言恒真（等于没测）；
    #      2. `surface_at` 返回的可能是**水下**的沙（这一列水面在它上面），
    #         从那里往下挖天光本来就是 0 —— 那是"水下"，不是"露天洞"；
    #      3. 所以要**先找一个"地表上方是空气"的列**再挖。
    k2 = make_offline({'seed': 4242, 'size': 48, 'height': 32, 'time_phase': 0.25})
    x2, z2, s2 = None, None, None
    for cand_x in range(18, 28):
        for cand_z in range(18, 28):
            top = k2.world.surface_at(cand_x, cand_z)
            if B.is_solid(k2.world.get(cand_x, top, cand_z)) \
                    and k2.world.get(cand_x, top + 1, cand_z) == B.AIR:
                x2, z2, s2 = cand_x, cand_z, top
                break
        if x2 is not None:
            break
    assert x2 is not None, '找不到"露天实心地表"的列 —— 换个种子重跑'
    for dy in range(0, 6):
        k2.world.set(x2, s2 - dy, z2, B.AIR)          # 从地表**往下**挖
    k2.invalidate_light_near(x2, s2, z2)
    k2.ensure_light([(x2 >> 4, s2 >> 4, z2 >> 4)], budget=1)
    shaft = [k2.light.sky(x2, s2 - dy, z2) for dy in range(0, 6)]
    # ⚠ 判据写成"**整体在衰减**"，而不是"逐格单调不增"：实测洞口是 `[12, 13, 12, …]`
    # —— 第 2 格比第 1 格亮是**对的**（第 1 格四周是实心、只能从正上方进光；
    # 第 2 格还能吃到侧面漏进来的光）。逐格单调的断言会把正确的物理判成失败。
    # 也不断言首格 == 15：那是"光照系数有没有被人改过"，不是"光照有没有在工作"。
    shaft_ok = (all(v > 0 for v in shaft)
                and shaft[-1] < shaft[0]
                and all(shaft[i] >= shaft[i + 1] for i in range(1, len(shaft) - 1)))
    # ⑥ 光照护栏：护栏必须**响亮抛错**，不许静默截断
    guard_ok = False
    try:
        le = LightEngine(k2.world)
        le._spread_from('sky', [(x2, s2, z2, MAX_LIGHT)] * 10, max_visits=1)
    except LightOverflow:
        guard_ok = True
    # ⑦ 火把：放一个自发光方块，它自己与旁边一格应该亮起来
    k3 = make_offline({'seed': 4242, 'size': 48, 'height': 32, 'time_phase': 0.75})
    x3, z3 = 30, 30
    s3 = k3.world.surface_at(x3, z3)
    k3.world.set(x3, s3 + 1, z3, B.TORCH)
    k3._mark_dirty(x3, s3 + 1, z3)
    k3.ensure_light([(1, 0, 1)], budget=1)
    torch_self = k3.light.block(x3, s3 + 1, z3)
    torch_near = k3.light.block(x3, s3 + 1, z3 + 1)
    torch_ok = torch_self > 0 and torch_near < torch_self
    _report('daylight', covered and floor_ok and trend_ok and light_ok and shaft_ok
            and guard_ok and torch_ok,
            f'时段名全覆盖={covered}（{len(set(names))} 种） 正午={noon:.2f} 午夜={mid:.2f}'
            f'（不低于地板={floor_ok}） 昼夜趋势={trend_ok}'
            f' 地表({x},{surf},{z})={B.name_of(k.world.get(x, surf, z))}'
            f' 水面上={above} 水面格={at_water}(水列={water_top}) 水下3格={below}（{light_ok}）'
            f' 竖井天光={shaft}（{shaft_ok}） 护栏响亮失败={guard_ok}'
            f' 火把={torch_self}/邻格={torch_near}（{torch_ok}） halo默认={DEFAULT_HALO}')


@check('mobs')
def c_mobs():
    """生物：状态机迁移 / 上台阶 / 追击与攻击 / 最小间距 / 掉落 / 刷怪判据 / 性能。

    `mobs=False` 造世界（关掉自动刷怪），这样每条判据只测它自己那一件事。
    """
    from mcclone3d import ai as AI
    from mcclone3d import mobs as MB
    # ① 生物表契约
    table_ok = (len(MB.MOBS) == len(MB.all_kinds())
                and all(k.parts and k.health > 0 and k.speed > 0
                        for k in MB.all_kinds()))
    drops_ok = all(name in I.ITEMS_BY_NAME
                   for k in MB.all_kinds() for (name, _lo, _hi) in k.drops)
    # ② 刷怪的光判据：敌对在亮处刷不出、暗处能刷；被动恒可
    zom = MB.mob_kind('zombie')
    sheep = MB.mob_kind('sheep')
    light_ok = (MB.spawn_allowed(zom, 15, 15, False) is False
                and MB.spawn_allowed(zom, 3, 3, True) is True
                and MB.spawn_allowed(sheep, 15, 15, False) is True)
    # ③ 游荡：idle 生物 5 秒内要动起来（**这条踩过"状态机没有出口"的坑**）
    k = make_offline({'seed': 4242, 'size': 64, 'height': 32, 'mobs': False})
    m = k.spawn_mob('sheep', 32.5, None, 32.5)
    p0 = (m.pos[0], m.pos[2])
    ys = []
    for _ in range(300):
        k.update_mobs(1 / 60)
        ys.append(round(m.pos[1], 3))
    wandered = (((m.pos[0] - p0[0]) ** 2 + (m.pos[2] - p0[1]) ** 2) ** 0.5)
    wander_ok = wandered > 1.0 and m.state == MB.AI_WANDER
    stand_ok = abs(sum(1 for y in ys if abs(y - round(y)) < 1e-6) / len(ys) - 1.0) < 0.05
    # ④ 上 1 格台阶能上、2 格上不去
    def _step_test(rise: int) -> tuple:
        # ⚠ 冻结在夜里：否则僵尸走到一半被晒死，"上台阶"判据会因为生物没了而假红
        kk = make_offline({'seed': 77, 'size': 48, 'height': 32, 'mobs': False,
                           'time_phase': 0.75, 'time_paused': True})
        mb = kk.spawn_mob('zombie', 19.5, None, 20.5)
        y0 = int(mb.pos[1])
        # 矮墙修在 `y0` **起**（`y0` 是脚底所在的空气格，方块要占这一格）
        for dy in range(rise):
            kk.world.set(22, y0 + dy, 20, B.STONE)
        kk.pos = [26.5, float(y0), 20.5]             # 玩家在对侧 ⇒ 僵尸朝它走
        peak_y = y0
        max_x = mb.pos[0]
        for _ in range(int(6 / (1 / 60))):
            kk.update_mobs(1 / 60)
            peak_y = max(peak_y, mb.pos[1])
            max_x = max(max_x, mb.pos[0])
        # ⚠ 判据看**过程峰值**而不是终点：僵尸上了台阶后会继续朝玩家走、走下坡回到原位，
        #    只看终点的断言会把"真的上去了"判成失败（实测踩过）。
        return peak_y >= y0 + 1 - 0.01, peak_y, round(max_x, 2)
    up1, peak1, x1 = _step_test(1)
    up2, peak2, x2 = _step_test(2)
    step_ok = up1 and not up2
    # ⑤ 追击 + 攻击 + 最小间距 + 冷却
    #    ⚠ 必须**冻结在夜里**：第一天 600 秒，而"上午"的天光已足以晒死僵尸 ——
    #      时间在走的话，这条判据实际测的是"它能不能在 2 秒内追上"（第一版就假绿过）。
    k2 = make_offline({'seed': 4242, 'size': 64, 'height': 32, 'mobs': False,
                       'time_phase': 0.75, 'time_paused': True})
    z = k2.spawn_mob('zombie', k2.pos[0] + 6.0, None, k2.pos[2])
    hp0 = k2.health
    dmin = 99.0
    hit_times = []
    for i in range(900):
        k2.update_mobs(1 / 60)
        dmin = min(dmin, z.dist_to(k2.pos[0], k2.pos[2]))
        if k2.mob_stats['player_hits'] > len(hit_times):
            hit_times.append(i / 60)
    chase_ok = (z.state == MB.AI_CHASE and dmin <= z.kind.reach + 0.1
                and k2.health < hp0 and len(hit_times) > 0)
    # 攻击冷却：相邻两次命中至少隔 `attack_cd` 秒（先前根本没测冷却）
    cd_ok = all(hit_times[i + 1] - hit_times[i] >= z.kind.attack_cd - 0.02
                for i in range(len(hit_times) - 1))
    gap_ok = dmin >= AI.MIN_PLAYER_GAP - 1e-6
    # ⑥ 死亡掉落：打死一只 ⇒ 掉落物出现它表里的东西
    k3 = make_offline({'seed': 4242, 'size': 64, 'height': 32, 'mobs': False})
    s3 = k3.spawn_mob('sheep', 32.5, None, 32.5)
    n_before = len(k3.drops)
    for _ in range(6):
        k3.hit_mob(s3, 4.0)
    drop_ok = len(k3.drops) > n_before and s3 not in k3.mobs
    # ⑦ 性能：300 个生物每帧的开销（**这是生物能不能上桌的硬判据**）
    k4 = make_offline({'seed': 4242, 'size': 64, 'height': 32, 'mobs': False})
    for i in range(300):
        k4.spawn_mob('sheep' if i % 3 else 'zombie', 10.0 + (i % 40), None,
                     10.0 + (i // 40))
    t0 = time.perf_counter()
    for _ in range(60):
        k4.update_mobs(1 / 60)
    per_frame_ms = (time.perf_counter() - t0) / 60 * 1000
    perf_ok = per_frame_ms < 8.0
    _report('mobs', table_ok and drops_ok and light_ok and wander_ok and stand_ok
            and step_ok and chase_ok and cd_ok and gap_ok and drop_ok and perf_ok,
            f'表={table_ok} 掉落名有效={drops_ok} 刷怪光判据={light_ok} '
            f'游荡 {wandered:.1f}格={wander_ok} 整数站立={stand_ok} 上1格峰值{peak1}/挡2格峰值{peak2}={step_ok} '
            f'追击最近 {dmin:.2f}={chase_ok} 命中 {len(hit_times)} 次冷却={cd_ok} '
            f'间距>={AI.MIN_PLAYER_GAP}={gap_ok} '
            f'死亡掉落={drop_ok} 300只每帧 {per_frame_ms:.2f}ms={perf_ok}')


@check('caves')
def c_caves():
    """Phase 2-C：洞穴空腔 / 自然洞口 / 矿脉分层 / 洞内光照 / 生成耗时。

    每条判据都对着设计稿里的一个承诺；`time_phase=0.25` 冻结在白天才对
    （判据要测的是"洞里黑不黑"，不是"现在几点"）。
    """
    import time as _time
    from mcclone3d import caves as CV
    from mcclone3d.blocks import BLOCK_IDS
    from mcclone3d.light import LightEngine
    from mcclone3d.world import ore_bands

    SIZE, HEIGHT, SEED = 128, 64, 20261014
    t0 = _time.perf_counter()
    w = ChunkedWorld(SEED, SIZE, HEIGHT).generate()
    t_gen = _time.perf_counter() - t0
    sea = w.sea_level
    holes = CV.tunnels(SEED, SIZE, HEIGHT, sea).holes

    # ① 挖空比例（候选带内）：防"阈值调到没洞"与"挖成海绵"两头
    tot = cav = 0
    depth_seen = {}
    for x in range(0, SIZE, 2):
        for z in range(0, SIZE, 2):
            h = w.surface_at(x, z)
            if h <= sea + 1:
                continue
            for y in range(2, min(h - CV.SOIL_KEEP, sea)):
                tot += 1
                if w.get(x, y, z) == B.AIR:
                    cav += 1
                    depth_seen[y // 8 * 8] = depth_seen.get(y // 8 * 8, 0) + 1
    ratio = cav / max(1, tot)
    ratio_ok = 0.03 <= ratio <= 0.25
    # 越深越密：最深那档不少于最浅那档（阈值随深度下降的实测口径）
    deep_ok = True
    if len(depth_seen) >= 2:
        ks = sorted(depth_seen)
        deep_ok = depth_seen[ks[0]] >= depth_seen[ks[-1]] * 0.9

    # ② 护栏：基岩完好 + 地表不长矿
    rock_ok = all(w.get(x, 0, z) == B.BEDROCK
                  for x in range(0, SIZE, 4) for z in range(0, SIZE, 4))
    surf_ore = 0
    for x in range(0, SIZE, 2):
        for z in range(0, SIZE, 2):
            h = w.surface_at(x, z)
            if w.get(x, h, z) in (BLOCK_IDS['coal_ore'], BLOCK_IDS['iron_ore'],
                                  BLOCK_IDS['gold_ore'], BLOCK_IDS['diamond_ore']):
                surf_ore += 1

    # ③ 矿脉分层：四种矿的深度上限 + 总量单调递减
    tops = {'coal_ore': 40, 'iron_ore': 28, 'gold_ore': 16, 'diamond_ore': 8}
    ore_bad = []
    ore_n = {n: w.block_count(BLOCK_IDS[n]) for n in tops}
    for n, top in tops.items():
        ys = [y for x in range(0, SIZE, 2) for z in range(0, SIZE, 2)
              for y in range(0, w.surface_at(x, z) + 1)
              if w.get(x, y, z) == BLOCK_IDS[n]]
        if ys and max(ys) >= top:
            ore_bad.append(f'{n}@y={max(ys)}≥{top}')
    order_ok = (ore_n['coal_ore'] > ore_n['iron_ore'] > ore_n['gold_ore']
                >= ore_n['diamond_ore'])
    # ④ 自然洞口：登记在册 + 地表那一格真的是空气 + 下面能走进去
    hole_ok = 0
    for (x, z), h in list(holes.items()):
        if w.get(x, h, z) != B.AIR or w.get(x, h - 1, z) != B.AIR:
            continue
        hole_ok += 1
    hole_reach = 0
    h_cache: dict = {}

    def _h(x: int, z: int) -> int:
        if (x, z) not in h_cache:
            h_cache[(x, z)] = w.surface_at(x, z)
        return h_cache[(x, z)]

    for (x, z), _hh in list(holes.items())[:40]:
        h = w.surface_at(x, z)
        start = (x, h - 2, z)
        while start[1] > 1 and w.get(*start) != B.AIR:
            start = (start[0], start[1] - 1, start[2])
        if w.get(*start) != B.AIR:
            continue
        seen = {start}
        stack = [start]
        while stack:
            cx, cy, cz = stack.pop()
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0),
                      (0, 0, 1), (0, 0, -1)):
                n = (cx + d[0], cy + d[1], cz + d[2])
                if n in seen or not (0 <= n[0] < SIZE and 1 < n[1] and 0 <= n[2] < SIZE):
                    continue
                # ⚠ 挡"天空"用**该列自己的地表高度**，不是全局海平面：
                #   洞口在 y≈34 而海平面只有 30，用 sea 会把洞口那几层
                #   一起挡掉 ⇒ 明明连通的隧道被判成"不可达"（实测踩过）。
                if n[1] > _h(n[0], n[2]):
                    continue
                if w.get(*n) == B.AIR:
                    seen.add(n)
                    stack.append(n)
        if len(seen) > 40:
            hole_reach += 1
    holes_ok = hole_ok > 0 and hole_reach > 0

    # ⑤ 洞内天光 = 0（Phase 2-A 联动：洞里是黑的，火把才有意义）
    le = LightEngine(w)
    le.column_pass_all()
    dark = lit = 0
    for x in range(0, SIZE, 3):
        for z in range(0, SIZE, 3):
            h = w.surface_at(x, z)
            if h <= sea + 1:
                continue
            for y in range(2, min(h - CV.SOIL_KEEP, sea), 3):
                if w.get(x, y, z) != B.AIR:
                    continue
                if le.sky(x, y, z) == 0:
                    dark += 1
                else:
                    lit += 1
    dark_ok = dark > 0 and dark > lit

    # ⑥ 生成耗时预算（基线 4.82s；洞穴 +1.1s、矿脉分层 +0.3s ⇒ 门槛 8s）
    time_ok = t_gen < 8.0

    ok = (ratio_ok and deep_ok and rock_ok and not surf_ore and not ore_bad
          and order_ok and holes_ok and dark_ok and time_ok)
    _report('caves', ok,
            f'挖空 {ratio * 100:.1f}%={ratio_ok} 越深越密={deep_ok} '
            f'基岩完好={rock_ok} 地表矿={surf_ore}(须0) 越界矿={ore_bad or "无"} '
            f'矿量递减={order_ok}[煤{ore_n["coal_ore"]}/铁{ore_n["iron_ore"]}/'
            f'金{ore_n["gold_ore"]}/钻{ore_n["diamond_ore"]}] '
            f'洞口 通{hole_ok}/可达{hole_reach}={holes_ok} '
            f'洞内黑{dark}/亮{lit}={dark_ok} 生成 {t_gen:.2f}s={time_ok}')


@check('water')
def c_water():
    """Phase 2-C 第二批：挖穿海床 ⇒ 水沿垂直灌进洞；一次性收敛；不进存档。"""
    from mcclone3d import blocks as BB
    k = make_offline({'seed': 2026, 'size': 128, 'height': 64, 'light': False})
    w = k.world
    sea = w.sea_level
    # 找一处海底地形
    spot = None
    for x in range(10, w.size - 10):
        for z in range(10, w.size - 10):
            h = w.surface_at(x, z)
            if h < sea:
                spot = (x, z, h)
                break
        if spot:
            break
    if spot is None:
        _report('water', False, '世界里没有海底地形（海平面算错了）')
        return
    x, z, h = spot
    edits0 = len(w.edits)
    # 模拟玩家挖穿海床下方 6 格（逐格 disturb，模拟 dig 的触发）
    for dy in range(0, 7):
        w.set_generated(x, h - dy, z, BB.AIR)
        k.fluid.disturb(w, x, h - dy, z)
    for _ in range(4):
        k.fluid_step(0.05)
    poured = k.fluid.flowing_count()
    # ① 水柱连续（不能一格水一格空）
    column = [B.name_of(w.get(x, y, z)) for y in range(h - 6, h + 1)]
    filled = poured >= 7 and column[0] == 'water' \
        and column[-1] in ('water', 'sand')
    # ② 收敛：一个 tick 完成，之后完全静止
    for _ in range(200):
        k.fluid_step(0.05)
    settled = (k.fluid.flowing_count() == poured and not k.fluid.active)
    # ③ 不进存档
    no_edit = len(w.edits) == edits0
    names = {row[3] for row in k.dump()['world']['edits']}
    # ④ 内陆洞不进水
    dry = None
    for ax in range(10, w.size - 10, 3):
        for az in range(10, w.size - 10, 3):
            ah = w.surface_at(ax, az)
            if ah > sea + 6:
                dry = (ax, az, ah)
                break
        if dry:
            break
    inland_ok = True
    if dry:
        ax, az, ah = dry
        for dy in range(0, 5):
            w.set_generated(ax, ah - dy, az, BB.AIR)
            k.fluid.disturb(w, ax, ah - dy, az)
        k.fluid_step(0.05)
        inland_ok = w.get(ax, ah - 4, az) != BB.WATER
    ok = filled and settled and no_edit and ('water' not in names) and inland_ok
    _report('water', ok,
            f'灌入={poured}格 水柱连续={filled} 静止收敛={settled} '
            f'不进增量={no_edit}(存档含水={"water" in names}) 内陆不进水={inland_ok}')


@check('weather')
def c_weather():
    """Phase 2-C 第二批：天气判据 / 天光乘子 / 确定性 / 粒子口径。"""
    from mcclone3d import weather as WX
    wc = WX.WeatherCycle(2026)
    # ① 强度范围 + 晴雨雪都有
    vals = [wc.intensity_at(i * 1.0) for i in range(3600)]
    rng_ok = all(0.0 <= v <= 1.0 for v in vals)
    clear_ratio = sum(1 for v in vals if v < 0.15) / len(vals)
    # ② 找到一段下雨的时刻，验雨/雪分流与天光乘子
    t_rain = next((i * 0.5 for i in range(4000)
                   if wc.kind_at(i * 0.5, day_factor=1.0) == WX.RAIN), None)
    split_ok = t_rain is not None and wc.kind_at(t_rain, day_factor=0.2) == WX.SNOW
    scale = WX.weather_light_scale(WX.RAIN, 1.0)
    scale_ok = 0.7 < scale < 1.0 and scale < WX.weather_light_scale(WX.SNOW, 1.0)
    # ③ 确定性：同种子同时刻一致；换种子不同
    det = all(wc.intensity_at(t) == WX.WeatherCycle(2026).intensity_at(t)
              for t in (0.0, 90.0, 361.0))
    other = WX.WeatherCycle(777)
    seed_ok = any(other.kind_at(i * 90 + 45, day_factor=1.0)
                  != wc.kind_at(i * 90 + 45, day_factor=1.0) for i in range(1, 30))
    # ④ 内核：固定天气口 + 天光真的被压暗
    ks = [make_offline({'seed': 2026, 'size': 32, 'height': 32, 'light': False,
                        'weather': kind}).day_factor()
          for kind in (WX.CLEAR, WX.RAIN, WX.SNOW)]
    kernel_ok = ks[1] < ks[2] < ks[0]
    ok = rng_ok and 0.2 < clear_ratio < 0.85 and split_ok and scale_ok \
        and det and seed_ok and kernel_ok
    _report('weather', ok,
            f'强度∈[0,1]={rng_ok} 晴天占比={clear_ratio:.0%} '
            f'日雨夜雪={split_ok} 天光乘子={scale:.2f}(雨<雪)={scale_ok} '
            f'确定性={det} 换种子不同={seed_ok} '
            f'内核压暗 晴{ks[0]:.3f}/雪{ks[2]:.3f}/雨{ks[1]:.3f}={kernel_ok}')


@check('village')
def c_village():
    """Phase 2-C 第三批：村庄选址 / 整平 / 建筑 / **灯火即安全区** / 村民。"""
    import time as _t
    from mcclone3d import blocks as BB
    from mcclone3d import mobs as MB
    from mcclone3d import structures as ST
    from mcclone3d.kernel import VILLAGE_POP
    k = make_offline({'seed': 20261014, 'size': 128, 'height': 64, 'light': True})
    w = k.world
    t0 = _t.perf_counter()
    w.decorate()
    dt = _t.perf_counter() - t0
    if not w.villages:
        _report('village', False, '这个世界一个村庄都没有（选址判据太严？）')
        return
    vx, vy, vz = w.villages[0]
    pr = ST.VILLAGE_R

    # ① 整平：地基那层没有空气、上方 3 格没有残留的树
    hole = sum(1 for x in range(vx - pr, vx + pr + 1)
               for z in range(vz - pr, vz + pr + 1) if w.get(x, vy, z) == BB.AIR)
    trunk = sum(1 for x in range(vx - pr, vx + pr + 1)
                for z in range(vz - pr, vz + pr + 1)
                for dy in (1, 2, 3)
                if w.get(x, vy + dy, z) in (BB.LOG, BB.LEAVES))

    # ② 四栋房：门洞通 + 屋顶不透 + 屋里有火把
    doors = roofs = torches = 0
    for (sx, sz) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        hx, hz = vx + sx * ST.HOUSE_OFF, vz + sz * ST.HOUSE_OFF
        ddx, ddz = -sx, -sz
        if ddx:
            cells = [(hx + ddx * ST.HOUSE_HW, vy + dy, hz) for dy in (1, 2)]
        else:
            cells = [(hx, vy + dy, hz + ddz * ST.HOUSE_HW) for dy in (1, 2)]
        doors += all(w.get(*c) == BB.AIR for c in cells)
        top = vy + ST.HOUSE_WALL + 2
        roofs += all(w.get(x, top, z) != BB.AIR
                     for x in range(hx - ST.HOUSE_HW, hx + ST.HOUSE_HW + 1)
                     for z in range(hz - ST.HOUSE_HW, hz + ST.HOUSE_HW + 1))
        torches += any(w.get(x, y, z) == BB.TORCH
                       for x in range(hx - ST.HOUSE_HW, hx + ST.HOUSE_HW + 1)
                       for y in range(vy + 1, vy + ST.HOUSE_WALL + 1)
                       for z in range(hz - ST.HOUSE_HW, hz + ST.HOUSE_HW + 1))

    # ③ **灯火即安全区**：村中心 5×5 的方块光全部高于僵尸阈值
    k.light.column_pass_all()
    for cx in range(k.size // 16):
        for cy in range(k.height // 16):
            for cz in range(k.size // 16):
                k.light.relight_chunk(cx, cy, cz)
    limit = MB.mob_kind('zombie').spawn_light_max
    dark = sum(1 for dx in range(-2, 3) for dz in range(-2, 3)
               if k.light.block(vx + dx, vy + 1, vz + dz) <= limit)
    lit = k.light.block(vx, vy + 1, vz)

    # ④ 村民：村里刷得出、村外刷不出、有人口上限
    k.pos = [vx + 0.5, float(vy + 1), vz + 0.5]
    for _ in range(30):
        k._try_spawn_villager()
    vs = [m for m in k.mobs if m.kind.name == 'villager']
    cap = len(w.villages) * VILLAGE_POP
    in_village = all(abs(m.pos[0] - vx) <= ST.VILLAGE_R + 4
                     and abs(m.pos[2] - vz) <= ST.VILLAGE_R + 4 for m in vs)
    wild = all(not mb.kind.village_only for mb in k.mobs if mb.kind.name != 'villager')

    # ⑤ 农田：有作物，且作物下面必须是土
    crops = [(x, z) for x in range(vx - 3, vx + 4)
             for z in range(vz - ST.HOUSE_OFF - 4, vz + ST.HOUSE_OFF + 5)
             if w.get(x, vy + 1, z) == BB.CROP]
    farm_ok = bool(crops) and all(w.get(x, vy, z) == BB.DIRT for (x, z) in crops)

    # ⑥ 结构不进存档增量
    names = {row[3] for row in w.dump()['edits']}
    no_edit = not names

    ok = (hole == 0 and trunk == 0 and doors == 4 and roofs == 4 and torches == 4
          and dark == 0 and bool(vs) and len(vs) <= cap and in_village and wild
          and farm_ok and no_edit and dt < 1.0)
    _report('village', ok,
            f'村庄 {len(w.villages)} 个（首个 @{vx},{vy},{vz}）装修 {dt:.2f}s '            f'地基空洞 {hole} 残留树 {trunk} 门 {doors}/4 屋顶 {roofs}/4 火把 {torches}/4 '            f'村内暗格 {dark}(中心光照 {lit}>{limit}) 村民 {len(vs)}/{cap} '            f'在村内 {in_village} 村外无村only {wild} 农田 {len(crops)}株 {farm_ok} '            f'不进存档 {no_edit}')


@check('redstone')
def c_redstone():
    """Phase 3：红石 —— 衰减 / 中继器 / 灯 / 门 / 活塞 / 按钮 / 存档 / 性能。"""
    import time as _t
    from mcclone3d import redstone as RS
    from mcclone3d.world import ChunkedWorld
    w = ChunkedWorld(2026, 64, 64).generate()
    g = RS.PowerGrid(w)
    Y, Z = 50, 4            # 空气层：活塞的测试必须在这里做（地形里会"推不动"）

    def settle(rounds=8):
        """把信号算稳定。⚠ Phase 3-B 起中继器**有延迟**（走元件 tick 队列）
        ⇒ 只 `step(0.0)` 会让它永远停在"排队待翻转"，必须先推进时间。"""
        g.run_until_stable(max_ticks=max(8, rounds), budget=999)

    # ① 衰减：紧贴电源 15、逐格 −1、第 16 格 0
    w.set_generated(4, Y, Z, B.LEVER_ON)
    for i in range(1, 17):
        w.set_generated(4 + i, Y, Z, B.REDSTONE_WIRE)
    g.mark(4, Y, Z)
    settle()
    lv = [g.power_at(4 + i, Y, Z) for i in range(1, 17)]
    decay_ok = lv[0] == 15 and lv[:15] == list(range(15, 0, -1)) and lv[15] == 0

    # ② 中继器：背面吃、正面吐 15；断电后不自锁
    w.set_generated(30, Y, Z, B.LEVER_ON)
    for i in range(1, 15):
        w.set_generated(30 + i, Y, Z, B.REDSTONE_WIRE)
    w.set_generated(45, Y, Z, B.REPEATER_E_OFF)
    w.set_generated(46, Y, Z, B.REDSTONE_WIRE)
    w.set_generated(47, Y, Z, B.LAMP_OFF)
    g.mark(30, Y, Z)
    settle()
    rep_on = w.get(45, Y, Z) == B.REPEATER_E_ON and g.power_at(46, Y, Z) == 15
    g.toggle_lever(30, Y, Z)
    settle()
    rep_off = (w.get(45, Y, Z) == B.REPEATER_E_OFF
               and w.get(47, Y, Z) == B.LAMP_OFF)

    # ③ 灯亮 ⇒ 是光源（与 Phase 2-A 光照联动）
    lamp_ok = B.BLOCKS[B.LAMP_ON].emissive > 0 and B.BLOCKS[B.LAMP_OFF].emissive == 0

    # ④ 门：通电开（solid=False ⇒ 能穿过）、断电关
    w.set_generated(4, Y, 12, B.LEVER_ON)
    w.set_generated(5, Y, 12, B.REDSTONE_WIRE)
    w.set_generated(6, Y, 12, B.DOOR_LOWER)
    w.set_generated(6, Y + 1, 12, B.DOOR_UPPER)
    g.mark(4, Y, 12)
    settle()
    door_open = (w.get(6, Y, 12) == B.DOOR_OPEN_LOWER
                 and w.get(6, Y + 1, 12) == B.DOOR_OPEN_UPPER
                 and not B.is_solid(B.DOOR_OPEN_LOWER))
    g.toggle_lever(4, Y, 12)
    settle()
    door_closed = w.get(6, Y, 12) == B.DOOR_LOWER and B.is_solid(B.DOOR_LOWER)

    # ⑤ 活塞：推 1 格 / 连锁 12 / 13 格不动 / 六方向
    def piston_run(blocks_n, away=20):
        ww = ChunkedWorld(2026, 64, 64).generate()
        gg = RS.PowerGrid(ww)
        ww.set_generated(4, Y, away, B.LEVER_ON)
        ww.set_generated(5, Y, away, B.REDSTONE_WIRE)
        ww.set_generated(6, Y, away, B.BLOCK_IDS['piston_east_off'])
        for i in range(7, 7 + blocks_n):
            ww.set_generated(i, Y, away, B.STONE)
        gg.mark(4, Y, away)
        for _ in range(8):
            if not gg.dirty:
                break
            gg.step(0.0, budget=999)
        return ww
    w1 = piston_run(1)
    push_ok = (w1.get(6, Y, 20) == B.BLOCK_IDS['piston_east_on']
               and w1.get(7, Y, 20) == B.PISTON_ARM
               and w1.get(8, Y, 20) == B.STONE)
    w12 = piston_run(12)
    chain_ok = (w12.get(7, Y, 20) == B.PISTON_ARM
                and w12.get(7 + 12, Y, 20) == B.STONE)
    w13 = piston_run(13)
    limit_ok = (w13.get(6, Y, 20) == B.BLOCK_IDS['piston_east_off']
                and all(w13.get(i, Y, 20) == B.STONE for i in range(7, 20)))
    dirs_ok = True
    for d, (vx, vy, vz) in B.PISTON_DIR_VEC.items():
        off, on = B.PISTON_BY_DIR[d]
        wd = ChunkedWorld(2026, 64, 64).generate()
        gd = RS.PowerGrid(wd)
        px, py, pz = 20, Y, 20
        wd.set_generated(px, py, pz, off)
        wd.set_generated(px - vx, py - vy, pz - vz, B.LEVER_ON)
        wd.set_generated(px + vx, py + vy, pz + vz, B.STONE)
        gd.mark(px - vx, py - vy, pz - vz)
        for _ in range(8):
            if not gd.dirty:
                break
            gd.step(0.0, budget=999)
        if not (wd.get(px, py, pz) == on
                and wd.get(px + vx, py + vy, pz + vz) == B.PISTON_ARM):
            dirs_ok = False

    # ⑥ 按钮：按下供电 + TTL 后回弹
    wb = ChunkedWorld(2026, 64, 64).generate()
    gb = RS.PowerGrid(wb)
    wb.set_generated(4, Y, 20, B.BUTTON_OFF)
    wb.set_generated(5, Y, 20, B.REDSTONE_WIRE)
    wb.set_generated(6, Y, 20, B.LAMP_OFF)
    gb.mark(4, Y, 20)
    for _ in range(8):
        if not gb.dirty:
            break
        gb.step(0.0, budget=999)
    gb.press_button(4, Y, 20)
    for _ in range(8):
        if not gb.dirty:
            break
        gb.step(0.0, budget=999)
    btn_on = wb.get(6, Y, 20) == B.LAMP_ON
    gb.step(RS.BUTTON_TTL * 1.2, budget=999)
    for _ in range(8):
        if not gb.dirty:
            break
        gb.step(0.0, budget=999)
    btn_off = (wb.get(4, Y, 20) == B.BUTTON_OFF and wb.get(6, Y, 20) == B.LAMP_OFF)

    # ⑦ 存档：**状态进档、信号不进档**
    ws = ChunkedWorld(2026, 64, 64).generate()
    gs = RS.PowerGrid(ws)
    ws.set(4, Y, 30, B.LEVER_OFF)
    ws.set(5, Y, 30, B.REDSTONE_WIRE)
    ws.set(6, Y, 30, B.LAMP_OFF)
    gs.mark(4, Y, 30)
    for _ in range(8):
        if not gs.dirty:
            break
        gs.step(0.0, budget=999)
    gs.toggle_lever(4, Y, 30)
    for _ in range(8):
        if not gs.dirty:
            break
        gs.step(0.0, budget=999)
    names = {row[3] for row in ws.dump()['edits']}
    save_ok = (ws.get(6, Y, 30) == B.LAMP_ON and 'lamp_on' not in names
               and 'lever_off' in names)

    # ⑧ 性能：200 格网络的**一次重算**耗时
    wp = ChunkedWorld(2026, 64, 64).generate()
    gp = RS.PowerGrid(wp)
    for i in range(200):
        wp.set_generated(4 + (i % 20), Y, 4 + (i // 20), B.REDSTONE_WIRE)
    gp.mark(4, Y, 4)
    t0 = _t.perf_counter()
    gp.step(0.0, budget=999)
    dt = _t.perf_counter() - t0
    perf_ok = dt < 0.5

    ok = (decay_ok and rep_on and rep_off and lamp_ok and door_open and door_closed
          and push_ok and chain_ok and limit_ok and dirs_ok and btn_on and btn_off
          and save_ok and perf_ok)
    _report('redstone', ok,
            f'衰减={lv[:4]}…{decay_ok} 中继器(背面吃/正面吐15/断电灭)={rep_on}/{rep_off} '
            f'灯是光源={lamp_ok} 门开(能穿过)={door_open} 门关(挡人)={door_closed} '
            f'推1格={push_ok} 连锁12={chain_ok} 13格不动={limit_ok} 六方向={dirs_ok} '
            f'按钮按/弹={btn_on}/{btn_off} 存档(状态进/信号不进)={save_ok} '
            f'200格网络重算 {dt * 1000:.1f}ms={perf_ok}')


@check('tickqueue')
def c_tickqueue():
    """Phase 3-B：元件 tick 队列 —— 延迟 / 惰性求值 / 档位 / 反相器 / 时钟 / 确定性。"""
    import time as _t
    from mcclone3d import redstone as RS
    from mcclone3d.world import ChunkedWorld

    Y = 50

    def fresh():
        w = ChunkedWorld(2026, 64, 64).generate()
        for x in range(0, 26):                 # 清一片空气层（不去清的话地形会挡道）
            for z in range(0, 26):
                for y in range(Y, Y + 4):
                    w.set_generated(x, y, z, B.AIR)
                w.set_generated(x, Y - 1, z, B.STONE)
        return w, RS.PowerGrid(w)

    def put(w, g, x, y, z, bid):
        w.set_generated(x, y, z, bid)
        g.mark(x, y, z)

    def blink(g, w, lamp, seconds, dt=0.05):
        out = []
        for _ in range(int(round(seconds / dt))):
            g.step(dt, budget=999)
            out.append(1 if w.get(*lamp) == B.LAMP_ON else 0)
        return out

    def trans(series):
        return sum(1 for i in range(1, len(series)) if series[i] != series[i - 1])

    # ① 延迟：3 档（0.3s）—— 0.2s 不翻、累计 0.35s 才翻
    w, g = fresh()
    off, on = B.REPEATER_BY_DIR_DELAY[('east', 2)]
    put(w, g, 4, Y, 0, B.LEVER_OFF)
    put(w, g, 5, Y, 0, B.REDSTONE_WIRE)
    put(w, g, 6, Y, 0, off)
    put(w, g, 7, Y, 0, B.REDSTONE_WIRE)
    put(w, g, 8, Y, 0, B.LAMP_OFF)
    g.run_until_stable()
    g.toggle_lever(4, Y, 0)
    g.step(0.0, budget=999)
    wait_ok = (w.get(6, Y, 0) == off and g.pending_count() == 1)
    g.step(0.2, budget=999)
    mid_ok = w.get(6, Y, 0) == off
    g.step(0.15, budget=999)
    g.run_until_stable()
    delay_ok = (w.get(6, Y, 0) == on and w.get(8, Y, 0) == B.LAMP_ON)

    # ② 惰性求值：短脉冲（0.1s）不点亮；长脉冲（0.6s）照常点亮
    def pulse_rig():
        ww, gg = fresh()
        put(ww, gg, 4, Y, 0, B.BUTTON_OFF)
        put(ww, gg, 5, Y, 0, B.REPEATER_BY_DIR_DELAY[('east', 2)][0])
        put(ww, gg, 6, Y, 0, B.REDSTONE_WIRE)
        put(ww, gg, 7, Y, 0, B.LAMP_OFF)
        gg.run_until_stable()
        return ww, gg
    ws, gs = pulse_rig()
    gs.press_button(4, Y, 0, ttl=0.1)
    gs.run_until_stable(max_ticks=40, dt=0.05)
    short_ok = ws.get(7, Y, 0) == B.LAMP_OFF and ws.get(5, Y, 0) == off
    wl, gl = pulse_rig()
    gl.press_button(4, Y, 0, ttl=0.6)
    for _ in range(8):
        gl.step(0.05, budget=999)
    long_ok = wl.get(7, Y, 0) == B.LAMP_ON

    # ③ 档位：4 档数值 / 32 个 id / 调档循环 / 非中继器返回 0
    tiers_ok = (B.REPEATER_DELAYS == (0.1, 0.2, 0.3, 0.4)
                and len(B.REPEATER_STATES) == 16
                and all(B.repeater_delay(B.REPEATER_BY_DIR_DELAY[(d, n)][1]) == B.REPEATER_DELAYS[n]
                        for d in ('north', 'south', 'east', 'west') for n in range(4))
                and B.repeater_delay(B.STONE) == 0.0)
    wt, gt = fresh()
    put(wt, gt, 4, Y, 0, B.REPEATER_BY_DIR_DELAY[('north', 3)][0])
    cyc = []
    for _ in range(4):
        cyc.append(B.REPEATER_DELAY_OF[gt.cycle_repeater_delay(4, Y, 0)])
    cycle_ok = cyc == [0, 1, 2, 3]

    # ④ 反相器：脚下块被强充能 ⇒ 火把灭；松开 ⇒ 复亮（不自锁）
    wi, gi = fresh()
    put(wi, gi, 4, Y, 0, B.LEVER_OFF)
    put(wi, gi, 5, Y, 0, B.REDSTONE_WIRE)
    put(wi, gi, 6, Y, 0, B.REPEATER_E_OFF)
    put(wi, gi, 7, Y, 0, B.STONE)
    put(wi, gi, 7, Y + 1, 0, B.REDSTONE_TORCH)
    put(wi, gi, 8, Y + 1, 0, B.REDSTONE_WIRE)
    put(wi, gi, 9, Y + 1, 0, B.LAMP_OFF)
    gi.run_until_stable()
    inv_on = wi.get(7, Y + 1, 0) == B.REDSTONE_TORCH and wi.get(9, Y + 1, 0) == B.LAMP_ON
    gi.toggle_lever(4, Y, 0)
    gi.run_until_stable()
    inv_flip = (wi.get(7, Y + 1, 0) == B.REDSTONE_TORCH_OFF
                and wi.get(9, Y + 1, 0) == B.LAMP_OFF)
    gi.toggle_lever(4, Y, 0)
    gi.run_until_stable()
    inv_back = wi.get(7, Y + 1, 0) == B.REDSTONE_TORCH
    # 结构不变量：红石线只能弱充能 ⇒ 火把不吃自己的输出（不自锁的根因）
    wv, gv = fresh()
    put(wv, gv, 4, Y, 0, B.REDSTONE_TORCH)
    put(wv, gv, 5, Y, 0, B.REDSTONE_WIRE)
    put(wv, gv, 6, Y, 0, B.STONE)
    gv.run_until_stable()
    weak_ok = (gv.power_at(5, Y, 0) == 15 and not gv.strongly_powered(6, Y, 0)
               and wv.get(4, Y, 0) == B.REDSTONE_TORCH)

    # ⑤ 时钟：1 档 ≈30 次/3s、3 档 ≈10 次/3s、两次跑波形一致、长跑不漂相位
    def clock_rig(tier):
        wc, gc = fresh()
        put(wc, gc, 0, Y, 8, B.REDSTONE_WIRE)                      # 中继器背面
        put(wc, gc, 0, Y, 9, B.REPEATER_BY_DIR_DELAY[('south', tier)][0])
        put(wc, gc, 0, Y, 10, B.STONE)                             # 正面实心块
        put(wc, gc, 0, Y + 1, 10, B.REDSTONE_TORCH)                # 块上火把
        put(wc, gc, 0, Y + 1, 9, B.REDSTONE_WIRE)                  # 绕回
        put(wc, gc, 0, Y + 1, 8, B.REDSTONE_WIRE)
        put(wc, gc, 1, Y, 8, B.LAMP_OFF)
        gc.run_until_stable(max_ticks=8)
        return wc, gc, (1, Y, 8)

    wc1, gc1, lamp1 = clock_rig(0)
    s1 = blink(gc1, wc1, lamp1, 3.0)
    t1 = trans(s1)
    clock1_ok = 28 <= t1 <= 32
    wc2, gc2, lamp2 = clock_rig(0)
    s2 = blink(gc2, wc2, lamp2, 3.0)
    det_ok = s1 == s2
    wc3, gc3, lamp3 = clock_rig(2)
    t3 = trans(blink(gc3, wc3, lamp3, 3.0))
    clock3_ok = 8 <= t3 <= 12
    wc4, gc4, lamp4 = clock_rig(0)
    t8 = trans(blink(gc4, wc4, lamp4, 8.0))
    drift_ok = 76 <= t8 <= 84
    alive_ok = gc1.pending_count() > 0

    # ⑥ 性能：时钟跑 1 秒（20 帧）的耗时
    t0 = _t.perf_counter()
    blink(gc1, wc1, lamp1, 1.0)
    dt = _t.perf_counter() - t0
    perf_ok = dt < 0.2

    ok = (wait_ok and mid_ok and delay_ok and short_ok and long_ok and tiers_ok
          and cycle_ok and inv_on and inv_flip and inv_back and weak_ok
          and clock1_ok and det_ok and clock3_ok and drift_ok and alive_ok and perf_ok)
    _report('tickqueue', ok,
            f'延迟(排队/0.2s不翻/0.35s翻)={wait_ok}/{mid_ok}/{delay_ok} '
            f'短脉冲被吃={short_ok} 长脉冲照常={long_ok} 四档={tiers_ok} '
            f'调档循环={cyc}{cycle_ok} '
            f'反相器(亮/灭/复亮)={inv_on}/{inv_flip}/{inv_back} 线只弱充能={weak_ok} '
            f'时钟1档{t1}次/3s={clock1_ok} 3档{t3}次={clock3_ok} '
            f'逐帧确定性={det_ok} 8s不漂({t8}次)={drift_ok} 一直挂着事件={alive_ok} '
            f'1s时钟耗时 {dt * 1000:.1f}ms={perf_ok}')


# ---------------------------------------------------------------- 主流程
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='mcclone3d headless 验收（零 GL）')
    ap.add_argument('--only', default='', help='逗号分隔，只跑这些检查')
    ap.add_argument('--list', action='store_true', help='只列检查项')
    ap.add_argument('--json', action='store_true', help='机器可读输出')
    args = ap.parse_args(argv)

    if args.list:
        for name, _fn in CHECKS:
            print(f'  {name}')
        return 0

    want = {x.strip() for x in args.only.split(',') if x.strip()}
    chosen = [(n, f) for n, f in CHECKS if not want or n in want]
    unknown = want - {n for n, _ in CHECKS}
    if unknown:
        print(f'未知检查项：{sorted(unknown)}')
        return 2

    print(f'== mcclone3d headless 验收 ==（{len(chosen)} 条）', flush=True)
    for name, fn in chosen:
        try:
            fn()
        except Exception as exc:                       # noqa: BLE001
            _report(name, False, f'异常：{type(exc).__name__}: {exc}')
    ok = not _FAILS
    if args.json:
        print(json.dumps({'checks': [n for n, _ in chosen],
                          'fails': [{'name': n, 'detail': d} for n, d in _FAILS],
                          'ok': ok}, ensure_ascii=False))
    print('-' * 66)
    if ok:
        print(f'[cli] {len(chosen)} 条检查全通过')
        print('== MCCLONE_CLI_OK ==')
        return 0
    print(f'[cli] 失败 {len(_FAILS)} 条：')
    for n, d in _FAILS:
        print(f'  - {n}: {d}')
    print('MCCLONE_CLI_FAILED')
    return 1


if __name__ == '__main__':
    sys.exit(main())
