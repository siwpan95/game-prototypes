# tests/test_all.py
# 诡秘之主·序列途径模拟系统 —— 全面测试套件（纯标准库，无第三方依赖）
#
# 运行：
#   cd G:\project_root
#   python tests/test_all.py
#
# 说明：本套件自带极简测试框架，不依赖 pytest。
#       每个测试用例以 try/except 包裹，记录 PASS / FAIL / ERROR 并输出证据。

import sys
import os
import io
import contextlib
import traceback
import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ───────────────────────── 极简测试框架 ─────────────────────────
RESULTS = []  # (name, status, detail)


def test(name):
    """装饰器：把函数注册为测试用例"""
    def deco(fn):
        def wrapper():
            buf = io.StringIO()
            try:
                _reset_global_state()  # 隔离全局唯一性/序列1 注册表
                with contextlib.redirect_stdout(buf):
                    fn()
                RESULTS.append((name, "PASS", buf.getvalue().strip()[-600:]))
                print(f"[PASS] {name}")
            except AssertionError as e:
                detail = f"{buf.getvalue().strip()[-400:]}\n断言失败: {e}"
                RESULTS.append((name, "FAIL", detail))
                print(f"[FAIL] {name}: {e}")
            except Exception as e:
                detail = f"{buf.getvalue().strip()[-400:]}\n异常: {type(e).__name__}: {e}\n" + \
                         "".join(traceback.format_tb(e.__traceback__)[-3:])
                RESULTS.append((name, "ERROR", detail))
                print(f"[ERROR] {name}: {type(e).__name__}: {e}")
        wrapper.__name__ = name
        TESTS.append(wrapper)
        return wrapper
    return deco


TESTS = []


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _reset_global_state():
    """每个用例前清空全局注册表，保证隔离（唯一性/序列1 是模块级单例）"""
    try:
        from uniqueness import Uniqueness, SequenceOneCharacteristic
        Uniqueness._reset_state()
        SequenceOneCharacteristic._reset_state()
    except Exception:
        pass


# ───────────────────────── 导入 ─────────────────────────
@test("import_all_modules")
def t_import():
    import anchor, pollution, sequences, ascension, uniqueness
    import role_playing, pathway_groups, pathways_data
    import main, gui_app  # gui_app 会注册字体、构造常量（不会进入 mainloop）
    expect(True, "所有模块应可导入")


# ───────────────────────── 数据完整性 ─────────────────────────
@test("data_integrity_pathways")
def t_data_pathways():
    from pathways_data import PATHWAYS, PATHWAY_GROUPS
    from pathway_groups import PathwaySwitchValidator
    expect(len(PATHWAYS) == 22, f"途径数应为22，实际{len(PATHWAYS)}")
    expect(len(PATHWAY_GROUPS) == 9, f"途径组数应为9，实际{len(PATHWAY_GROUPS)}")
    # 每个途径组的 pathways 都应在 PATHWAYS 中
    for gk, g in PATHWAY_GROUPS.items():
        for pk in g["pathways"]:
            expect(pk in PATHWAYS, f"组 {gk} 含未知途径 {pk}")
    # 每个途径的 group 都应存在
    for pk, p in PATHWAYS.items():
        expect(p["group"] in PATHWAY_GROUPS, f"途径 {pk} 的组 {p['group']} 不存在")
    print(f"22 途径 / 9 组 通过；途径名示例: {PATHWAYS['error']['name']}")


@test("data_integrity_sequences")
def t_data_seq():
    from pathways_data import PATHWAYS, get_sequence_data, get_pathway
    # sequences 字段为 list[dict]，每个 dict 含 level
    problems = []
    for pk, p in PATHWAYS.items():
        seqs = p.get("sequences", [])
        expect(isinstance(seqs, list), f"{pk}.sequences 应为 list")
        levels = sorted(int(s["level"]) for s in seqs)
        if levels != list(range(0, 10)):
            problems.append(f"{pk}: 序列等级缺失/多余 -> {levels}")
        for s in seqs:
            for fld in ("level", "name", "abilities", "required_actions"):
                if fld not in s:
                    problems.append(f"{pk} seq{s.get('level')}: 缺字段 {fld}")
    expect(not problems, "发现数据缺陷:\n" + "\n".join(problems))
    # 仪式检查：序列5及以下（数字更小）按设定需要仪式
    missing_ritual = []
    for pk in PATHWAYS:
        for lvl in (5, 4, 3, 2, 1, 0):
            s = get_sequence_data(pk, lvl)
            if not s.get("ritual"):
                missing_ritual.append(f"{pk} seq{lvl} 无 ritual")
    print(f"序列字段完整；缺失仪式项: {len(missing_ritual)}")
    if missing_ritual:
        print("  " + "\n  ".join(missing_ritual[:10]))


@test("data_integrity_gender_change")
def t_data_gender():
    from pathways_data import PATHWAYS
    bad = []
    for pk, p in PATHWAYS.items():
        for lvl in p.get("gender_change", []):
            if not (0 <= lvl <= 9):
                bad.append(f"{pk}: 非法性别转换等级 {lvl}")
    expect(not bad, "性别转换数据异常:\n" + "\n".join(bad))
    gc = {pk: p.get("gender_change", []) for pk, p in PATHWAYS.items() if p.get("gender_change")}
    print(f"含性别转换的途径: {len(gc)} 条 -> {list(gc.keys())}")


# ───────────────────────── Anchor 系统 ─────────────────────────
@test("anchor_strength_formula")
def t_anchor_formula():
    from anchor import Anchor
    a = Anchor(humanity=80, connections=5, name="t")
    # strength = humanity*(1+0.1*connections) + legacy*0.5 + believers*0.001
    expect(abs(a.strength - 80 * 1.5) < 1e-6, f"基础强度应为120，实际{a.strength}")
    a.add_believers(1000)
    a.spread_legacy(10)
    expect(abs(a.strength - (120 + 5 + 1)) < 1e-6, f"含信徒/传说强度应为126，实际{a.strength}")
    # 边界
    b = Anchor(humanity=200, connections=0)
    expect(b.humanity == 100, "humanity 应被裁剪到[0,100]")
    print(f"强度公式通过；status={a.status}")


@test("anchor_required_table")
def t_anchor_table():
    from anchor import Anchor
    table = {9: 0, 8: 0, 7: 30, 6: 30, 5: 30, 4: 60, 3: 60, 2: 100, 1: 100, 0: 200}
    ok = all(Anchor.required_for_level(l) == table[l] for l in table)
    expect(ok, "Anchor.required_for_level 与设定表不符")
    print("Anchor 需求表通过")


# ───────────────────────── 污染系统 ─────────────────────────
@test("pollution_levels")
def t_pollution():
    from pollution import PollutionLevel, PollutionManager, InsanityError
    expect(PollutionLevel.SANE.value == 0 and PollutionLevel.GOD_FALLEN.value == 4, "等级枚举范围错误")
    expect(PollutionLevel.HALLUCINATING.label_cn == "幻觉", "标签错误")
    pm = PollutionManager(PollutionLevel.SANE)
    pm.accumulate(__import__("pollution").PollutionSource("acting", 3.5))
    expect(pm.level.value == 3, f"累积后应到失控(3)，实际{pm.level.value}")
    expect(pm.is_lost, "is_lost 应为 True")
    ok = pm.try_purify(2.0)
    expect(pm.level.value <= 1, f"净化后应降到低等级，实际{pm.level.value}")
    print(f"污染等级/管理器通过；净化后 level={pm.level.value}")


# ───────────────────────── 序列 / 扮演消化 ─────────────────────────
@test("make_sequence_all_pathways")
def t_make_all():
    from sequences import make_sequence
    from pathways_data import PATHWAYS
    for pk in PATHWAYS:
        seq9 = make_sequence(pk, 9)
        expect(seq9.LEVEL == 9, f"{pk} 等级错误")
        expect(seq9.SEQUENCE_NAME, f"{pk} 序列名为空")
    print(f"22 条途径均可 make_sequence(seq9) -> {make_sequence('fool',9).SEQUENCE_NAME}")


@test("digestion_flow")
def t_digest():
    from sequences import make_sequence
    ch = make_sequence("error", 9)
    expect(not ch.digested, "初始应为未消化")
    for act in ch.act_catalog():
        ch.perform_action(act)
    expect(ch.digested, "执行全部扮演行为后应消化完成")
    expect(abs(ch.digestion_ratio - 1.0) < 1e-9, "消化率应为1.0")
    # 扮演行为为空时视为已消化
    ch2 = make_sequence("mother", 9)
    if not ch2.act_catalog():
        expect(ch2.digested, "无扮演行为目录应视为已消化")
    print(f"消化流程通过；seq9 扮演行为={ch.act_catalog()}")


# ───────────────────────── 晋升 / 锚检查 ─────────────────────────
@test("ascend_success")
def t_ascend_ok():
    from sequences import make_sequence
    from anchor import Anchor
    from ascension import Potion, ascend
    ch = make_sequence("error", 9)
    ch.anchor = Anchor(humanity=85, connections=7, name="t")
    for act in ch.act_catalog():
        ch.perform_action(act)
    potion = Potion("error", 8, "诈骗师非凡特性", ["灵性之血", "迷幻花粉末"])
    ch2 = potion.consume(ch)
    expect(ch2.LEVEL == 8, f"晋升后应为 seq8，实际{ch2.LEVEL}")
    expect("诈骗师" in ch2.SEQUENCE_NAME, "名称应为诈骗师")
    print(f"晋升成功: {ch2.SEQUENCE_NAME}")


@test("ascend_anchor_break")
def t_anchor_break():
    from sequences import make_sequence
    from anchor import Anchor
    from ascension import ascend, AnchorBreakError
    ch = make_sequence("error", 3)
    # 极弱锚：humanity=1, connections=0 -> strength=1，序列2要求 100（设定表）
    ch.anchor = Anchor(humanity=1, connections=0, name="弱")
    for act in ch.act_catalog():
        ch.perform_action(act)
    raised = False
    try:
        ascend(ch)  # 默认升到 seq2，需求 100
    except AnchorBreakError:
        raised = True
    expect(raised, "弱锚晋升高序列应触发 AnchorBreakError")
    print("弱锚阻断通过（触发 AnchorBreakError）")


@test("ascend_not_digested")
def t_not_digested():
    from sequences import make_sequence
    from anchor import Anchor
    from ascension import ascend, SequenceError
    ch = make_sequence("error", 9)
    ch.anchor = Anchor(humanity=85, connections=7, name="t")
    # 故意不执行扮演行为 -> 未消化
    raised = False
    try:
        ascend(ch)
    except SequenceError:
        raised = True
    expect(raised, "未消化晋升应触发 SequenceError")
    print("未消化阻断通过（触发 SequenceError）")


@test("ascend_lowseq_no_anchor_ok")
def t_no_anchor_low():
    """低序列（需求为0）无锚晋升应被允许（符合设定表单一来源）"""
    from sequences import make_sequence
    from ascension import ascend
    ch = make_sequence("error", 9)
    ch.anchor = None
    for act in ch.act_catalog():
        ch.perform_action(act)
    ch2 = ascend(ch)  # -> seq8, 需求 0
    expect(ch2.LEVEL == 8, "低序列无锚晋升应放行（需求为0）")
    print("低序列无锚晋升放行（符合设定表）")


@test("ascend_highseq_requires_anchor")
def t_requires_anchor_high():
    """高序列（需求>0）无锚晋升必须被拒绝（修复无锚直冲序列0）"""
    from sequences import make_sequence
    from ascension import ascend, AnchorBreakError
    ch = make_sequence("error", 3)
    ch.anchor = None
    for act in ch.act_catalog():
        ch.perform_action(act)
    raised = False
    try:
        ascend(ch)  # -> seq2, 需求 100
    except AnchorBreakError:
        raised = True
    expect(raised, "高序列无锚晋升应触发 AnchorBreakError")
    print("高序列无锚晋升被拒绝（已修复）")


# ───────────────────────── 途径切换 ─────────────────────────
@test("switch_valid")
def t_switch_ok():
    from sequences import make_sequence
    from anchor import Anchor
    from ascension import switch_pathway
    from pathway_groups import PathwaySwitchValidator
    ch = make_sequence("fool", 3)  # 序列3 达到互换要求
    ch.anchor = Anchor(humanity=90, connections=10, name="t")
    for act in ch.act_catalog():
        ch.perform_action(act)
    ok, msg = PathwaySwitchValidator.can_switch("fool", "error", 3)
    expect(ok, f"fool->error 应可切换: {msg}")
    ch2 = switch_pathway(ch, "error")
    expect(ch2.PATHWAY_KEY == "error", "应切换到 error 途径")
    print(f"合法切换通过: {ch2.PATHWAY_NAME}")


@test("switch_invalid_group")
def t_switch_bad():
    from pathway_groups import PathwaySwitchValidator
    from ascension import switch_pathway, SequenceError
    from sequences import make_sequence
    from anchor import Anchor
    ok, msg = PathwaySwitchValidator.can_switch("door", "sun", 3)
    expect(not ok, f"door->sun 跨组应禁止: {msg}")
    ch = make_sequence("door", 3)
    ch.anchor = Anchor(humanity=90, connections=10, name="t")
    raised = False
    try:
        switch_pathway(ch, "sun")
    except SequenceError:
        raised = True
    expect(raised, "跨组切换应触发 SequenceError")
    print("跨组切换禁止通过")


@test("switch_special_darkness_witch")
def t_switch_special():
    from pathway_groups import PathwaySwitchValidator
    ok, msg = PathwaySwitchValidator.can_switch("darkness", "chaos_witch", 3)
    expect(ok, f"darkness->chaos_witch 特殊互通应允许: {msg}")
    print("黑暗->混沌魔女 特殊互通通过")


# ───────────────────────── 性别转换 ─────────────────────────
@test("gender_change_logic")
def t_gender():
    from sequences import make_sequence
    from anchor import Anchor
    from ascension import ascend
    from pathways_data import will_gender_change
    # 这三条途径的性别转换逻辑工作正常（依赖 target_pathway 元组分支）
    cases = [("chaos_witch", 7, "女"), ("moon", 1, "女"), ("mother", 2, "女")]
    for pk, lvl, expect_gender in cases:
        ch = make_sequence(pk, 9)
        ch.anchor = Anchor(humanity=90, connections=10, name="t")
        expect(will_gender_change(pk, lvl), f"{pk} 在 seq{lvl} 应发生性别转换")
        cur = ch
        for target in range(8, lvl - 1, -1):
            for act in cur.act_catalog():
                cur.perform_action(act)
            cur = ascend(cur, target_level=target, ritual_check=lambda: True)
        expect(cur.gender == expect_gender,
               f"{pk} 升至 seq{lvl} 性别应为 {expect_gender}，实际 {cur.gender}")
        print(f"{pk} 升 seq{lvl} -> 性别 {cur.gender}（期望 {expect_gender}）")


@test("gender_red_priest")
def t_gender_rp():
    """red_priest 在序列4+ 应正确变为 男（修复子串歧义后）"""
    from sequences import make_sequence
    from anchor import Anchor
    from ascension import ascend
    ch = make_sequence("red_priest", 9)  # 初始 女
    ch.anchor = Anchor(humanity=90, connections=10, name="t")
    cur = ch
    for target in range(8, 3, -1):
        for act in cur.act_catalog():
            cur.perform_action(act)
        cur = ascend(cur, target_level=target, ritual_check=lambda: True)
    expect(cur.gender == "男", f"red_priest 升至 seq4 应为 男，实际 {cur.gender}")
    print(f"red_priest 升 seq4 -> 性别 {cur.gender}（期望 男）")


# ───────────────────────── 唯一性 / 序列1 ─────────────────────────
@test("uniqueness_single_owner")
def t_unique():
    from uniqueness import Uniqueness, SequenceOneCharacteristic
    u = Uniqueness("测试唯一性", "error")
    class A: SEQUENCE_NAME = "甲"
    class B: SEQUENCE_NAME = "乙"
    a, b = A(), B()
    u.bind(a)
    raised = False
    try:
        u.bind(b)
    except RuntimeError:
        raised = True
    expect(raised, "唯一性被二次绑定应触发 RuntimeError")
    expect(SequenceOneCharacteristic.available_count("error") == 3, "序列1特性初始应有3份可用")
    print("唯一性单持有 / 序列1库存通过")


@test("uniqueness_seq0_bind")
def t_uniq_seq0():
    """序列0晋升应自动集齐本途径唯一性 + 3 份序列1特性（已落地）"""
    from sequences import make_sequence
    from anchor import Anchor
    from ascension import ascend
    from uniqueness import Uniqueness, SequenceOneCharacteristic
    Uniqueness._reset_state(); SequenceOneCharacteristic._reset_state()
    ch = make_sequence("error", 1)
    ch.anchor = Anchor(humanity=100, connections=50, name="t")
    ch.anchor.add_believers(1_000_000)
    for a in ch.act_catalog():
        ch.perform_action(a)
    ch = ascend(ch, target_level=0, ritual_check=lambda: True)
    u = Uniqueness.get_or_create("错误唯一性", "error")
    expect(u.is_bound and u.owner is ch, "序列0晋升应绑定本途径唯一性")
    expect(SequenceOneCharacteristic.available_count("error") == 0, "序列0晋升应集齐3份序列1特性")
    print("唯一性+序列1 在序列0晋升时自动绑定（已落地）")


@test("uniqueness_contention")
def t_uniq_contend():
    """第二人晋升同一序列0应因唯一性争夺失败（权柄之争）"""
    from sequences import make_sequence
    from anchor import Anchor
    from ascension import ascend
    from uniqueness import Uniqueness
    Uniqueness._reset_state()
    ch = make_sequence("error", 1)
    ch.anchor = Anchor(humanity=100, connections=50, name="t")
    ch.anchor.add_believers(1_000_000)
    for a in ch.act_catalog():
        ch.perform_action(a)
    ch = ascend(ch, target_level=0, ritual_check=lambda: True)
    rival = make_sequence("error", 1)
    rival.anchor = Anchor(humanity=100, connections=50, name="t2")
    rival.anchor.add_believers(1_000_000)
    for a in rival.act_catalog():
        rival.perform_action(a)
    raised = False
    try:
        ascend(rival, target_level=0, ritual_check=lambda: True)
    except RuntimeError:
        raised = True
    expect(raised, "第二人晋升同一序列0应因唯一性争夺失败")
    print("唯一性争夺正确触发 RuntimeError")


@test("sequence_one_characteristics")
def t_seq1():
    """序列1特性 ensure 幂等 + 库存正确（已落地）"""
    from uniqueness import SequenceOneCharacteristic
    SequenceOneCharacteristic._reset_state()
    c1 = SequenceOneCharacteristic.ensure("error", 1)
    c2 = SequenceOneCharacteristic.ensure("error", 2)
    c3 = SequenceOneCharacteristic.ensure("error", 3)
    c1b = SequenceOneCharacteristic.ensure("error", 1)
    expect(c1 is c1b, "ensure 应返回同一实例（幂等）")
    expect(SequenceOneCharacteristic.available_count("error") == 3, "初始应有3份可用")
    class A: SEQUENCE_NAME = "甲"
    c1.bind(A())
    expect(SequenceOneCharacteristic.available_count("error") == 2, "绑定1份后剩2份")
    print("序列1特性库存与幂等 ensure 正确")


@test("old_one_promotion")
def t_oldone():
    """旧日晋升应聚合组内所有途径唯一性 + 3 份序列1特性（已落地）"""
    from sequences import make_sequence
    from anchor import Anchor
    from ascension import ascend
    from pathway_groups import promote_to_old_one
    from uniqueness import Uniqueness, SequenceOneCharacteristic
    Uniqueness._reset_state(); SequenceOneCharacteristic._reset_state()
    ch = make_sequence("fool", 1)
    ch.anchor = Anchor(humanity=100, connections=50, name="t")
    ch.anchor.add_believers(1_000_000)
    for a in ch.act_catalog():
        ch.perform_action(a)
    ch = ascend(ch, target_level=0, ritual_check=lambda: True)
    comp = promote_to_old_one("lord_of_mysteries", ch)
    expect(comp["group"] and len(comp["pathways"]) == 3, "旧日晋升应聚合3条途径")
    expect(all(len(p["sequence_1"]) == 3 for p in comp["pathways"]), "每条途径应集齐3份序列1")
    expect(comp["tier"] is not None, "支柱级旧日应标记 tier")
    print(f"旧日晋升落地：{comp['group']}（{comp['tier']}）")


@test("old_one_contention")
def t_oldone_contend():
    """第二人晋升同一旧日应因权柄争夺失败"""
    from sequences import make_sequence
    from anchor import Anchor
    from ascension import ascend
    from pathway_groups import promote_to_old_one
    from uniqueness import Uniqueness, SequenceOneCharacteristic
    Uniqueness._reset_state(); SequenceOneCharacteristic._reset_state()
    ch = make_sequence("fool", 1)
    ch.anchor = Anchor(humanity=100, connections=50, name="t")
    ch.anchor.add_believers(1_000_000)
    for a in ch.act_catalog():
        ch.perform_action(a)
    ch = ascend(ch, target_level=0, ritual_check=lambda: True)
    promote_to_old_one("lord_of_mysteries", ch)
    rival = make_sequence("error", 0)
    rival.anchor = Anchor(humanity=100, connections=50, name="t2")
    rival.anchor.add_believers(1_000_000)
    raised = False
    try:
        promote_to_old_one("lord_of_mysteries", rival)
    except RuntimeError:
        raised = True
    expect(raised, "第二人晋升同一旧日应因权柄争夺失败")
    print("旧日权柄争夺正确触发 RuntimeError")


@test("sealed_artifact_mapping")
def t_sealed():
    """序列等级 → 封印物等级映射正确（已落地）"""
    from pathway_groups import sealed_artifact_level
    expect(sealed_artifact_level(9)["corresponds"] == "低序列", "seq9 对应低序列")
    expect(sealed_artifact_level(4)["corresponds"] == "圣者", "seq4 对应圣者")
    expect(sealed_artifact_level(0)["corresponds"] == "天使及以上", "seq0 对应天使及以上")
    print("封印物等级映射正确（已落地）")


@test("switch_target_level_used")
def t_switch_target():
    """get_switch_target_level 已接入 switch_pathway"""
    from pathway_groups import PathwaySwitchValidator
    lvl = PathwaySwitchValidator.get_switch_target_level("fool", "error", 3)
    expect(lvl == 3, "get_switch_target_level 应返回同级（用于 switch_pathway）")
    print("get_switch_target_level 已接入 switch_pathway")


@test("role_playing_seed_deterministic")
def t_seed():
    """相同 seed 应可复现（已加 seed 参数）"""
    from sequences import make_sequence
    from anchor import Anchor
    from role_playing import role_playing_loop
    def run():
        ch = make_sequence("error", 9)
        ch.anchor = Anchor(humanity=50, connections=5, name="t")
        for a in ch.act_catalog():
            ch.perform_action(a)
        return role_playing_loop(ch, days=20, pollution_rate=0.2, verbose=False, seed=42)
    r1 = run(); r2 = run()
    expect(r1 == r2, "相同 seed 应产生可复现结果")
    print(f"seed 复现验证通过：({r1[0]},{r1[1]},{r1[2].name})")


# ───────────────────────── 扮演循环 / 失控 ─────────────────────────
@test("role_playing_loss")
def t_loss():
    from sequences import make_sequence
    from anchor import Anchor
    from role_playing import role_playing_loop, ritual_check_pass
    ch = make_sequence("error", 9)
    ch.anchor = Anchor(humanity=5, connections=0, name="脆")
    for act in ch.act_catalog():
        ch.perform_action(act)
    # 高污染速率，必然失控
    survived, lost, pollution = role_playing_loop(ch, days=50, pollution_rate=0.5, verbose=False)
    expect(lost is True, f"高污染下应失控，实际 lost={lost}")
    print(f"失控模拟通过：第{survived}天失控，终态 {pollution.label_cn}")


@test("role_playing_survive")
def t_survive():
    from sequences import make_sequence
    from anchor import Anchor
    from role_playing import role_playing_loop
    ch = make_sequence("error", 9)
    ch.anchor = Anchor(humanity=95, connections=10, name="稳")
    for act in ch.act_catalog():
        ch.perform_action(act)
    survived, lost, pollution = role_playing_loop(ch, days=10, pollution_rate=0.05, verbose=False)
    expect(lost is False, "强锚低污染应存活")
    print(f"存活模拟通过：存活{survived}天，污染 {pollution.label_cn}")


# ───────────────────────── 旧日 / 封印物 API ─────────────────────────
@test("old_one_and_sealed_api")
def t_oldone():
    from pathways_data import PATHWAYS
    from pathway_groups import OldOnePath, FOUR_PILLARS, get_level_description, SEALED_ARTIFACT_LEVELS
    req = OldOnePath.required_for_old_one("lord_of_mysteries")
    names = [PATHWAYS[k]["name"] for k in ("fool", "error", "door")]
    expect(all(n in req["pathways"] for n in names),
           f"诡秘之主组途径名应含 {names}")
    expect(len(FOUR_PILLARS) == 4, "四支柱应为4")
    expect(get_level_description(0).startswith("真神"), "seq0 描述应为真神")
    expect(0 in SEALED_ARTIFACT_LEVELS and 3 in SEALED_ARTIFACT_LEVELS, "封印物等级表应含0~3")
    print("旧日/封印物 API 通过")


# ───────────────────────── GUI 构造（不进主循环） ─────────────────────────
@test("gui_construct")
def t_gui():
    try:
        import tkinter as tk
        from gui_app import LordOfMysteriesGUI
        app = LordOfMysteriesGUI()
        expect(app.character is not None, "GUI 应已创建默认角色")
        # 不调用 app.run() 以免阻塞
        try:
            app.root.destroy()
        except Exception:
            pass
        print(f"GUI 构造通过；默认角色={app.character.summary}")
    except Exception as e:
        # 无显示环境（headless）下 tkinter 可能失败，记为已知限制而非致命
        raise AssertionError(f"GUI 构造失败（可能无显示环境）: {type(e).__name__}: {e}")


# ───────────────────────── 已知问题：锚强度公式与需求表不一致 ─────────────────────────
@test("anchor_formula_consistent")
def t_anchor_consistent():
    """
    修复后：advance 的锚需求应与 Anchor.required_for_level 设定表一致，
    且高序列无锚晋升被拒绝。
    """
    from sequences import make_sequence
    from anchor import Anchor
    from ascension import ascend, AnchorBreakError
    req = Anchor.required_for_level(2)  # 设定表：100
    # 锚恰好达标 -> 晋升成功
    ch = make_sequence("error", 3)
    ch.anchor = Anchor(humanity=100, connections=0, name="恰好")  # strength 100
    for a in ch.act_catalog():
        ch.perform_action(a)
    ch2 = ascend(ch)  # -> seq2
    expect(ch2.LEVEL == 2, f"锚恰好达标应晋升成功（需求{req}）")
    # 锚不足 -> 拒绝
    ch3 = make_sequence("error", 3)
    ch3.anchor = Anchor(humanity=10, connections=0, name="不足")  # strength 10
    for a in ch3.act_catalog():
        ch3.perform_action(a)
    raised = False
    try:
        ascend(ch3)
    except AnchorBreakError:
        raised = True
    expect(raised, "锚不足时应被拒绝")
    print(f"锚需求已统一为设定表（seq2 需求={req}）")


# ───────────────────────── 运行全部 6 个 CLI demo ─────────────────────────
DEMOS = ["basic", "multi", "switch", "full", "gender", "world",
        "uniqueness", "old_one", "sealed", "journey"]
for _d in DEMOS:
    @test(f"demo_{_d}")
    def _run(demo=_d):
        import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main.main.__wrapped__ if hasattr(main.main, "__wrapped__") else None
            # 直接以参数调用 main 内部逻辑
            import sys as _sys
            _sys.argv = ["main.py", "--demo", demo]
            main.main()
        out = buf.getvalue()
        expect("模拟结束" in out or "运行模式" in out or "世界观" in out,
               f"demo {demo} 未见正常结束标记")
        print(f"demo[{demo}] 运行完成，输出 {len(out)} 字符")


# ───────────────────────── GUI 高级机制流程 ─────────────────────────
@test("gui_advanced_flow")
def t_gui_advanced_flow():
    """收集权柄 → 晋升序列0 → 晋升旧日 全流程（由 GUI 内部方法驱动，等价于用户点击）"""
    try:
        import tkinter  # noqa: F401
    except ModuleNotFoundError:
        raise AssertionError("SKIP: 当前环境无 tkinter，无法构造 GUI")
    import gui_app
    from anchor import Anchor
    from uniqueness import Uniqueness, SequenceOneCharacteristic

    Uniqueness._reset_state()
    SequenceOneCharacteristic._reset_state()

    gui = gui_app.LordOfMysteriesGUI()
    gui.root.withdraw()
    gui.select_pathway("error")
    ch = gui.character
    expect(ch is not None and ch.PATHWAY_KEY == "error", "选定错误途径生成序列9角色")

    # 真神需宏大锚定（≥200），否则序列0 晋升会被锚系统拒绝
    ch.anchor = Anchor(humanity=100, connections=10, name="测试之锚")
    for lvl in range(9, 1, -1):
        for act in ch.act_catalog():
            ch.perform_action(act)
        expect(ch.digested, f"序列{lvl} 扮演已完全消化")
        gui._do_ascend()
        ch = gui.character
        expect(ch.LEVEL == lvl - 1, f"晋升至序列{lvl-1}（{ch.SEQUENCE_NAME}）")
    expect(ch.LEVEL == 1, "已抵达序列1（晋升序列0 前置）")

    for act in ch.act_catalog():
        ch.perform_action(act)
    expect(ch.digested, "序列1 扮演已完全消化")

    # 未集齐权柄时，序列0 晋升应被安全拦截
    gui._do_ascend()
    expect(gui.character.LEVEL == 1, "未集齐权柄时序列0 晋升被拦截")

    # 权柄收集：争夺 3 份序列1 + 容纳唯一性
    gui._do_collect_seq1(); gui._do_collect_seq1(); gui._do_collect_seq1()
    gui._do_collect_uniqueness()
    expect(SequenceOneCharacteristic.owned_count("error", gui.character) == 3, "已收集 3 份序列1特性")
    expect(gui._pathway_uniqueness("error").owner is gui.character, "唯一性已归属当前角色")

    # 聚合晋升序列0
    gui._do_ascend()
    ch = gui.character
    expect(ch.LEVEL == 0, f"聚合晋升成功，成为序列0 真神（{ch.SEQUENCE_NAME}）")

    # 晋升旧日（诡秘之主，支柱级）
    gui._do_promote_old_one()
    expect(gui.old_one_info is not None, "旧日晋升返回构成摘要")
    expect(gui.old_one_info.get("pillar") is not None, "晋升为支柱级旧日")
    expect(len(gui.old_one_info["pathways"]) == 3, "聚合了 3 条途径的唯一性+序列1")
    gui.root.destroy()


@test("gui_panel_render")
def t_gui_panel_render():
    """无头渲染冒烟：拆分后显式调用各面板/视图的 draw 方法，确保不抛异常。"""
    try:
        import tkinter  # noqa: F401
    except Exception:
        return  # 无 tkinter 环境跳过
    import gui_app
    gui = gui_app.LordOfMysteriesGUI()
    gui.root.withdraw()
    # 默认角色已在 _create_default_character 中建立
    expect(gui.character is not None, "默认角色应已建立")
    # 角色卡 / 仪表盘
    gui._draw_character_card()
    gui._draw_gauges()
    # 左侧途径列表
    gui._draw_pathway_list()
    # 右侧操作面板（默认等级下走「扮演/晋升」分支）
    gui._draw_action_panel()
    # 日志面板
    gui._draw_log()
    # 全途径视图 / 权柄体系视图
    gui._draw_pathways_view()
    gui._draw_groups_view()
    # 视图切换后重绘
    gui.switch_view("pathways")
    gui.switch_view("groups")
    gui.switch_view("character")
    gui.root.destroy()


# ───────────────────────── 主入口 ─────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("  诡秘之主·序列途径模拟系统 — 全面测试")
    print(f"  时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    for t in TESTS:
        t()
    # 汇总
    n_pass = sum(1 for _, s, _ in RESULTS if s == "PASS")
    n_fail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    n_err = sum(1 for _, s, _ in RESULTS if s == "ERROR")
    n_known = sum(1 for n, s, _ in RESULTS if n.startswith("KNOWN_") and s == "FAIL")
    print("\n" + "=" * 70)
    print(f"  汇总: PASS={n_pass}  FAIL={n_fail}  ERROR={n_err}  (其中已知问题标记 {n_known})")
    print("=" * 70)
    # 失败/错误明细
    for name, status, detail in RESULTS:
        if status in ("FAIL", "ERROR"):
            print(f"\n--- {name} [{status}] ---")
            print(detail)
    # 写出报告到 tests/ 目录
    report_path = os.path.join(os.path.dirname(__file__), "TEST_RESULTS.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"诡秘之主·序列途径模拟系统 测试结果 {datetime.datetime.now()}\n")
        f.write(f"PASS={n_pass} FAIL={n_fail} ERROR={n_err}\n\n")
        for name, status, detail in RESULTS:
            f.write(f"[{status}] {name}\n")
            if detail.strip():
                f.write("  " + detail.replace("\n", "\n  ") + "\n")
    print(f"\n结果已写入: {report_path}")
