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
from . import items as I
from . import recipes as R
from ._engine import Service
from . import ai as AI
from . import mobs as MB
from .light import DEFAULT_HALO, MAX_LIGHT, LightEngine
from .sun import DAY_LENGTH, DayCycle
from .world import CHUNK, SEA_LEVEL, ChunkedWorld

__all__ = ['McCloneKernel', 'make_offline', 'DEFAULT_SEED', 'REACH', 'PLAYER_HALF',
           'PLAYER_HEIGHT', 'GRAVITY', 'JUMP_V', 'WALK_SPEED', 'FLY_SPEED', 'SCRIPT',
           'WORLD_SIZE', 'WORLD_HEIGHT', 'STEP_HZ', 'START_STOCK',
           'MAX_HEALTH', 'MAX_HUNGER', 'DROP_PICKUP_R', 'DROP_TTL',
           'DAY_LENGTH', 'LIGHT_BUDGET_PER_FRAME', 'SAVE_VERSION',
           'MOB_SPAWN_INTERVAL', 'MOB_CAP', 'VILLAGE_SPAWN_SPAN', 'VILLAGE_POP',
           'REDSTONE_BUDGET_PER_FRAME']

#: 存档版本。**只增不改语义**：加字段就 +1，读档必须能吃所有老版本。
#: v1 = Phase 0 ｜ v2 = Phase 1（工具/生存/掉落/熔炉）｜ v3 = Phase 2-A（世界时刻）
SAVE_VERSION = 3

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

#: 默认 hotbar（**物品名** → id；配置树可覆盖）
DEFAULT_HOTBAR = B.DEFAULT_HOTBAR

#: 开局赠送（创造模式手感：每样给一组，挖了还会补）
START_STOCK = 64

# ---------------------------------------------------------------- 生存（Phase 1）
MAX_HEALTH = 20.0                 # 血量上限（10 颗心，与 MC 同量级）
MAX_HUNGER = 20.0                 # 饥饿上限
START_SATURATION = 5.0            # 开局"饱食度"（先掉它、再掉饥饿）
HUNGER_PER_METER = 0.012          # 每走一格消耗的饥饿（走得远才饿）
HUNGER_PER_DIG = 0.05             # 挖一格的消耗
REGEN_AT = 18.0                   # 饥饿高于它才自然回血
REGEN_RATE = 0.35                 # 回血速度（点/秒）
STARVE_RATE = 0.5                 # 饿到 0 后掉血速度（点/秒）
FALL_SAFE = 3.5                   # 摔落安全高度（格）
FALL_DAMAGE_PER = 1.0             # 每多摔一格掉多少血

# ---------------------------------------------------------------- 掉落物
DROP_PICKUP_R = 1.4               # 拾取半径（格）
DROP_TTL = 300.0                  # 掉落物存在时长（秒）；太长会拖慢存档
DROP_FALL_V = 6.0                 # 掉落物下落速度（格/秒，简单常量不走重力积分）

# ---------------------------------------------------------------- 光照（Phase 2-A）
#: 每帧最多算几个区块的光照（**光照比网格贵**：实测 halo=4 时 ~36ms/区块）
LIGHT_BUDGET_PER_FRAME = 2

# ---------------------------------------------------------------- 生物（Phase 2-B）
#: 每隔多少秒尝试刷一批生物（不是每帧都刷：刷怪本身要查方块与光照）
MOB_SPAWN_INTERVAL = 4.0
#: 同时存在的生物上限（性能护栏）
MOB_CAP = AI.MAX_MOBS
#: 每次尝试刷几只（成功一只就够，多试几次给失败的尝试留机会）
MOB_SPAWN_TRIES = 24
#: 村庄刷村民的搜索半径（格）—— 村庄半径 13，取 10 让村民待在村里
VILLAGE_SPAWN_SPAN = 10
#: 每帧最多重算几个红石网络（护栏：一个网络的重算是几十毫秒级）
REDSTONE_BUDGET_PER_FRAME = 2
#: 每个村庄的村民上限（见 `_try_spawn_villager` 的说明）
VILLAGE_POP = 4


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
        # hotbar 里放的是**物品 id**（方块物品同名），这样手持工具/食物也能进 hotbar
        self.hotbar = [I.item_by_name(n).id for n in hotbar_names]
        self.world = ChunkedWorld(self.seed, self.size, self.height)
        self.world.generate()
        self.world.decorate()
        #: 世界被改动的次数 —— demo 用它判断"哪些区块的网格要重建"
        self.revision = 0
        #: 哪些区块的网格需要（重）建。**开局 = 全部区块**：否则第一次渲染
        #: 一个面都不会出现（`chunk_meshes` 只建"脏"的，而没人标脏）。
        self.dirty_chunks: set = set(self.world.chunks)
        self._meshes: dict = {}
        self._built: set = set()
        # --- Phase 2-A：昼夜 + 逐格光照 ---
        self.cycle = DayCycle(float(cfg.get('time', 0.0)),
                              float(cfg.get('day_length', DAY_LENGTH)))
        if cfg.get('time_phase') is not None:
            self.cycle.skip_to_phase(float(cfg['time_phase']))
        #: 冻结昼夜（配置口）。**给"要固定在同一时刻"的判据用** ——
        #: 例如测"僵尸会不会追上来打人"，如果时间在走，天亮时僵尸会被晒死，
        #: 于是判据变成"能不能在 2 秒内追上"，与它想测的东西无关（实测踩过）。
        self.cycle.paused = bool(cfg.get('time_paused', False))
        # --- Phase 2-C：天气（**由时刻+种子决定**，与昼夜同口径；不进存档） ---
        from .weather import WeatherCycle
        self.weather = WeatherCycle(self.seed)
        if cfg.get('weather') is not None:
            self.weather_kind = str(cfg['weather'])       # 固定天气（判据/截图用）
        else:
            self.weather_kind = None
        self.light = LightEngine(self.world)
        # --- Phase 2-C：水流（元状态**可由「源 + 方块」完全重算** ⇒ 不进存档） ---
        #: 生成时的水全部标成源（海/湖是无限水源，MC 同款）；玩家挖出来的水
        #: 才是"非源"，会 level 衰减并干涸。见 `fluid.FluidSystem` 的模型说明。
        from . import fluid as FL
        self.fluid = FL.FluidSystem()
        self.fluid.mark_sources(self.world)
        #: 水流计时器（累加到 `FLUID_INTERVAL` 才跑一步）
        self._fluid_t = 0.0
        # --- Phase 3：红石（信号是**派生状态**，不进存档；见 redstone 模块说明）---
        from .redstone import PowerGrid
        #: `on_change` 直接接 `_mark_dirty`：红石改了方块 ⇒ 网格重建 + 光照失效
        #: （红石灯点亮时正是靠这条让光照引擎知道"这里多了个光源"）
        self.redstone = PowerGrid(self.world, on_change=self._mark_dirty)
        #: 全局天光列传播**默认做一次**（与高度成正比，很快）。
        #: `light=False` 可以跳过 —— 给"完全不关心光照"的体检/单测用
        #: （否则每个 `make_offline` 都要付一次全图列传播；CLI 一次跑十几个内核，
        #   实测这一条能把整个验收从 20 多秒压回几秒）。
        if cfg.get('light', True):
            self.light.column_pass_all()
            self._lit: set = set()
        else:
            self.light.columns_done = True     # 声明"不用算"，避免按需路径又补一遍
            self._lit = set()
        # --- Phase 2-B：生物 ---
        #: 世界里的生物（`Mob` 列表）。**不是每个区块各一份** —— 生物会跨区块移动，
        #: 按区块存反而要处理"迁移"，那是没有收益的复杂度。
        self.mobs: list = []
        self._mob_t = 0.0
        #: 是否启用生物（`mobs=False` 给"纯建造"场景与不测生物的体检用）
        self.mob_enabled = bool(cfg.get('mobs', True))
        #: 刷新用确定性随机（`random.Random(seed)`：同种子同结果，可回放）
        import random as _random
        self._mob_rng = _random.Random(self.seed ^ 0x5EED)
        self.mob_stats = {'spawned': 0, 'despawned': 0, 'killed': 0,
                          'mob_hits': 0, 'player_hits': 0}
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
        #: 背包：**物品 id** → 数量（Phase 1 起用物品 id 空间，方块物品是 100+）
        self.inventory = {}
        #: 工具实例：物品 id → 剩余耐久（工具带状态，不能压在数量里）
        self.tool_durability = {}
        self.selected = 0
        self.stats = {'dug': 0, 'placed': 0, 'crafted': 0, 'smelted': 0,
                      'picked': 0, 'eaten': 0, 'deaths': 0, 'damage': 0.0}
        # --- 生存状态 ---
        self.max_health = MAX_HEALTH
        self.health = float(MAX_HEALTH)
        self.max_hunger = MAX_HUNGER
        self.hunger = float(MAX_HUNGER)
        self.saturation = float(START_SATURATION)
        self.state = 'playing'          # playing / dead
        self.death_cause = ''
        #: 世界里的掉落物：`[{'pos':[x,y,z], 'item':id, 'n':count, 't':已存活秒}]`
        self.drops = []
        #: 当前挖掘进度（秒）；换目标就清零
        self.dig_target = None
        self.dig_progress = 0.0
        #: 摔落结算用：离地那一刻的高度（落地时清零）
        self._fall_from = None
        #: 熔炉状态：`{'fuel_left':秒, 'cook_left':秒, 'recipe':id|None}`
        self.furnace = {'fuel_left': 0.0, 'cook_left': 0.0, 'recipe': None}
        if self.creative:
            for it in I.all_items():
                self.inventory[it.id] = START_STOCK
                if it.is_tool:
                    self.tool_durability[it.id] = it.durability

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
            self.world.decorate()
        else:
            self.world.generate()
            self.world.decorate()
        # 世界重建 ⇒ 源与水位全部作废，重新标记（否则会拿着旧世界的坐标去演化）
        from . import fluid as FL
        self.fluid = FL.FluidSystem()
        self.fluid.mark_sources(self.world)
        # 同理：红石的信号场也是**按坐标存**的 ⇒ 必须重建（否则拿着旧世界的信号）
        from .redstone import PowerGrid
        self.redstone = PowerGrid(self.world, on_change=self._mark_dirty)
        #: 水流计时器（累加到 `FLUID_INTERVAL` 才跑一步）
        self._fluid_t = 0.0
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

    def selected_item(self) -> int:
        """当前手持的**物品** id（空气返回 0）。"""
        return self.hotbar[self.selected] if self.hotbar else 0

    def selected_block(self) -> int:
        """当前手持物品对应的**方块** id（手持工具/材料时返回 AIR）。

        Phase 0 的语义保留在这里：hotbar 里仍以"放下就成方块"为主。
        """
        it = I.ITEMS.get(self.selected_item())
        return it.block_id if (it is not None and it.is_block) else B.AIR

    def held_tool(self):
        """当前手持的 `Item`（不是工具、或**这把工具已经断了**都返回 None）。

        ⚠ 必须同时看"背包里还有没有"：`_use_tool` 断裂时清的是 `inventory` 与
        `tool_durability`，但 **hotbar 那一格还留着那个 id** ——
        只按 hotbar 判会让断掉的镐变成"幽灵镐"：照旧按镐的速度挖、照旧掉落
        （TEST-SMITH 实测抓出：断裂后 `held_durability()` 还报满耐久 60）。
        """
        it = I.ITEMS.get(self.selected_item())
        if it is None or not it.is_tool:
            return None
        if it.id not in self.inventory and it.id not in self.tool_durability:
            return None
        return it

    def held_durability(self):
        """手持工具的剩余耐久（不是工具返回 None）。"""
        it = self.held_tool()
        return None if it is None else int(self.tool_durability.get(it.id, it.durability))

    # ---------------------------------------------------------------- 挖
    def dig_time(self) -> float:
        """挖"准星正指的那一格"需要多少秒（没瞄到返回 0）。"""
        hit = self.raycast()
        if hit is None:
            return 0.0
        b = self.world.get(*hit[0])
        if not I.can_break(b):
            return float('inf')                    # 基岩：永远挖不完
        return I.break_time(b, self.held_tool())

    def dig_dt(self, dt: float):
        """**按住左键**推进挖掘：累积到 `dig_time()` 才真正挖掉。

        返回 `('digging', 进度0..1)` / `('done', 掉落列表)` / `('idle', None)`。
        换目标（准星指到别的格子）会**清零进度** —— 这是 MC 的手感，
        也避免了"左右横跳蹭进度"。
        """
        hit = self.raycast()
        if hit is None:
            self.dig_target, self.dig_progress = None, 0.0
            return 'idle', None
        target = hit[0]
        if self.dig_target != target:
            self.dig_target, self.dig_progress = target, 0.0
        need = self.dig_time()
        if need == float('inf'):
            return 'idle', None                    # 基岩：进度条永远不动
        if need <= 0.0:
            ok, info = self._finish_dig(target)
            return ('done' if ok else 'idle'), info
        self.dig_progress += max(0.0, float(dt))
        if self.dig_progress >= need:
            ok, info = self._finish_dig(target)
            return ('done' if ok else 'idle'), info
        return 'digging', min(1.0, self.dig_progress / need)

    def dig(self):
        """**瞬时挖**（创造模式手感 / 自检脚本用）：挖掉准星指的方块。

        返回 `(ok, 掉落物名或方块名)`。生存模式走 `dig_dt()` 的累积路径，
        这个方法是它的"一步到位"等价物（`dig_dt(dig_time())`）。

        ⚠ 返回协议是 `(bool, 名字)`，**不是** `dig_dt` 的 `(状态, 进度)` ——
        两者刻意不同（一个答"成没成"，一个答"挖到哪了"），
        早期版本在这里返回了 `_finish_dig` 的原始元组，导致 `dig_dt` 的调用方
        拿到 `(True, 'dirt')` 却以为第一个元素是状态串（实测踩过）。
        """
        hit = self.raycast()
        if hit is None:
            return False, None
        return self._finish_dig(hit[0])

    def _finish_dig(self, target):
        """真正破坏一格：掉落 + 工具磨损 + 计数 + 标脏。"""
        x, y, z = target
        old = self.world.get(x, y, z)
        if old == B.AIR or not I.can_break(old):
            self.dig_target, self.dig_progress = None, 0.0
            return False, None
        if not self.world.set(x, y, z, B.AIR):
            return False, None
        self._mark_dirty(x, y, z)
        # Phase 2-C：挖穿池底/洞顶时**邻域的水要重新演化**（`disturb` 只加活跃格，
        # 演化在 `fluid_step`）。这是"挖开 ⇒ 排水 / 灌水"的触发点。
        self.fluid.disturb(self.world, x, y, z)
        # Phase 3：门是**两格一体**的（挖一半、另一半跟着掉），
        # 推出的活塞要**连臂一起**收掉，红石元件被挖掉则网络要重算。
        from . import redstone as RS
        other = B.door_other_half(old)
        if other is not None:
            up = old in (B.DOOR_UPPER, B.DOOR_OPEN_UPPER)
            y2 = y - 1 if up else y + 1
            if B.door_other_half(self.world.get(x, y2, z)) is not None \
                    and self.world.set(x, y2, z, B.AIR):
                self._mark_dirty(x, y2, z)
                self.redstone.mark(x, y2, z)
        elif RS.is_piston(old) and RS.piston_input_on(old):
            d = B.PISTON_DIR_OF[old]
            dx, dy, dz = B.PISTON_DIR_VEC[d]
            if self.world.get(x + dx, y + dy, z + dz) == B.PISTON_ARM \
                    and self.world.set(x + dx, y + dy, z + dz, B.AIR):
                self._mark_dirty(x + dx, y + dy, z + dz)
        self.redstone.mark(x, y, z)
        self.stats['dug'] += 1
        self.dig_target, self.dig_progress = None, 0.0

        tool = self.held_tool()
        dropped = R.drops_for(old, tool, seed_parts=(x, y, z, self.seed))
        label = I.name_of(dropped[0][0]) if dropped else B.name_of(old)
        if self.creative:
            # 创造模式：方块**本身**直接进背包（搭房子要的是方块，不是它的生存掉落物）。
            # ⚠ 标签要跟**实际给的东西**一致（先前标签取自生存掉落 ⇒ 挖石头进的是石头、
            #    日志却报 cobble，HUD 会骗人 —— TEST-SMITH 实测抓出）。
            it = R.as_item(old)
            if it is not None:
                self.give(it.id, 1)
                label = it.name
        else:
            for (iid, n) in dropped:
                self.spawn_drop(x + 0.5, y + 0.5, z + 0.5, iid, n)
            self.hunger = max(0.0, self.hunger - HUNGER_PER_DIG)
            self._use_tool(tool)
        return True, label

    def _use_tool(self, tool, n: int = 1):
        """扣工具耐久；扣到 0 就**断掉**（从背包移除）。返回是否断了。"""
        if tool is None:
            return False
        left = int(self.tool_durability.get(tool.id, tool.durability)) - int(n)
        if left <= 0:
            self.tool_durability.pop(tool.id, None)
            self.inventory.pop(tool.id, None)
            return True
        self.tool_durability[tool.id] = left
        return False

    # ---------------------------------------------------------------- 放
    def place(self):
        """在准星指的**相邻空位**放当前手持的方块。返回 `(ok, 坐标或 None)`。"""
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
            return False, None                     # 手持的不是方块（工具/材料）
        it = R.as_item(bid)
        if it is None:
            return False, None
        if not self.creative and self.inventory.get(it.id, 0) <= 0:
            return False, None
        # Phase 3：**多格方块与朝向在这里展开**（门占两格、活塞按视线定向）——
        # 空位 / "不许把自己封死"这两条判据对**每一格**都要过。
        cells = B.place_cells(bid, tx, ty, tz, self.look_dir())
        for (cx, cy, cz, _cb) in cells:
            if not (0 <= cx < self.size and 0 <= cy < self.height
                    and 0 <= cz < self.size):
                return False, None
            if self.world.get(cx, cy, cz) != B.AIR:
                return False, None                 # 门的上半格被挡住 ⇒ 整体不放下
            if self._would_trap_player(cx, cy, cz):
                return False, None
        placed = False
        for (cx, cy, cz, cb) in cells:
            if self.world.set(cx, cy, cz, cb):
                self._mark_dirty(cx, cy, cz)
                # Phase 2-C：在水里筑坝 ⇒ 挡住的水要重新演化（往上积水或干涸）
                self.fluid.disturb(self.world, cx, cy, cz)
                # Phase 3：放下红石元件 ⇒ 网络要重算（拉杆/中继器会立刻改状态）
                self.redstone.mark(cx, cy, cz)
                placed = True
        if placed:
            self.stats['placed'] += 1
            if not self.creative:
                self.take(it.id, 1)                # 门占两格，但**只消耗一件**
            return True, (tx, ty, tz)
        return False, None

    # ---------------------------------------------------------------- 交互
    def use(self):
        """右键对着**可交互方块**用一下。返回 `(ok, (方块名, 说明))`。

        交互对象（Phase 3）：拉杆（切换开/关）、按钮（按下，1 秒后自动回弹）、
        中继器（手动切换）、铁门（手动开关 —— 若门同时被红石控制，下一帧会被信号纠正）。

        没打到可交互方块 ⇒ 返回 `(False, None)`，调用方接着走 `place()`
        （demo 的右键就是"先试 use，不行再放方块"，与 MC 同手感）。
        """
        hit = self.raycast()
        if hit is None:
            return False, None
        (x, y, z), _n = hit
        b = self.world.get(x, y, z)
        name = B.name_of(b)
        if b in (B.LEVER_OFF, B.LEVER_ON):
            new = self.redstone.toggle_lever(x, y, z)
            if new is not None:
                return True, (name, '开' if new == B.LEVER_ON else '关')
        elif b in (B.BUTTON_OFF, B.BUTTON_ON):
            if self.redstone.press_button(x, y, z) is not None:
                return True, (name, '按下')
        elif b in B.REPEATER_DIR_OF:
            # 中继器右键 = **调档**（1~4 档 = 0.1/0.2/0.3/0.4 秒）。
            # 不提供"手动点亮"：亮灭是信号算出来的，手动切会和信号打架
            # （下一帧就被信号纠正回来，看着像"点了没反应"）。
            new = self.redstone.cycle_repeater_delay(x, y, z)
            if new is not None:
                return True, (name, f'{self.redstone.delay_label(new)}（延迟 '
                                    f'{B.repeater_delay(new):.1f}s）')
        elif B.door_other_half(b) is not None:
            opened = b in (B.DOOR_OPEN_LOWER, B.DOOR_OPEN_UPPER)
            if self.redstone.set_door(x, y, z, not opened):
                return True, (name, '关' if opened else '开')
        return False, None

    # ---------------------------------------------------------------- 背包
    def give(self, item_id: int, n: int = 1):
        """进背包（**物品 id**）。工具进包时初始化耐久。"""
        it = I.ITEMS.get(int(item_id))
        if it is None:
            raise KeyError(f'未知物品 id {item_id!r}')
        self.inventory[it.id] = int(self.inventory.get(it.id, 0)) + int(n)
        if it.is_tool and it.id not in self.tool_durability:
            self.tool_durability[it.id] = it.durability
        return it.id

    def give_item(self, name: str, n: int = 1):
        """按名字进背包（脚本/配方用；名字错会当场爆）。"""
        return self.give(I.item_by_name(name).id, n)

    def take(self, item_id: int, n: int = 1) -> bool:
        """从背包扣（不够则**一点不扣**并返回 False）。"""
        have = int(self.inventory.get(int(item_id), 0))
        if have < n:
            return False
        left = have - int(n)
        if left <= 0:
            self.inventory.pop(int(item_id), None)
            self.tool_durability.pop(int(item_id), None)
        else:
            self.inventory[int(item_id)] = left
        return True

    def have(self, name: str, n: int = 1) -> bool:
        """按名字查背包（配方判定用）。"""
        return int(self.inventory.get(I.item_by_name(name).id, 0)) >= int(n)

    def inventory_by_name(self) -> dict:
        """`{物品名: 数量}` —— 配方系统吃这个口径（不认 id）。"""
        out = {}
        for iid, n in self.inventory.items():
            if n > 0:
                out[I.name_of(iid)] = int(n)
        return out

    # ---------------------------------------------------------------- 掉落物
    def spawn_drop(self, x: float, y: float, z: float, item_id: int, n: int = 1):
        """在世界里放一个掉落物（生存模式挖方块的产物）。"""
        self.drops.append({'pos': [float(x), float(y), float(z)],
                           'item': int(item_id), 'n': int(n), 't': 0.0})
        return self.drops[-1]

    def pickup_nearby(self):
        """把玩家附近的掉落物收进背包，返回 `[(物品名, 数量)]`。"""
        picked = []
        keep = []
        px, py, pz = self.pos
        for d in self.drops:
            dx = d['pos'][0] - px
            dy = d['pos'][1] - (py + 0.9)
            dz = d['pos'][2] - pz
            if dx * dx + dy * dy + dz * dz <= DROP_PICKUP_R ** 2:
                self.give(d['item'], d['n'])
                self.stats['picked'] += int(d['n'])
                picked.append((I.name_of(d['item']), int(d['n'])))
            else:
                keep.append(d)
        self.drops = keep
        return picked

    def _update_drops(self, dt: float):
        """掉落物：简单下落（不接物理引擎）+ 超时清理。

        ⚠ 落地判据必须用 `floor(中心 y)` 与 `floor(中心 y) - 1`（TEST-SMITH 实测抓出）：
        先前写的是 `int(p[1] - 0.5)`，而 `int()` 是**截断**不是向下取整 ——
        掉落物中心在 20.9 时 `int(20.4) == 20`，查的是"它自己那一格"（空气），
        而地板在 19 ⇒ 判据**恒为假**，掉落物一路沉穿地板掉到 y=0，玩家再也捡不到。
        """
        alive = []
        for d in self.drops:
            d['t'] += dt
            if d['t'] > DROP_TTL:
                continue
            p = d['pos']
            cx, cz = int(math.floor(p[0])), int(math.floor(p[2]))
            here = B.is_solid(self.world.get(cx, int(math.floor(p[1])), cz))
            below = B.is_solid(self.world.get(cx, int(math.floor(p[1])) - 1, cz))
            if not (here or below):
                p[1] = max(0.0, p[1] - DROP_FALL_V * dt)
            alive.append(d)
        self.drops = alive

    # ---------------------------------------------------------------- 合成
    def craft(self, recipe_id: str):
        """按配方 id 合成（在背包上就地扣减）。返回 `(ok, 产出物品名或原因)`。"""
        try:
            rec = R.recipe_by_id(recipe_id)
        except KeyError as exc:
            return False, str(exc)
        if rec.kind != 'craft':
            return False, f'{recipe_id} 不是合成配方（是 {rec.kind}）'
        inv = self.inventory_by_name()
        if not R.craftable(rec, inv):
            return False, '材料不足'
        if not R.craft(rec, inv):
            return False, '材料不足（扣减阶段）'
        self._apply_inventory_names(inv)
        self.stats['crafted'] += 1
        return True, rec.output

    def _apply_inventory_names(self, inv_by_name: dict):
        """把"名字口径"的背包写回 id 口径（合成的收尾；工具顺带补耐久）。"""
        new = {}
        for name, n in inv_by_name.items():
            it = I.ITEMS_BY_NAME.get(name)
            if it is None:
                raise KeyError(f'配方产出了未知物品 {name!r}')
            if n > 0:
                new[it.id] = int(n)
        self.inventory = new
        # 清掉已不在包里的工具耐久
        for iid in list(self.tool_durability):
            if iid not in new:
                self.tool_durability.pop(iid, None)
        for iid in new:
            it = I.ITEMS.get(iid)
            if it is not None and it.is_tool and iid not in self.tool_durability:
                self.tool_durability[iid] = it.durability

    # ---------------------------------------------------------------- 熔炉
    def furnace_load(self, recipe_id: str):
        """给熔炉装上配方（**只扣料、不发货**）。返回 `(ok, 说明)`。

        ⚠ 这里必须用 `R.consume()` 而**不是** `R.craft()`：`craft()` 的语义含"加产出"，
        用它装料会让产物在**装炉那一刻**就进背包，烧完再给一次（一炉发货两次）。
        TEST-SMITH 实测抓出过这个 bug（5 条烧炼配方全中），这条注释就是那次的结论。
        """
        rec = R.recipe_by_id(recipe_id)
        if rec.kind != 'smelt':
            return False, f'{recipe_id} 不是烧炼配方'
        if self.furnace['recipe'] is not None:
            return False, '熔炉里还有东西'
        inv = self.inventory_by_name()
        if not R.craftable(rec, inv):
            return False, '材料不足（含燃料）'
        if not R.consume(rec, inv):              # 只扣输入；产出等 furnace_step
            return False, '材料不足（扣减阶段）'
        self._apply_inventory_names(inv)
        self.furnace['recipe'] = recipe_id
        self.furnace['cook_left'] = rec.time
        self.furnace['fuel_left'] = rec.time * 1.5      # 燃料给 1.5 倍时间（够一炉）
        return True, rec.output

    def furnace_step(self, dt: float):
        """推进熔炉（按累计时间，与帧率无关）。返回 `('idle'|'cooking'|'done', 产出名)`。"""
        st = self.furnace
        if st['recipe'] is None:
            return 'idle', None
        dt = max(0.0, float(dt))
        st['fuel_left'] = max(0.0, st['fuel_left'] - dt)
        if st['fuel_left'] <= 0.0:
            st['recipe'] = None
            return 'idle', None                     # 没柴了：炉子停（材料已扣，属正常损耗）
        st['cook_left'] -= dt
        if st['cook_left'] <= 0.0:
            rec = R.recipe_by_id(st['recipe'])
            self.give_item(rec.output, rec.count)
            self.stats['smelted'] += 1
            st['recipe'] = None
            return 'done', rec.output
        return 'cooking', None

    # ---------------------------------------------------------------- 生存
    def hurt(self, amount: float, cause: str = ''):
        """掉血（Phase 2 的生物也走这个入口 —— '受伤来源'只有这一处）。"""
        if self.state != 'playing' or amount <= 0:
            return self.health
        self.health = max(0.0, self.health - float(amount))
        self.stats['damage'] += float(amount)
        if self.health <= 0.0:
            self.state = 'dead'
            self.death_cause = cause or 'unknown'
            self.stats['deaths'] += 1
        return self.health

    def eat(self, slot_index: int | None = None):
        """吃手持（或指定格）的食物：回饥饿与血，消耗一个。返回 `(ok, 物品名)`。"""
        it = I.ITEMS.get(self.selected_item() if slot_index is None
                         else (self.hotbar[slot_index] if self.hotbar else 0))
        if it is None or it.kind != I.KIND_FOOD:
            return False, None
        if self.hunger >= self.max_hunger and it.heal <= 0:
            return False, 'already_full'
        if not self.take(it.id, 1):
            return False, 'none_left'
        self.hunger = min(self.max_hunger, self.hunger + it.food)
        if it.heal:
            self.health = min(self.max_health, self.health + it.heal)
        self.stats['eaten'] += 1
        return True, it.name

    def respawn(self):
        """死亡后重生：状态归位（**背包保留** —— 本版不做掉落惩罚，见设计稿 §五）。"""
        if self.state != 'dead':
            return False
        self.state = 'playing'
        self.health = float(self.max_health)
        self.hunger = float(self.max_hunger)
        self.saturation = float(START_SATURATION)
        self.death_cause = ''
        x, z = self.size // 2, self.size // 2
        self.pos = [float(x) + 0.5, float(self._spawn_y(x, z)), float(z) + 0.5]
        self.vel = [0.0, 0.0, 0.0]
        return True

    def _survival_step(self, dt: float, moved: float):
        """饥饿 / 回血 / 饿死 / 摔落伤害（**只在生存模式生效**）。"""
        if self.creative or self.state != 'playing':
            return
        # 走路消耗（先吃"饱食度"，它见底才吃饥饿）
        cost = moved * HUNGER_PER_METER
        if cost > 0:
            if self.saturation > 0:
                self.saturation = max(0.0, self.saturation - cost)
            else:
                self.hunger = max(0.0, self.hunger - cost)
        # 自然回血（饿过头不回血，这是 MC 的核心手感）
        if self.hunger >= REGEN_AT and self.health < self.max_health:
            self.health = min(self.max_health, self.health + REGEN_RATE * dt)
        # 饿死
        if self.hunger <= 0.0:
            self.hurt(STARVE_RATE * dt, 'starve')
        # 摔落：落地那一刻按落差结算（只在"刚落地"这一帧触发）
        if self.grounded and self._fall_from is not None:
            fall = self._fall_from - self.pos[1]
            if fall > FALL_SAFE:
                self.hurt((fall - FALL_SAFE) * FALL_DAMAGE_PER, 'fall')
            self._fall_from = None

    def _mark_dirty(self, x: int, y: int, z: int):
        """记下"哪些区块脏了"：改动格所在区块 + 贴在边界时相邻区块也要重建。

        （Phase 1 重构时被误删过一次 —— 症状是"一挖就 AttributeError"。
        它是网格重建的唯一入口，所以有单测直接盯着它。）

        Phase 2-A 起它**同时负责让光照失效**：改了方块 ⇒ 相关区块的光照缓存作废，
        下一次渲染按需重算（不在这里同步重算，避免"挖一下卡半秒"）。
        """
        self.revision += 1
        cx, cy, cz = x // CHUNK, y // CHUNK, z // CHUNK
        self.dirty_chunks.add((cx, cy, cz))
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1),
                           (0, 1, 0), (0, -1, 0)):
            nx, ny, nz = x + dx, y + dy, z + dz
            if (nx // CHUNK, ny // CHUNK, nz // CHUNK) != (cx, cy, cz):
                self.dirty_chunks.add((nx // CHUNK, ny // CHUNK, nz // CHUNK))
        # 光照：受影响的是"光可能走到的地方"（半径 MAX_LIGHT 的邻域），比网格范围大
        self.invalidate_light_near(x, y, z)

    def invalidate_light_near(self, x: int, y: int, z: int, radius: int = MAX_LIGHT):
        """把 (x,y,z) 附近的光照缓存标记为失效（不重算，只记账）。"""
        if not hasattr(self, '_lit'):
            return 0
        n = 0
        r = int(radius)
        for cx in range((x - r) >> 4, ((x + r) >> 4) + 1):
            for cy in range(max(0, (y - r) >> 4), ((y + r) >> 4) + 1):
                for cz in range((z - r) >> 4, ((z + r) >> 4) + 1):
                    if (cx, cy, cz) in self._lit:
                        self._lit.discard((cx, cy, cz))
                        n += 1
        return n

    def ensure_light(self, keys, budget: int | None = None, halo: int | None = None):
        """按需算光照（每帧最多 `budget` 个区块，避免掉帧）。返回这次算了几个。

        **为什么要缓存**：`relight_chunk` 实测 ~36ms（halo=4），一帧算 16 个就是半秒。
        所以只在渲染真正要建网格时才补算，且限流。
        """
        if budget is None:
            budget = LIGHT_BUDGET_PER_FRAME
        done = 0
        for key in keys:
            if done >= budget:
                break
            if key in self._lit:
                continue
            self.light.relight_chunk(key[0], key[1], key[2], halo=halo)
            self._lit.add(key)
            done += 1
        return done

    def light_at(self, x: int, y: int, z: int):
        """某格的最终亮度 `(组合值, 方块光, 天光)` —— 全按当前昼夜折算。"""
        df = self.day_factor()
        blk = self.light.block(x, y, z)
        sk = self.light.sky(x, y, z)
        return (int(round(max(blk, sk * df))), blk, sk)

    def weather_state(self) -> dict:
        """当前天气一行快照（`kind/name/intensity/light_scale`）。

        `weather='rain'` 配置口会**固定**天气（截图与判据要可复现，
        而自然天气是"每 90s 一段"的）。
        """
        if getattr(self, 'weather_kind', None):
            from .weather import describe_weather, weather_light_scale
            return {'kind': self.weather_kind,
                    'name': describe_weather(self.weather_kind),
                    'intensity': 1.0,
                    'light_scale': weather_light_scale(self.weather_kind, 1.0)}
        return self.weather.state_at(self.cycle.time,
                                     day_factor=self.cycle.sky()['day_factor'])

    def day_factor(self) -> float:
        """当前"天有多亮"（0..1）—— 光照与天空配色同源（见 `sun.py`）。

        Phase 2-C：**再乘一层天气**（雨天 ×0.72 / 雪天 ×0.80）。
        口径只有这一处，所以光照、天空色、生物自燃判据看到的都是同一个值
        —— 不会出现"天还亮着但地面已经按雨天暗下来了"这种分裂。
        """
        base = self.cycle.sky()['day_factor']
        w = self.weather_state()
        return base * w['light_scale']

    def face_light(self, x: int, y: int, z: int, nx: int, ny: int, nz: int) -> int:
        """某个面外侧那格的亮度（网格顶点色用它上色）。"""
        return self.light.face_light(x, y, z, nx, ny, nz, self.day_factor())

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
        # ⚠ 昼夜只在这里推进（内核**不读系统时钟**）⇒ 同一条时间线可回放、可对拍
        self.cycle.advance(dt)
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
            before = list(self.pos)
            self.pos[0] += self.vel[0] * dt
            self.pos[2] += self.vel[2] * dt
            self.pos[1] += self.vel[1] * dt
            self._clamp_bounds()
            self._post_step(dt, before)
            return

        self.vel[0] = wish_x * speed
        self.vel[2] = wish_z * speed
        if jump and self.grounded:
            self.vel[1] = JUMP_V
            self.grounded = False
        self.vel[1] = max(-TERMINAL_V, self.vel[1] - GRAVITY * dt)

        before = list(self.pos)
        was_grounded = self.grounded
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
        # 离地那一刻记高度（摔落伤害的判据：只算"这一次离地到落地"的落差）
        if was_grounded and not self.grounded and self._fall_from is None:
            self._fall_from = before[1]
        self._post_step(dt, before)

    def _post_step(self, dt: float, before):
        """一帧收尾：位移统计 → 生存结算 → 掉落物 → 拾取 → 熔炉 → 生物 → 水流。

        顺序有讲究：**先生存结算再拾取**（这一帧饿死就不该再捡东西），
        生物放最后（它会通过 `hurt` 反过来影响玩家血量，所以要在玩家结算之后），
        **水流放最后**：它改的是方块，而 `_mark_dirty` 必须在网格重建之前发生
        （否则水会"改了但网格不更新"，看着像渲染丢了水）。
        """
        moved = math.dist(self.pos, before) if hasattr(math, 'dist') else (
            sum((a - b) ** 2 for a, b in zip(self.pos, before)) ** 0.5)
        self._survival_step(dt, 0.0 if self.flying else moved)
        self._update_drops(dt)
        self.pickup_nearby()
        self.furnace_step(dt)
        self.update_mobs(dt)
        self.fluid_step(dt)
        # Phase 3：红石（按钮回弹 + 脏网络重算；预算与光照同思路，防掉帧）
        self.redstone.step(dt, budget=REDSTONE_BUDGET_PER_FRAME)

    # ============================================================== 水流
    #: 每帧最多处理多少水格（**防卡顿的硬预算**：挖开一个湖可能瞬间激活上万格）
    FLUID_BUDGET = 2048
    #: 水流 tick 的间隔（秒）。水不需要每帧都算 —— 0.05s 一次足够，
    #: 而且**与帧率无关**（30/60/120Hz 在同一 dt 下走过同样次数）。
    FLUID_INTERVAL = 0.05

    def fluid_step(self, dt: float = 1.0 / 60.0) -> int:
        """按固定间隔推进一步水流（dt 只用于累加计时）。返回本 tick 灌注的格数。

        ⚠ 间隔到点就把累加器**清零**（不补齐余数）—— 灌注是幂等的，
        漏掉一帧不会留下"永远差一点"的半格状态。
        """
        self._fluid_t = self._fluid_t + float(dt)
        if self._fluid_t < self.FLUID_INTERVAL:
            return 0
        self._fluid_t = 0.0
        return self.fluid.step(self.world, budget=self.FLUID_BUDGET)

    # ============================================================== 生物
    def mob_context(self) -> AI.MobContext:
        """给 AI 的世界视图（**刻意收窄**，见 `ai.MobContext` 的说明）。"""
        df = self.day_factor()
        return AI.MobContext(
            get=self.world.get,
            is_solid=B.is_solid,
            block_light=lambda x, y, z: self.light.block(x, y, z),
            day_factor=df,
            player_pos=lambda: (self.pos[0], self.pos[1], self.pos[2]),
            # ⚠ 必须接 `damage_player_from_mob` 而**不是**裸 `self.hurt`：
            # 早先接的是 hurt，于是"生物打玩家"这条路跳过了统计计数与**击退**，
            # 症状是"玩家被打了但一点反馈都没有、`mob_stats['player_hits']` 恒为 0"
            # （守卫判定看起来全绿，因为它只查了血量）。
            hurt_player=self.damage_player_from_mob,
            size=self.size,
            height=self.height,
        )

    def update_mobs(self, dt: float):
        """推进所有生物 + 清理 + 周期性刷怪。返回这次移除的数量。"""
        if not self.mobs and not getattr(self, 'mob_enabled', True):
            return 0                        # 没有生物且不开自动刷怪 ⇒ 没什么可做
        ctx = self.mob_context()
        keep = []
        for mob in self.mobs:
            AI.step_mob(ctx, mob, dt)
            if not mob.alive or mob.pos[1] < -4.0:
                self._kill_mob(mob, drops=True)
                continue
            if mob.dist_to(self.pos[0], self.pos[2]) > AI.DESPAWN_DIST:
                self.mob_stats['despawned'] += 1
                continue
            # 敌对生物的"白天自燃"：**只在露天**（头顶有天光）时发生 ——
            # 这与"洞里白天也安全"的直觉一致，也让玩家能用"挖洞躲"来应对
            if mob.kind.hostile and not self.cycle.is_night() and mob.age > 1.0:
                if self.light.sky(int(mob.pos[0]), min(self.height - 1,
                                                       int(mob.pos[1]) + 1),
                                  int(mob.pos[2])) >= 12:
                    mob.health -= 6.0 * dt
                    if not mob.alive:
                        self._kill_mob(mob, drops=False)     # 烧死不掉落
                        continue
            keep.append(mob)
        self.mobs = keep
        self._mob_t += dt
        if self._mob_t >= MOB_SPAWN_INTERVAL:
            self._mob_t = 0.0
            self._try_spawn_mobs()
        return 0

    def _kill_mob(self, mob, drops: bool = True):
        """生物死亡：掉落走**与方块同一条路径**（`spawn_drop`）。"""
        self.mob_stats['killed'] += 1
        if drops:
            for (name, lo, hi) in mob.kind.drops:
                n = lo if hi <= lo else lo + int(self._mob_rng.random() * (hi - lo + 1))
                if n > 0:
                    self.spawn_drop(mob.pos[0], mob.pos[1] + 0.4, mob.pos[2],
                                    I.item_by_name(name).id, n)

    def hit_mob(self, mob, amount: float = 4.0) -> bool:
        """玩家打生物（左键）。返回是否**致死**。"""
        dead = mob.hurt(amount, 'player')
        self.mob_stats['mob_hits'] += 1
        if dead:
            self._kill_mob(mob, drops=True)
            if mob in self.mobs:
                self.mobs.remove(mob)
        return dead

    def attack(self):
        """朝准星方向上最近的生物挥一下（demo 的左键在没有方块可挖时调它）。

        判据：生物中心到**视线**的距离 < 生物半宽 + 一点余量，
        且**视线前方没有方块挡住**（与挖方块同一套路：`raycast` 先问到墙，
        这一下就什么都不会发生 —— 墙后的生物打不到）。
        """
        eye = self.eye_pos()
        dx, dy, dz = self.look_dir()
        best, best_t = None, 4.0
        for mob in self.mobs:
            if not mob.alive:
                continue
            vx = mob.pos[0] - eye[0]
            vy = mob.pos[1] + mob.kind.height * 0.5 - eye[1]
            vz = mob.pos[2] - eye[2]
            t = vx * dx + vy * dy + vz * dz                 # 投影到视线
            if not (0.0 < t < best_t):
                continue
            py, pz = vx - dx * t, vz - dz * t
            perp = math.sqrt(py * py + pz * pz + (vy - dy * t) ** 2)
            if perp <= mob.kind.width * 0.75 + 0.25:
                best, best_t = mob, t
        if best is None:
            return None
        # 墙后打不到：在这个生物之前 `raycast` 就问到方块 ⇒ 当没发生
        # （docstring 早就这么承诺，先前只写在文档里没实现 —— 隔墙抡人实测复现过）
        if self.raycast(max_dist=best_t - 1e-6) is not None:
            return None
        dead = self.hit_mob(best, 4.0)
        return (best.kind.name, dead)

    def damage_player_from_mob(self, amount: float, cause: str):
        """生物打玩家的入口（`ai.MobContext.hurt_player` 指向它）。

        除了掉血，还做一件 MC 的手感：**击退**（否则玩家站着不动就永远不会被打死，
        因为生物贴上来后一直打、玩家却毫无反馈）。
        """
        self.mob_stats['player_hits'] += 1
        self.hurt(amount, cause)
        # 击退：沿"生物 → 玩家"方向推一下
        for mob in self.mobs[:8]:
            if mob.dist_to(self.pos[0], self.pos[2]) < 1.6:
                kx = self.pos[0] - mob.pos[0]
                kz = self.pos[2] - mob.pos[2]
                n = math.hypot(kx, kz) or 1.0
                self.vel[0] += kx / n * 3.0
                self.vel[2] += kz / n * 3.0
                self.vel[1] = max(self.vel[1], 2.5)
                break

    def spawn_mob(self, kind_name: str, x: float | None = None,
                  y: float | None = None, z: float | None = None):
        """**显式**放一只生物（脚本/单测/demo 用）。

        ⚠ 不受 `mobs=False` 限制：那个开关管的是**自动刷怪**（见 `_try_spawn_mobs`），
        而"手动放一只"是显式意图 —— 早先两者共用一个开关，于是
        `make_offline({'mobs': False})` 之后 `spawn_mob` 静默返回 None，
        测试拿到 None 才在下一行炸 `AttributeError`（实测踩过，报错点离根因很远）。
        """
        if len(self.mobs) >= MOB_CAP:
            return None
        kind = MB.mob_kind(kind_name)
        if x is None:
            spot = AI.find_spawn_spot(self.mob_context(), self._mob_rng.random,
                                     light_max=kind.spawn_light_max,
                                     night=self.cycle.is_night())
            if spot is None:
                return None
            x, y, z = spot
        elif y is None:
            # 只给了 x/z：用 `ground_below` 找"站得住"的脚底高度。
            # **不能用 `surface_at + 1`** —— 实测那会把生物埋进沙/水里
            # （`surface_at(38,32)` 返回 12 而沙堆到 y=13），症状是"生物一动不动"。
            gy = AI.ground_below(self.mob_context(), int(math.floor(x)),
                                 int(math.floor(z)), self.height - 1)
            if gy is None:
                return None
            y = float(gy)
        mob = MB.Mob(kind, x, y, z)
        self.mobs.append(mob)
        self.mob_stats['spawned'] += 1
        return mob

    def _try_spawn_mobs(self):
        """周期刷怪：**敌对的看光与昼夜，被动的看白昼**（判据在 `mobs.spawn_allowed`）。

        `mobs=False` 关掉的是**这一条**（自动刷怪），不是"能不能有生物"。
        """
        if not getattr(self, 'mob_enabled', True):
            return 0
        night = self.cycle.is_night()
        spawned = 0
        for kind in MB.all_kinds():
            if kind.village_only:
                continue        # 村民走**村庄通道**（下面那条），不在荒野随机刷
            # 被动生物夜里少刷（`night` 时 1/3 概率）
            if not kind.hostile and night and self._mob_rng.random() > 0.33:
                continue
            # 敌对生物白天只在暗处刷；夜里可以刷在露天
            if kind.hostile and not night and self._mob_rng.random() > 0.25:
                continue
            spot = AI.find_spawn_spot(self.mob_context(), self._mob_rng.random,
                                     light_max=kind.spawn_light_max, night=night)
            if spot is None:
                continue
            ix, iy, iz = int(spot[0]), int(spot[1]), int(spot[2])
            bl = self.light.block(ix, iy, iz)
            sky = int(round(self.light.sky(ix, iy, iz) * self.day_factor()))
            if not MB.spawn_allowed(kind, bl, sky, night):
                continue
            mob = self.spawn_mob(kind.name, *spot)
            if mob is not None:
                spawned += 1
            if spawned >= 2:
                break
        # Phase 2-C：**村庄通道**（每次都试一次；村里没人就补一个）
        spawned += self._try_spawn_villager()
        return spawned

    def _try_spawn_villager(self) -> int:
        """在村庄范围内刷一个村民（返回 0/1）。

        为什么村民要独立通道：**"村庄有人住"这件事不该由荒野刷怪规则决定** ——
        它不看光照、不看昼夜（村里白天夜里都有人），只看"这里是不是村庄"。
        村外永远不会刷出村民（`MobKind.village_only` 让荒野那条路跳过它）。

        落脚判据：站在**村庄地基高度附近**（±3 格，避免刷进村下面的洞）且
        **头顶 3 格净空**（人形高 5 体素，2 格净空会卡进屋顶/树冠）。
        """
        villages = self.world.villages
        if not villages or len(self.mobs) >= MOB_CAP:
            return 0
        # 人口上限（**每村**）：不设限的话村民会以"每 4 秒一只"的速度刷满 MOB_CAP，
        # 把其他生物的名额全占了，而且村里挤成一片（实测 30 次刷怪 ⇒ 30 只村民）。
        pop_cap = len(villages) * VILLAGE_POP
        if sum(1 for m in self.mobs if m.kind.name == 'villager') >= pop_cap:
            return 0
        ctx = self.mob_context()
        vx, vy, vz = villages[int(self._mob_rng.random() * len(villages)) % len(villages)]
        span = VILLAGE_SPAWN_SPAN
        for _ in range(10):
            x = vx + int((self._mob_rng.random() * 2 - 1) * span)
            z = vz + int((self._mob_rng.random() * 2 - 1) * span)
            if not (1 <= x < self.size - 1 and 1 <= z < self.size - 1):
                continue
            gy = AI.ground_below(ctx, x, z, min(self.height - 2, vy + 5))
            if gy is None or not (vy - 3 <= gy <= vy + 3):
                continue
            if any(self.world.get(x, gy + dy, z) != B.AIR for dy in (1, 2, 3)):
                continue
            return 1 if self.spawn_mob('villager', x + 0.5, float(gy), z + 0.5) else 0
        return 0

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
        # `hold_dig`：按住左键 —— 每帧推进挖掘进度（**和真人按住一样走 dig_dt**）
        if getattr(self, '_auto_hold', False):
            kind, info = self.dig_dt(dt)
            if kind == 'done':
                self._auto_log.append(('dig_done', True, info))
                self._auto_hold = False
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
        elif kind == 'hold_dig':
            # 生存模式：按住左键（每帧 dig_dt 推进）—— 与真人操作同一条代码路径
            self._auto_move = (0.0, 0.0)
            self._auto_hold = True
        elif kind == 'select':
            self.select(int(arg))
        elif kind == 'select_item':
            # 按**物品名**选 hotbar（hotbar 里没有就临时塞进去 —— 脚本要能自足）
            iid = I.item_by_name(str(arg)).id
            if iid not in self.hotbar:
                self.hotbar[self.selected] = iid
            else:
                self.select(self.hotbar.index(iid))
            self._auto_log.append(('select_item', True, str(arg)))
        elif kind == 'give':
            # `arg` 可以是名字或 `(名字, 数量)`（脚本里两种写法都方便）
            if isinstance(arg, (tuple, list)):
                name, n = arg[0], int(arg[1])
            else:
                name, n = arg, 1
            self.give_item(str(name), n)
            self._auto_log.append(('give', True, f'{name}x{n}'))
        elif kind == 'place':
            ok, at = self.place()
            self._auto_log.append(('place', ok, at))
        elif kind == 'craft':
            ok, out = self.craft(str(arg))
            self._auto_log.append(('craft', ok, f'{arg}->{out}'))
        elif kind == 'smelt_load':
            ok, out = self.furnace_load(str(arg))
            self._auto_log.append(('smelt_load', ok, str(out)))
        elif kind == 'eat':
            ok, name = self.eat()
            self._auto_log.append(('eat', ok, name))
        elif kind == 'aim_down':
            self.pitch = -35.0
        elif kind == 'aim_up':
            self.pitch = 25.0
        elif kind == 'hurt':
            self.hurt(float(arg), 'scripted')
            self._auto_log.append(('hurt', True, arg))
        elif kind == 'respawn':
            self._auto_log.append(('respawn', self.respawn(), None))

    # ============================================================== 网格
    def _redstone_power_for_mesh(self, x: int, y: int, z: int):
        """给网格用：**红石线**返回它的信号强度（0..15），其他方块返回 None。

        只对红石线返回 —— 别的方块就算邻居有电也不该被染色
        （`_append_face` 里 None = 保持原色）。这样信号强度就成了**看得见的东西**：
        一条线的亮度会顺着衰减下去，一眼看出"通到哪一格为止"。
        """
        if self.world.get(x, y, z) != B.REDSTONE_WIRE:
            return None
        return self.redstone.power_at(x, y, z)

    def _redstone_cells_in(self, cx: int, cy: int, cz: int):
        """列出一个区块里的红石元件坐标（读档后要把它们排进重算队列）。"""
        from . import redstone as RS
        buf = self.world.chunks.get((cx, cy, cz))
        if buf is None:
            return
        x0, y0, z0 = cx * CHUNK, cy * CHUNK, cz * CHUNK
        for i, b in enumerate(buf):
            if RS.is_component(b):       # 含**灭的火把**（反相器）与关着的拉杆所属网络
                ly, lz, lx = i // 256, (i // 16) % 16, i % 16
                yield (x0 + lx, y0 + ly, z0 + lz)

    def chunk_meshes(self, *, only_dirty: bool = True, limit: int = 8,
                     ensure_light: bool = True):
        """建（或重建）区块网格 —— **纯数据，不碰 GL**，demo 负责上传。

        `only_dirty=True` 时只建"脏"区块（改动过或还没建过），每次最多 `limit` 个 ——
        交互时一帧建太多会卡顿，所以摊到多帧（与引擎侧 blockworld 的做法同源）。

        `ensure_light=True` 时**先补光照再建网格**（光照是顶点色的来源，
        没算就建网格会得到一片全亮或全黑 —— 这正是"看着差不多但其实是错的"那种 bug）。
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
        if ensure_light:
            # ⚠ 预算必须**跟这一帧要建的区块数一致**，否则会出现
            #    "网格建好了、光还没算" ⇒ 那些区块按"没算 = 0"渲染成**全黑**。
            #    实测踩过：光照预算 2/帧、网格预算 16/帧 ⇒ 只有 1/8 的区块有光，
            #    整片地形看着像夜里（而昼夜其实是正午）。
            #    现在按同一批 key 同步补算 —— 代价是这一帧贵一点，但**不会出错**。
            self.ensure_light([k for k in todo[:max(1, limit)]], budget=limit)
        built = []
        night = 1.0 - max(0.0, min(1.0, self.day_factor()))
        for key in todo[:max(1, limit)]:
            mb, st = build_chunk_mesh(self.world, *key,
                                      light_of=self.face_light, night=night,
                                      power_of=self._redstone_power_for_mesh)
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
        """完整存档：世界（种子 + 编辑增量）+ 玩家 + 背包/工具 + 生存状态 + 掉落物
        + 世界时刻。

        **一律按名字存**（方块名与物品名），这样将来重排编号不会读坏旧档；
        未知名字在读档时**响亮报错**（不静默丢格/丢物品）。
        """
        return {
            'version': SAVE_VERSION,
            'world': self.world.dump(),
            'player': {
                'pos': [float(v) for v in self.pos],
                'vel': [float(v) for v in self.vel],
                'yaw': float(self.yaw),
                'pitch': float(self.pitch),
                'flying': bool(self.flying),
                'selected': int(self.selected),
                'hotbar': [I.name_of(i) for i in self.hotbar],
                'inventory': {I.name_of(k): int(v)
                              for k, v in sorted(self.inventory.items()) if v},
                # 工具耐久：只存"还没满"的那些（与默认值相同的没必要写进去）
                'tools': {I.name_of(k): int(v) for k, v in sorted(self.tool_durability.items())
                          if I.ITEMS.get(k) and int(v) != I.ITEMS[k].durability},
                'health': float(self.health),
                'hunger': float(self.hunger),
                'saturation': float(self.saturation),
                'state': self.state,
                'death_cause': self.death_cause,
                'stats': dict(self.stats),
            },
            'drops': [{'pos': [float(c) for c in d['pos']], 'item': I.name_of(d['item']),
                       'n': int(d['n']), 't': float(d['t'])} for d in self.drops],
            'furnace': dict(self.furnace),
            # Phase 2-A：世界时刻（**光照本身不存** —— 它由方块与世界时钟完全决定，
            # 存了反而会出现"存档里的光照与方块不一致"这种不可自愈的脏数据）
            'day': self.cycle.dump(),
        }

    def load(self, data: dict):
        """读档（世界按存档的种子/尺寸重建，再重放增量与玩家状态）。"""
        ver = int(data.get('version', 0))
        if ver not in (1, 2, 3):
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
        # Phase 2-C：世界是**重建**的 ⇒ 水的源/水位全部作废，重新标记。
        # 读档后水会自己再流一遍收敛到同样状态（与"光源不进存档"同口径）。
        from . import fluid as FL
        self.fluid = FL.FluidSystem()
        self.fluid.mark_sources(self.world)
        #: 水流计时器（累加到 `FLUID_INTERVAL` 才跑一步）
        self._fluid_t = 0.0
        # 水本身不进存档（可由源重算），但**洞还在增量里** ⇒ 必须重灌一遍，
        # 否则读档回来洞是干的（实测：读档后水量 0）。
        self.fluid.repour_all(self.world)
        # Phase 3：红石同理 —— 信号不进存档 ⇒ 重建后必须把**每个元件排进重算队列**，
        # 否则读档回来"灯看着是亮的、信号场却是空的"，下一帧又把它算灭。
        from .redstone import PowerGrid
        self.redstone = PowerGrid(self.world, on_change=self._mark_dirty)
        for (cx, cy, cz) in list(self.world.chunks):
            for (ex, ey, ez) in self._redstone_cells_in(cx, cy, cz):
                self.redstone.mark(ex, ey, ez)
        p = data['player']
        self.pos = [float(v) for v in p['pos']]
        self.vel = [float(v) for v in p.get('vel', (0, 0, 0))]
        self.yaw = float(p.get('yaw', 0.0))
        self.pitch = float(p.get('pitch', 0.0))
        self.flying = bool(p.get('flying', False))
        # ⚠ 读档要能吃两种口径：v1 存的是**方块名**（Phase 0），v2 存的是**物品名**。
        # 两者同名（`grass` 既是方块名也是物品名），所以这里统一按物品名查；
        # 查不到就响亮报错（不静默丢物品）。
        def _item_id(name: str) -> int:
            if name in I.ITEMS_BY_NAME:
                return I.ITEMS_BY_NAME[name].id
            if name in B.BLOCK_NAMES:                  # 只在 v1 存档里可能出现
                it = R.as_item(B.BLOCK_NAMES[name].id)
                if it is not None:
                    return it.id
            raise ValueError(f'存档里有未知物品/方块名：{name!r}')
        self.hotbar = [_item_id(n) for n in p['hotbar']]
        self.selected = int(p.get('selected', 0)) % max(1, len(self.hotbar))
        self.inventory = {}
        for n, v in (p.get('inventory') or {}).items():
            if int(v) > 0:
                self.inventory[_item_id(n)] = int(v)
        self.tool_durability = {}
        for n, v in (p.get('tools') or {}).items():
            iid = _item_id(n)
            self.tool_durability[iid] = int(v)
        for iid in list(self.inventory):
            it = I.ITEMS.get(iid)
            if it is not None and it.is_tool and iid not in self.tool_durability:
                self.tool_durability[iid] = it.durability
        self.health = float(p.get('health', self.max_health))
        self.hunger = float(p.get('hunger', self.max_hunger))
        self.saturation = float(p.get('saturation', START_SATURATION))
        self.state = str(p.get('state', 'playing'))
        self.death_cause = str(p.get('death_cause', ''))
        self.stats = dict(p.get('stats') or {})
        for key in ('dug', 'placed', 'crafted', 'smelted', 'picked', 'eaten',
                    'deaths'):
            self.stats.setdefault(key, 0)
        self.stats.setdefault('damage', 0.0)
        self.drops = [{'pos': [float(c) for c in d['pos']],
                       'item': _item_id(d['item']), 'n': int(d['n']),
                       't': float(d.get('t', 0.0))}
                      for d in (data.get('drops') or [])]
        self.furnace = dict(data.get('furnace') or
                            {'fuel_left': 0.0, 'cook_left': 0.0, 'recipe': None})
        self.dig_target, self.dig_progress = None, 0.0
        self._fall_from = None
        # Phase 2-A：世界时刻按存档恢复；光照缓存整体作废（方块变了 ⇒ 光照必须重算）
        self.cycle.load(data.get('day') or {})
        self._lit = set()
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
        held = I.ITEMS.get(self.selected_item())
        return {
            'seed': self.seed, 'pos': tuple(round(v, 2) for v in self.pos),
            'yaw': round(self.yaw, 1), 'pitch': round(self.pitch, 1),
            'grounded': self.grounded, 'flying': self.flying,
            'slot': self.selected,
            # `holding` 保留"方块名"口径（Phase 0 的调用方按它取方块）；
            # 新增 `holding_item` / `durability` 供 Phase 1 的 UI 用。
            'holding': B.name_of(self.selected_block()),
            'holding_item': held.name if held else 'air',
            'durability': self.held_durability(),
            'health': round(float(self.health), 2),
            'hunger': round(float(self.hunger), 2),
            'state': self.state,
            'drops': len(self.drops),
            'furnace': self.furnace['recipe'],
            'dig': self.stats.get('dug', 0), 'placed': self.stats.get('placed', 0),
            'crafted': self.stats.get('crafted', 0),
            'smelted': self.stats.get('smelted', 0),
            'picked': self.stats.get('picked', 0),
            'blocks': w['blocks'], 'edits': w['edits'],
            'mesh_chunks': m['chunks'], 'faces': m['faces'],
            # --- Phase 2-A：时间与光照 ---
            'day': round(self.cycle.time, 1),
            'phase': round(self.cycle.sky()['phase'], 3),
            'day_factor': round(self.day_factor(), 3),
            'night': self.cycle.is_night(),
            'lit_chunks': len(getattr(self, '_lit', ())),
        }


#: 自动机脚本：`(时刻秒, 动作, 参数)`。**时间驱动 ⇒ 与帧率无关**。
#:
#: Phase 1 起这条脚本跑的是**完整生存循环**：给材料 → 合成工具 → 挖（按住左键）
#: → 烧炼 → 吃东西。前 8 秒的 Phase 0 段（走 / 挖 / 放）保持不变，
#: 老断言（`dug >= 2` 等）继续成立。
SCRIPT = (
    # --- Phase 0 段：走 / 挖 / 放（老断言靠它） ---
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
    # --- Phase 1 段：给材料 → 合成 → 挖 → 烧 → 吃 ---
    (8.20, 'stop', None),
    (8.40, 'give', ('log', 8)),          # 原木：8 根 ⇒ 32 木板（够做 2 把镐 + 木棍）
    (8.60, 'craft', 'planks_from_log'),  # 原木 → 木板 ×4
    (8.80, 'craft', 'sticks_from_planks'),   # 木板 → 木棍
    (9.00, 'craft', 'wooden_pickaxe'),   # 合成木镐
    (9.20, 'select_item', 'wooden_pickaxe'),
    (9.40, 'give', ('stone', 3)),
    (9.60, 'give', ('cobble', 3)),
    (9.80, 'craft', 'stone_pickaxe'),
    (10.00, 'select_item', 'stone_pickaxe'),
    (10.20, 'aim_down', None),
    (10.40, 'hold_dig', None),           # 按住左键（每帧 dig_dt 推进）
    (12.40, 'give', ('raw_iron', 2)),
    (12.60, 'give', ('coal', 2)),
    (12.80, 'smelt_load', 'iron_ingot'),   # 装炉
    (14.00, 'stop', None),
    (14.20, 'give', ('bread', 2)),
    (14.40, 'select_item', 'bread'),
    (14.60, 'eat', None),
    (14.80, 'hurt', 3.0),                # 受点伤（验证 hurt 入口）
    (15.00, 'stop', None),
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
