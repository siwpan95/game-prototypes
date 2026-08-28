"""d20.attributes - 属性购买服务（原 AttributesMixin 改写）

基于 D&D 六属性（力量/敏捷/体质/智力/感知/魅力，凡人均值 10），叠加 GURPS 的
递增标价。作为 Service 挂到 ``ctx.attributes``，读写宿主状态 ``ctx.state``。
"""
from .context import Service
from .data import ATTRIBUTES, ATTR_COST_BRACKETS, ability_mod


def calc_attribute_cost(value: int) -> int:
    """计算从 10 提升到 value 的总 CP 花费（value >= 10）。"""
    if value < 10:
        return 0
    cost = 0
    for attr in range(11, value + 1):
        for low, high, price in ATTR_COST_BRACKETS:
            if low <= attr <= high:
                cost += price
                break
    return cost


class AttributesService(Service):
    """属性购买能力。"""

    ATTRIBUTES = ATTRIBUTES

    def calc_attr_cost(self, value: int) -> int:
        """计算从 10 提升到 value 的 CP 花费（保留老 API）。"""
        return calc_attribute_cost(value)

    def set_attribute(self, attr: str, value: int) -> tuple[bool, str]:
        st = self.ctx.state
        if attr not in st.attributes:
            return False, f"未知属性: {attr}"
        if value < 10:
            return False, "属性不能低于10"
        current = st.attributes[attr]
        current_cost = calc_attribute_cost(current)
        new_cost = calc_attribute_cost(value)
        delta = new_cost - current_cost
        if st.cp - delta < 0:
            return False, f"CP不足，需要 {delta} CP，当前剩余 {st.cp} CP"
        st.cp -= delta
        st.attributes[attr] = value
        st.purchases += 1
        self.ctx.emit("character/changed", "attributes")
        return True, f"{attr} 设置为 {value}，消耗 {delta} CP"

    def attr_mod(self, attr: str) -> int:
        """获取指定属性的调整值 (value-10)//2。"""
        return ability_mod(self.ctx.state.attributes[attr])
