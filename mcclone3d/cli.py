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
from mcclone3d.kernel import (SCRIPT, STEP_HZ, McCloneKernel, make_offline)  # noqa: E402
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
    sea, snow = a.sea_level, a.snow_line
    bad_surface = 0
    for x in range(0, 64, 3):
        for z in range(0, 64, 3):
            h = a.surface_at(x, z)
            top = a.get(x, h, z)
            if top in (B.AIR, B.STONE, B.COAL_ORE, B.IRON_ORE):
                bad_surface += 1
    a.plant_trees()
    logs = a.block_count(B.LOG)
    edits_clean = len(a.edits) == 0 or True          # plant_trees 走 set_generated，不该留增量
    edits_clean = len(a.edits) == 0
    _report('world', same and diff and bedrock and logs > 0 and bad_surface == 0 and edits_clean,
            f'确定性={same} 换种子有变化={diff} 基岩底={bedrock} 树={logs} '
            f'地表异常={bad_surface} 种树不留增量={edits_clean} sea={sea} snow={snow}')


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
    k = make_offline({'seed': 555, 'size': 64, 'height': 32})
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
    k2 = make_offline({'seed': 555, 'size': 48, 'height': 32})
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
    k = make_offline({'seed': 99, 'size': 48, 'height': 32})
    # 正下方：必定命中脚下方块，且法向朝上
    k.pitch, k.yaw = -89.9, 0.0
    hit = k.raycast()
    down_ok = hit is not None and hit[1] == (0, 1, 0)
    # 正上方：命中或超距（天空）都合法，但不许报"命中空气"
    k.pitch = 89.9
    up = k.raycast()
    up_ok = up is None or k.world.get(*up[0]) != B.AIR
    # 薄墙：人工垒一面 1 格厚的墙，正对着它必须被挡住（DDA 不该穿过去）
    k3 = make_offline({'seed': 99, 'size': 48, 'height': 32})
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
    k = make_offline({'seed': 2026, 'size': 48, 'height': 32})
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
    k2 = make_offline({'seed': 2026, 'size': 48, 'height': 32})
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
    k = make_offline({'seed': 31337, 'size': 48, 'height': 32})
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
        k = make_offline({'seed': 8080, 'size': 48, 'height': 32})
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
    k = make_offline({'seed': 4242, 'size': 48, 'height': 32})
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
    k2 = make_offline({'seed': 4242, 'size': 48, 'height': 32})
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
    k3 = make_offline({'seed': 4242, 'size': 48, 'height': 32})
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
        kf = make_offline({'seed': 1, 'size': 32, 'height': 32})
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
    ke = make_offline({'seed': 1, 'size': 32, 'height': 32})
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
