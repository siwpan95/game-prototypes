"""
Components - Pure data containers for the endless highway game (3D).

Each component is a dataclass that holds state; no logic.

坐标系约定（右手系，OpenGL 惯例，-z 为屏幕深处）：

    x  横向（左右转向）—— 公路沿 x=0 居中
    y  竖向（向上）    —— 地面 y=0
    z  纵深（前后）    —— 车辆固定在 z=0，世界朝 +z 移动（即"迎面驶来"）

「无尽」的实现在 z 上：装饰物从远端（far_z）生成，向 +z 行进，
越过镜头（near_z）后回收；里程随滚动累计。
"""

from dataclasses import dataclass

from ecs import Component


# ── 位置与运动 ──────────────────────────────────────────────────────

@dataclass
class Position(Component):
    """世界坐标（3D）。"""
    x: float
    y: float = 0.0
    z: float = 0.0


@dataclass
class Lateral(Component):
    """横向速度（世界单位/秒）—— 转向与漂移都作用在它上面。"""
    vx: float = 0.0


@dataclass
class KeyState:
    """键盘状态快照（由表现层从 pyglet 读出后注入，系统层不依赖 pyglet）。"""
    left: bool = False
    right: bool = False


# ── 玩法 ─────────────────────────────────────────────────────────────

@dataclass
class VehicleControl(Component):
    """玩家可控实体（左右转向）。"""
    pass


@dataclass
class Drift(Component):
    """随机左右推力（每次触发给横向速度一个冲量）。"""
    chance: float = 0.015
    min_push: float = 3.0
    max_push: float = 7.0


@dataclass
class Decoration(Component):
    """路旁装饰物实体（仙人掌 / 岩石 / 枯灌木 / 护栏）。"""
    deco_type: str = "cactus"   # "cactus" | "rock" | "dead_bush" | "guardrail"
    side: str = "left"          # "left" 或 "right"
    size: int = 20              # 原始尺寸（配置像素值，决定 3D 缩放）
    color: tuple = (0.2, 0.47, 0.2)   # 归一化基色（0~1）
    active: bool = True


# ── 全局状态 ─────────────────────────────────────────────────────────

@dataclass
class GameState(Component):
    """单例组件：跟踪全局游戏状态。"""
    alive: bool = True
    paused: bool = False
    drift_count: int = 0
    distance_km: float = 0.0
    dash_offset: float = 0.0     # 车道虚线滚动偏移（世界单位）
