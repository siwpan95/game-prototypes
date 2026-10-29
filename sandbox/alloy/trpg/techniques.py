"""d20.techniques - 技术（战技/法术）购买服务（原 TechniquesMixin 改写）

融合 D&D 的战技/法术与 GURPS 的 Technique（买除惩罚）。每项技术有前置技能/属性
要求与 CP 成本。挂到 ``ctx.techniques``。
"""
from .context import Service
from .data import TECHNIQUES


class TechniquesService(Service):
    """技术相关能力。"""

    TECHNIQUES = TECHNIQUES

    def purchase_technique(self, tech_name: str) -> tuple[bool, str]:
        """购买一项技术（战技/法术），检查前置与 CP。"""
        st = self.ctx.state
        if tech_name not in self.TECHNIQUES:
            return False, f"未知技术: {tech_name}"
        if tech_name in st.techniques:
            return False, "已拥有此技术"
        req_skill, req_rank, attr_req, _penalty, cost, _desc = self.TECHNIQUES[tech_name]
        current_rank = st.skills.get(req_skill, 0)
        if current_rank < req_rank:
            return False, f"需要 {req_skill} 至少 {req_rank} 级"
        for attr, min_val in attr_req.items():
            if st.attributes[attr] < min_val:
                return False, f"需要 {attr} {min_val}"
        if st.cp < cost:
            return False, "CP不足"
        st.cp -= cost
        st.techniques.append(tech_name)
        st.purchases += 1
        self.ctx.emit("character/changed", "techniques")
        return True, f"学会技术 {tech_name}，消耗 {cost} CP"

    def has_technique(self, tech_name: str) -> bool:
        """是否已学会某技术。"""
        return tech_name in self.ctx.state.techniques
