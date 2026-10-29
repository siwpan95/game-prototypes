"""d20.slots - 法术位系统服务（决策 A：独立 CP 购买环位）

D&D 5e SRD 法术位：每环有上限（4/3/3/3/3/2/2/1/1）、总量上限 22、单价 = 环位 CP；
购买某环需「奥术施法」有效等级 ≥ 2×环位-1（SRD 新环位出现于奇数施法者等级）。
挂到 ctx.slots。法术宏（combat）经 spend_slot 消耗环位；长休经 recover_all 恢复。
"""
from .context import Service
from .data import SPELL_SLOT_CAPS, SPELL_SLOT_TOTAL_CAP, SPELL_SLOT_COST, SPELL_RING_PREREQ


class SpellSlotsService(Service):
    """法术位购买/消耗/恢复能力。"""

    inject = ["skills"]

    SPELL_SLOT_CAPS = SPELL_SLOT_CAPS
    SPELL_SLOT_TOTAL_CAP = SPELL_SLOT_TOTAL_CAP

    # ---------- 购买 ----------
    def buy_slot(self, ring: int) -> tuple[bool, str]:
        """购买一个 ring 环法术位（1-9）。"""
        st = self.ctx.state
        if ring not in SPELL_SLOT_COST:
            return False, f"非法环位: {ring}（1-9）"
        prereq = SPELL_RING_PREREQ[ring]
        eff = self.ctx.skills.effective_skill_rank("奥术施法")
        if eff < prereq:
            return False, f"需要 奥术施法 有效等级 ≥ {prereq} 才能购买 {ring} 环法术位"
        cap = self.SPELL_SLOT_CAPS[ring - 1]
        owned = st.slots.get(ring, 0)
        if owned >= cap:
            return False, f"{ring} 环法术位已达上限 {cap}"
        if sum(st.slots.values()) >= self.SPELL_SLOT_TOTAL_CAP:
            return False, f"总法术位已达上限 {self.SPELL_SLOT_TOTAL_CAP}"
        cost = SPELL_SLOT_COST[ring]
        if st.cp < cost:
            return False, f"CP不足，需要 {cost} CP"
        st.cp -= cost
        st.slots[ring] = owned + 1
        st.purchases += 1
        self.ctx.emit("character/changed", "slots")
        return True, f"购买 {ring} 环法术位，消耗 {cost} CP（当前 {owned + 1}/{cap}）"

    # ---------- 消耗 / 查询 ----------
    def available(self, ring: int) -> int:
        """该环当前可用法术位数。"""
        st = self.ctx.state
        return st.slots.get(ring, 0) - st.slots_used.get(ring, 0)

    def spend_slot(self, ring: int) -> tuple[bool, str]:
        """消耗一个 ring 环法术位。"""
        if ring == 0:
            return True, "戏法不消耗法术位"
        if self.available(ring) <= 0:
            return False, f"无可用 {ring} 环法术位"
        st = self.ctx.state
        st.slots_used[ring] = st.slots_used.get(ring, 0) + 1
        self.ctx.emit("character/changed", "slots")
        return True, f"消耗 {ring} 环法术位（剩余 {self.available(ring)}）"

    def recover_all(self) -> None:
        """长休：恢复全部法术位。"""
        self.ctx.state.slots_used = {}

    def slot_table(self) -> list[tuple[int, int, int]]:
        """返回已拥有环位的 (环位, 已用, 拥有) 列表（升序）。"""
        st = self.ctx.state
        out = []
        for ring in sorted(st.slots):
            out.append((ring, st.slots_used.get(ring, 0), st.slots[ring]))
        return out
