"""AutoSellSystem（priority=65）：玩法六阶段——自动卖出。

与 :func:`fishtank.offline.advance_step` 的第⑥阶段**同一个函数**：
   直接调 :func:`fishtank.offline.attempt_autosell`，
   不会写出第二份实现。

准则 L1（修正）：允许卖出以腾出空间——缸满时按"最老优先"卖出。
"""

from fishtank.constants import (
    WD_BALANCE, WD_BUS, WD_SPECIES, WD_STATE, WD_STEP, WD_AUTOSELL,
)
from fishtank.engine_bootstrap import System
from fishtank.events import FISH_SOLD
from fishtank.offline import attempt_autosell

_MAX_PER_FRAME = 4
"""单帧最多结算多少次自动卖出（防止卡帧刷空鱼缸）。"""


class AutoSellSystem(System):
    """定时自动卖出：缸满时出售最老的鱼。"""

    priority = 65

    def __init__(self, logger=None):
        """:param logger: 可选日志器。"""
        self._log = logger

    def update(self, world, dt):
        """执行一帧自动卖出判定。"""
        state = world.get_data(WD_STATE)
        bal = world.get_data(WD_BALANCE)
        species = world.get_data(WD_SPECIES)
        if state is None or bal is None or species is None:
            return
        step = float(world.get_data(WD_STEP, 0.0) or 0.0)
        if step <= 0.0:
            return

        interval = max(1, int(bal.get("autosell.check_interval_sec", 300) or 300))
        bus = world.get_data(WD_BUS)

        state.autosell_timer += step
        fired = 0
        while state.autosell_timer >= interval and fired < _MAX_PER_FRAME:
            state.autosell_timer -= interval
            fired += 1
            uid, sold_milli = attempt_autosell(state, bal, species)
            if uid is None:
                continue

            # 写入待移除队列（由 game.py 在 world.update() 后处理实体销毁）
            queue = world.get_data(WD_AUTOSELL)
            if queue is None:
                queue = []
                world.set_data(WD_AUTOSELL, queue)
            queue.append(uid)

            if bus is not None:
                bus.emit(FISH_SOLD, {"uid": uid, "sold_milli": sold_milli})
