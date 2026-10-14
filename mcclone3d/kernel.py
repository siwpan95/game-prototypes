# -*- coding: utf-8 -*-
"""mcclone3d 玩法内核（Cordis `Service`）—— 体素沙盒的**全部玩法语义**。

为什么玩法都住在这里
--------------------
引擎的约定是「demo 只做输入与渲染，玩法全在内核」：
`examples/mcclone3d.py` 把按键映射成这里的方法调用，然后把内核状态画出来。
好处是**同一套玩法能被两条路径驱动**：
* demo（有人按键）—— 人玩；
* `auto_step()`（脚本化自动机）—— headless 验收，不需要窗口。

`inject = []` 是**有意的**：本内核零 GL、不取任何引擎句柄 ⇒
`cli/config_boot` 对它 `require_gl=False`，`python -m mcclone3d.cli` 在没有显卡的
机器上也能跑完整验收。

坐标与单位
----------
* 玩家位置是**浮点世界坐标**（脚底中心），方块是整数格号；
* 面向：`yaw` 绕 y（0 = 朝 -z），`pitch` 抬头为正（钳在 ±89°）；
* 一切时间推进都经 `step(dt)`，`dt` 由调用方给 —— 内核自己不读时钟（可回放）。

确定性
------
`auto_step` 只依赖"累计时间"与"脚本下标"，不依赖帧率 ⇒ 同一条脚本在任何
帧率下走到同一个结果（有单测钉住，与引擎侧其它内核同一口径）。
"""
from __future__ import annotations

import json
import math
import os

from . import blocks as B
from ._engine import Service
from .world import CHUNK, SEA_LEVEL, ChunkedWorld

__all__ = ['McCloneKernel', 'make_offline', 'DEFAULT_SEED', 'REACH', 'PLAYER_HALF',
           'PLAYER_HEIGHT', 'GRAVITY', 'JUMP_V', 'WALK_SPEED', 'FLY_SPEED', 'SCRIPT',
           'WORLD_SIZE', 'WORLD_HEIGHT', 'STEP_HZ', 'START_STOCK']

# ---------------------------------------------------------------- 常量
DEFAULT_SEED = 20261014
WORLD_SIZE = 256                  # 世界水平边长（格）
WORLD_HEIGHT = 64                 # 世界高度（格）

REACH = 5.0                       # 准星够得着的距离（格）
PLAYER_HALF = 0.3                 # 玩家 AABB 半宽
PLAYER_HEIGHT = 1.8               # 玩家高度
EYE_HEIGHT = 1.62                 # 眼睛高度（射线起点）
GRAVITY = 28.0                    # 重力（格/秒²）
JUMP_V = 8.4                      # 起跳速度（≈1.25 格高）
WALK_SPEED = 4.8                  # 行走速度（格/秒）
FLY_SPEED = 11.0                  # 飞行速度
TERMINAL_V = 40.0                 # 终端速度（防穿地）
STEP_HZ = 60.0                    # 自动机的量化步频

#: 默认 hotbar（名字 → id；配置树可覆盖）
DEFAULT_HOTBAR = B.DEFAULT_HOTBAR

#: 开局赠送（创造模式手感：每样给一组，挖了还会补）
START_STOCK = 64


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


class McCloneKernel(Service):
    """体素沙盒内核。构造参数 `config` 由配置树透传（见 `configs/cordis.mcclone.yml`）。"""

    inject = []

    def __init__(self, ctx, config=None):
        super().__init__(ctx, 'mcclone')
        self._init(config)

    def _init(self, config=None):
        """真正建状态的地方。**`__init__` 与 `make_offline` 都走这里**。

        分成两半是因为：离线装配（单测 / 回放）必须绕开 `Service.__init__`
        （它要 `ctx.reflect.provide` 真挂服务），但**不能因此少走一步初始化** ——
        早先有项目在两条装配路径各写一份 `_init_state`，漏一个字段就静默算出错的答案。
        """
        cfg = dict(config or {})
        self.seed = int(cfg.get('seed', DEFAULT_SEED))
        self.size = int(cfg.get('size', WORLD_SIZE))
        self.height = int(cfg.get('height', WORLD_HEIGHT))
        self.creative = bool(cfg.get('creative', True))
        self.reach = float(cfg.get('reach', REACH))
        hotbar_names = cfg.get('hotbar') or list(DEFAULT_HOTBAR)
        self.hotbar = [B.by_name(n).id for n in hotbar_names]
        self.world = ChunkedWorld(self.seed, self.size, self.height)
        self.world.generate()
        self.world.plant_trees()
        #: 世界被改动的次数 —— demo 用它判断"哪些区块的网格要重建"
        self.revision = 0
        #: 哪些区块的网格需要（重）建。**开局 = 全部区块**：否则第一次渲染
        #: 一个面都不会出现（`chunk_meshes` 只建"脏"的，而没人标脏）。
        self.dirty_chunks: set = set(self.world.chunks)
        self._meshes: dict = {}
        self._built: set = set()
        self._init_player()

    # ============================================================== 玩家
    def _init_player(self):
        x = self.size // 2
        z = self.size // 2
        y = self._spawn_y(x, z)
        self.pos = [float(x) + 0.5, float(y), float(z) + 0.5]
        self.vel = [0.0, 0.0, 0.0]
        self.yaw = 0.0            # 0 = 朝 -z
        self.pitch = -8.0         # 略微低头，看得见脚下
        self.flying = False
        self.grounded = False
        self.inventory = {}
        if self.creative:
            for b in B.all_blocks():
                self.inventory[b.id] = START_STOCK
        self.selected = 0
        self.stats = {'dug': 0, 'placed': 0}

    def _spawn_y(self, x: int, z: int) -> int:
        """出生高度：**站在该列真实的地表上**（脚能站、头不卡）。

        判据用 `world.surface_at()`（与生成/种树同一个口径）—— 先前这里从
        `height-2` 往下找固体，在"地表被水盖住"或"世界比地表高得多"两种情况下
        都会退化成"生在半空/水面之上"。现在直接问地表，再从地表往上找第一个空位。
        """
        x = max(0, min(self.size - 1, x))
        z = max(0, min(self.size - 1, z))
        surface = self.world.surface_at(x, z)
        for y in range(surface, min(self.height - 2, surface + 8)):
            if not B.is_solid(self.world.get(x, y, z)) \
                    and not B.is_solid(self.world.get(x, y + 1, z)):
                return y
        return min(surface, self.height - 3)

    def reset(self, seed: int | None = None):
        """重开一局（换种子则重建世界）。"""
        if seed is not None and int(seed) != self.seed:
            self.seed = int(seed)
            self.world = ChunkedWorld(self.seed, self.size, self.height)
            self.world.generate()
            self.world.plant_trees()
        else:
            self.world.generate()
            self.world.plant_trees()
        self._init_player()
        self.revision += 1
        self.dirty_chunks = set(self.world.chunks)
        return self

    def status(self) -> str:
        """引擎约定的状态串（`cli/config_boot` 会读它）。"""
        return 'playing'

    # ============================================================== 视线
    def look_dir(self):
        """面向单位向量（与 `yaw`/`pitch` 一致；射线与相机共用同一个口径）。"""
        y = math.radians(self.yaw)
        p = math.radians(self.pitch)
        cp = math.cos(p)
        return (-math.sin(y) * cp, math.sin(p), -math.cos(y) * cp)

    def eye_pos(self):
        return (self.pos[0], self.pos[1] + EYE_HEIGHT, self.pos[2])

    def raycast(self, max_dist: float | None = None):
        """DDA 体素射线：返回 `(hit_xyz, normal_xyz)` 或 `None`。

        用 Amanatides & Woo 的整数步进（**不做小步长采样**）：步数只与跨过的
        格子数成正比，且不会因为步长太大而"穿过"薄墙。

        ⚠ 两处曾经写错、值得记下来的坑（2026-10-14 实测）：

        1. **到第一个边界的参数距离**：正方向是 `(floor(o)+1 − o)/d`，
           负方向是 `(floor(o) − o)/d`。先前统一用 `i + (1 if s > 0 else 0)`，
           对负方向会得到一个**负的 t**（因为 `floor(o) − o ≤ 0`）⇒ 射线照常走完，
           **却一格都命中不了** —— 症状是"正下方有方块，raycast 返回 None"。
        2. **命中判定必须在推进之后**：先判当前格、再 `t > dist` 收尾。
           若把 `dist` 判在推进前，最后一格会被跳过（贴脸的方块反而挖不到）。
        """
        dist = self.reach if max_dist is None else float(max_dist)
        ox, oy, oz = self.eye_pos()
        dx, dy, dz = self.look_dir()

        x, y, z = int(math.floor(ox)), int(math.floor(oy)), int(math.floor(oz))
        sx, sy, sz = _sign(dx), _sign(dy), _sign(dz)

        def _tmax(o, d, s):
            """到下一个格边界的参数距离（按方向取 floor 或 floor+1）。

            ⚠ **恰好落在格边界上、且往负方向走** 时必须返回 `inf`：
            此时 `floor(o) - o == 0`，公式给 `-0.0`，会被当成"立刻跨过这个边界"，
            于是**跳过了那一轴的相邻格**（实测症状：眼睛正好在 x=24.0/z=24.0，
            向下的射线却先在 z 轴上"跨"出去，正下方的方块永远看不到）。
            物理上的正确读法是：站在边界上往负方向走，该轴的第一个边界在
            **下一个**单位处，不是现在 —— 交给其它两轴先推进，走到那格再算。
            """
            if s == 0:
                return float('inf')
            if s < 0 and float(o).is_integer():
                return float('inf')
            boundary = (math.floor(o) + 1) if s > 0 else math.floor(o)
            return (boundary - o) / d
        tx = _tmax(ox, dx, sx)
        ty = _tmax(oy, dy, sy)
        tz = _tmax(oz, dz, sz)
        tdx = abs(1.0 / dx) if dx else float('inf')
        tdy = abs(1.0 / dy) if dy else float('inf')
        tdz = abs(1.0 / dz) if dz else float('inf')

        normal = (0, 0, 0)
        t = 0.0
        for _ in range(512):                       # 硬上限：绝不无限循环
            if not (0 <= x < self.size and 0 <= y < self.height and 0 <= z < self.size):
                return None                        # 出界（世界外一律是空气）
            if self.world.get(x, y, z) != B.AIR:
                return (x, y, z), normal
            if tx <= ty and tx <= tz:
                t = tx
                x += sx
                tx += tdx
                normal = (-sx, 0, 0)
            elif ty <= tz:
                t = ty
                y += sy
                ty += tdy
                normal = (0, -sy, 0)
            else:
                t = tz
                z += sz
                tz += tdz
                normal = (0, 0, -sz)
            if t > dist:                           # 推进后才发现超距：这一格就不该看
                return None
        return None

    # ============================================================== 玩法动作
    def select(self, index: int) -> int:
        """选 hotbar 格（环形回绕）。返回当前格号。"""
        if not self.hotbar:
            return 0
        self.selected = int(index) % len(self.hotbar)
        return self.selected

    def scroll(self, delta: int) -> int:
        return self.select(self.selected + int(delta))

    def selected_block(self) -> int:
        return self.hotbar[self.selected] if self.hotbar else B.AIR

    def dig(self):
        """挖掉准星指的方块。返回 `(ok, 方块名)`（没瞄到就 `(False, None)`）。"""
        hit = self.raycast()
        if hit is None:
            return False, None
        (x, y, z), _n = hit
        old = self.world.get(x, y, z)
        if old == B.AIR or old == B.BEDROCK:
            return False, None                     # 基岩挖不动（与 MC 一致）
        if self.world.set(x, y, z, B.AIR):
            self._mark_dirty(x, y, z)
            self.stats['dug'] += 1
            if not self.creative:
                self._give(old, 1)
            return True, B.by_id(old).name
        return False, None

    def place(self):
        """在准星指的**相邻空位**放当前 hotbar 方块。返回 `(ok, 坐标或 None)`。"""
        hit = self.raycast()
        if hit is None:
            return False, None
        (x, y, z), n = hit
        tx, ty, tz = x + n[0], y + n[1], z + n[2]
        if not (0 <= tx < self.size and 0 <= ty < self.height and 0 <= tz < self.size):
            return False, None
        if self.world.get(tx, ty, tz) != B.AIR:
            return False, None
        if self._would_trap_player(tx, ty, tz):
            return False, None                     # 不许把自己封死
        bid = self.selected_block()
        if bid == B.AIR:
            return False, None
        if not self.creative and self.inventory.get(bid, 0) <= 0:
            return False, None
        if self.world.set(tx, ty, tz, bid):
            self._mark_dirty(tx, ty, tz)
            self.stats['placed'] += 1
            if not self.creative:
                self._take(bid, 1)
            return True, (tx, ty, tz)
        return False, None

    def _mark_dirty(self, x: int, y: int, z: int):
        """记下"哪些区块脏了"：改动格所在区块 + 贴在边界时相邻区块也要重建。"""
        self.revision += 1
        cx, cy, cz = x // CHUNK, y // CHUNK, z // CHUNK
        self.dirty_chunks.add((cx, cy, cz))
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0)):
            nx, ny, nz = x + dx, y + dy, z + dz
            if (nx // CHUNK, ny // CHUNK, nz // CHUNK) != (cx, cy, cz):
                self.dirty_chunks.add((nx // CHUNK, ny // CHUNK, nz // CHUNK))

    def _give(self, block_id: int, n: int):
        self.inventory[block_id] = self.inventory.get(block_id, 0) + int(n)

    def _take(self, block_id: int, n: int = 1) -> bool:
        have = self.inventory.get(block_id, 0)
        if have < n:
            return False
        self.inventory[block_id] = have - n
        return True

    # ============================================================== 物理
    def _player_boxes(self, x: float, y: float, z: float):
        """玩家 AABB 覆盖的整数格范围（半开区间）。"""
        x0 = int(math.floor(x - PLAYER_HALF))
        x1 = int(math.floor(x + PLAYER_HALF))
        z0 = int(math.floor(z - PLAYER_HALF))
        z1 = int(math.floor(z + PLAYER_HALF))
        y0 = int(math.floor(y))
        y1 = int(math.floor(y + PLAYER_HEIGHT - 1e-6))
        return x0, x1, y0, y1, z0, z1

    def _blocked(self, x: float, y: float, z: float) -> bool:
        """这个位置会不会与固体方块相交。"""
        x0, x1, y0, y1, z0, z1 = self._player_boxes(x, y, z)
        for bx in range(x0, x1 + 1):
            for by in range(y0, y1 + 1):
                for bz in range(z0, z1 + 1):
                    if B.is_solid(self.world.get(bx, by, bz)):
                        return True
        return False

    def _would_trap_player(self, x: int, y: int, z: int) -> bool:
        """在那个格子放方块，会不会把玩家卡住（脚或头所在格）。"""
        px, py, pz = self.pos
        x0, x1, y0, y1, z0, z1 = self._player_boxes(px, py, pz)
        return x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1

    def _move_axis(self, axis: int, amount: float):
        """单轴移动 + 碰撞（分轴求解：这是"贴墙滑行"能成立的关键）。"""
        if amount == 0.0:
            return
        target = list(self.pos)
        target[axis] += amount
        if self._blocked(*target):
            if axis == 1 and amount < 0:
                # 落地：把坐标**吸附到支撑面**（脚下方块的上边），别停在"差一点点"处。
                # 不吸附的话会进一个浮点极限环：`_blocked(y-0.05)` 为真 ⇒ 速度清零，
                # 下一帧重力又把 y 推下去一点点、再次被挡回来 ⇒ 实测在
                # 9.0 ± 0.0022 之间永远抖，"停在地面上"这类断言只能靠模糊比较。
                self.pos[1] = float(math.floor(self.pos[1]))
                self.grounded = True
            self.vel[axis] = 0.0
            return
        self.pos[axis] = target[axis]
        if axis == 1 and amount < 0:
            self.grounded = False

    def step(self, dt: float, move=(0.0, 0.0), jump: bool = False):
        """推进一帧：先按输入与重力更新速度，再分轴移动。

        `move` 是**玩家坐标系的输入**（前后, 左右），会被 `yaw` 转到世界坐标系。
        """
        dt = max(0.0, min(0.1, float(dt)))         # 卡帧保护（掉帧时不穿墙）
        fwd, side = move
        yaw = math.radians(self.yaw)
        # 前方 = 视线在水平面的投影；右方 = 前方逆时针 90°
        fx, fz = -math.sin(yaw), -math.cos(yaw)
        rx, rz = -fz, fx
        wish_x = fx * fwd + rx * side
        wish_z = fz * fwd + rz * side
        n = math.hypot(wish_x, wish_z)
        if n > 1e-6:
            wish_x, wish_z = wish_x / n, wish_z / n

        speed = FLY_SPEED if self.flying else WALK_SPEED
        if self.flying:
            self.vel[0] = wish_x * speed
            self.vel[2] = wish_z * speed
            self.vel[1] = 0.0
            if jump:
                self.vel[1] = speed
            self.pos[0] += self.vel[0] * dt
            self.pos[2] += self.vel[2] * dt
            self.pos[1] += self.vel[1] * dt
            self._clamp_bounds()
            return

        self.vel[0] = wish_x * speed
        self.vel[2] = wish_z * speed
        if jump and self.grounded:
            self.vel[1] = JUMP_V
            self.grounded = False
        self.vel[1] = max(-TERMINAL_V, self.vel[1] - GRAVITY * dt)

        self._move_axis(1, self.vel[1] * dt)
        self._move_axis(0, self.vel[0] * dt)
        self._move_axis(2, self.vel[2] * dt)
        self._clamp_bounds()

        # 落地判定：脚下那格是固体 ⇒ 站稳（分轴求解里只在撞到东西时置位，
        # 静止站在地面上时 amount=0 不会触发，所以这里补一次）
        if not self.grounded and self.vel[1] <= 0:
            below = [self.pos[0], self.pos[1] - 0.05, self.pos[2]]
            if self._blocked(*below):
                self.grounded = True
                self.vel[1] = 0.0

    def _clamp_bounds(self):
        """别掉出世界（掉出去就送回地表）。"""
        if self.pos[1] < -2:
            x, z = int(self.pos[0]), int(self.pos[2])
            self.pos[1] = float(self._spawn_y(max(0, min(self.size - 1, x)),
                                              max(0, min(self.size - 1, z))))
            self.vel = [0.0, 0.0, 0.0]
        self.pos[0] = min(max(self.pos[0], PLAYER_HALF), self.size - PLAYER_HALF)
        self.pos[2] = min(max(self.pos[2], PLAYER_HALF), self.size - PLAYER_HALF)

    # ============================================================== 自动机
    def auto_step(self, dt: float):
        """脚本化自动机（headless 验收与录制共用）。

        按**累计时间**推进脚本：走出四段路、每段尽头挖 3 格、再在空位放回去。
        只依赖累计时间 ⇒ 与帧率无关（同一条脚本在任何帧率下结果相同）。
        """
        if not hasattr(self, '_auto_t'):
            self._auto_t = 0.0
            self._auto_i = 0
            self._auto_log = []
        self._auto_t += float(dt)
        while self._auto_i < len(SCRIPT) and self._auto_t >= SCRIPT[self._auto_i][0]:
            self._auto_run(self._auto_i)
            self._auto_i += 1
        # 脚本之外：每帧按当前指令走（move/jump 由 _auto_run 写进 _auto_move）
        self.step(dt, getattr(self, '_auto_move', (0.0, 0.0)),
                  getattr(self, '_auto_jump', False))
        return self.status()

    def _auto_run(self, i: int):
        """执行脚本第 i 步。"""
        t, kind, arg = SCRIPT[i]
        if kind == 'face':
            self.yaw, self.pitch = arg
        elif kind == 'walk':
            self._auto_move = arg
            self._auto_jump = False
        elif kind == 'stop':
            self._auto_move = (0.0, 0.0)
        elif kind == 'jump':
            self._auto_jump = True
        elif kind == 'dig':
            self._auto_move = (0.0, 0.0)
            ok, name = self.dig()
            self._auto_log.append(('dig', ok, name))
        elif kind == 'select':
            self.select(int(arg))
        elif kind == 'place':
            ok, at = self.place()
            self._auto_log.append(('place', ok, at))
        elif kind == 'aim_down':
            self.pitch = -35.0
        elif kind == 'aim_up':
            self.pitch = 25.0

    # ============================================================== 网格
    def chunk_meshes(self, *, only_dirty: bool = True, limit: int = 8):
        """建（或重建）区块网格 —— **纯数据，不碰 GL**，demo 负责上传。

        `only_dirty=True` 时只建"脏"区块（改动过或还没建过），每次最多 `limit` 个 ——
        交互时一帧建太多会卡顿，所以摊到多帧（与引擎侧 blockworld 的做法同源）。
        """
        from .mesh import build_chunk_mesh
        if not hasattr(self, '_meshes'):
            self._meshes = {}
            self._built: set = set()
        todo = []
        for key in (self.dirty_chunks if only_dirty else set(self.world.chunks)):
            if key in self._meshes and key not in self.dirty_chunks:
                continue
            todo.append(key)
        todo.sort()
        built = []
        for key in todo[:max(1, limit)]:
            mb, st = build_chunk_mesh(self.world, *key)
            self._meshes[key] = (mb, st)
            self._built.add(key)
            self.dirty_chunks.discard(key)
            built.append((key, st))
        return built

    def mesh_stats(self) -> dict:
        """已建网格的汇总（面数 / 顶点数 / 区块数）—— 验收与 HUD 用。"""
        if not hasattr(self, '_meshes'):
            return {'chunks': 0, 'faces': 0, 'verts': 0}
        faces = sum(st['faces'] for _mb, st in self._meshes.values())
        verts = sum(st['verts'] for _mb, st in self._meshes.values())
        return {'chunks': len(self._meshes), 'faces': faces, 'verts': verts}

    # ============================================================== 存档
    def dump(self) -> dict:
        """完整存档：世界（种子 + 编辑增量）+ 玩家 + hotbar。"""
        return {
            'version': 1,
            'world': self.world.dump(),
            'player': {
                'pos': [float(v) for v in self.pos],
                'vel': [float(v) for v in self.vel],
                'yaw': float(self.yaw),
                'pitch': float(self.pitch),
                'flying': bool(self.flying),
                'selected': int(self.selected),
                'hotbar': [B.by_id(b).name for b in self.hotbar],
                'inventory': {B.by_id(k).name: int(v)
                              for k, v in sorted(self.inventory.items()) if v},
                'stats': dict(self.stats),
            },
        }

    def load(self, data: dict):
        """读档（世界按存档的种子/尺寸重建，再重放增量与玩家状态）。"""
        if int(data.get('version', 0)) != 1:
            raise ValueError(f'不支持的存档版本：{data.get("version")!r}')
        wd = data['world']
        # ⚠ 校验必须在**覆盖字段之前**（实测踩过：先 `self.size = wd['size']` 再比对，
        # 于是"尺寸不匹配"这条校验永远通过 —— 自己刚赋的值当然等于自己）
        if int(wd['seed']) != self.seed or int(wd['size']) != self.size \
                or int(wd['height']) != self.height:
            raise ValueError(
                f'存档与当前世界不一致：存档 seed={wd["seed"]} size={wd["size"]} '
                f'height={wd["height"]}，当前 seed={self.seed} size={self.size} '
                f'height={self.height} ⇒ 请按存档参数新建内核再读')
        self.seed = int(wd['seed'])
        self.size = int(wd['size'])
        self.height = int(wd['height'])
        self.world = ChunkedWorld(self.seed, self.size, self.height)
        self.world.load(wd)
        p = data['player']
        self.pos = [float(v) for v in p['pos']]
        self.vel = [float(v) for v in p.get('vel', (0, 0, 0))]
        self.yaw = float(p.get('yaw', 0.0))
        self.pitch = float(p.get('pitch', 0.0))
        self.flying = bool(p.get('flying', False))
        self.hotbar = [B.by_name(n).id for n in p['hotbar']]
        self.selected = int(p.get('selected', 0)) % max(1, len(self.hotbar))
        self.inventory = {B.by_name(n).id: int(v)
                          for n, v in (p.get('inventory') or {}).items()}
        self.stats = dict(p.get('stats') or {'dug': 0, 'placed': 0})
        self.revision += 1
        self.dirty_chunks = set(self.world.chunks)
        self._meshes = {}
        self._built = set()
        return self

    def save(self, path: str) -> str:
        """写存档（UTF-8 显式编码 —— 文本 I/O 一律显式，见项目纪律）。"""
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(self.dump(), fh, ensure_ascii=False, indent=1, sort_keys=True)
        return path

    def load_file(self, path: str):
        with open(path, encoding='utf-8') as fh:
            return self.load(json.load(fh))

    # ============================================================== 体检
    def summary(self) -> dict:
        """一句话状态（CLI 打印与 HUD 共用）。"""
        w = self.world.stats()
        m = self.mesh_stats()
        return {
            'seed': self.seed, 'pos': tuple(round(v, 2) for v in self.pos),
            'yaw': round(self.yaw, 1), 'pitch': round(self.pitch, 1),
            'grounded': self.grounded, 'flying': self.flying,
            'slot': self.selected, 'holding': B.by_id(self.selected_block()).name,
            'dig': self.stats['dug'], 'placed': self.stats['placed'],
            'blocks': w['blocks'], 'edits': w['edits'],
            'mesh_chunks': m['chunks'], 'faces': m['faces'],
        }


#: 自动机脚本：`(时刻秒, 动作, 参数)`。**时间驱动 ⇒ 与帧率无关**。
SCRIPT = (
    (0.10, 'aim_down', None),
    (0.20, 'walk', (1.0, 0.0)),
    (2.00, 'stop', None),
    (2.20, 'dig', None),
    (2.50, 'dig', None),
    (2.80, 'dig', None),
    (3.10, 'select', 2),
    (3.30, 'place', None),
    (3.60, 'place', None),
    (3.90, 'walk', (0.0, -1.0)),
    (5.20, 'stop', None),
    (5.40, 'aim_up', None),
    (5.60, 'jump', None),
    (5.80, 'walk', (1.0, 0.0)),
    (7.00, 'stop', None),
    (7.20, 'dig', None),
    (7.50, 'select', 0),
    (7.70, 'place', None),
    (8.20, 'stop', None),
)


def make_offline(config=None, seed: int | None = None) -> McCloneKernel:
    """**离线内核**（不挂 ctx）：单测 / 回放 / CLI 共用这一条装配路径。

    用 `__new__` 绕开 `Service.__init__`（它要 `ctx.reflect.provide` 真挂服务），
    但初始化仍然走 `McCloneKernel._init` —— **装配只有一处**，不会两条路各漂一半。
    """
    k = McCloneKernel.__new__(McCloneKernel)
    k.ctx = None
    cfg = dict(config or {})
    if seed is not None:
        cfg['seed'] = int(seed)
    k._init(cfg)
    return k
