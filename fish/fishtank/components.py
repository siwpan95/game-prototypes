"""ECS 组件定义。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 组件只放**运行期表现数据**（位置、朝向、动画相位…）；
   一切需要持久化的玩法数据都在 :class:`fishtank.state.GameState` 里，
   组件通过 `uid` 反查。这样"存档 = 唯一真相"，ECS 只是它的一层投影。

引擎约定（`allin_engine.core.ecs`）：组件继承 `Component`（ABC），
推荐用 `@dataclass` 声明。
"""

from dataclasses import dataclass, field

from fishtank.constants import AI_WANDER, STAGE_FRY
from fishtank.engine_bootstrap import Component


@dataclass
class FishTag(Component):
    """把一个 ECS 实体与存档里的 :class:`~fishtank.state.FishState` 关联起来。"""

    uid: int = 0
    species: str = ""


@dataclass
class Transform(Component):
    """归一化坐标下的位置与朝向。

    * `x`, `y` ∈ [0, 1]，与窗口像素尺寸解耦（双端共用同一套坐标）
    * `heading` 为 +1（朝右）或 -1（朝左）
    * `scale` 由成长阶段决定，由 GrowthSystem 写入
    """

    x: float = 0.5
    y: float = 0.5
    heading: float = 1.0
    scale: float = 1.0


@dataclass
class Motion(Component):
    """速度与目标点（行为树写、MovementSystem 读）。"""

    vx: float = 0.0
    vy: float = 0.0
    speed: float = 0.0
    base_speed: float = 0.0
    target_x: float = 0.5
    target_y: float = 0.5
    turn_rate: float = 2.2


@dataclass
class Growth(Component):
    """成长的运行期镜像（权威值在 FishState.age_sec）。"""

    age_sec: float = 0.0
    cycle_sec: float = 1.0
    stage: str = STAGE_FRY
    rarity: str = "R1"


@dataclass
class Appearance(Component):
    """绘制所需的静态外观参数（从鱼种定义烘焙而来，运行期不变）。"""

    species: str = ""
    rarity: str = "R1"
    body_color: str = "#FFFFFF"
    belly_color: str = "#FFFFFF"
    fin_color: str = "#FFFFFF"
    accent_color: str = "#FFFFFF"
    tail: str = "fork"
    body_len: float = 1.0
    """体长系数（fish_data.json 的 `shape.length`），画鱼的基准尺度。"""
    body_ratio: float = 0.4
    """体高/体长之比（fish_data.json 的 `shape.height_ratio`）。"""
    variant: bool = False
    gradient: int = 0
    outline: int = 0
    pattern: str = "none"
    glow: int = 0


@dataclass
class Animation(Component):
    """摆尾动画相位。"""

    tail_phase: float = 0.0
    tail_hz: float = 1.8
    tail_amp: float = 1.0
    blink_timer: float = 0.0


@dataclass
class AIState(Component):
    """行为树的输出快照，供渲染层与测试读取（避免直接读黑板）。"""

    state: str = AI_WANDER
    speed_mul: float = 1.0
    tail_mul: float = 1.0
    idle_left: float = 0.0
    retarget_left: float = 0.0


@dataclass
class Schooling(Component):
    """群游倾向（由鱼种 behavior.schooling 映射而来）。"""

    attract: float = 0.0
    radius: float = 0.3
    layer_y: float = 0.5
    layer_bias: float = 0.3


@dataclass
class FoodPellet(Component):
    """一颗鱼食（玩家点击投喂产生）。"""

    x: float = 0.5
    y: float = 0.1
    life: float = 12.0
    sink_speed: float = 0.05
    claimed_by: int = -1


@dataclass
class DecorItem(Component):
    """一件缸内装饰的渲染信息。"""

    decor_id: str = ""
    draw: str = ""
    x: float = 0.5
    y: float = 0.95
    scale: float = 1.0
    colors: list = field(default_factory=list)


@dataclass
class RenderCache(Component):
    """渲染差分用的缓存：上一帧提交给画布的图元。

    键是部件名（见 constants 的 PART_*），值是 canvas item id 或坐标元组。
    """

    items: dict = field(default_factory=dict)
    dirty: bool = True
    last_key: tuple = ()
