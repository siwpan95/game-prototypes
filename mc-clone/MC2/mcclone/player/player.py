# -*- coding: utf-8 -*-
"""player — 玩家实体与物理（AABB 碰撞 / 重力 / 跳跃 / 挖放）。

提供：
  - Player(AABB2D): 用浮点脚底坐标做物理，碰撞用 floor 取整；
                    水平移动、跳跃、重力下落、与 solid 方块扫掠碰撞；
                    try_break / try_place；快捷栏 held_id / hotbar；事件发射。

坐标约定（继承地基，§7.8）：
  - AABB2D.min_x/min_y 运行时存浮点脚底（左下）坐标；
    max_x = min_x + width_f，max_y = min_y + height_f（每帧派生）。
  - 方块 (x,y) 占用连续单元 [x, x+1) × [y, y+1)。

本模块无 pygame 依赖，可在 headless 下断言（T-M1-02 / T-M1-05 / T-M1-11）。
"""

from __future__ import annotations

import math

from mcclone.core.geometry import AABB2D
from mcclone.core.block_registry import (
    AIR, STONE, DIRT, GRASS, SAND, WATER, BlockRegistry,
)
from mcclone.core.block_world import BlockWorld
from mcclone.core.event_bus import EventTypes
from mcclone.player.inventory import Inventory


# 物理常数（架构 §7.12；目标跳跃 3–4 格，见下方说明）。
# 说明：§7.12 给出的 JUMP_V≈9 在 GRAVITY=30 下仅能跳约 1.35 格，
# 不满足验收「跳跃约 3–4 格」。为达成可测量验收，将 JUMP_V 调到 15.0
# （h ≈ v²/2g = 225/60 ≈ 3.75 格），其余常数沿用推荐值。M1-R2 验收优先。
GRAVITY: float = 30.0       # tile/s^2
MOVE_SPEED: float = 6.0     # tile/s
JUMP_V: float = 15.0        # tile/s（初速度，调参使跳跃 ≈ 3–4 格）
MAX_FALL: float = 40.0      # tile/s（下落速度上限，防穿透）

# 生存数值默认值（M2-R1；与 main_gui / SurvivalConfig 保持一致）。
# 说明：Player 不直接依赖 main_gui（避免循环导入），此处保留同源默认值。
MAX_HP: float = 20.0         # 生命上限
MAX_HUNGER: float = 20.0     # 饥饿上限
STACK_MAX: int = Inventory.STACK_MAX  # 单栈上限（=64）


class Player(AABB2D):
    """玩家实体（继承 geometry.AABB2D）。

    AABB2D 的 min_x/min_y 在本类运行时存浮点脚底坐标的派生整数；
    _fx/_fy 为权威浮点脚底坐标。所有世界 get/set 用 z=0（M1 depth=1）。
    """

    def __init__(self, x: float, y: float, registry: BlockRegistry) -> None:
        # 浮点脚底坐标（左下角）为权威状态。
        self._fx = float(x)
        self._fy = float(y)
        self.registry = registry
        # 尺寸（tile）：宽 < 1 格，高跨 2 格。
        self.width_f: float = 0.8
        self.height_f: float = 1.8
        # 物理状态
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.on_ground: bool = False
        self.facing: int = 1  # 1=右, -1=左
        # 快捷栏（默认：stone/dirt/grass/sand/water/air）
        self.hotbar: list[int] = [STONE, DIRT, GRASS, SAND, WATER, AIR]
        self.selected_slot: int = 0
        self.held_id: int = self.hotbar[self.selected_slot]
        # 事件总线（None 时静默）
        self.event_bus = None

        # ── 生存状态（M2-R1 / T-M2-04）──
        self.max_hp: float = MAX_HP
        self.hp: float = self.max_hp
        self.max_hunger: float = MAX_HUNGER
        self.hunger: float = self.max_hunger
        self.alive: bool = True

        # ── 背包（M2-R2）──
        # 前 hotbar_size(6) 槽预填 STACK_MAX 个可放置方块；AIR 槽为空（None）。
        # 预填保证 M1 放置测试（test_try_place_basic 等）仍成功。
        self.inventory = Inventory()
        for _i, _bid in enumerate(self.hotbar):
            if _bid != AIR:
                self.inventory._items[_i] = (_bid, Inventory.STACK_MAX)
            else:
                self.inventory._items[_i] = None
        # 上一帧位置（用于移动事件去抖）
        self._last_x: float = self._fx
        self._last_y: float = self._fy
        # 初始化整数包围盒
        super().__init__(min_x=0, min_y=0, max_x=1, max_y=2)
        self._sync_aabb()

    # ── 浮点脚底坐标访问器（供渲染器/相机/测试读取）──
    @property
    def fx(self) -> float:
        """脚底浮点 x。"""
        return self._fx

    @property
    def fy(self) -> float:
        """脚底浮点 y。"""
        return self._fy

    # ── 坐标同步 ──
    def _sync_aabb(self) -> None:
        """由浮点脚底坐标派生整数包围盒（供几何/渲染查询）。"""
        self.min_x = int(math.floor(self._fx))
        self.min_y = int(math.floor(self._fy))
        self.max_x = self.min_x + 1
        self.max_y = int(math.floor(self._fy + self.height_f))

    # ── 方块查询 ──
    def _is_solid(self, world: BlockWorld, x: int, y: int) -> bool:
        """查询某格是否为 solid 方块（未知 id 按 solid 保守处理）。"""
        bid = world.get(x, y, 0)
        if bid == AIR:
            return False
        try:
            return self.registry.get(bid).solid
        except KeyError:
            return True

    def _occupied_cells(self) -> list[tuple[int, int]]:
        """返回玩家 AABB 当前重叠的整数格列表（浮点精确）。"""
        x0 = int(math.floor(self._fx))
        x1 = int(math.floor(self._fx + self.width_f - 1e-9))
        y0 = int(math.floor(self._fy))
        y1 = int(math.floor(self._fy + self.height_f - 1e-9))
        return [(x, y) for x in range(x0, x1 + 1)
                for y in range(y0, y1 + 1)]

    def _overlaps_cell(self, tx: int, ty: int) -> bool:
        """判断玩家 AABB 是否与方块单元 (tx,ty) 占据的单元重叠。"""
        px0, py0 = self._fx, self._fy
        px1, py1 = self._fx + self.width_f, self._fy + self.height_f
        bx0, by0 = float(tx), float(ty)
        bx1, by1 = float(tx + 1), float(ty + 1)
        return not (bx1 <= px0 or px1 <= bx0 or by1 <= py0 or py1 <= by0)

    def _is_floor_cell(self, tx: int, ty: int) -> bool:
        """判断 (tx,ty) 是否为玩家正下方且水平对齐的脚底支撑格（防穿地）。"""
        foot_cell_y = int(math.floor(self._fy))
        below = foot_cell_y - 1
        if ty != below:
            return False
        x0 = int(math.floor(self._fx))
        x1 = int(math.floor(self._fx + self.width_f))
        return x0 <= tx <= x1

    # ── 快捷栏 ──
    def select_slot(self, i: int) -> None:
        """切换到第 i 个快捷栏槽（越界忽略）；同步 inventory 与 held_id（M2）。"""
        if 0 <= i < len(self.hotbar):
            self.selected_slot = i
            self.inventory.select(i)               # 同步背包选中
            self.held_id = self.inventory.held_block()  # 空槽→AIR

    # ── 物理更新 ──
    def update(self, dt: float, world: BlockWorld, input) -> None:
        """固定步长物理更新：移动 / 跳跃 / 重力 / 分轴碰撞 / 事件。

        参数：
            dt: 固定时间步长（秒）
            world: 方块世界
            input: 输入源，需提供 left()/right()/jump_pressed() 语义方法
        """
        # 水平输入
        move = 0
        if input.left():
            move -= 1
        if input.right():
            move += 1
        self.vx = move * MOVE_SPEED
        if move < 0:
            self.facing = -1
        elif move > 0:
            self.facing = 1

        # 跳跃（本帧刚按下且着地）
        was_ground = self.on_ground
        if input.jump_pressed() and self.on_ground:
            self.vy = JUMP_V
            self.on_ground = False

        # 重力
        self.vy -= GRAVITY * dt
        if self.vy < -MAX_FALL:
            self.vy = -MAX_FALL

        # 分轴移动 + 扫掠碰撞
        self._move_x(world, dt)
        self._move_y(world, dt)

        # 世界水平边界钳制（防止走出世界）
        self._fx = max(0.0, min(self._fx, world.width - self.width_f))
        if self._fy < 0.0:
            self._fy = 0.0
            self.vy = 0.0
        self._sync_aabb()

        # 事件发射（M1 仅日志）
        if self.event_bus is not None:
            moved = (abs(self._fx - self._last_x) > 1e-6
                     or abs(self._fy - self._last_y) > 1e-6)
            if moved:
                self.event_bus.emit(EventTypes.PLAYER_MOVED,
                                    x=self._fx, y=self._fy, facing=self.facing)
            if self.on_ground and not was_ground:
                self.event_bus.emit(EventTypes.PLAYER_LANDED,
                                    x=self._fx, y=self._fy)
        self._last_x, self._last_y = self._fx, self._fy

    def _move_x(self, world: BlockWorld, dt: float) -> None:
        """水平移动 + 与 solid 方块扫掠碰撞（先 x 后 y）。"""
        self._fx += self.vx * dt
        if self.vx > 0:
            xr = int(math.floor(self._fx + self.width_f - 1e-6))
            y0 = int(math.floor(self._fy))
            y1 = int(math.floor(self._fy + self.height_f - 1e-6))
            for y in range(y0, y1 + 1):
                if self._is_solid(world, xr, y):
                    self._fx = xr - self.width_f
                    self.vx = 0
                    break
        elif self.vx < 0:
            xl = int(math.floor(self._fx))
            y0 = int(math.floor(self._fy))
            y1 = int(math.floor(self._fy + self.height_f - 1e-6))
            for y in range(y0, y1 + 1):
                if self._is_solid(world, xl, y):
                    self._fx = xl + 1
                    self.vx = 0
                    break

    def _move_y(self, world: BlockWorld, dt: float) -> None:
        """垂直移动 + 与 solid 方块扫掠碰撞（落地置 on_ground）。"""
        self._fy += self.vy * dt
        self.on_ground = False
        x0 = int(math.floor(self._fx))
        x1 = int(math.floor(self._fx + self.width_f - 1e-6))
        if self.vy < 0:
            yb = int(math.floor(self._fy))
            for x in range(x0, x1 + 1):
                if self._is_solid(world, x, yb):
                    self._fy = yb + 1
                    self.vy = 0
                    self.on_ground = True
                    break
        elif self.vy > 0:
            yt = int(math.floor(self._fy + self.height_f - 1e-6))
            for x in range(x0, x1 + 1):
                if self._is_solid(world, x, yt):
                    self._fy = yt - self.height_f
                    self.vy = 0
                    break

    # ── 破坏 / 放置 ──
    def try_break(self, world: BlockWorld, tx: int, ty: int,
                   tz: int = 0) -> bool:
        """尝试破坏 (tx,ty,tz) 格为空气。

        保护：越界拒绝；已是空气拒绝；脚下支撑格（防穿地）拒绝；
        玩家占用格（防自埋）拒绝。成功发 BLOCK_BROKEN 事件。
        tz 默认 0（M1/M2 行为不变）；玩家实体仅在 z=0，故脚下/占用
        防护仅在 tz==0 生效（跨层编辑不触发）。
        """
        if not world.in_bounds(tx, ty, tz):
            return False
        if world.get(tx, ty, tz) == AIR:
            return False
        if tz == 0 and self.on_ground and self._is_floor_cell(tx, ty):
            return False  # 不挖脚下防穿地
        if tz == 0 and self._overlaps_cell(tx, ty):
            return False  # 不挖玩家占用格（防自埋）
        broken_id = world.get(tx, ty, tz)
        world.set(tx, ty, tz, AIR)
        self.inventory.add(broken_id, 1)          # 入包（M2-R2）
        if self.event_bus is not None:
            self.event_bus.emit(EventTypes.BLOCK_BROKEN,
                                x=tx, y=ty, z=tz, id=broken_id)
        return True

    def try_place(self, world: BlockWorld, tx: int, ty: int,
                  tz: int = 0) -> bool:
        """尝试在 (tx,ty,tz) 放置手持方块。

        保护：越界拒绝；空手（AIR）拒绝；目标须为空气或水（非 solid）；
        不可放在玩家占用格（防卡死）。成功消耗 1 个手持方块并发
        BLOCK_PLACED 事件（M2-R2）。tz 默认 0（向后兼容）。
        """
        if not world.in_bounds(tx, ty, tz):
            return False
        if self.held_id == AIR:
            return False  # 空手不可放置
        cur = world.get(tx, ty, tz)
        if cur not in (AIR, WATER):
            return False
        if tz == 0 and self._overlaps_cell(tx, ty):
            return False  # 不可放在玩家占用格（防卡死）
        # 消耗 1 个手持方块（hotbar 预填保证 M1 放置测试成功）
        if self.inventory.remove(self.held_id, 1) == 0:
            return False
        world.set(tx, ty, tz, self.held_id)
        if self.event_bus is not None:
            self.event_bus.emit(EventTypes.BLOCK_PLACED,
                                x=tx, y=ty, z=tz, id=self.held_id)
        return True

    # ── 生存薄封装（M2，可选；委托 SurvivalSystem 语义）──
    def take_damage(self, amount: float) -> None:
        """受到伤害（钳制 hp 到 [0, max_hp]）。"""
        if amount <= 0:
            return
        self.hp = max(0.0, min(self.max_hp, self.hp - amount))

    def heal(self, amount: float) -> None:
        """恢复生命（钳制 hp 到 [0, max_hp]）。"""
        if amount <= 0:
            return
        self.hp = max(0.0, min(self.max_hp, self.hp + amount))

    # ── 快照接口（M5 存档/读档，供 savegame.py 使用）──

    def to_snapshot(self) -> dict:
        """返回玩家的可序列化快照 dict。"""
        return {
            "fx": self._fx,
            "fy": self._fy,
            "vx": self.vx,
            "vy": self.vy,
            "on_ground": self.on_ground,
            "facing": self.facing,
            "max_hp": self.max_hp,
            "hp": self.hp,
            "max_hunger": self.max_hunger,
            "hunger": self.hunger,
            "alive": self.alive,
            "selected_slot": self.selected_slot,
            "hotbar": list(self.hotbar),
            "held_id": self.held_id,
            "inventory": [([int(it[0]), int(it[1])] if it is not None else None)
                          for it in self.inventory.as_list()],
        }

    @classmethod
    def from_snapshot(cls, d: dict, registry) -> "Player":
        """由快照 dict 重建 Player（仅走公开接口）。"""
        fx = float(d.get("fx", 0.0))
        fy = float(d.get("fy", 0.0))
        p = cls(fx, fy, registry)
        p.vx = float(d.get("vx", 0.0))
        p.vy = float(d.get("vy", 0.0))
        p.on_ground = bool(d.get("on_ground", False))
        p.facing = int(d.get("facing", 1))
        p.max_hp = float(d.get("max_hp", p.max_hp))
        p.hp = float(d.get("hp", p.max_hp))
        p.max_hunger = float(d.get("max_hunger", p.max_hunger))
        p.hunger = float(d.get("hunger", p.max_hunger))
        p.alive = bool(d.get("alive", True))
        if "hotbar" in d:
            p.hotbar = list(d["hotbar"])
        p.selected_slot = int(d.get("selected_slot", 0))
        p.inventory.load_list(d.get("inventory", []))
        if "held_id" in d:
            p.held_id = int(d["held_id"])
        else:
            _sel = p.selected_slot if 0 <= p.selected_slot < len(p.hotbar) else 0
            p.held_id = p.hotbar[_sel] if p.hotbar else 0
        p._sync_aabb()
        return p
