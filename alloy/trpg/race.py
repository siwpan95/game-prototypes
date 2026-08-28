"""d20.race - 种族系统服务（决策 C：GURPS 式模板定价；决策 F：仅创建期）

D&D 5e SRD 9 族：模板定价 = Σ 属性加值成本（calc_attribute_cost）+ Σ 所授优点 CP。
选择种族即支付模板 CP、应用属性加值（上限 20）、免费授予优点与熟练；
种族机制特性（HP/先攻/豁免/重掷/龙息/抗性）经事件钩子与查询方法生效。
挂到 ctx.race。
"""
from .context import Service
from .data import RACE_TEMPLATES, HALF_ELF_DEFAULT_PICKS, ATTRIBUTES
from .dice import roll_d20


class RaceService(Service):
    """种族选择与种族特性查询能力。"""

    RACE_TEMPLATES = RACE_TEMPLATES

    # ---------- 生命周期：注册种族事件钩子 ----------
    def apply(self) -> None:
        self._disposers = [
            # 丘陵矮人：最大 HP +活力等级
            self.ctx.on("derived/max_hp",
                        lambda hp, nxt: nxt(hp + self.ctx.state.skills.get("活力", 0))
                        if self.has_trait("HP+活力等级") else nxt(hp)),
            # 木精灵：先攻 +1
            self.ctx.on("derived/initiative",
                        lambda b, nxt: nxt(b + 1) if self.has_trait("先攻+1") else nxt(b)),
            # 半身人系：d20 掷出 1 重掷一次（幸运）
            self.ctx.on("dice/d20_roll",
                        lambda r, nxt: nxt(roll_d20()) if r == 1 and self.has_trait("幸运重掷") else nxt(r)),
        ]

    def dispose(self) -> None:
        for d in getattr(self, "_disposers", []):
            d()

    # ---------- 选择 ----------
    def set_race(self, name: str, choices: dict | None = None) -> tuple[bool, str]:
        """选择种族（仅创建期，未购买任何内容前）。choices 支持 半精灵/龙裔 的自选。"""
        st = self.ctx.state
        if st.race:
            return False, f"已选择种族: {st.race}"
        if name not in self.RACE_TEMPLATES:
            return False, f"未知种族: {name}"
        # 决策 F：仅创建期（无任何购买动作）
        if st.purchases > 0:
            return False, "种族仅可在创建期（未购买任何内容前）选择"

        tpl = self.RACE_TEMPLATES[name]
        if st.cp < tpl["cp"]:
            return False, f"CP不足，{name} 模板价格 {tpl['cp']} CP"
        st.cp -= tpl["cp"]
        for attr, bonus in tpl["bonuses"].items():
            st.attributes[attr] = min(10 + bonus, 20)
        # 半精灵：任选两项属性 +1（仅该种族有 choose.任选+1）
        choose = tpl.get("choose") or {}
        if "任选+1" in choose:
            picks = (choices or {}).get("任选+1") or HALF_ELF_DEFAULT_PICKS
            for attr in picks[:2]:
                if attr in ATTRIBUTES:
                    st.attributes[attr] = min(st.attributes[attr] + 1, 20)
        # 龙裔：元素选择（默认 火）
        if "元素" in choose:
            st.race_element = (choices or {}).get("元素") or "火"
        st.advantages.extend(tpl["advantages"])
        for sk in tpl["proficiencies"]:
            if sk not in st.proficiencies:
                st.proficiencies.append(sk)
        # 高等精灵：免费学会一个 0 环戏法
        if "免费戏法" in tpl["traits"] and "火焰箭" not in st.techniques:
            st.techniques.append("火焰箭")
        st.race = name
        self.ctx.emit("character/changed", "race")
        return True, f"选择种族 {name}，消耗 {tpl['cp']} CP"

    # ---------- 查询 ----------
    def template(self, name: str | None = None) -> dict | None:
        return self.RACE_TEMPLATES.get(name or self.ctx.state.race)

    def has_trait(self, trait: str) -> bool:
        tpl = self.template()
        return bool(tpl and trait in tpl.get("traits", []))

    def save_bonus_adjust(self, save_type: str) -> int:
        """种族对豁免的加值：强韧（矮人系/壮实半身人）、意志（半身人/侏儒/半精灵）。"""
        if save_type == "fort" and self.has_trait("强韧豁免+2"):
            return 2
        if save_type == "will" and self.has_trait("意志豁免+2"):
            return 2
        return 0

    def elemental(self) -> str:
        """龙裔元素 / 提夫林（火）。"""
        if self.ctx.state.race == "提夫林":
            return "火"
        return self.ctx.state.race_element or "火"
