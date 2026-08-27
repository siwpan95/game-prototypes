# ascension.py
# 晋升系统 —— 魔药、仪式、途径切换、堕落晋升
from sequences import BaseSequence, Sequence, make_sequence
from pollution import SequenceError, AnchorBreakError
from uniqueness import Uniqueness, SequenceOneCharacteristic
from anchor import Anchor
from typing import Type, Optional, Callable

# ============================================================
# AscensionManager —— 晋升核心逻辑
# ============================================================
class AscensionManager:
    """晋升管理器：处理消化检查、锚检查、仪式、途径切换、性别转换"""

    @staticmethod
    def advance(current: BaseSequence,
                next_level: int,
                pathway_key: Optional[str] = None,
                uniqueness: Optional[Uniqueness] = None,
                ritual_check: Optional[Callable[[], bool]] = None) -> BaseSequence:
        """
        核心晋升方法

        参数:
            current: 当前序列实例
            next_level: 目标序列等级
            pathway_key: 目标途径（None = 同一途径，指定 = 途径切换）
            uniqueness: 要绑定的唯一性
            ritual_check: 仪式校验回调（返回 True 表示仪式完成）

        返回:
            新的序列实例
        """
        # 使用当前途径或指定途径
        target_pathway = pathway_key or current.PATHWAY_KEY

        # 导入途径数据
        from pathways_data import get_sequence_data, get_pathway, needs_ritual, will_gender_change, get_gender_change_message

        seq_data = get_sequence_data(target_pathway, next_level)
        pathway_data = get_pathway(target_pathway)

        # ---- 1. 扮演消化度检查 ----
        if not current.digested:
            raise SequenceError(
                f"扮演度不足，消化未完成 "
                f"({current.SEQUENCE_NAME}: {current.digestion_ratio:.0%})"
            )

        # ---- 2. 锚检查（统一使用 Anchor.required_for_level 设定表，单一来源）----
        required_anchor = Anchor.required_for_level(next_level)
        if required_anchor > 0 and current.anchor is None:
            raise AnchorBreakError(
                f"序列{next_level}需要锚定人性以维持理智，但未设置任何锚"
            )
        if current.anchor is not None and current.anchor.strength < required_anchor:
            raise AnchorBreakError(
                f"锚不足以支撑晋升！需要{required_anchor:.0f}，当前{current.anchor.strength:.1f}"
            )

        # ---- 3. 仪式检查（序列5+） ----
        if needs_ritual(next_level):
            ritual_desc = seq_data.get("ritual", "未知仪式")
            if ritual_check is None:
                print(f"  ⚠ 警告：序列{next_level}晋升需要仪式！")
                print(f"     仪式要求：{ritual_desc}")
                print(f"     未提供仪式校验，继续晋升（可能在扮演中被跳过）……")
            elif not ritual_check():
                raise SequenceError(f"仪式未完成！要求：{ritual_desc}")

        # ---- 4. 途径切换验证 ----
        if pathway_key and pathway_key != current.PATHWAY_KEY:
            from pathway_groups import PathwaySwitchValidator
            valid, msg = PathwaySwitchValidator.can_switch(
                current.PATHWAY_KEY, pathway_key, current.LEVEL
            )
            if not valid:
                raise SequenceError(f"途径切换失败：{msg}")
            print(f"  ⇄ 途径切换：{get_pathway(current.PATHWAY_KEY)['name']} → {get_pathway(target_pathway)['name']}")

        # ---- 5. 性别转换检查（按途径元组判定，避免消息子串自相矛盾）----
        gender = current.gender
        if will_gender_change(target_pathway, next_level):
            msg = get_gender_change_message(target_pathway, next_level)
            old_gender = gender
            if target_pathway in ("mother", "moon", "chaos_witch"):
                gender = "女"
            elif target_pathway == "red_priest":
                gender = "男"
            # 其余途径不触发性别转换，保留当前性别
            if gender != old_gender:
                print(f"  ⚧ 性别转换：{old_gender} → {gender}（{msg or '强制变性'}）")

        # ---- 6. 实例化新序列 ----
        new_instance = Sequence(target_pathway, next_level, seq_data, pathway_data, gender)
        new_instance.pollution = current.pollution
        new_instance.anchor = current.anchor
        # 能力继承：保留旧能力（可兼容），追加新能力
        new_instance.abilities = current.abilities + [
            a for a in new_instance.abilities if a not in current.abilities
        ]

        # ---- 7. 序列0 晋升：集齐唯一性 + 3 份序列1非凡特性 ----
        if next_level == 0:
            # 晋升序列0（真神）必须持有本途径唯一性与全部 3 份序列1特性
            if uniqueness is None:
                uniqueness = Uniqueness.get_or_create(
                    f"{pathway_data['name']}唯一性", target_pathway
                )
            uniqueness.bind(new_instance)
            print(f"  🔒 唯一性[{uniqueness.name}]已绑定")
            for i in (1, 2, 3):
                char1 = SequenceOneCharacteristic.ensure(target_pathway, i)
                char1.bind(new_instance)
            print(f"  🔒 已集齐 {pathway_data['name']}途径 3 份序列1非凡特性")
        elif uniqueness:
            uniqueness.bind(new_instance)
            print(f"  🔒 唯一性[{uniqueness.name}]已绑定")

        return new_instance

    @staticmethod
    def fall(current: BaseSequence) -> BaseSequence:
        """
        堕落晋升：因污染/失控而降级
        返回降级后的序列实例（等级+1，即降级）
        """
        if current.LEVEL >= 9:
            raise SequenceError("已是序列9，无法继续堕落")

        target_level = current.LEVEL + 1  # 等级数字增大 = 降级
        from pathways_data import get_sequence_data, get_pathway
        seq_data = get_sequence_data(current.PATHWAY_KEY, target_level)
        pathway_data = get_pathway(current.PATHWAY_KEY)

        fallen = Sequence(current.PATHWAY_KEY, target_level, seq_data, pathway_data, current.gender)
        fallen.pollution = current.pollution
        fallen.anchor = current.anchor
        # 能力减少
        fallen.abilities = [a for a in current.abilities if a in fallen.abilities]
        if not fallen.abilities:
            fallen.abilities = list(seq_data.get("abilities", []))

        print(f"  ⚠ 堕落！{current.SEQUENCE_NAME} 降至 {fallen.SEQUENCE_NAME}")
        return fallen


# ============================================================
# Potion —— 魔药类
# ============================================================
class Potion:
    """
    魔药：绑定目标序列与材料

    使用方式：
        # 同途径晋升
        potion = Potion("error", 8, "诈骗师非凡特性", ["灵性之血", "迷幻花粉末"])
        character = potion.consume(character)

        # 途径切换晋升
        potion = Potion("fool", 7, "魔术师非凡特性", [...], switch=True)
        character = potion.consume(character)
    """

    def __init__(self,
                 pathway_key: str,
                 target_level: int,
                 main_ingredient: str,
                 supplementary: list,
                 switch: bool = False,
                 uniqueness: Optional[Uniqueness] = None,
                 ritual_check: Optional[Callable[[], bool]] = None):
        """
        pathway_key: 目标途径 key
        target_level: 目标序列等级
        main_ingredient: 主材料（对应序列的非凡特性）
        supplementary: 辅助材料列表
        switch: 是否为途径切换
        uniqueness: 要绑定的唯一性
        ritual_check: 仪式完成校验
        """
        self.pathway_key = pathway_key
        self.target_level = target_level
        self.main = main_ingredient
        self.sup = supplementary
        self.switch = switch
        self.uniqueness = uniqueness
        self.ritual_check = ritual_check

    def consume(self, character: BaseSequence) -> BaseSequence:
        """服用魔药，触发晋升"""
        from pathways_data import get_sequence_data, get_pathway

        target_data = get_sequence_data(self.pathway_key, self.target_level)
        target_name = target_data["name"]
        pathway_name = get_pathway(self.pathway_key)["name"]

        if self.switch:
            print(f"服用 {pathway_name}途径·{target_name} 魔药：{self.main} + {'、'.join(self.sup)}")
            print(f"  ⇄ 途径切换中……")
        else:
            print(f"服用 {target_name} 魔药：{self.main} + {'、'.join(self.sup)}")

        return AscensionManager.advance(
            character,
            self.target_level,
            pathway_key=self.pathway_key if self.switch else None,
            uniqueness=self.uniqueness,
            ritual_check=self.ritual_check,
        )


# ============================================================
# 便捷晋升函数
# ============================================================
def ascend(character: BaseSequence,
           target_level: Optional[int] = None,
           pathway_key: Optional[str] = None,
           ritual_check: Optional[Callable[[], bool]] = None) -> BaseSequence:
    """
    便捷晋升：自动推断目标等级和途径

    character: 当前角色
    target_level: 目标等级（默认 = 当前等级 - 1，即序列数字减小 = 晋升）
    pathway_key: 切换到的途径（None = 同一途径）
    ritual_check: 仪式校验
    """
    if target_level is None:
        target_level = character.LEVEL - 1
    if target_level < 0:
        raise SequenceError("已是序列0，无法继续晋升")

    return AscensionManager.advance(
        character, target_level,
        pathway_key=pathway_key,
        ritual_check=ritual_check,
    )


def switch_pathway(character: BaseSequence,
                   to_pathway: str,
                   ritual_check: Optional[Callable[[], bool]] = None) -> BaseSequence:
    """
    同等级途径切换

    character: 当前角色
    to_pathway: 目标途径
    ritual_check: 仪式校验
    """
    from pathway_groups import PathwaySwitchValidator
    target = PathwaySwitchValidator.get_switch_target_level(
        character.PATHWAY_KEY, to_pathway, character.LEVEL
    )
    if target is None:
        valid, msg = PathwaySwitchValidator.can_switch(
            character.PATHWAY_KEY, to_pathway, character.LEVEL
        )
        raise SequenceError(msg)
    return AscensionManager.advance(
        character, target,
        pathway_key=to_pathway,
        ritual_check=ritual_check,
    )
