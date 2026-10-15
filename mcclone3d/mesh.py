# -*- coding: utf-8 -*-
"""区块网格：面剔除 + **逐面 UV 投影**（纯逻辑，零 GL）。

## 这件事的两个难点

**① 面剔除**：只画"从外面看得见"的面。判据在 `blocks.face_visible`（纯函数），
邻块查询走 `world.get()` —— 它**自动跨区块**，所以区块边界上不会漏面也不会多面。

**② UV 怎么算**（这一版的重点，也是与旧 `blockworld` 写法的分水岭）：

旧写法是"每个面直接给一个图集格号的 [0,1] 矩形"。这次改走**世界坐标投影**：

    u = (p · u_dir) * scale + offset        （与 Source `texinfo` 同构）

对单位方块、密度 `scale = 1/(图集列数 × 每格像素)` 来说，"一格方块面"恰好跨越
**一格图集格**，且**跨方块连续** —— 于是同一面墙上相邻方块的花纹是接着的，
而不是每格都从头开始贴（这是"贴图规则"与"每格一图"最直观的区别）。
图集内的环绕由 `texproj.Atlas.remap` 的 `fract()` 接管（= `TexWrap.REPEAT`）。

## ⚠ 两个必须显式处理的坑（都实测踩过，结论以引擎的**实测口径**为准）

**① 图集的 v 方向**：引擎实测口径是「数据第 0 行在 GL 的 v 小侧」
（`proctex.make_atlas` 的说明：pyglet `ImageData` 上传后 `v=0.25` 采到数据第一行），
而 `textures.build_atlas()` 是**第 0 行写在上边**。两者相反 ⇒ `atlas_rect()` 里
**把行号翻过来**（`rows-1-row`）。
*踩过的错法*：把面上的 v 取反（`fv = 1-fv`）—— 那会让面的上下边取到同一行，
贴图看着"对折"；**该翻的是图集的行，不是面上的参数**。

**② 面的朝向**：引擎的轴向基不区分面的正负（`+x` 与 `-x` 同一套基），直接套用会让
侧面贴图躺倒或镜像 ⇒ 本模块给出**每个面的基** `FACE_BASIS`（v 一律朝上 = +y）。
"""
from __future__ import annotations

import array
import math

from . import textures
from ._engine import geometry as _geo
from ._engine import texproj as _texproj
from .blocks import AIR, faces_of, face_visible, tile_for_face
from .light import MAX_LIGHT
from .world import CHUNK

__all__ = ['M3D_ATLAS', 'uv_projection_for', 'face_uv_quad', 'box_faces',
           'build_chunk_mesh', 'build_mob_mesh', 'FACE_BASIS', 'UV_DEBUG',
           'light_scale', 'light_color', 'LIGHT_FLOOR']

#: 图集映射表（名字 → 归一化矩形）。列/行与 `textures` 的图集几何一致。
M3D_ATLAS = _texproj.Atlas(textures.ATLAS_TILE_NAMES,
                           cols=textures.ATLAS_COLS, rows=textures.ATLAS_ROWS)

#: 图集格内的内缩比例（防相邻格渗色；NEAREST 采样下 0 也行，留一点更稳）
ATLAS_PADDING = 0.002

#: UV 调试开关：打开后 `build_chunk_mesh` 会把每面用到的原始 (u,v) 记进
#: `UV_DEBUG`，单测据此核对投影数值（不在正常路径上，零开销）。
UV_DEBUG: list = []
_DEBUG_ON = False


def _norm_axis(axis: str) -> str:
    return axis if axis in ('x', 'y', 'z') else 'z'


def uv_projection_for(face: str, tile_size: float = 1.0):
    """某个方块面的 UV 投影（`UvProjection`）。

    密度口径：`tile_size` = **一张贴图覆盖多少格**（默认 1 ⇒ 一格贴满一张图）。
    图集有 `cols` 列，所以"跨过 1 格世界距离"对应的 UV 增量是 `1/(cols × tile_size)` ——
    这样一格方块面恰好落在**一格图集格**内，而相邻方块之间 UV 连续（花纹接得上）。
    漏掉 `cols` 那一项会让 UV 跨度变成 1.0（= 整张图集），实测把"密度"与"跨格连续"
    两条断言同时打红。

    ⚠ **面的朝向要显式管**：引擎的轴向基不区分面的正负（`+x` 与 `-x` 的基相同），
    直接用会让侧面的贴图**躺倒 90°**、或者左右镜像。所以这里给出**每个面的 u/v 方向**
    （见 `FACE_BASIS`，直接存单位向量），并按 `cross(u_dir,v_dir)==面法向` 自证。
    """
    u_dir, v_dir, axis = FACE_BASIS[face]
    s = 1.0 / (textures.ATLAS_COLS * max(1e-6, float(tile_size)))
    return _texproj.UvProjection(axis, (s, s))


#: 每个面的面内基：`face -> (u_dir, v_dir, 投影轴)`（方向向量为**单位向量**）。
#:
#: 为什么直接存向量、而不是"轴 + 两个符号"：先前那样写要同时对齐四件事
#: （引擎的轴向基约定、两个符号、面法向、绕序），**实测连错三次**（±x 的 u 随错轴、
#: +y 的 v 变成 -Z…），每次症状都是"贴图躺倒/镜像"这种肉眼难判的东西。
#: 现在 `cross(u_dir, v_dir)` 必须等于面法向，`test_mesh` 穷举六面自证 —— 表写错必红。
#:
#: 两条约束：
#:   ① `cross(u_dir, v_dir) == 面法向`；
#:   ② 侧面的 `v_dir = +Y`（贴图不许躺倒）。
FACE_BASIS = {
    '+z': ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 'z'),     # u=+X, v=+Y
    '-z': ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 'z'),    # 镜像
    '+x': ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0), 'x'),    # u=-Z, v=+Y
    '-x': ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), 'x'),     # u=+Z, v=+Y
    '+y': ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), 'y'),    # 俯视：u=+X, v=-Z
    '-y': ((-1.0, 0.0, 0.0), (0.0, 0.0, -1.0), 'y'),   # 仰视：u=-X, v=-Z
}


def face_basis_normal(face: str):
    """由 `FACE_BASIS` 反算的面法向 `cross(u_dir, v_dir)`（**自检导出**）。

    表写错一个符号的症状是"贴图躺倒/镜像"，肉眼很难判 —— 把它做成可断言的函数，
    `test_mesh` 就能穷举六面核对，而不是靠人看表。
    """
    u, v, _axis = FACE_BASIS[face]
    cr = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return tuple(0 if abs(c) < 1e-9 else (1 if c > 0 else -1) for c in cr)

#: 六个面的四个角（单位方块、局部坐标 0..1），顺序为**逆时针（从外面看）**：
#: 左下 → 右下 → 右上 → 左上（对应 UV 的 (0,0) (1,0) (1,1) (0,1)）。
#: ✅ 逐面验算过绕序：`cross(c1-c0, c2-c0) == 面法向`（六面全过，`test_mesh` 也钉了它）——
#: 绕序反了的话，开背面剔除后该面会整片消失（而关剔除时又完全看不出来）。
#: 顶/底面**特别容易写反**（俯视图的"逆时针"在右手系里是 (0,-1,0)）。
_CORNERS = {
    '+z': ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),
    '-z': ((1, 0, 0), (0, 0, 0), (0, 1, 0), (1, 1, 0)),
    '+x': ((1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1)),
    '-x': ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)),
    '+y': ((0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)),
    '-y': ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),
}

#: 面法向（光照 / 背面剔除会用到）
NORMALS = {
    '+z': (0, 0, 1), '-z': (0, 0, -1),
    '+x': (1, 0, 0), '-x': (-1, 0, 0),
    '+y': (0, 1, 0), '-y': (0, -1, 0),
}

#: 面向光方向时的明暗系数（纯几何光照，不接光源）：顶最亮、底最暗、东西次之
FACE_BRIGHT = {'+y': 1.00, '-y': 0.55, '+z': 0.86, '-z': 0.80, '+x': 0.72, '-x': 0.66}


def face_uv_quad(face: str, wx: int, wy: int, wz: int, tile_size: float = 1.0):
    """一个方块面的四个角 UV（世界坐标投影的真身，纯数学 ⇒ 可单测）。

    返回 `((u0,v0), (u1,v1), (u2,v2), (u3,v3))`，与 `_CORNERS` 的四个角一一对应。

    公式与引擎 `texproj` 同构（`u = (p · u_dir) * scale + offset`），但**方向向量由
    `FACE_BASIS` 显式给出** —— 引擎的 `UvProjection` 只接受它自己的轴向基，
    表达不了"每个面各自的手性"（那正是贴图躺倒/镜像的来源）。
    密度 `scale` 与 `uv_projection_for` 完全一致（同一行公式，不重复推导）。
    """
    u_dir, v_dir, _axis = FACE_BASIS[face]
    scale = uv_projection_for(face, tile_size).scale
    out = []
    for (cx, cy, cz) in _CORNERS[face]:
        p = (wx + cx, wy + cy, wz + cz)
        u = (p[0] * u_dir[0] + p[1] * u_dir[1] + p[2] * u_dir[2]) * scale[0]
        v = (p[0] * v_dir[0] + p[1] * v_dir[1] + p[2] * v_dir[2]) * scale[1]
        out.append((u, v))
    if _DEBUG_ON:
        UV_DEBUG.append({'face': face, 'world': (wx, wy, wz), 'uv': tuple(out)})
    return tuple(out)


def _atlas_uv(u: float, v: float, tile: str):
    """世界 UV → 图集内的**归一化坐标** `(u', v')`。

    平铺语义 = `TexWrap.REPEAT`：先取小数（与引擎 `Atlas.remap` 的 `fract()` 同义），
    再映射进该贴图的矩形（矩形的 v 方向由 `atlas_rect` 按"第 0 行在上"给好）。
    """
    au0, av0, au1, av1 = atlas_rect(tile)
    fu = u - math.floor(u)
    fv = v - math.floor(v)
    return (au0 + fu * (au1 - au0), av0 + fv * (av1 - av0))


def atlas_rect(tile: str):
    """某张贴图在图集里的**内缩后**矩形 `(u0, v0, u1, v1)`（归一化）。

    ⚠ **v 要按行翻转**：引擎的实测口径是「数据第 0 行在 GL 的 v 小侧」
    （见 `proctex.make_atlas` 的说明），而 `textures.build_atlas()` 是**第 0 行写在上边**。
    两者相反 ⇒ 必须把"行号"翻过来（`rows-1-row`），否则整张图上下颠倒
    （草方块会长在天上）。

    ⚠ 踩过的错法：先前是**把面上的 v 取反**（`fv = 1 - fv`）。那会让同一张贴图
    在面的上下边取到同一行 —— 实测 `v=0` 与 `v=0.999` 落在矩形的同一侧（0.5996 / 0.4006），
    贴图看着"对折"了。**该翻的是图集的行，不是面上的参数**。
    """
    u0, v0, u1, v1 = M3D_ATLAS.rect(tile)
    rows = max(1, M3D_ATLAS.rows)
    row = int(round(v0 * rows))                    # 该格的行号（0 = 数据最前 = v 小侧）
    flip_row = rows - 1 - row                      # 换算到"第 0 行在上"的行号
    fv0, fv1 = flip_row / rows, (flip_row + 1) / rows
    w, h = u1 - u0, fv1 - fv0
    return (u0 + ATLAS_PADDING * w, fv0 + ATLAS_PADDING * h,
            u1 - ATLAS_PADDING * w, fv1 - ATLAS_PADDING * h)


def light_scale(level: int) -> float:
    """光照等级（0..15）→ 顶点色系数。

    **为什么地板是 0.10 而不是 0**：全黑等于"看不见路"，那不是夜晚是黑屏。
    0.10 相当于"月光下的轮廓" —— 这也是 MC 的做法（夜里有可见度但看不清细节）。

    曲线用 `0.10 + 0.90 × (level/15)^1.35`：指数略大于 1 ⇒ 中间档偏暗，
    于是"火把周围一圈"的过渡更明显（线性映射会让 7 和 15 看着差不多）。
    """
    t = max(0.0, min(1.0, float(level) / MAX_LIGHT))
    return LIGHT_FLOOR + (1.0 - LIGHT_FLOOR) * (t ** 1.35)


#: 光照等级为 0 时的顶点色系数（见 `light_scale` 的说明）
LIGHT_FLOOR = 0.10


def light_color(rgb, level: int, night: float = 0.0):
    """把"面亮度"与"光照等级"合成顶点色。

    `night` ∈ [0,1]（0 = 白天、1 = 深夜）用来给暗处**加一点蓝**：
    纯粹降低亮度会让夜里看着像"褪色的白天"，而偏蓝才像月夜
    （这是表现层的手感参数，与光照数值无关，所以放在 mesh 而不放在 light 里）。
    """
    k = light_scale(level)
    r, g, b = rgb * k, rgb * k, rgb * k
    if night > 0.0:
        # 暗处往蓝偏：`(1-k)` 越暗偏得越多，乘以夜色强度
        t = night * (1.0 - k) * 0.45
        r *= (1.0 - t)
        b *= (1.0 + t * 0.35)
    return (min(1.0, r), min(1.0, g), min(1.0, b))


def _append_face(mb, face: str, x: int, y: int, z: int, tile: str,
                 tile_size: float = 1.0):
    """追加一个面：几何 + 法向 + **投影 UV → 图集 UV**。

    `build_chunk_mesh`（区块批量）与 `box_faces`（单块）**都走这里** ——
    同一套 UV 规则只写一遍，写两遍必然漂。

    顶点色（`v_col.rgb`）在 Phase 2-A 起 = **面亮度 × 光照系数**（见 `light_color`）：
    `mb.light_of` 是调用方给的"查光函数"，默认 None ⇒ 系数 1（**不传就保持旧行为**，
    这样单测/无光照路径拿到的顶点色与 Phase 1 逐字节相同）。
    """
    corners = _CORNERS[face]
    uvs = face_uv_quad(face, x, y, z, tile_size)
    bright = FACE_BRIGHT[face]
    n = NORMALS[face]
    level = MAX_LIGHT
    if mb.light_of is not None:
        level = mb.light_of(x, y, z, n[0], n[1], n[2])
    col = light_color(bright, level, mb.night)
    base = len(mb.positions) // 3
    for (cx, cy, cz), (u, v) in zip(corners, uvs):
        # ⚠ `array.array` 的 `+=` 只吃 array，不吃 tuple（实测 TypeError）——
        # 用 `append` 逐个加，代价一样是 O(1)，但没有这层类型陷阱。
        mb.positions.append(x + cx)
        mb.positions.append(y + cy)
        mb.positions.append(z + cz)
        mb.normals.append(n[0])
        mb.normals.append(n[1])
        mb.normals.append(n[2])
        au, av = _atlas_uv(u, v, tile)
        mb.uvs.append(au)
        mb.uvs.append(av)
        mb.colors.append(col[0])
        mb.colors.append(col[1])
        mb.colors.append(col[2])
        mb.colors.append(1.0)
    # 两个三角形：0-1-2 与 0-2-3（与 _CORNERS 的逆时针绕序一致）
    mb.indices.append(base)
    mb.indices.append(base + 1)
    mb.indices.append(base + 2)
    mb.indices.append(base)
    mb.indices.append(base + 2)
    mb.indices.append(base + 3)
    mb.faces += 1
    return mb


def box_faces(mesh, x: int, y: int, z: int, block_id: int, tile_size: float = 1.0):
    """把一个方块的全部面追加进网格（**不做邻块剔除** —— 调用方自己判）。

    "六面都画"在两种场景下是对的：① 孤立方块（手持预览、掉落物）；
    ② 调用方已经用它自己的规则剔过了。
    """
    for face in faces_of(block_id):
        tile = tile_for_face(block_id, face)
        if not tile:
            continue
        _append_face(mesh, face, x, y, z, tile, tile_size)
    return mesh


class _MeshBuilder:
    """在 `array.array('f')` 上累积网格（与引擎 `blocks.mesh_world` 同一套做法）。"""

    __slots__ = ('positions', 'normals', 'uvs', 'colors', 'indices', 'faces',
                 'light_of', 'night')

    def __init__(self, light_of=None, night: float = 0.0):
        self.positions = array.array('f')
        self.normals = array.array('f')
        self.uvs = array.array('f')
        self.colors = array.array('f')
        self.indices = array.array('i')
        self.faces = 0
        #: 查光函数 `(x,y,z,nx,ny,nz) -> 0..15`；None = 不打光（顶点色 = 面亮度）
        self.light_of = light_of
        #: 夜色强度 0..1（只影响顶点色的偏蓝，不影响几何）
        self.night = float(night)

    def empty(self) -> bool:
        return not self.indices

    def to_mesh(self):
        """转成引擎的 `MeshData`（GL 上传与几何工具都吃它）。"""
        return _geo.MeshData(
            positions=self.positions, normals=self.normals, uvs=self.uvs,
            colors=self.colors, indices=self.indices)

    def stats(self) -> dict:
        return {'faces': self.faces, 'verts': len(self.positions) // 3,
                'tris': len(self.indices) // 3}


def build_mob_mesh(kind, *, tile: str = 'wool'):
    """按生物的盒模型建一份**局部坐标**网格（脚底中心为原点）。

    返回 `(_MeshBuilder, stats)`。渲染端把它按每个生物实例平移/旋转即可
    （所以"生物长什么样"完全由 `mobs.MobKind.parts` 这份**数据**决定，
    加一种生物不用碰渲染代码）。

    ⚠ 顶点色只烘 **部件色 × 面亮度**，**不烘光照**：光照是逐实例的
    （同一只羊在洞口和屋顶下亮度不同），而网格按种类只建一份 ——
    烘进去就等于"第一只生物在哪被看到，这一辈子就按那个亮度画"。
    正确做法是渲染端把 `light_color((1,1,1), 该生物所在格的光, night)`
    作为逐实例 uniform 乘上来（见 `examples/mcclone3d.py` 的 `u_light`）。

    ⚠ 每个部件是一个**实心盒子**（六面全画，不做邻面剔除）：
    部件之间本来就会互相遮挡一部分，剔除它们的接触面需要知道"哪个部件挨着哪个"，
    而那对 3~5 个部件的模型没有收益。
    """
    mb = _MeshBuilder()
    base_tile = tile if tile in textures.ATLAS_TILE_NAMES else textures.ATLAS_TILE_NAMES[0]
    for (origin, size, rgb) in kind.parts:
        ox, oy, oz = origin
        sx, sy, sz = size
        # 用"整数化的角落"生成几何：这样 UV 投影的跨格连续性仍然成立
        x0, y0, z0 = int(round(ox - sx / 2)), int(round(oy)), int(round(oz - sz / 2))
        for face in ('+x', '-x', '+y', '-y', '+z', '-z'):
            corners = _CORNERS[face]
            bright = FACE_BRIGHT[face]
            uvs = face_uv_quad(face, x0, y0, z0, 1.0)
            n = NORMALS[face]
            base = len(mb.positions) // 3
            for (cx, cy, cz), (u, v) in zip(corners, uvs):
                mb.positions.append(x0 + cx * max(1, int(round(sx))))
                mb.positions.append(y0 + cy * max(1, int(round(sy))))
                mb.positions.append(z0 + cz * max(1, int(round(sz))))
                mb.normals.append(n[0])
                mb.normals.append(n[1])
                mb.normals.append(n[2])
                au, av = _atlas_uv(u, v, base_tile)
                mb.uvs.append(au)
                mb.uvs.append(av)
                # 顶点色 = 部件自己的颜色 × 面亮度（颜色表达"这是羊还是猪"；
                # 光照不在这里 —— 见 docstring 的 ⚠）
                mb.colors.append(rgb[0] * bright)
                mb.colors.append(rgb[1] * bright)
                mb.colors.append(rgb[2] * bright)
                mb.colors.append(1.0)
            mb.indices.append(base)
            mb.indices.append(base + 1)
            mb.indices.append(base + 2)
            mb.indices.append(base)
            mb.indices.append(base + 2)
            mb.indices.append(base + 3)
            mb.faces += 1
    return mb, mb.stats()


def build_chunk_mesh(world, cx: int, cy: int, cz: int, *, debug: bool = False,
                     tile_size: float = 1.0, light_of=None, night: float = 0.0):
    """建一个区块的网格（只出可见面）。

    返回 `(_MeshBuilder, stats)`；`stats` 含面数/顶点数/三角形数 —— 单测用它
    断言"邻块剔除真的起作用了"（把相邻两块的接触面数算成 0）。

    `light_of` / `night` 是 Phase 2-A 的顶点色来源（见 `_append_face`）：
    **不传就与 Phase 1 逐字节相同**（顶点色只含面亮度）—— 这条"默认不改行为"
    让老的网格单测继续有效，也方便把"光照是否生效"单独测。
    """
    global _DEBUG_ON
    if debug:
        _DEBUG_ON = True
        UV_DEBUG.clear()
    mb = _MeshBuilder(light_of=light_of, night=night)
    x0, y0, z0 = cx * CHUNK, cy * CHUNK, cz * CHUNK
    get = world.get
    for lx in range(CHUNK):
        x = x0 + lx
        if x >= world.size:
            break
        for lz in range(CHUNK):
            z = z0 + lz
            if z >= world.size:
                break
            for ly in range(CHUNK):
                y = y0 + ly
                if y >= world.height:
                    break
                b = get(x, y, z)
                if b == AIR:
                    continue
                for face in faces_of(b):
                    n = NORMALS[face]
                    nb = get(x + n[0], y + n[1], z + n[2])
                    if not face_visible(b, nb):
                        continue
                    tile = tile_for_face(b, face)
                    if not tile:
                        continue
                    _append_face(mb, face, x, y, z, tile, tile_size)
    if debug:
        _DEBUG_ON = False
    stats = mb.stats()
    return mb, stats
