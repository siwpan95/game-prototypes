"""ECS 系统包。

优先级即执行顺序（`allin_engine.core.ecs.World` 按 `priority` 升序调度）::

    10  TickSystem          感知：钳 dt、推固定步、鱼食下沉、给每条鱼的黑板喂数据
    20  BrainSystem         （引擎自带）驱动每条鱼的行为树
    30  MovementSystem      决策 → 位移：转向、积分、边界、掉头、摆尾相位
    40  GrowthSystem        玩法①成长
    45  WaterSystem         玩法②水质
    47  AutoFeederSystem    玩法③饱食 + 自动投食 + 吃掉鱼食
    50  IncomeSystem        玩法④收益（全流程唯一一次取整）
    60  BreedingSystem      玩法⑤繁殖
    65  AutoSellSystem      玩法⑥自动卖出（缸满时出售最老的鱼）
    70  ParticleBridgeSystem 气泡特效（纯表现，不碰存档）

🔴 40 → 45 → 47 → 50 → 60 → 65 这个顺序**必须**与
:func:`fishtank.offline.advance_step` 的六阶段顺序逐字一致
（成长 → 水质 → 饱食 → 收益 → 繁殖 → 卖出），否则在线与离线会算出不同结果，
C++ 端也无从对齐。这是 `tests/test_systems.py::test_online_matches_advance_step`
守护的不变式。

⚠️ 与架构文档的唯一偏差：文档给 AutoFeederSystem 排的是 55（在 IncomeSystem 之后）。
   实现改为 47（在之前），理由见上 —— 饱食度是收益公式的输入，
   必须先于收益结算，否则收益会滞后一步，与 `advance_step` 对不上。
"""

from fishtank.systems.autosell import AutoSellSystem
from fishtank.systems.breeding import BreedingSystem
from fishtank.systems.feeder import AutoFeederSystem
from fishtank.systems.growth import GrowthSystem
from fishtank.systems.income import IncomeSystem
from fishtank.systems.movement import MovementSystem
from fishtank.systems.particles import ParticleBridgeSystem
from fishtank.systems.tick import TickSystem
from fishtank.systems.water import WaterSystem

__all__ = [
    "AutoSellSystem", "TickSystem", "MovementSystem", "GrowthSystem",
    "WaterSystem", "AutoFeederSystem", "IncomeSystem", "BreedingSystem",
    "ParticleBridgeSystem",
]
