"""
Systems - Logic processors that operate on entities with specific components.

本层**不依赖任何渲染/框架**（无 pygame / 无 pyglet）：只处理玩法状态。
3D 表现由 ``highway_scene.py`` 读取这些状态来生成。

坐标语义见 ``components.py`` 顶部：x 横向、y 竖向、z 纵深。
「无尽」= 装饰物沿 +z 朝镜头移动并循环回收，里程随滚动累计。
"""

import math
import random

from ecs import System
from ecs.components import (
    Decoration, Drift, GameState, KeyState, Lateral, Position, VehicleControl,
)


# ── 输入 ─────────────────────────────────────────────────────────────

class InputSystem(System):
    """读取键盘左右方向，给车辆加横向加速度（不是直接瞬移，手感更像开车）。"""

    def __init__(self, key_state: KeyState, steer_accel: float = 22.0):
        self.key_state = key_state
        self.steer_accel = float(steer_accel)

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or not state.alive:
            return

        direction = 0.0
        if self.key_state.left:
            direction -= 1.0
        if self.key_state.right:
            direction += 1.0
        if direction == 0.0:
            return

        for entity in world.get_entities_with(Position, VehicleControl, Lateral):
            lat = world.get_component(entity, Lateral)
            lat.vx += direction * self.steer_accel * dt


# ── 横向运动（积分 + 阻尼）──────────────────────────────────────────

class MotionSystem(System):
    """把横向速度积分进位置，并用指数阻尼让车自然回正/停稳。"""

    def __init__(self, drag: float = 3.2):
        self.drag = float(drag)

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or not state.alive:
            return

        decay = math.exp(-self.drag * dt)
        for entity in world.get_entities_with(Position, VehicleControl, Lateral):
            pos = world.get_component(entity, Position)
            lat = world.get_component(entity, Lateral)
            lat.vx *= decay
            pos.x += lat.vx * dt


# ── 漂移 ─────────────────────────────────────────────────────────────

class DriftSystem(System):
    """随机给车辆一个横向冲量（左右各半）。

    强度随里程增长：``intensity = 1 + distance_km * scale_per_km``，
    触发概率也随里程微增——跑得越远，路面越"滑"。
    """

    def __init__(self, scale_per_km: float = 0.3, world_scale: float = 12.0):
        self.scale_per_km = float(scale_per_km)
        self.world_scale = float(world_scale)

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or not state.alive:
            return

        intensity = 1.0 + state.distance_km * self.scale_per_km

        for entity in world.get_entities_with(Position, Lateral, Drift):
            drift = world.get_component(entity, Drift)
            # chance 原本是"每帧概率"，这里按 dt*60 折算成时间一致的触发率
            if random.random() < drift.chance * (1.0 + state.distance_km * 0.1) * dt * 60.0:
                direction = random.choice([-1, 1])
                push = direction * random.uniform(
                    drift.min_push * intensity,
                    drift.max_push * intensity,
                ) * self.world_scale
                lat = world.get_component(entity, Lateral)
                lat.vx += push
                state.drift_count += 1


# ── 碰撞 ─────────────────────────────────────────────────────────────

class CollisionSystem(System):
    """车辆撞上公路边缘 → 结束旅程（alive=False）。"""

    def __init__(self, road_half_width: float, car_half_width: float):
        self.road_half_width = float(road_half_width)
        self.car_half_width = float(car_half_width)

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or not state.alive:
            return

        limit = self.road_half_width - self.car_half_width
        for entity in world.get_entities_with(Position, VehicleControl):
            pos = world.get_component(entity, Position)
            if abs(pos.x) > limit:
                state.alive = False


# ── 滚动与里程 ───────────────────────────────────────────────────────

class ScrollSystem(System):
    """累计里程，并推进车道虚线的滚动偏移。"""

    def __init__(self, scroll_speed: float, distance_factor: float,
                 world_scroll: float, dash_period: float):
        self.scroll_speed = float(scroll_speed)
        self.distance_factor = float(distance_factor)
        self.world_scroll = float(world_scroll)
        self.dash_period = float(dash_period)

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or not state.alive:
            return

        # 保持原版"每帧 scroll_speed*distance_factor"的节奏（按 dt 折算）
        state.distance_km += self.scroll_speed * self.distance_factor * dt * 60.0
        if self.dash_period > 0.0:
            state.dash_offset = (state.dash_offset + self.world_scroll * dt) % self.dash_period


# ── 装饰物 ───────────────────────────────────────────────────────────

class DecorationSpawnSystem(System):
    """在公路两侧的远端生成装饰物（仙人掌 / 岩石 / 枯灌木 / 护栏）。"""

    def __init__(self, config: dict, road_half_width: float, far_z: float):
        self.config = config or {"spawn_interval": 80, "types": {}}
        self.road_half_width = float(road_half_width)
        self.far_z = float(far_z)
        self._timer = 0.0
        self._type_names = []
        self._type_weights = []
        for name, props in self.config.get("types", {}).items():
            self._type_names.append(name)
            self._type_weights.append(props.get("spawn_weight", 1))

    def _pick_type(self) -> str:
        if not self._type_names:
            return "cactus"
        return random.choices(self._type_names, weights=self._type_weights, k=1)[0]

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or not state.alive or not self._type_names:
            return

        # 原本是"每 N 帧一次"，这里折算成时间
        interval = self.config.get("spawn_interval", 80) / 60.0
        self._timer += dt
        if self._timer < interval:
            return
        self._timer = 0.0

        for _ in range(random.randint(1, 3)):
            deco_type = self._pick_type()
            side = random.choice(["left", "right"])
            type_cfg = self.config["types"][deco_type]

            # 落在公路外侧：离路肩 2~16 个单位
            offset = random.uniform(2.0, 16.0)
            x = side_sign(side) * (self.road_half_width + offset)

            min_sz = type_cfg.get("min_size", 18)
            max_sz = type_cfg.get("max_size", 28)
            size = random.randint(min_sz, max_sz)
            rgb = type_cfg.get("color", [150, 150, 150])
            color = tuple(c / 255.0 for c in rgb[:3])

            entity = world.create_entity()
            world.add_component(entity, Position(x=x, y=0.0, z=self.far_z + random.uniform(0.0, 20.0)))
            world.add_component(entity, Decoration(
                deco_type=deco_type, side=side, size=size, color=color,
            ))


class DecorationScrollSystem(System):
    """装饰物朝镜头（+z）移动，越过镜头后回收。"""

    def __init__(self, world_scroll: float, near_z: float):
        self.world_scroll = float(world_scroll)
        self.near_z = float(near_z)

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or not state.alive:
            return

        to_remove = []
        for entity in world.get_entities_with(Position, Decoration):
            pos = world.get_component(entity, Position)
            deco = world.get_component(entity, Decoration)
            if not deco.active:
                continue
            pos.z += self.world_scroll * dt
            if pos.z > self.near_z:
                to_remove.append(entity)

        for entity in to_remove:
            world.remove_entity(entity)


def side_sign(side: str) -> float:
    """'left' → -1，'right' → +1。"""
    return -1.0 if side == "left" else 1.0
