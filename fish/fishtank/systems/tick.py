"""TickSystem（priority=10）：每帧的"感知"阶段。

🔴 禁止 `from __future__ import annotations`（E6）。

它必须跑在引擎 `BrainSystem`(20) 之前，因为：
`BrainSystem.update()` 只调 `tree.tick()`，**不会把 dt 传给行为树**。
所以 dt / now / 当前坐标 / 鱼食位置这些行为树要用的输入，
只能由本系统提前写进每条鱼的黑板。

四件事：

1. 钳制帧时长，写 `WD_DT`（表现用）；
2. 固定步累加，写 `WD_STEP`（玩法用）并推进存档时间锚点 —— 见下方"时间锚点"；
3. 鱼食下沉与过期；
4. 计算同鱼种质心（群游用），逐条鱼刷新黑板。

时间锚点（准则 L2：收益永不丢失）
--------------------------------
`GameState.saved_at_utc` 的语义是"**玩法已模拟到的 UTC 秒**"，不是"上次写盘时间"。
在线每推进一个固定步就把它 +1 步；于是"现在 − 锚点"天然等于**尚未结算的时间**。
笔记本合盖 / 进程被挂起导致主循环卡住时，这个差值会变大，
:meth:`fishtank.game.FishTankGame.update` 会据此触发一次 `settle_offline` 补回来。
"""

from fishtank.constants import (
    BB_ATTRACT, BB_CFG, BB_DT, BB_FOOD_X, BB_FOOD_Y, BB_HAS_FOOD,
    BB_HAS_INTEREST, BB_HAS_SCHOOL, BB_HEADING, BB_INTEREST_X, BB_INTEREST_Y,
    BB_NOW, BB_NX, BB_NY, BB_RNG, BB_SCHOOL_X, BB_SCHOOL_Y,
    WD_AI_RNG, WD_BALANCE, WD_CFG, WD_DT, WD_NOW, WD_STATE, WD_STEP, WD_STEPS,
    WD_TURNS,
)
from fishtank.components import FishTag, FoodPellet, Transform
from fishtank.engine_bootstrap import BlackboardComponent, System

_MIN_STEP_SEC = 0.001
"""固定步长的下限，纯粹防止配置写 0 导致除零。"""

_STEP_EPS = 1e-9
"""固定步累加的浮点容差（秒）。

`accum += dt` 累加上千帧后会攒下 ~1e-12 量级的误差。
比如 15Hz 跑满 600 秒，累加结果是 599.999999999… 而不是 600，
取整就会**少算一个整步**（表现为少一次收益结算）。
加上 1e-9 容差再取整即可吸收这种误差：它远小于任何真实帧长，
不可能凭空多结算一步；而多减掉的那点余量会留在 accum 里下一帧自动补回，
所以既不丢时间也不重复计时。
"""


class TickSystem(System):
    """感知阶段：时间推进 + 鱼食 + 黑板灌数据。"""

    priority = 10

    def __init__(self, logger=None):
        """:param logger: 可选日志器。"""
        self._log = logger
        self.accum = 0.0
        """固定步累加器（秒）。跨帧保留小数余量，长期不丢时间。"""
        self.frames = 0
        self.sim_seconds = 0.0
        """本次会话累计推进的模拟秒数（诊断用）。"""

    # ── 主循环 ──

    def update(self, world, dt):
        """执行一帧感知。

        :param world: ECS World
        :param dt: 真实帧时长（秒）
        """
        bal = world.get_data(WD_BALANCE)
        state = world.get_data(WD_STATE)
        cfg = world.get_data(WD_CFG)
        if bal is None or state is None or cfg is None:
            return

        self.frames += 1
        dt = self._clamp_dt(bal, dt)
        world.set_data(WD_DT, dt)
        world.set_data(WD_TURNS, [])

        now = int(world.get_data(WD_NOW) or 0)

        # ① 固定步推进
        step_sec = self._advance_clock(world, bal, state, dt, now)

        # ② 鱼食下沉 / 过期（用真实 dt，属于表现层节奏）
        self._update_food(world, dt)

        # ③ 群游质心
        centers = self._school_centers(world)

        # ④ 逐条鱼刷新黑板
        ai_rng = world.get_data(WD_AI_RNG)
        interest = world.get_data("fishtank.interest")
        self._prime_blackboards(world, cfg, ai_rng, dt, now, centers, interest)
        return step_sec

    # ── 分步实现 ──

    def _clamp_dt(self, bal, dt):
        """钳制帧时长，避免调试断点后一帧跳几十秒。"""
        try:
            max_ft = float(bal.get("loop.max_frame_time", 0.25) or 0.25)
        except (TypeError, ValueError):
            max_ft = 0.25
        dt = float(dt)
        if dt < 0.0:
            return 0.0
        return dt if dt < max_ft else max_ft

    def _advance_clock(self, world, bal, state, dt, now):
        """把真实 dt 攒成整数个固定步，写 `WD_STEP` 并推进时间锚点。

        :returns: 本帧应推进的模拟秒数（0 表示这帧不推进玩法）
        """
        try:
            step_unit = float(bal.get("economy.online_step_sec", 1.0) or 1.0)
        except (TypeError, ValueError):
            step_unit = 1.0
        if step_unit < _MIN_STEP_SEC:
            step_unit = _MIN_STEP_SEC

        self.accum += dt
        n = int((self.accum + _STEP_EPS) / step_unit)
        if n > 0:
            self.accum -= n * step_unit
        step_sec = n * step_unit

        world.set_data(WD_STEPS, n)
        world.set_data(WD_STEP, step_sec)
        if n > 0:
            self.sim_seconds += step_sec
            # 锚点只前进，且绝不越过"现在"（时钟被回拨时保持不动，准则 L2）
            nxt = int(state.saved_at_utc) + int(step_sec)
            if now > 0:
                nxt = min(nxt, now)
            if nxt > int(state.saved_at_utc):
                state.saved_at_utc = nxt
        return step_sec

    def _update_food(self, world, dt):
        """鱼食下沉、寿命衰减、过期回收。"""
        expired = []
        for ent in world.each(FoodPellet):
            p = ent.get(FoodPellet)
            p.life -= dt
            if p.life <= 0.0:
                # 🔴 必须用 ent.id（int）而不是 ent.eid：
                # 匿名实体的 eid 是 None，World.remove_entity(None) 会静默失败，
                # 鱼食永远清不掉（life 一路跌成负数）。int 分支两张表都会清干净。
                expired.append(ent.id)
                continue
            p.y += p.sink_speed * dt
            if p.y > 1.0:
                p.y = 1.0
        for eid in expired:
            world.remove_entity(eid)

    def _school_centers(self, world):
        """按鱼种求归一化质心，供群游倾向使用。

        :returns: {species: (cx, cy)}
        """
        acc = {}
        for ent in world.each(FishTag, Transform):
            tag = ent.get(FishTag)
            tr = ent.get(Transform)
            slot = acc.get(tag.species)
            if slot is None:
                acc[tag.species] = [tr.x, tr.y, 1]
            else:
                slot[0] += tr.x
                slot[1] += tr.y
                slot[2] += 1
        return {k: (v[0] / v[2], v[1] / v[2]) for k, v in acc.items() if v[2] > 0}

    def _nearest_food(self, world, x, y, uid):
        """找离 (x, y) 最近的、未被别的鱼认领的鱼食。

        认领机制保证一颗鱼食只被一条鱼追（避免所有鱼挤成一团）。

        :returns: (found, fx, fy)
        """
        best = None
        best_d2 = 0.0
        for ent in world.each(FoodPellet):
            p = ent.get(FoodPellet)
            if p.claimed_by not in (-1, uid):
                continue
            dx = p.x - x
            dy = p.y - y
            d2 = dx * dx + dy * dy
            if best is None or d2 < best_d2:
                best = p
                best_d2 = d2
        if best is None:
            return False, 0.0, 0.0
        best.claimed_by = uid
        return True, best.x, best.y

    def _prime_blackboards(self, world, cfg, ai_rng, dt, now, centers, interest):
        """把这一帧的感知结果写进每条鱼的黑板。"""
        for ent in world.each(FishTag, Transform, BlackboardComponent):
            tag = ent.get(FishTag)
            tr = ent.get(Transform)
            bb = ent.get(BlackboardComponent).blackboard

            bb.set(BB_DT, dt)
            bb.set(BB_NOW, now)
            bb.set(BB_NX, tr.x)
            bb.set(BB_NY, tr.y)
            bb.set(BB_HEADING, tr.heading)
            bb.set(BB_CFG, cfg)
            if ai_rng is not None:
                bb.set(BB_RNG, ai_rng)

            has_food, fx, fy = self._nearest_food(world, tr.x, tr.y, tag.uid)
            bb.set(BB_HAS_FOOD, has_food)
            bb.set(BB_FOOD_X, fx)
            bb.set(BB_FOOD_Y, fy)

            if interest:
                bb.set(BB_HAS_INTEREST, True)
                bb.set(BB_INTEREST_X, float(interest[0]))
                bb.set(BB_INTEREST_Y, float(interest[1]))
            else:
                bb.set(BB_HAS_INTEREST, False)

            center = centers.get(tag.species)
            attract = float(bb.get(BB_ATTRACT, 0.0))
            if center is not None and attract > 0.0:
                bb.set(BB_HAS_SCHOOL, True)
                bb.set(BB_SCHOOL_X, center[0])
                bb.set(BB_SCHOOL_Y, center[1])
            else:
                bb.set(BB_HAS_SCHOOL, False)
