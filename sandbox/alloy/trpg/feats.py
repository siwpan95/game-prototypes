"""d20.feats - 专长系统服务（决策 B：8/12/15 CP 分档）

D&D 5e SRD 专长：带前置条件（属性/技能/施法能力），效果通过事件钩子（waterfall）挂到
derived 等计算链上——卸载本服务（web 端热卸载）后加成随之消失。
挂到 ctx.feats。含选择的专长以「名(选择)」形式入 state.feats。
"""
from .context import Service
from .data import FEATS_LIBRARY, ELEMENTS


class FeatsService(Service):
    """专长购买/查询能力。"""

    FEATS_LIBRARY = FEATS_LIBRARY
    ELEMENTS = ELEMENTS

    # ---------- 生命周期：注册 effect 钩子 ----------
    def apply(self) -> None:
        self._disposers = [
            # 强壮：最大 HP +2×活力等级
            self.ctx.on("derived/max_hp",
                        lambda hp, nxt: nxt(hp + 2 * self.ctx.state.skills.get("活力", 0))
                        if self.has_feat("强壮") else nxt(hp)),
            # 警觉：先攻 +5
            self.ctx.on("derived/initiative",
                        lambda b, nxt: nxt(b + 5) if self.has_feat("警觉") else nxt(b)),
        ]

    def dispose(self) -> None:
        for d in getattr(self, "_disposers", []):
            d()

    # ---------- 购买 ----------
    def add_feat(self, name: str, choice: str = "") -> tuple[bool, str]:
        """购买一项专长；choice 用于带选择的专长（运动员=属性名，元素亲和=元素名）。"""
        st = self.ctx.state
        if name not in self.FEATS_LIBRARY:
            return False, f"未知专长: {name}"
        if self.has_feat(name):
            return False, "已拥有此专长"
        info = self.FEATS_LIBRARY[name]
        ok, msg = self._check_prereq(info.get("prereq", {}))
        if not ok:
            return False, msg
        if name == "元素亲和" and choice not in self.ELEMENTS:
            return False, f"元素亲和需指定元素: {'/'.join(self.ELEMENTS)}"
        if name == "运动员" and choice not in ("力量", "敏捷"):
            return False, "运动员需指定 力量 或 敏捷"
        if st.cp < info["cp"]:
            return False, f"CP不足，需要 {info['cp']} CP"
        st.cp -= info["cp"]
        label = f"{name}({choice})" if choice else name
        st.feats.append(label)
        st.purchases += 1
        self._apply_immediate(name, choice)
        self.ctx.emit("character/changed", "feats")
        return True, f"获得专长 {label}，消耗 {info['cp']} CP"

    def _check_prereq(self, prereq: dict) -> tuple[bool, str]:
        st = self.ctx.state
        for attr, min_val in prereq.get("attr", {}).items():
            if st.attributes.get(attr, 0) < min_val:
                return False, f"需要 {attr} ≥ {min_val}"
        for skill, min_rank in prereq.get("skills", []):
            if st.skills.get(skill, 0) < min_rank:
                return False, f"需要 {skill} ≥ {min_rank} 级"
        if prereq.get("spellcasting"):
            if st.skills.get("奥术施法", 0) < 1 and st.skills.get("施法攻击", 0) < 1:
                return False, "需要会施法（奥术施法或施法攻击 ≥1 级）"
        return True, ""

    def _apply_immediate(self, name: str, choice: str) -> None:
        """立即生效的静态效果（属性 +1，上限 20）。"""
        st = self.ctx.state
        if name == "运动员" and choice:
            st.attributes[choice] = min(st.attributes[choice] + 1, 20)
        elif name == "演员":
            st.attributes["魅力"] = min(st.attributes["魅力"] + 1, 20)
        elif name == "顽强":
            st.attributes["体质"] = min(st.attributes["体质"] + 1, 20)

    # ---------- 查询 ----------
    def has_feat(self, name: str) -> bool:
        return any(f == name or f.startswith(name + "(") for f in self.ctx.state.feats)

    def skill_bonus(self, skill_name: str) -> int:
        """专长对技能检定的加值（演员/观察力）。"""
        bonus = 0
        if self.has_feat("演员") and skill_name in ("欺瞒", "表演"):
            bonus += 2
        if self.has_feat("观察力") and skill_name in ("侦察", "调查"):
            bonus += 2
        return bonus

    def element_picked(self) -> str:
        """元素亲和选择的元素（无则返回空串）。"""
        for f in self.ctx.state.feats:
            if f.startswith("元素亲和("):
                return f[len("元素亲和("):-1]
        return ""
