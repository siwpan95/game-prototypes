"""BreedingSystem（priority=60）：玩法五阶段之⑤——繁殖。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 与 :func:`fishtank.offline.advance_step` 的第⑤阶段**同一个函数**：
   直接调 :func:`fishtank.offline.attempt_breed`，
   连"随机数消耗顺序"这个双端契约都自动继承，不会写出第二份实现。

🔴 随机源必须是玩法流 `WD_RNG`（会随存档持久化），
   **不能**用表现流 `WD_AI_RNG`：帧率不同会打乱抽样序列，双端立刻发散。

准则 L1：只增不减 —— 繁殖只会往缸里加鱼，缸满了就静默跳过（不提示、不排队）。
"""

from fishtank.constants import (
    WD_BALANCE, WD_BUS, WD_RNG, WD_SPECIES, WD_STATE, WD_STEP, WD_NOW,
)
from fishtank.engine_bootstrap import System
from fishtank.events import CODEX_UNLOCKED, FISH_HATCHED
from fishtank.offline import attempt_breed

_MAX_PER_FRAME = 8
"""单帧最多结算多少次繁殖检查。防止时钟异常导致一帧刷出几百条鱼。
   多余的次数留在 `breed_timer` 里，下一帧继续 —— 一次都不会丢。"""


class BreedingSystem(System):
    """定时繁殖判定。"""

    priority = 60

    def __init__(self, logger=None):
        """:param logger: 可选日志器。"""
        self._log = logger
        self.born = []
        """本次会话新生鱼记录（供 HUD 展示，不入档）。"""
        self.checks = 0
        """累计繁殖判定次数（诊断用）。"""

    def update(self, world, dt):
        """执行一帧繁殖。"""
        state = world.get_data(WD_STATE)
        bal = world.get_data(WD_BALANCE)
        species = world.get_data(WD_SPECIES)
        rng = world.get_data(WD_RNG)
        if state is None or bal is None or species is None or rng is None:
            return
        step = float(world.get_data(WD_STEP, 0.0) or 0.0)
        if step <= 0.0:
            return

        interval = max(1, int(bal.get("breeding.check_interval_sec", 600) or 600))
        now = int(world.get_data(WD_NOW) or state.saved_at_utc)
        bus = world.get_data(WD_BUS)

        state.breed_timer += step
        fired = 0
        while state.breed_timer >= interval and fired < _MAX_PER_FRAME:
            state.breed_timer -= interval
            fired += 1
            self.checks += 1
            child, first = attempt_breed(state, bal, species, rng, now)
            if child is None:
                continue
            rec = {"uid": child.uid, "species": child.species,
                   "variant": bool(child.variant)}
            self.born.append(rec)
            state.bump_stat("bred", 1)
            if bus is not None:
                bus.emit(FISH_HATCHED, rec)
                if first:
                    bus.emit(CODEX_UNLOCKED, {"species": child.species})

        # 玩法随机流推进后要落回存档，读档才能接着抽
        state.rng_seed = rng.state()
