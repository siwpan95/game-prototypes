"""GrowthSystem（priority=40）：玩法五阶段之①——成长。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 与 :func:`fishtank.offline.advance_step` 的第①阶段逐字同构：
   `age_sec += step` → `stage_of(age, cycle, thresholds)` → 跨阶段则记事件。
   任何改动都要同步改那边，否则在线/离线/双端结果发散。

准则 L1：鱼**只会长大**，绝不退化、绝不生病、绝不消失。
准则 L7：离线不打折 —— 成长阶段完全不看 `efficiency`。
"""

from fishtank.components import Appearance, FishTag, Growth, Transform
from fishtank.constants import WD_BALANCE, WD_BUS, WD_SPECIES, WD_STATE, WD_STEP
from fishtank.economy import stage_of, stage_scale
from fishtank.engine_bootstrap import System
from fishtank.events import FISH_GROWN


class GrowthSystem(System):
    """按固定步长推进年龄，并把成长结果同步到渲染组件。"""

    priority = 40

    def __init__(self, logger=None):
        """:param logger: 可选日志器。"""
        self._log = logger
        self.grown = []
        """本次会话内跨阶段的记录（供 HUD 展示，不入档）。"""

    def update(self, world, dt):
        """执行一帧成长。"""
        state = world.get_data(WD_STATE)
        bal = world.get_data(WD_BALANCE)
        species = world.get_data(WD_SPECIES)
        if state is None or bal is None or species is None:
            return
        step = float(world.get_data(WD_STEP, 0.0) or 0.0)

        if step > 0.0:
            self._advance(world, state, bal, species, step)
        # 组件同步每帧都做：读档 / 新生鱼 / 离线补算后也要立刻正确
        self._sync_components(world, state, bal, species)

    # ── 玩法推进 ──

    def _advance(self, world, state, bal, species, step):
        """年龄 +step，跨阶段则发事件。"""
        bus = world.get_data(WD_BUS)
        th = bal.thresholds()
        for f in state.fishes_sorted():
            f.age_sec += step
            sp = species.get(f.species)
            cycle = bal.growth_cycle_sec(sp.rarity if sp else "R1")
            new_stage = stage_of(f.age_sec, cycle, th)
            if new_stage != f.stage:
                rec = {"uid": f.uid, "species": f.species,
                       "from": f.stage, "to": new_stage}
                f.stage = new_stage
                self.grown.append(rec)
                if bus is not None:
                    bus.emit(FISH_GROWN, rec)

    # ── 组件同步 ──

    def _sync_components(self, world, state, bal, species):
        """把 FishState 的成长结果投影到 Growth / Transform.scale。"""
        scale_table = bal.stage_scale_table()
        for ent in world.each(FishTag, Growth):
            tag = ent.get(FishTag)
            g = ent.get(Growth)
            f = state.get_fish(tag.uid)
            if f is None:
                continue
            sp = species.get(f.species)
            g.age_sec = f.age_sec
            g.cycle_sec = float(bal.growth_cycle_sec(sp.rarity if sp else "R1"))
            g.stage = f.stage
            g.rarity = sp.rarity if sp else "R1"
            tr = ent.get(Transform)
            if tr is not None:
                tr.scale = stage_scale(f.stage, scale_table)
            app = ent.get(Appearance)
            if app is not None:
                app.variant = bool(f.variant)
