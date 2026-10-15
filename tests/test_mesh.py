# -*- coding: utf-8 -*-
"""网格单测：面剔除 / 绕序 / UV 投影（纯数学，零 GL）。

跑：`python -m tests.test_mesh`
"""
from __future__ import annotations

import math
import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d import textures as T
from mcclone3d.mesh import (FACE_BRIGHT, NORMALS, _CORNERS, _atlas_uv, box_faces,
                            build_chunk_mesh, face_uv_quad, uv_projection_for,
                            _MeshBuilder)
from mcclone3d.world import CHUNK, ChunkedWorld

test, main = make_suite('ALL_MESH_TESTS_PASSED', '网格与 UV')


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _sign3(v):
    return tuple(0 if abs(c) < 1e-9 else (1 if c > 0 else -1) for c in v)


@test('绕序：六个面 cross(c1-c0, c2-c0) 都等于面法向（反了开剔除会整片消失）')
def t_winding():
    for face, corners in _CORNERS.items():
        cr = _cross(_sub(corners[1], corners[0]), _sub(corners[2], corners[0]))
        assert _sign3(cr) == NORMALS[face], f'{face} 绕序反了：{_sign3(cr)} vs {NORMALS[face]}'


@test('四个角都是单位方块面上的点（0/1 坐标，平面共面）')
def t_corners():
    for face, corners in _CORNERS.items():
        assert len(corners) == 4
        axis = 'xyz'[max(range(3), key=lambda i: abs(NORMALS[face][i]))]
        vals = {c['xyz'.index(axis)] for c in corners}
        assert len(vals) == 1, f'{face} 的四个角不在同一平面（{axis} 坐标不唯一）'
        for c in corners:
            assert all(v in (0, 1) for v in c), f'{face} 有非 0/1 坐标：{c}'


@test('面的基与法向一致：cross(u_dir, v_dir) == 面法向（六面穷举）')
def t_basis_matches_normal():
    from mcclone3d.mesh import face_basis_normal
    for face in _CORNERS:
        got = face_basis_normal(face)
        assert got == NORMALS[face], \
            f'{face} 的基反算法向 {got} != 面法向 {NORMALS[face]}（手写表里某个符号错了）'


@test('UV 密度：单位方块面恰好跨越一格图集格（1/列数）')
def t_uv_density():
    span = 1.0 / T.ATLAS_COLS
    for face in _CORNERS:
        uv = face_uv_quad(face, 3, 7, 11)
        du = max(p[0] for p in uv) - min(p[0] for p in uv)
        dv = max(p[1] for p in uv) - min(p[1] for p in uv)
        assert abs(du - span) < 1e-6, f'{face} 的 u 跨度 {du:.6f} != {span:.6f}'
        assert abs(dv - span) < 1e-6, f'{face} 的 v 跨度 {dv:.6f} != {span:.6f}'


@test('UV 连续：沿 u 方向挪一格，UV 起点恰好差一格（贴图接得上，不是每格重来）')
def t_uv_continuous():
    span = 1.0 / T.ATLAS_COLS
    # ⚠ 每个面"u 随哪个世界轴变化"不一样，而且镜像面（±x）方向相反 ——
    # 所以这里按**面的基**算步进方向，而不是写死一个 (+1,0,0)：
    # 写死会让 +x 面永远量到 Δu=0（实测踩过），看着像 UV 坏了，其实是量错了轴。
    from mcclone3d.mesh import FACE_BASIS, face_basis_normal, uv_projection_for
    for face in _CORNERS:
        proj = uv_projection_for(face, 1.0)
        u_dir = FACE_BASIS[face][0]
        # 取 u 方向里"最大的那个分量"作为步进轴；步进符号 = 让 (d · u_dir) > 0
        axis = max(range(3), key=lambda i: abs(u_dir[i]))
        if abs(u_dir[axis]) < 1e-9:
            continue                                   # 该面 u 与世界轴平行得无法步进
        d = [0, 0, 0]
        d[axis] = 1 if u_dir[axis] > 0 else -1
        # 自证：这个步进方向确实让 u 变大（u 的梯度是 u_dir * scale[0]）
        assert d[axis] * u_dir[axis] * proj.scale[0] > 0, f'{face} 步进方向与 u 梯度反了'
        a = face_uv_quad(face, 5, 5, 5)[0]
        b = face_uv_quad(face, 5 + d[0], 5 + d[1], 5 + d[2])[0]
        du = b[0] - a[0]
        assert abs(abs(du) - span) < 1e-6, \
            f'{face} 沿 u 方向挪一格后 Δu={du:.6f}，期望 ±{span:.6f}（step={tuple(d)}）'
        assert du > 0, f'{face} 沿 u 正方向挪动却让 u 变小了（基的符号反了？）'


@test('UV 竖直方向：侧面的 v 必须朝上（贴图不许躺倒）')
def t_uv_upright():
    for face in ('+z', '-z', '+x', '-x'):
        uv = face_uv_quad(face, 0, 0, 0)
        corners = _CORNERS[face]
        # 找 y=0 与 y=1 的两个角，比对它们的 v
        low = [uv[i][1] for i, c in enumerate(corners) if c[1] == 0]
        high = [uv[i][1] for i, c in enumerate(corners) if c[1] == 1]
        assert min(high) > max(low), f'{face} 的 v 没随 y 单调上升（贴图躺倒了）'


@test('图集映射：v 轴按"第 0 行在上"翻转，且落在该贴图自己的矩形内')
def t_atlas_map():
    from mcclone3d.mesh import atlas_rect
    tile = 'grass_top'
    u0, v0, u1, v1 = atlas_rect(tile)
    assert u0 < u1 and v0 < v1, f'矩形非法：{(u0, v0, u1, v1)}'
    # 面上的四个角映射后必须**全部落在本贴图的矩形内**（含 padding 内缩）
    for pt in ((0.0, 0.0), (0.2, 0.8), (0.5, 0.5), (0.99, 0.01)):
        au, av = _atlas_uv(pt[0], pt[1], tile)
        assert u0 - 1e-9 <= au <= u1 + 1e-9, f'u 跑出矩形：{au} ∉ [{u0},{u1}]'
        assert v0 - 1e-9 <= av <= v1 + 1e-9, f'v 跑出矩形：{av} ∉ [{v0},{v1}]'
    # v 方向：面上 v 越大 ⇒ 图集里的 v 越大（"第 0 行在上"，草皮就该在草方块侧面上边）
    _, low = _atlas_uv(0.0, 0.0, tile)
    _, high = _atlas_uv(0.0, 0.999, tile)
    assert low < high, f'v 没有随面内高度上升（图集行翻转反了）：low={low} high={high}'
    assert abs(low - v0) < 0.01 and abs(high - v1) < 0.01


@test('平铺：UV 超出 [0,1) 时按小数回绕（= TexWrap.REPEAT）')
def t_atlas_wrap():
    tile = 'stone'
    a = _atlas_uv(0.25, 0.25, tile)
    b = _atlas_uv(3.25, 7.25, tile)
    assert abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9, '平铺回绕没生效'


@test('面剔除：被完全包住的方块一个面都不画')
def t_culling_buried():
    w = ChunkedWorld(555, 32, 32).generate()
    # 造一个 3x3x3 的实心石头块，检查正中间那块
    cx, cy, cz = 10, 10, 10
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                w.set(cx + dx, cy + dy, cz + dz, B.STONE)
    from mcclone3d.blocks import face_visible
    visible = 0
    for face, n in NORMALS.items():
        nb = w.get(cx + n[0], cy + n[1], cz + n[2])
        visible += bool(face_visible(B.STONE, nb))
    assert visible == 0, f'被包住的方块仍画了 {visible} 个面'


@test('面剔除：孤立方块恰好 6 面、24 顶点、12 三角形')
def t_box_faces():
    mb = _MeshBuilder()
    box_faces(mb, 0, 0, 0, B.STONE)
    st = mb.stats()
    assert st['faces'] == 6, st
    assert st['verts'] == 24 and st['tris'] == 12, st
    assert len(mb.uvs) == 24 * 2 and len(mb.normals) == 24 * 3 and len(mb.colors) == 24 * 4
    mesh = mb.to_mesh()
    # ⚠ `MeshData.vertex_count` / `triangle_count` 是**属性**，不是方法
    # （引擎 `engine/geometry.py` 用 @property 定义）—— 加括号会得到
    # `TypeError: 'int' object is not callable`，实测踩过一次。
    assert mesh.vertex_count == 24, mesh.vertex_count
    assert len(mesh.indices) // 3 == 12, len(mesh.indices)
    # ⚠ 引擎的 `MeshData.triangle_count` 对本网格返回 **4**（用 `// 9`：它对
    # **非索引**网格按"每三角形 9 个 float"算，对索引网格就少算 3 倍）。
    # 这是 3dworld 仓的问题，本仓**不改引擎**，改用显式断言钉住正确值，
    # 并把这条差异记进 README/交接，等用户决定是否回报上游。
    assert mesh.triangle_count == 4, \
        f'引擎 triangle_count 的已知偏差变了（现在 {mesh.triangle_count}）：' \
        f'说明 3dworld 侧修了或改了算法，本仓的说明要同步更新'


@test('区块网格：面数与"逐格可见面"逐一相符（不是抽样）')
def t_chunk_matches_bruteforce():
    w = ChunkedWorld(4321, 32, 32).generate()
    _mb, st = build_chunk_mesh(w, 0, 0, 0)
    expect = 0
    for x in range(CHUNK):
        for z in range(CHUNK):
            for y in range(CHUNK):
                b = w.get(x, y, z)
                if b == B.AIR:
                    continue
                for face, n in NORMALS.items():
                    if face not in B.faces_of(b):
                        continue
                    if B.face_visible(b, w.get(x + n[0], y + n[1], z + n[2])):
                        expect += 1
    assert st['faces'] == expect, f'网格面数 {st["faces"]} != 逐格统计 {expect}'


@test('邻块剔除：区块交界处不产生内部面（改一格只影响本区块的面数）')
def t_cross_chunk_culling():
    w = ChunkedWorld(88, 32, 32).generate()
    # 把整层 y=20 填成实心石头 ⇒ 该层内部的面全部互相挡死
    for x in range(32):
        for z in range(32):
            w.set(x, 20, z, B.STONE)
            w.set(x, 21, z, B.STONE)
    _mb0, st0 = build_chunk_mesh(w, 0, 1, 0)      # y=16..31 层
    # 逐格核对（含跨区块邻块）
    expect = 0
    for x in range(CHUNK):
        for z in range(CHUNK):
            for y in range(16, 32):
                b = w.get(x, y, z)
                if b == B.AIR:
                    continue
                for face, n in NORMALS.items():
                    if face not in B.faces_of(b):
                        continue
                    if B.face_visible(b, w.get(x + n[0], y + n[1], z + n[2])):
                        expect += 1
    assert st0['faces'] == expect, f'跨区块剔除不一致：{st0["faces"]} vs {expect}'
    # y=20/21 两层实心之间**不该**有面
    inner = 0
    for x in range(1, CHUNK - 1):
        for z in range(1, CHUNK - 1):
            inner += bool(B.face_visible(w.get(x, 20, z), w.get(x, 21, z)))
            inner += bool(B.face_visible(w.get(x, 21, z), w.get(x, 20, z)))
    assert inner == 0, f'实心层内部产生了 {inner} 个面'


@test('UV 投影与引擎 texproj 数值一致（同一套公式，不是自己另写一套）')
def t_matches_engine_texproj():
    from mcclone3d._engine import texproj as tp
    proj = uv_projection_for('+z', 1.0)
    u_dir, v_dir = proj.directions()
    for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (2.0, 3.0, 4.0)):
        u, v = tp.project_uv(p, proj)
        eu = (p[0] * u_dir[0] + p[1] * u_dir[1] + p[2] * u_dir[2]) * proj.scale[0] + proj.offset[0]
        ev = (p[0] * v_dir[0] + p[1] * v_dir[1] + p[2] * v_dir[2]) * proj.scale[1] + proj.offset[1]
        assert abs(u - eu) < 1e-9 and abs(v - ev) < 1e-9, f'{p}: 与引擎公式不一致'
    # 反向也要对得上：uv_to_world 把 UV 还原回世界平面上的点
    got = tp.uv_to_world(tp.project_uv((3.0, 4.0, 5.0), proj), proj, plane=5.0)
    assert abs(got[0] - 3.0) < 1e-6 and abs(got[1] - 4.0) < 1e-6, f'正反不互逆：{got}'


@test('明暗系数：顶面最亮、底面最暗（否则方块看起来是纸片）')
def t_brightness():
    assert FACE_BRIGHT['+y'] == max(FACE_BRIGHT.values())
    assert FACE_BRIGHT['-y'] == min(FACE_BRIGHT.values())
    for face, v in FACE_BRIGHT.items():
        assert 0.4 < v <= 1.0, f'{face} 的明暗系数不合法：{v}'


# ==================================================================== 生物网格（Phase 2-B）
_FACE_ORDER = ('+x', '-x', '+y', '-y', '+z', '-z')


@test('生物网格：每种生物 = parts×6 面，整数格几何，UV 都落在图集矩形内')
def t_mob_mesh_structure():
    from mcclone3d import mobs as MB
    from mcclone3d.mesh import atlas_rect, build_mob_mesh
    u0, v0, u1, v1 = atlas_rect('wool')
    for kind in MB.all_kinds():
        mb, st = build_mob_mesh(kind)
        assert st['faces'] == len(kind.parts) * 6, f'{kind.name}: {st}'
        assert st['verts'] == len(kind.parts) * 24 and st['tris'] == len(kind.parts) * 12, st
        # 整数格几何：UV 投影的跨格连续性以它为前提（0.6 格会被 round 成 0 厚度）
        assert all(float(v).is_integer() for v in mb.positions), \
            f'{kind.name}: 几何不是整数格'
        for i in range(0, len(mb.uvs), 2):
            assert u0 - 1e-6 <= mb.uvs[i] <= u1 + 1e-6, f'{kind.name}: u 越界'
            assert v0 - 1e-6 <= mb.uvs[i + 1] <= v1 + 1e-6, f'{kind.name}: v 越界'


@test('生物网格：顶点色 = 部件色 × 面亮度（**不烘光照**）')
def t_mob_mesh_color_bakes_no_light():
    """光照烘进顶点色 = "第一只生物在哪被看到，这一辈子按那个亮度画"
    —— 夜里和洞里的生物会全亮，截图一眼穿邦（Phase 2-A 修过同类的
    "天空色写死"）。所以顶点色里只许有部件色与面亮度，
    光照由渲染端走逐实例 uniform（`u_light`）乘上来。"""
    from mcclone3d import mobs as MB
    from mcclone3d.mesh import build_mob_mesh
    for kind in MB.all_kinds():
        mb, _st = build_mob_mesh(kind)
        for pi, (_origin, _size, rgb) in enumerate(kind.parts):
            for fi, face in enumerate(_FACE_ORDER):
                bright = FACE_BRIGHT[face]
                for vi in range(4):
                    idx = (pi * 6 + fi) * 4 + vi
                    r, g, b, a = mb.colors[idx *4: idx *4 + 4]
                    assert abs(r - rgb[0] * bright) < 1e-6, \
                        f'{kind.name}.parts[{pi}] {face} 顶点{vi}: r={r}'
                    assert abs(g - rgb[1] * bright) < 1e-6 and abs(b - rgb[2] * bright) < 1e-6
                    assert a == 1.0, f'{kind.name}: alpha 该是 1.0：{a}'


@test('生物网格：模型总高与 MobKind.height 一致（否则碰撞与渲染对不上）')
def t_mob_mesh_height_matches_kind():
    from mcclone3d import mobs as MB
    from mcclone3d.mesh import build_mob_mesh
    for kind in MB.all_kinds():
        mb, _st = build_mob_mesh(kind)
        top = max(mb.positions[i] for i in range(1, len(mb.positions), 3))
        assert abs(top - kind.height) < 1e-6, \
            f'{kind.name}: 模型高 {top} ≠ kind.height {kind.height}'


@test('生物网格：未知贴图名回落到默认（不抛 KeyError）')
def t_mob_mesh_bad_tile_falls_back():
    from mcclone3d import mobs as MB
    from mcclone3d.mesh import build_mob_mesh
    mb, st = build_mob_mesh(MB.mob_kind('sheep'), tile='no_such_tile')
    assert st['faces'] == 18, st                       # 3 parts × 6 面
    assert mb.uvs, '回落之后一个顶点都没有'


if __name__ == '__main__':
    sys.exit(main())
