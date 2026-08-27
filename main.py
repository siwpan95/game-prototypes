# main.py
# 诡秘之主 · 序列途径模拟系统
# 基于亵渎石板的 22 条神之途径完全实现
#
# 运行：python main.py
# 可选参数：python main.py --demo <demo_name>
#   可选 demo：basic / multi / switch / full / gender / world
#             uniqueness / old_one / sealed

import sys
import os
# 允许从任意工作目录运行（与 gui_app.py 一致）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sequences import BaseSequence, Sequence, make_sequence, Thief, Fraudster
from anchor import Anchor
from ascension import Potion, ascend, switch_pathway
from pollution import PollutionLevel, InsanityError, PollutionSource
from uniqueness import Uniqueness, SequenceOneCharacteristic
from role_playing import role_playing_loop, ritual_check_pass, demo_single_pathway, demo_pathway_switch
from pathways_data import (
    PATHWAYS, PATHWAY_GROUPS,
    get_pathway, get_sequence_data, get_all_pathway_keys,
    get_compatible_pathways, get_interchange_at,
    needs_ritual, will_gender_change,
)
from pathway_groups import (
    PathwaySwitchValidator, OldOnePath, OldOneTier,
    FOUR_PILLARS, get_level_description,
    promote_to_old_one, sealed_artifact_level,
)
# ── E11：CLI↔GUI 共享核心 ──
import types
from inventory import Inventory
from save_load import GameSession
from rivals import RivalSystem
from achievements import (AchievementSystem, CodexSystem,
                          evaluate_achievements, record_codex, evaluate_ending)
from events import pick_event, resolve_choice


# ============================================================
# 分隔线工具
# ============================================================
def section(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def banner(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


# ============================================================
# Demo 1：基础演示 —— 保持向后兼容
# ============================================================
def demo_basic():
    """基础演示：偷盗者 → 诈骗师，与原版保持兼容"""
    banner("基础演示 · 错误途径：偷盗者 → 诈骗师")

    # 1. 初始化
    klein = Thief()
    klein.anchor = Anchor(humanity=80, connections=5, name="克莱恩之锚")
    print(f"\n初始序列：{klein.summary}")

    # 2. 扮演消化
    section("扮演消化阶段")
    klein.perform_action("偷窃")
    klein.perform_action("潜入")
    print(f"消化进度：{klein.digestion_ratio:.0%}")

    # 3. 晋升
    section("晋升阶段")
    seq8_potion = Potion("error", 8, "诈骗师非凡特性", ["灵性之血", "迷幻花粉末"])
    try:
        klein = seq8_potion.consume(klein)
        print(f"✅ 晋升成功！\n{klein.summary}")
    except Exception as e:
        print(f"❌ 晋升失败：{e}")
        return

    # 4. 污染积累模拟
    section("污染积累模拟（30天）")
    survived, lost, pollution = role_playing_loop(klein, days=30, verbose=True)
    print(f"\n模拟结束：存活 {survived} 天，失控={lost}，污染={pollution.label_cn}")


# ============================================================
# Demo 2：多途径展示
# ============================================================
def demo_multi_pathways():
    """展示多条途径的序列9→序列8晋升"""
    banner("多途径展示 · 各序列9角色晋升")

    demos = [
        ("fool", "愚者途径：占卜家 → 小丑"),
        ("error", "错误途径：偷盗者 → 诈骗师"),
        ("door", "门途径：学徒 → 戏法大师"),
        ("sun", "太阳途径：歌颂者 → 祈光人"),
        ("darkness", "黑暗途径：不眠者 → 午夜诗人"),
        ("abyss", "深渊途径：罪犯 → 折翼天使"),
    ]

    for pathway_key, title in demos:
        demo_single_pathway(pathway_key, from_level=9, to_level=8, days=8)


# ============================================================
# Demo 3：途径切换
# ============================================================
def demo_pathway_switching():
    """展示诡秘之主途径组的序列3互换"""
    banner("途径切换演示 · 诡秘之主途径组（愚者/错误/门 序列3互换）")

    # 展示诡秘之主途径组
    group = PATHWAY_GROUPS["lord_of_mysteries"]
    print(f"\n途径组：{group['name']}")
    print(f"互换规则：{group['description']}")
    print(f"互换等级：序列{group['interchange_at']}及以上")
    print(f"包含途径：{', '.join(PATHWAYS[k]['name'] for k in group['pathways'])}")

    # 创建愚者途径序列3角色
    section("初始化：愚者途径·序列3·古代学者")
    scholar = make_sequence("fool", 3)
    scholar.anchor = Anchor(humanity=90, connections=10, name="古代学者之锚")
    scholar.anchor.add_believers(50000)
    scholar.anchor.spread_legacy(50)

    print(scholar.full_report())

    # 先完成当前序列的扮演消化
    section("扮演消化：古代学者")
    for action in scholar.act_catalog():
        scholar.perform_action(action)
    print(f"消化完成：{scholar.digestion_ratio:.0%}")

    # 切换到错误途径
    section("切换：愚者 → 错误（序列3·欺瞒导师）")
    try:
        scholar = switch_pathway(scholar, "error")
        print(scholar.full_report())
    except Exception as e:
        print(f"❌ {e}")

    # 先消化欺瞒导师
    for action in scholar.act_catalog():
        scholar.perform_action(action)

    # 切换到门途径
    section("切换：错误 → 门（序列3·漫游者）")
    try:
        scholar = switch_pathway(scholar, "door")
        print(scholar.full_report())
    except Exception as e:
        print(f"❌ {e}")

    # 先消化漫游者
    for action in scholar.act_catalog():
        scholar.perform_action(action)

    # 尝试非法切换（不在同一组）
    section("尝试非法切换：门 → 太阳（不同途径组，应失败）")
    try:
        scholar = switch_pathway(scholar, "sun")
    except Exception as e:
        print(f"❌ {e}")


# ============================================================
# Demo 4：完整演示 —— 序列9到序列6全流程
# ============================================================
def demo_full_journey():
    """
    完整旅程：错误途径 序列9 → 序列6
    展示扮演消化、仪式、锚强度、污染管理等完整机制
    """
    banner("完整旅程 · 错误途径 序列9 → 序列6")

    # 创建角色
    klein = make_sequence("error", 9)
    klein.anchor = Anchor(humanity=85, connections=7, name="克莱恩的日常锚")
    print(f"\n初始：{klein.summary}")

    # ---- 序列9→8 ----
    section("第一幕：偷盗者(9) → 诈骗师(8)")
    print("扮演偷窃与潜入……")
    klein.perform_action("偷窃")
    klein.perform_action("潜入")
    print(f"消化完成：{klein.digestion_ratio:.0%}")

    potion = Potion("error", 8, "诈骗师非凡特性", ["灵性之血", "迷幻花粉末"])
    klein = potion.consume(klein)

    # ---- 序列8→7 ----
    section("第二幕：诈骗师(8) → 解密学者(7)")
    klein.anchor.add_connection("梅丽莎")  # 增强锚
    # 扮演欺诈和谎言
    for _ in range(3):
        klein.perform_action("编织谎言")
        klein.perform_action("欺诈他人")
    if not klein.digested:
        klein.perform_action("编织谎言")  # 确保消化
    print(f"消化完成：{klein.digestion_ratio:.0%}")

    potion = Potion("error", 7, "解密学者非凡特性",
                    ["灵性之血", "古代文字残片", "逻辑之水银"])
    klein = potion.consume(klein)

    # ---- 序列7→6 ----
    section("第三幕：解密学者(7) → 盗火人(6)")
    klein.anchor.add_connection("值夜者小队")  # 进一步增强锚
    print(f"当前锚强度：{klein.anchor.strength:.1f} / 需要：{klein.LEVEL * 10}")

    # 扮演解密学者的行为
    klein.perform_action("解密神秘事件")
    klein.perform_action("推导真相")
    print(f"消化完成：{klein.digestion_ratio:.0%}")

    # 盗火人是序列6，需要仪式吗？序列5起才需要
    seq6 = get_sequence_data("error", 6)
    if seq6.get("ritual"):
        print(f"⚠ 序列6也需要仪式：{seq6['ritual']}")

    potion = Potion("error", 6, "盗火人非凡特性",
                    ["灵性之血", "火种之心", "盗贼之影"])
    klein = potion.consume(klein)

    # ---- 最终状态 ----
    section("最终状态")
    print(klein.full_report())

    # ---- 污染模拟 ----
    section("后记：在序列6继续扮演的污染风险")
    survived, lost, pollution = role_playing_loop(klein, days=20, verbose=True)
    print(f"\n最终：存活 {survived} 天，失控={lost}，污染={pollution.label_cn}")

    # 锚状态
    if klein.anchor:
        print(f"\n{klein.anchor.report()}")


# ============================================================
# Demo 5：禁忌知识 —— 性别转换与强制变性
# ============================================================
def demo_gender_change():
    """展示部分途径的性别转换机制"""
    banner("禁忌知识 · 性别转换途径")

    cases = [
        ("chaos_witch", 7, "混沌魔女途径：刺客(9♂) → 女巫(7♀)"),
        ("red_priest", 4, "红祭司途径：猎人(9) → 铁血骑士(4♂)"),
        ("moon", 1, "月亮途径：药师(9) → 美神(1♀)"),
        ("mother", 2, "母亲途径：耕种者(9) → 荒芜主母(2♀)"),
    ]

    for pathway_key, level, desc in cases:
        pathway = get_pathway(pathway_key)
        gender_changes = pathway.get("gender_change", [])

        print(f"\n📌 {desc}")
        print(f"   途径：{pathway['name']}（塔罗：{pathway['tarot']}）")
        print(f"   性别转换等级：序列{'、'.join(str(l) for l in gender_changes)}")

        char = make_sequence(pathway_key, 9)
        char.anchor = Anchor(humanity=85, connections=8, name=f"{pathway['name']}锚")
        print(f"   初始性别：{char.gender}")

        # 模拟晋升到指定等级
        for lvl in range(8, level - 1, -1):
            # 先完成当前等级的扮演消化
            for action in char.act_catalog():
                char.perform_action(action)

            if not char.digested:
                print(f"   ⚠ 序列{char.LEVEL}消化未完成")
                break

            try:
                ritual = None
                if needs_ritual(lvl):
                    seq_data = get_sequence_data(pathway_key, lvl)
                    ritual = seq_data.get("ritual", "")

                char = ascend(char, target_level=lvl,
                             ritual_check=ritual_check_pass(0.9) if ritual else None)

                will_change = will_gender_change(pathway_key, lvl)
                if will_change:
                    print(f"   ⚧ 序列{lvl}：性别已变为 {char.gender}")
            except Exception as e:
                print(f"   ❌ 序列{lvl}晋升失败：{e}")
                break

        print(f"   最终：{char.summary}")


# ============================================================
# Demo 6：世界概览
# ============================================================
def demo_world_overview():
    """展示完整的世界观概览"""
    banner("诡秘之主 · 22条神之途径 世界观全览")

    # 力量体系
    print(f"\n{'='*60}")
    print("  力量体系总纲")
    print(f"{'='*60}")
    print("  序列魔药体系：序列9 → 序列0，共十个等级")
    print("  扮演法：根据序列魔药名称进行扮演，消化魔药降低失控风险")
    print("  仪式：序列5起需要晋升仪式辅助")
    print("  途径互换：高序列可在同一权柄体系的途径间切换")
    print("  唯一性：每条途径有且只有一个唯一性")
    print("  序列1特性：每条途径仅有三份")

    # 三大定律
    print(f"\n{'='*60}")
    print("  非凡体系三大定律")
    print(f"{'='*60}")
    print("  ① 非凡特性不灭定律：非凡特性不会毁灭、不会减少")
    print("  ② 同序列内非凡特性守恒定律：高序列越多则低序列越少")
    print("  ③ 相近途径非凡特性聚合定律：同途径及相近途径的非凡特性会向同一方向聚集")

    # 序列等级
    print(f"\n{'='*60}")
    print("  序列等级划分")
    print(f"{'='*60}")
    for lvl, desc in [(9, 9), (7, 5), (4, 3), (2, 1), (0, 0)]:
        print(f"  序列{lvl}～{desc}：{get_level_description(lvl)}")

    # 22条途径汇总
    print(f"\n{'='*60}")
    print("  22条神之途径汇总")
    print(f"{'='*60}")
    print(f"  {'编号':<4} {'途径':<8} {'塔罗':<8} {'权柄体系':<16}")
    print(f"  {'─'*4} {'─'*8} {'─'*8} {'─'*16}")

    pathway_order = [
        ("darkness", "①"), ("eternal_sleeper", "②"), ("dusk_giant", "③"),
        ("tyrant", "④"), ("hanged_man", "⑤"), ("visionary", "⑥"),
        ("white_tower", "⑦"), ("sun", "⑧"),
        ("bound_one", "⑨"), ("abyss", "⑩"),
        ("hermit", "⑪"), ("paragon", "⑫"),
        ("fool", "⑬"), ("error", "⑭"), ("door", "⑮"),
        ("mother", "⑯"), ("moon", "⑰"),
        ("judge", "⑱"), ("black_emperor", "⑲"),
        ("red_priest", "⑳"), ("chaos_witch", "㉑"),
        ("wheel_of_fortune", "㉒"),
    ]

    for key, num in pathway_order:
        p = PATHWAYS[key]
        group_name = PATHWAY_GROUPS[p["group"]]["name"][:12]
        gender_note = ""
        if p.get("gender_change"):
            gender_note = "⚧"
        print(f"  {num:<4} {p['name']+gender_note:<8} {p['tarot']:<8} {group_name:<16}")

    # 四大支柱
    print(f"\n{'='*60}")
    print("  四大支柱级旧日")
    print(f"{'='*60}")
    for key, pillar in FOUR_PILLARS.items():
        print(f"  ▸ {pillar['name']}")


# ============================================================
# Demo 7：唯一性争夺 —— 序列0真神的权柄之争
# ============================================================
def demo_uniqueness():
    """展示序列0晋升自动集齐唯一性 + 3份序列1特性，以及权柄争夺"""
    from ascension import ascend
    banner("唯一性争夺 · 序列0真神的权柄之争")

    # 1. 正常晋升序列0：触发唯一性 + 3 份序列1特性绑定
    section("晋升序列0（错误途径）")
    god = make_sequence("error", 1)
    god.anchor = Anchor(humanity=100, connections=50, name="真神之锚")
    god.anchor.add_believers(1_000_000)
    for a in god.act_catalog():
        god.perform_action(a)
    god = ascend(god, target_level=0, ritual_check=lambda: True)
    print(f"✅ 已成为：{god.summary}")
    u = Uniqueness.get_or_create("错误唯一性", "error")
    owner = getattr(u.owner, "SEQUENCE_NAME", u.owner)
    print(f"   唯一性持有者：{owner}")
    print(f"   序列1特性可用数：{SequenceOneCharacteristic.available_count('error')}（应为0）")

    # 2. 争夺：另一人试图晋升同一途径序列0 -> 唯一性已被持有
    section("竞争者试图晋升同一序列0")
    rival = make_sequence("error", 1)
    rival.anchor = Anchor(humanity=100, connections=50, name="对手之锚")
    rival.anchor.add_believers(1_000_000)
    for a in rival.act_catalog():
        rival.perform_action(a)
    try:
        rival = ascend(rival, target_level=0, ritual_check=lambda: True)
        print(f"⚠ 意外：争夺竟成功了 -> {rival.summary}")
    except RuntimeError as e:
        print(f"❌ 权柄争夺失败（符合预期）：{e}")


# ============================================================
# Demo 8：旧日晋升 —— 诡秘之主（支柱级）
# ============================================================
def demo_old_one():
    """展示旧日晋升：聚合组内所有途径唯一性 + 3份序列1特性"""
    banner("旧日晋升 · 诡秘之主（支柱级）")

    # 先成为序列0真神（愚者途径）
    section("晋升序列0（愚者途径）")
    god = make_sequence("fool", 1)
    god.anchor = Anchor(humanity=100, connections=50, name="源堡之锚")
    god.anchor.add_believers(1_000_000)
    for a in god.act_catalog():
        god.perform_action(a)
    god = ascend(god, target_level=0, ritual_check=lambda: True)
    print(f"✅ 已成为序列0：{god.summary}")

    # 晋升旧日：聚合愚者/错误/门 三途径唯一性与序列1特性
    section("聚合诡秘之主组权柄")
    comp = promote_to_old_one("lord_of_mysteries", god)
    print(f"\n🜂 旧日晋升成功：{comp['group']}")
    if comp.get("pillar"):
        print(f"   支柱：{comp['pillar']}（{comp['tier']}）")
    for p in comp["pathways"]:
        print(f"   - {p['pathway']}：唯一性[{p['uniqueness']}] + 序列1 {p['sequence_1']}")

    # 争夺：另一人无法再晋升同一旧日
    section("竞争者试图晋升同一旧日")
    rival = make_sequence("error", 0)
    rival.anchor = Anchor(humanity=100, connections=50, name="对手之锚")
    rival.anchor.add_believers(1_000_000)
    try:
        promote_to_old_one("lord_of_mysteries", rival)
        print("⚠ 意外：旧日争夺竟成功了？")
    except RuntimeError as e:
        print(f"❌ 旧日权柄争夺失败（符合预期）：{e}")


# ============================================================
# Demo 9：封印物等级映射
# ============================================================
def demo_sealed_artifact():
    """展示序列等级与封印物等级的对应关系（接入 SEALED_ARTIFACT_LEVELS）"""
    banner("封印物等级映射 · 序列 ↔ 封印物")
    for lvl in (9, 8, 7, 6, 5, 4, 3, 2, 1, 0):
        sa = sealed_artifact_level(lvl)
        print(f"   序列{lvl} → {sa['name']}（对应{sa['corresponds']}）")
    print("\n结合角色序列报告：")
    ch = make_sequence("abyss", 4)
    print(ch.full_report())


# ============================================================
# Demo 10：共享核心 · 完整养成循环（E11）
# ============================================================
def run_journey_demo():
    """
    用 GameSession 承载一次完整养成循环（消化→晋升→事件→阵营→对手→成就/图鉴/结局），
    并演示存档/读档。CLI 与 GUI 共用同一引擎（GameSession），证明二者已统一。
    返回汇总 dict 供测试断言。
    """
    # 用 SimpleNamespace 模拟 GUIState 的「最小状态接口」（achievements/codex/rivals 协作）
    st = types.SimpleNamespace()
    ch = make_sequence("error", 9)
    ch.anchor = Anchor(humanity=90, connections=10, name="克莱恩的锚")
    st.character = ch
    st.old_one_info = None
    st.factions = {"tarot": 0}
    st.seen_events = set()
    st.event_log = []
    st.inventory = Inventory()
    st.achievements = AchievementSystem()
    st.codex = CodexSystem()
    st.rival_system = RivalSystem(seed=7)

    # 第一幕：消化 + 晋升 序列9 → 序列8
    for a in ch.act_catalog():
        ch.perform_action(a)
    potion = Potion("error", 8, "诈骗师非凡特性", ["灵性之血", "迷幻花粉末"])
    st.character = potion.consume(ch)

    # 第二幕：遭遇事件
    ev = pick_event(st.character, st)
    if ev is not None:
        st.seen_events.add(ev["title"])
        for line in resolve_choice(st, ev, 0):
            pass

    # 第三幕：塔罗会社交（阵营声望 → 材料）
    from factions import FactionSystem
    fs = FactionSystem(st.factions)
    fdays = fs.do_action(st, "tarot_exchange")
    st.factions = fs.to_dict()

    # 第四幕：对手推进 30 tick（竞争唯一性/序列1）
    st.rival_system.add_rival("fool")
    st.rival_system.tick(30)

    # 第五幕：成就 / 图鉴 / 结局
    record_codex(st)
    new_ach = evaluate_achievements(st)
    key, ending_title, _ = evaluate_ending(st)

    # 第六幕：GameSession 存档 / 读档（CLI↔GUI 共用引擎）
    sess = GameSession(
        character=st.character.to_dict(),
        inventory=st.inventory.to_dict(),
        event_log=list(st.event_log),
        old_one_info=st.old_one_info,
        view_mode="character",
        factions=dict(st.factions),
        rival_system=st.rival_system.to_dict(),
        achievements=st.achievements.to_dict(),
        codex=st.codex.to_dict(),
    )
    sess.save("journey_demo")
    sess2 = GameSession.load("journey_demo")
    ch2 = Sequence.from_dict(sess2.character)
    rs2 = RivalSystem.from_dict(sess2.rival_system)
    ach2 = AchievementSystem.from_dict(sess2.achievements)
    codex2 = CodexSystem.from_dict(sess2.codex)

    # 校验 roundtrip 一致性
    assert ch2.LEVEL == st.character.LEVEL, "读档后序列等级应一致"
    assert rs2.count() == st.rival_system.count(), "读档后对手数应一致"
    assert ach2.progress() == st.achievements.progress(), "读档后成就进度应一致"

    return {
        "level": st.character.LEVEL,
        "sequence": st.character.SEQUENCE_NAME,
        "rival_count": st.rival_system.count(),
        "achievements": st.achievements.progress(),
        "codex_sequences": codex2.sequence_progress(),
        "new_achievements": new_ach,
        "ending": ending_title,
    }


def demo_journey():
    """共享核心演示：完整养成循环 + 存档/读档（CLI 与 GUI 同引擎）。"""
    banner("共享核心演示 · 完整养成循环（CLI 与 GUI 共用 GameSession 引擎）")
    summary = run_journey_demo()
    section("旅程结算")
    print(f"  当前序列：序列{summary['level']} · {summary['sequence']}")
    print(f"  AI 对手数：{summary['rival_count']}")
    print(f"  成就进度：{summary['achievements'][0]}/{summary['achievements'][1]}"
          f"（本次新解锁：{summary['new_achievements'] or '无'}）")
    print(f"  图鉴序列收集：{summary['codex_sequences'][0]}/{summary['codex_sequences'][1]}")
    print(f"  当前结局走向：{summary['ending']}")
    print(f"\n  ✓ GameSession 存档/读档 roundtrip 一致（CLI 与 GUI 共用同一引擎）")


# ============================================================
# 主入口
# ============================================================
def main():
    """主入口：根据命令行参数选择演示模式"""
    print("""
╔══════════════════════════════════════════════════════╗
║     诡秘之主 · 序列途径模拟系统 v2.0                  ║
║     基于亵渎石板 — 22条神之途径完全实现                ║
║     "你是穿越者，也可能是复苏者"                       ║
╚══════════════════════════════════════════════════════╝
    """)

    # 解析命令行参数
    demo_name = "full"
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith("--demo="):
                demo_name = arg.split("=", 1)[1]
            elif arg in ("basic", "multi", "switch", "full", "gender", "world",
                         "uniqueness", "old_one", "sealed", "journey"):
                demo_name = arg

    demos = {
        "basic": ("基础演示：偷盗者→诈骗师", demo_basic),
        "multi": ("多途径展示：6条途径的序列9→8晋升", demo_multi_pathways),
        "switch": ("途径切换：诡秘之主途径组序列3互换", demo_pathway_switching),
        "full": ("完整旅程：错误途径 序列9→序列6", demo_full_journey),
        "gender": ("禁忌知识：性别转换途径展示", demo_gender_change),
        "world": ("世界概览：22条途径全貌", demo_world_overview),
        "uniqueness": ("唯一性争夺：序列0权柄之争", demo_uniqueness),
        "old_one": ("旧日晋升：诡秘之主（支柱级）", demo_old_one),
        "sealed": ("封印物等级映射", demo_sealed_artifact),
        "journey": ("共享核心：完整养成循环 + 存档/读档", demo_journey),
    }

    if demo_name == "all":
        for name, (desc, func) in demos.items():
            func()
            print()
    elif demo_name in demos:
        desc, func = demos[demo_name]
        print(f"\n▶ 运行：{desc}\n")
        func()
    else:
        print(f"未知演示模式：{demo_name}")
        print(f"可用模式：{', '.join(demos.keys())} / all")
        return

    print(f"\n{'='*60}")
    print("  模拟结束")
    print(f"  运行模式：{demo_name}")
    print(f"  途径数据：{len(PATHWAYS)} 条途径已加载")
    print(f"  途径组：{len(PATHWAY_GROUPS)} 个权柄体系")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
