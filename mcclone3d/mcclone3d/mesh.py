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
from .blocks import (AIR, OPAQUE_IDS, REDSTONE_WIRE, faces_of, face_visible,
                     tile_for_face)
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

#: Phase 3：**画成扁平盒**的方块（高度 `THIN_H`）—— 只有红石线：
#: 它是一个整方块高的红砖的话，既挡路又完全不像"地上的线"。
THIN_BLOCKS = frozenset({REDSTONE_WIRE})
#: 扁平盒的高度。**取 1/8 格**（不是 1/16）：1/16 时实测在 9 格开外会被地面顶面
#: 的深度精度吃掉（顶面只高 0.0625 格，远处两个面抢同一段深度缓冲）⇒
#: 截图里"主线整条看不见、只有近处的支线偶尔露出"。1/8 格既躲开这个问题，
#: 在观感上也更像 MC 的红石线。
THIN_H = 1.0 / 8.0


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


def _atlas_uv(u: float, v: float, tile: str, wrap: bool = True):
    """**贴图内**坐标 → 图集内的归一化坐标 `(u', v')`。

    平铺语义 = `TexWrap.REPEAT`：先取小数（与引擎 `Atlas.remap` 的 `fract()` 同义），
    再映射进该贴图的矩形（矩形的 v 方向由 `atlas_rect` 按"第 0 行在上"给好）。

    `wrap=False` ⇒ **不取小数、改成夹到 [0,1]**。这是给"一整面"用的（见
    `_atlas_uv_quad`）：面正好跨满一格时末角落在 1.0，`frac(1.0)=0.0` 会把整面
    折成一个纹素（贴图变成一块纯色）—— 那是个**必须避开**的边界。
    """
    au0, av0, au1, av1 = atlas_rect(tile)
    if wrap:
        fu, fv = u - math.floor(u), v - math.floor(v)
    else:
        fu = 0.0 if u < 0.0 else (1.0 if u > 1.0 else u)
        fv = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
    return (au0 + fu * (au1 - au0), av0 + fv * (av1 - av0))


def _atlas_uv_quad(uvs, tile: str):
    """**一整面**的四角 UV：图集空间（一格世界距离走 `1/cols`）→ 图集坐标。

    ⚠⚠ 这个函数是 Phase 3-F 补上的，它修的是一个**从 Phase 0 就存在的静默错误**
    （整个世界的贴图大了 8 倍，近看是一团团糊斑）：

    * `uv_projection_for` 给的密度是 `1/(cols × tile_size)` ⇒ 跨过 1 格世界距离，
      `u` 只走 **1/cols**。这本身没错 —— 图集有 `cols` 列，一格方块面在**图集空间**里
      正好占一格宽（CLI 的 `mesh` 条盯的就是这条）；
    * 但要对上"这一格贴图"的矩形，就必须先把 `u` 换算成**贴图内**坐标：
      `u × cols − 这一面起点所在的格号`。**先前是每个角各自 `frac(u)`**，
      于是面内只走完 `1/cols` ⇒ 一格方块只显示这张贴图的 1/8，
      而相邻方块显示的是相邻的 1/8 切片（花纹跨格连续，远看"像那么回事"，极难发现）。

    取 `uvs[0]` 的格号当基准（整面共用），四角于是落在 `[0,1]` 上、**首尾不重合**。

    比一格还宽的面（生物盒模型的部件，最多 5 格）会被**夹到 [0,1]**：
    即"一张贴图铺满整个部件"而不是平铺 5 次 —— 生物用的是无花纹的羊毛贴图，
    两者视觉上一样，而夹住能避免接缝。这条是明写的取舍，不是疏忽。
    """
    cols = textures.ATLAS_COLS
    bu = math.floor(uvs[0][0] * cols)
    bv = math.floor(uvs[0][1] * cols)
    return [_atlas_uv(u * cols - bu, v * cols - bv, tile, wrap=False)
            for (u, v) in uvs]


def atlas_rect(tile: str):
    """某张贴图在图集里的**内缩后**矩形 `(u0, v0, u1, v1)`（归一化）。

    ## 为什么用 `textures.LAYOUT` 而不是引擎的 `M3D_ATLAS.rect`

    2026-10-15 实测踩到：原先拿 `M3D_ATLAS.rect(tile)` 给的 v0 反推行号
    （`int(round(v0 * rows))`），在图集**不是正方形**时才暴露 ——
    引擎按"每格 1/cols"归一化 v，而反推用的是 `rows`，两者不相等就取到错的行。
    Phase 3 把 `ATLAS_COLS` 从 6 提到 8（44 张贴图 ⇒ 6 行）之后，**整个世界都采样到了
    红石线/红石灯的贴图**（截图里地形一片暗红）—— 排查了半天才发现是这里。

    现在改成"**行号自己算**"：`TILE_INDEX` + `ATLAS_COLS` 是数据源，
    `LAYOUT.uv_rect` 与 `build_atlas()` 的像素布局严格对应（`test_atlas_layout` 钉着它）。

    ⚠ 只保留**一次 v 翻转**：引擎的图集把"数据第 0 行"放在 GL 的 **v 小侧**
    （见 `proctex.make_atlas`），而 `LAYOUT.uv_rect` 给的是"第 0 行在 v 大侧"
    ⇒ 两者相反，必须翻一次，否则整张贴图上下颠倒（草会长在天上）。
    """
    u0, v0, u1, v1 = textures.LAYOUT.uv_rect(tile)
    v0, v1 = 1.0 - v1, 1.0 - v0                   # 唯一的一次翻转（见 docstring）
    w, h = u1 - u0, v1 - v0
    return (u0 + ATLAS_PADDING * w, v0 + ATLAS_PADDING * h,
            u1 - ATLAS_PADDING * w, v1 - ATLAS_PADDING * h)


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


# ---------------------------------------------------------------- 顶点级 AO（平滑光照）
#: AO 明暗表（索引 = AO 级别 0..3）。0 = 最暗（两条邻边都被挡）、3 = 全亮。
#: 取值是"看起来对"的**手调表**，不是物理量：MC 的口径也在这附近
#: （关键是**单调**且最暗不要到 0，否则角落会变成黑洞、失去体积感）。
AO_FACTOR = (0.55, 0.72, 0.86, 1.0)

#: 面 → 法向所在轴（0=x 1=y 2=z）与"朝外"的符号
_AXIS_OF = {'+x': 0, '-x': 0, '+y': 1, '-y': 1, '+z': 2, '-z': 2}
_OUT_SIGN = {'+x': 1, '-x': -1, '+y': 1, '-y': -1, '+z': 1, '-z': -1}
#: 轴向 → 另外两个轴（即该面的两个**切向**）
_TANGENTS = {0: (1, 2), 1: (0, 2), 2: (0, 1)}
#: 面 → 四个角在"两个切向轴"上的偏移（**与 `_CORNERS[face]` 同序**）
_CORNER_TAN = {}
#: 面 → 外侧那一层 3×3 环的**坐标偏移**（9 元组，中心是 None）。
#: ⚠ **预计算**，不要在 `face_ao` 里现算：初版每次 `list(base)` + 按轴写下标
#: （8 次列表分配/面），47 万面就是 380 万次分配 —— 实测 AO 代价 +24%，
#: 换成预计算偏移后降到 +8%（同口径，只是不再分配）。
_RING_OFF = {}
for _f, _cs in _CORNERS.items():
    _a, _u, _v = _AXIS_OF[_f], *_TANGENTS[_AXIS_OF[_f]]
    _out = 1 if _OUT_SIGN[_f] > 0 else -1
    _CORNER_TAN[_f] = tuple((c[_u], c[_v]) for c in _cs)
    _offs = []
    for _i in (0, 1, 2):
        for _j in (0, 1, 2):
            if _i == 1 and _j == 1:
                _offs.append(None)               # 中心：面剔除已保证它透明
                continue
            _d = [0, 0, 0]
            _d[_a] = _out
            _d[_u] += _i - 1
            _d[_v] += _j - 1
            _offs.append(tuple(_d))
    _RING_OFF[_f] = tuple(_offs)
del _f, _cs, _a, _u, _v, _out, _offs, _i, _j, _d


def face_ao(world, x: int, y: int, z: int, face: str):
    """这个面四个角的 **AO 系数**（与 `_CORNERS[face]` 同序；1.0 = 全亮）。

    规则（与 MC 的"平滑光照"同口径，且是**纯函数** ⇒ 单测可穷举）：

    只看面**外侧那一层**的 3×3 环（中心那格由面剔除保证是透明的，不算遮挡），
    对每个角数三个遮挡（两条邻边 + 对角）：

    ```
    两条邻边都被挡        → 0 级（最暗）
    否则                 → 3 − (邻边1 + 邻边2 + 对角)
    ```

    **遮挡 = 不透明**（`not is_transparent`）：空气/玻璃/水都不算 ——
    水算不算遮挡在 MC 里一直有争议，这里统一按"不挡光就不挡 AO"，一条口径说到底。

    ⚠ 只查 **8 格**（3×3 去掉中心），不是"每角 3 次 × 4 角 = 12 次"：
    那 12 次里有 4 次是重复的边邻居。实测这个细节决定了 AO 的代价是 +8% 还是 +16%
    （整世界 47 万面 × 4 次多余的 `world.get` 不是小数）。
    """
    # ⚠ 基准就是方块自己那一格 —— **法向偏移已经算在 `_RING_OFF` 里了**。
    #   初版优化时把"基准先挪到外侧层"和"偏移里含法向"两条同时留下 ⇒ 法向被加两次、
    #   采样到错误的层（症状：遮挡全部看不出来，AO 恒为 1.0 —— 正是单测当场抓到的）。
    bx, by, bz = x, y, z
    get = world.get

    # 3×3 环的遮挡位（行 = u 偏移 −1/0/+1，列 = v 偏移 −1/0/+1；中心恒为 False）
    ring = []
    for d in _RING_OFF[face]:
        if d is None:
            ring.append(False)
        else:
            # 一次集合成员测试判"不透明"，不做两层查找（见 `blocks.OPAQUE_IDS`）
            ring.append(get(bx + d[0], by + d[1], bz + d[2]) in OPAQUE_IDS)

    factors = []
    for (cu, cv) in _CORNER_TAN[face]:
        i = 2 if cu else 0
        j = 2 if cv else 0
        s1 = ring[i * 3 + 1]                     # 沿 u 的邻边
        s2 = ring[1 * 3 + j]                     # 沿 v 的邻边
        corner = ring[i * 3 + j]                 # 对角
        level = 0 if (s1 and s2) else 3 - (s1 + s2 + corner)
        factors.append(AO_FACTOR[level])
    return tuple(factors)


def _append_face(mb, face: str, x: int, y: int, z: int, tile: str,
                 tile_size: float = 1.0, height: float = 1.0):
    """追加一个面：几何 + 法向 + **投影 UV → 图集 UV**。

    `build_chunk_mesh`（区块批量）与 `box_faces`（单块）**都走这里** ——
    同一套 UV 规则只写一遍，写两遍必然漂。

    顶点色（`v_col.rgb`）在 Phase 2-A 起 = **面亮度 × 光照系数**（见 `light_color`）：
    `mb.light_of` 是调用方给的"查光函数"，默认 None ⇒ 系数 1（**不传就保持旧行为**，
    这样单测/无光照路径拿到的顶点色与 Phase 1 逐字节相同）。
    Phase 3 又乘一层**红石信号系数**（`mb.power_of`，同样默认 None ⇒ 不影响旧行为）。

    `height` 是**方块高度缩放**（1.0 = 整方块）：红石线要贴地画成 1/16 的扁盒
    （`THIN_BLOCKS`）。只缩放 y 偏移，UV/法向不变 ⇒ 顶面仍是完整的"十字"贴图。
    """
    corners = _CORNERS[face]
    uvs = face_uv_quad(face, x, y, z, tile_size)
    atlas_uvs = _atlas_uv_quad(uvs, tile)          # 整面一次换算（见该函数的说明）
    bright = FACE_BRIGHT[face]
    n = NORMALS[face]
    level = MAX_LIGHT
    if mb.light_of is not None:
        level = mb.light_of(x, y, z, n[0], n[1], n[2])
    col = light_color(bright, level, mb.night)
    if mb.power_of is not None:
        pw = mb.power_of(x, y, z)
        if pw is not None:
            # 信号越弱越暗（0 → 35% 亮度）：一眼看出"这条线通到哪里为止"
            k = 0.35 + 0.65 * (max(0, min(15, int(pw))) / 15.0)
            col = (col[0] * k, col[1] * k, col[2] * k)
    #: 顶点级 AO：四个角各一个系数（不启用时是 None ⇒ 逐字节保持旧行为）
    ao = None
    if mb.smooth and mb.world is not None:
        ao = face_ao(mb.world, x, y, z, face)
    base = len(mb.positions) // 3
    for _i, ((cx, cy, cz), (au, av)) in enumerate(zip(corners, atlas_uvs)):
        # ⚠ `array.array` 的 `+=` 只吃 array，不吃 tuple（实测 TypeError）——
        # 用 `append` 逐个加，代价一样是 O(1)，但没有这层类型陷阱。
        mb.positions.append(x + cx)
        mb.positions.append(y + cy * height)
        mb.positions.append(z + cz)
        mb.normals.append(n[0])
        mb.normals.append(n[1])
        mb.normals.append(n[2])
        mb.uvs.append(au)
        mb.uvs.append(av)
        # 每角再乘 AO（`ao is None` 时是 ×1.0 ⇒ 与旧行为逐位相同）
        k = ao[_i] if ao is not None else 1.0
        mb.colors.append(col[0] * k)
        mb.colors.append(col[1] * k)
        mb.colors.append(col[2] * k)
        mb.colors.append(1.0)
    # 两个三角形：默认 0-1-2 与 0-2-3（与 _CORNERS 的逆时针绕序一致）。
    # ⚠ 启用 AO 时要**按 AO 选对角线**（MC 的 "quad flip"）：两个三角形的插值沿共享
    #   对角线进行 ⇒ 若那条对角线两端明暗差很大，面内会出现一条可见的斜向渐变。
    #   规则：让**较暗的一对**落在同一条对角线上。
    if ao is not None and ao[0] + ao[2] > ao[1] + ao[3]:
        mb.indices.append(base + 1)
        mb.indices.append(base + 2)
        mb.indices.append(base + 3)
        mb.indices.append(base + 1)
        mb.indices.append(base + 3)
        mb.indices.append(base)
    else:
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
                 'light_of', 'night', 'power_of', 'world', 'smooth')

    def __init__(self, light_of=None, night: float = 0.0, power_of=None,
                 world=None, smooth: bool = False):
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
        #: Phase 3：查**红石信号**的函数 `(x,y,z) -> 0..15 或 None`。
        #: 返回 None = "这个方块跟红石无关"（保持原色）；红石线按强度调暗到 35%。
        self.power_of = power_of
        #: Phase 3-C：顶点级 AO。**默认关** —— 不传就与 Phase 3 的顶点色逐字节相同
        #: （老网格单测继续有效，也方便把"AO 是否生效"单独测）。
        self.world = world
        self.smooth = bool(smooth)

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
            atlas_uvs = _atlas_uv_quad(uvs, base_tile)
            n = NORMALS[face]
            base = len(mb.positions) // 3
            for (cx, cy, cz), (au, av) in zip(corners, atlas_uvs):
                mb.positions.append(x0 + cx * max(1, int(round(sx))))
                mb.positions.append(y0 + cy * max(1, int(round(sy))))
                mb.positions.append(z0 + cz * max(1, int(round(sz))))
                mb.normals.append(n[0])
                mb.normals.append(n[1])
                mb.normals.append(n[2])
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
                     tile_size: float = 1.0, light_of=None, night: float = 0.0,
                     power_of=None, smooth: bool = False):
    """建一个区块的网格（只出可见面）。

    返回 `(_MeshBuilder, stats)`；`stats` 含面数/顶点数/三角形数 —— 单测用它
    断言"邻块剔除真的起作用了"（把相邻两块的接触面数算成 0）。

    `light_of` / `night` 是 Phase 2-A 的顶点色来源（见 `_append_face`）：
    **不传就与 Phase 1 逐字节相同**（顶点色只含面亮度）—— 这条"默认不改行为"
    让老的网格单测继续有效，也方便把"光照是否生效"单独测。

    `smooth=True` 打开 **Phase 3-C 的顶点级 AO**（见 `face_ao`）：每个角按邻格遮挡调暗，
    并把四边形按 AO 翻转对角线。**默认关** ⇒ 与 Phase 3 的网格逐字节相同。
    """
    global _DEBUG_ON
    if debug:
        _DEBUG_ON = True
        UV_DEBUG.clear()
    mb = _MeshBuilder(light_of=light_of, night=night, power_of=power_of,
                      world=world if smooth else None, smooth=smooth)
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
                    # Phase 3：红石线画成贴地的扁盒（`THIN_H` 高），其余方块整格
                    h = THIN_H if b in THIN_BLOCKS else 1.0
                    _append_face(mb, face, x, y, z, tile, tile_size, height=h)
    if debug:
        _DEBUG_ON = False
    stats = mb.stats()
    return mb, stats
