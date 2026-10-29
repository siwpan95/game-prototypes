# role_playing.py
# 扮演循环模拟 —— 非凡者的日常、扮演消化、污染积累
from sequences import BaseSequence, Sequence, make_sequence
from pollution import PollutionLevel, InsanityError, PollutionSource
from anchor import Anchor
from typing import Optional, Callable
import random

# ============================================================
# 核心扮演循环
# ============================================================
def role_playing_loop(character: BaseSequence,
                      days: int,
                      anchor: Optional[Anchor] = None,
                      pollution_rate: float = 0.1,
                      action_weights: Optional[dict] = None,
                      on_day: Optional[Callable[[int, BaseSequence], None]] = None,
                      verbose: bool = False,
                      seed: Optional[int] = None):
    """
    模拟多日扮演与污染积累

    参数:
        character: 非凡者序列实例
        days: 模拟天数
        anchor: 锚（如不提供则使用 character.anchor）
        pollution_rate: 每天污染累积量
        action_weights: 行为权重 {行为名: 概率}（用于自动选择扮演行为）
        on_day: 每天回调 (day, character) -> None
        verbose: 是否打印每天的详细信息
        seed: 随机种子（指定后结果可复现）

    返回:
        (存活天数, 是否失控, 结束时的污染等级)
    """
    if seed is not None:
        random.seed(seed)
    if anchor:
        character.anchor = anchor

    # 兼容旧逻辑：用连续污染点推进（character.pollution 现为 PollutionManager）
    sanity_points = float(character.pollution.value)
    action_catalog = character.act_catalog()
    # 只在「由未消化→已消化」的当天提示一次，避免循环中重复刷「可以晋升了」
    prev_digested = character.digested

    for day in range(1, days + 1):
        try:
            # ---- 行为选择 ----
            if action_catalog and action_weights:
                # 按权重随机选择行为
                actions = list(action_weights.keys())
                weights = [action_weights[a] for a in actions]
                chosen = random.choices(actions, weights=weights, k=1)[0]
            elif action_catalog:
                chosen = random.choice(action_catalog)
            else:
                chosen = None

            # ---- 执行行为 ----
            if chosen:
                character.perform_action(chosen)
                if verbose:
                    print(f"  第{day}天：执行「{chosen}」")
            else:
                character.act()
                if verbose:
                    print(f"  第{day}天：自由行动")

            # ---- 理智检查 ----
            character.check_sanity()

            # ---- 污染累积（连续 SAN 同步下降）----
            sanity_points += pollution_rate
            character.pollution.accumulate(PollutionSource("acting", pollution_rate))

            # 如果污染进入幻觉级，有概率获得额外污染
            if character.pollution.value >= PollutionLevel.HALLUCINATING.value:
                if random.random() < 0.2:
                    sanity_points += 0.3
                    character.pollution.accumulate(PollutionSource("whisper", 0.3))
                    if verbose:
                        print(f"  ⚠ 第{day}天：听见了不该听见的低语……污染加深")

            # ---- 每日回调 ----
            if on_day:
                on_day(day, character)

            # ---- 消化度达标提示（仅首次达标当天提示一次）----
            if character.digested and not prev_digested and verbose:
                print(f"  ✓ 第{day}天：扮演消化完成！可以晋升了")
            prev_digested = character.digested

        except InsanityError as e:
            print(f"\n💀 第{day}天，角色失控：{e}")
            return day, True, character.pollution.level

    return days, False, character.pollution.level


# ============================================================
# 仪式校验 —— 模拟仪式完成检查
# ============================================================
def ritual_check_pass(probability: float = 1.0) -> Callable[[], bool]:
    """
    创建一个仪式校验函数

    参数:
        probability: 仪式成功的概率 (0.0~1.0)
    返回:
        一个无参函数，调用时返回 True/False 表示仪式是否成功
    """
    def checker() -> bool:
        if probability >= 1.0:
            return True
        success = random.random() < probability
        if not success:
            print("  ⚠ 仪式失败！")
        return success
    return checker


# ============================================================
# 多途径演示场景
# ============================================================
def demo_single_pathway(pathway_key: str,
                        from_level: int = 9,
                        to_level: int = 8,
                        days: int = 15,
                        humanity: float = 80,
                        connections: int = 5):
    """
    单途径晋升演示

    演示一条途径从一个等级晋升到另一个等级的完整流程
    """
    from pathways_data import get_pathway, get_sequence_data
    from ascension import Potion

    pathway = get_pathway(pathway_key)
    seq_from = get_sequence_data(pathway_key, from_level)
    seq_to = get_sequence_data(pathway_key, to_level)

    print(f"\n{'='*60}")
    print(f"  {pathway['name']}途径 · 塔罗牌：{pathway['tarot']}")
    print(f"  序列{from_level}《{seq_from['name']}》→ 序列{to_level}《{seq_to['name']}》")
    print(f"{'='*60}")

    # 创建角色
    character = make_sequence(pathway_key, from_level)
    character.anchor = Anchor(humanity=humanity, connections=connections, name=f"{seq_from['name']}之锚")

    print(f"\n📋 {character.summary}")
    print(f"   能力：{'、'.join(character.abilities)}")
    print(f"   扮演行为：{'、'.join(character.act_catalog())}")

    # 扮演消化
    print(f"\n--- 扮演消化阶段（{days}天模拟）---")
    action_catalog = character.act_catalog()
    weights = {a: 1.0 for a in action_catalog} if action_catalog else {}

    survived, lost, pollution = role_playing_loop(
        character, days=days,
        action_weights=weights if weights else None,
        verbose=True,
    )

    if lost:
        print(f"  ⚠ 角色在消化阶段失控！")
        return None

    print(f"\n  消化进度：{character.digestion_ratio:.0%}")
    print(f"  污染等级：{character.pollution.label_cn}")

    # 晋升
    if character.digested:
        print(f"\n--- 晋升阶段 ---")
        ritual = seq_to.get("ritual")
        if ritual:
            print(f"  仪式要求：{ritual}")

        potion = Potion(
            pathway_key, to_level,
            f"{seq_to['name']}非凡特性",
            ["灵性之血", "星界之尘"],
        )
        try:
            character = potion.consume(character)
            print(f"  ✅ 晋升成功！")
            print(f"  {character.summary}")
            print(f"  新能力：{'、'.join(character.abilities)}")
            return character
        except Exception as e:
            print(f"  ❌ 晋升失败：{e}")
            return None
    else:
        print(f"  ⚠ 消化未完成，无法晋升")
        return character


# ============================================================
# 途径切换演示
# ============================================================
def demo_pathway_switch(from_pathway: str, to_pathway: str, level: int):
    """
    途径切换演示

    演示从一条途径切换到同一途径组的另一条途径
    """
    from pathways_data import get_pathway, get_sequence_data
    from pathway_groups import PathwaySwitchValidator

    from_pw = get_pathway(from_pathway)
    to_pw = get_pathway(to_pathway)

    print(f"\n{'='*60}")
    print(f"  途径切换：{from_pw['name']} → {to_pw['name']}")
    print(f"  等级：序列{level}")
    print(f"{'='*60}")

    # 验证
    valid, msg = PathwaySwitchValidator.can_switch(from_pathway, to_pathway, level)
    if not valid:
        print(f"  ❌ {msg}")
        return

    print(f"  ✅ {msg}")

    # 创建角色并完成扮演消化
    character = make_sequence(from_pathway, level)
    character.anchor = Anchor(humanity=90, connections=10, name="切换前锚")
    print(f"\n  切换前：{character.summary}")

    # 先完成当前序列的扮演消化
    print(f"\n  扮演消化中……")
    for action in character.act_catalog():
        character.perform_action(action)
    print(f"  消化完成：{character.digestion_ratio:.0%}")

    # 执行切换
    from ascension import switch_pathway
    try:
        character = switch_pathway(character, to_pathway)
        print(f"\n  切换后：{character.summary}")
        print(f"  能力：{'、'.join(character.abilities)}")
    except Exception as e:
        print(f"\n  ❌ 切换失败：{e}")
