"""d20.background - 背景系统服务（决策 D：+2 熟练加值；决策 F：仅创建期）

D&D 5e SRD 6 款背景：0 CP，授予 2 项技能「熟练」（有效等级 +2，经 state.proficiencies
参与技能有效等级计算）与叙事特性。挂到 ctx.background。
"""
from .context import Service
from .data import BACKGROUNDS


class BackgroundService(Service):
    """背景选择与特性查询能力。"""

    BACKGROUNDS = BACKGROUNDS

    def set_background(self, name: str) -> tuple[bool, str]:
        st = self.ctx.state
        if st.background:
            return False, f"已选择背景: {st.background}"
        if name not in self.BACKGROUNDS:
            return False, f"未知背景: {name}"
        # 决策 F：仅创建期（无任何购买动作）
        if st.purchases > 0:
            return False, "背景仅可在创建期（未购买任何内容前）选择"

        bg = self.BACKGROUNDS[name]
        for sk in bg["skills"]:
            if sk not in st.proficiencies:
                st.proficiencies.append(sk)
        st.background = name
        self.ctx.emit("character/changed", "background")
        return True, f"选择背景 {name}：{bg['skills'][0]}、{bg['skills'][1]} 熟练 +2"

    def feature(self) -> str:
        st = self.ctx.state
        if not st.background:
            return ""
        return self.BACKGROUNDS[st.background]["feature"]
