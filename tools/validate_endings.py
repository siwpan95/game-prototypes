# -*- coding: utf-8 -*-
"""
tools/validate_endings.py — 结局解析器回归验证

验证目标：
    1. 60 个结局全部可加载，priority 降序排列无误
    2. 旧版 12 个硬编码结局（legacy_tag）在等价条件下仍能被触发（R7 兼容）
    3. 兜底结局在极端空玩家下仍能返回，永不 None
    4. record_ending / collection_summary 写入正确
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import endings as E  # noqa: E402


class FakePlayer:
    """最小玩家桩，字段与 main.Player / game_gui.Player 对齐。"""

    def __init__(self, **kw):
        self.name = "测试者"
        self.age = 60
        self.wealth = 5
        self.happiness = 5
        self.charisma = 5
        self.intelligence = 5
        self.strength = 5
        self.agility = 5
        self.luck = 5
        self.health = 80
        self.career_tier = 0
        self.career_id = None
        self.education = "none"
        self.traits = []
        self.relationships = {"parent": 60, "partner": 0, "friend": 40}
        self.decision_tree = None
        self.game_mode = "traditional"
        self.score = 0
        for k, v in kw.items():
            setattr(self, k, v)


class FakeDim:
    """模拟 decision_tree.dimensions（键为 Dimension 枚举）。"""

    def __init__(self, **dims):
        try:
            from decision_tree import Dimension
        except Exception:
            self.dimensions = {}
            self.year = 0
            self.history = []
            return
        self.dimensions = {}
        for name, val in dims.items():
            member = getattr(Dimension, name, None)
            if member is not None:
                self.dimensions[member] = val
        self.year = 20
        self.history = []


def main() -> int:
    fails = []

    # ── 1. 加载完整性 ──
    all_e = E.all_endings()
    print(f"[1] 结局加载：{len(all_e)} 个", end="")
    if len(all_e) < 60:
        fails.append(f"结局数不足：{len(all_e)} < 60")
        print("  ✗")
    else:
        print("  ✓")

    pris = [getattr(e, "priority", 0) for e in all_e]
    if pris != sorted(pris, reverse=True):
        fails.append("priority 未按降序排列")
        print("[1b] priority 降序  ✗")
    else:
        print(f"[1b] priority 降序：{pris[0]} → {pris[-1]}  ✓")

    # ── 2. 旧版硬编码结局等价触发（R7） ──
    print("\n[2] 旧版硬编码结局回归：")
    legacy_cases = [
        # (说明, 玩家参数, 期望 legacy_tag)
        ("传统-富甲受爱戴", dict(wealth=13, charisma=9, age=70), "wealth_charisma"),
        ("传统-伟大学者", dict(intelligence=13, age=70, charisma=5), "intelligence"),
        ("传统-传说冒险家", dict(strength=13, agility=9, age=65), "strength_agility"),
        ("传统-快乐隐士", dict(wealth=2, happiness=11, age=70), "poor_happy"),
        ("传统-大贤者", dict(traits=["神秘知识"], intelligence=11, age=70), "mystery_sage"),
        ("传统-人生遗憾", dict(happiness=1, age=70), "regret"),
        ("王权-教会圣王", dict(game_mode="reigns", decision_tree=FakeDim(CHURCH=95)), "reigns_church"),
        ("王权-平民之王", dict(game_mode="reigns", decision_tree=FakeDim(COMMONERS=90)), "reigns_people"),
        ("王权-暴君", dict(game_mode="reigns", decision_tree=FakeDim(MORALITY=10)), "reigns_tyrant"),
        ("王权-国库空虚", dict(game_mode="reigns", decision_tree=FakeDim(WEALTH=3, MORALITY=50)), "reigns_corrupt"),
        ("王权-平衡统治", dict(game_mode="reigns", decision_tree=FakeDim(STABILITY=60, MORALITY=50, WEALTH=50)), "reigns_balanced"),
        ("修行-飞升", dict(game_mode="cultivation", age=100, health=90, intelligence=10, happiness=15), "ascend"),
    ]
    for desc, kw, expect_tag in legacy_cases:
        p = FakePlayer(**kw)
        e = E.resolve(p)
        got_tag = getattr(e, "legacy_tag", None) if e else None
        ok = got_tag == expect_tag
        mark = "✓" if ok else "✗"
        got_name = getattr(e, "name", "None") if e else "None"
        print(f"  {mark} {desc:16s} → {got_name:12s} (tag={got_tag})")
        if not ok:
            fails.append(f"{desc}: 期望 tag={expect_tag}，实得 {got_tag}")

    # ── 3. 兜底：空玩家永不 None ──
    print("\n[3] 兜底测试：")
    edge_cases = [
        ("全零玩家", FakePlayer(age=0, wealth=0, happiness=0, charisma=0,
                             intelligence=0, strength=0, agility=0, luck=0, health=0)),
        ("中庸玩家", FakePlayer(age=40, wealth=5, happiness=5)),
        ("无属性对象", type("Bare", (), {})()),
    ]
    for desc, p in edge_cases:
        try:
            e = E.resolve(p)
            ok = e is not None
            print(f"  {'✓' if ok else '✗'} {desc:12s} → {getattr(e, 'name', 'None')}")
            if not ok:
                fails.append(f"{desc} 返回 None")
        except Exception as ex:
            print(f"  ✗ {desc:12s} → 抛异常 {type(ex).__name__}: {ex}")
            fails.append(f"{desc} 抛异常 {ex}")

    # ── 4. 职业门类反查 ──
    print("\n[4] 职业门类结局：")
    career_cases = [
        ("院士", dict(career_id="car_acad_academician", career_tier=5, age=65), "academic"),
        ("特聘专家", dict(career_id="car_med_expert", career_tier=5, age=60), "medical"),
        ("阶下囚", dict(career_id="car_gray_inmate", career_tier=5, age=45), "gray"),
    ]
    for desc, kw, expect_cat in career_cases:
        p = FakePlayer(**kw)
        ctx = E.build_context(p)
        got = ctx.get("career_category")
        ok = got == expect_cat
        e = E.resolve(p)
        print(f"  {'✓' if ok else '✗'} {desc:8s} career_id={kw['career_id']} → category={got} → 结局「{getattr(e,'name','?')}」")
        if not ok:
            fails.append(f"{desc}: 门类反查失败，期望 {expect_cat} 实得 {got}")

    # ── 5. record_ending / collection_summary ──
    print("\n[5] 档案写入：")
    prof = {"seen_endings": [], "stats": {}}
    e1 = E.resolve(FakePlayer(wealth=13, charisma=9, age=70))
    r1 = E.record_ending(prof, e1)
    r2 = E.record_ending(prof, e1)  # 重复写入
    ok = r1["is_new"] and not r2["is_new"] and prof["stats"]["total_endings"] == 1
    print(f"  {'✓' if ok else '✗'} 去重写入：首次 is_new={r1['is_new']}，重复 is_new={r2['is_new']}，"
          f"total={prof['stats']['total_endings']}")
    if not ok:
        fails.append("record_ending 去重逻辑异常")

    summ = E.collection_summary(prof)
    ok2 = summ["total"] == len(all_e) and summ["seen"] == 1
    print(f"  {'✓' if ok2 else '✗'} 图鉴统计：{summ['seen']}/{summ['total']}，"
          f"分类数={len(summ['by_category'])}")
    if not ok2:
        fails.append("collection_summary 统计异常")

    # ── 6. 多结局命中 ──
    print("\n[6] 副结局提示：")
    p = FakePlayer(wealth=13, charisma=9, intelligence=13, age=70)
    multi = E.resolve_all_matching(p, limit=5)
    print(f"  命中 {len(multi)} 个：{ '、'.join(getattr(m,'name','?') for m in multi) }")
    if len(multi) < 2:
        fails.append("resolve_all_matching 未返回多个命中")

    # ── 汇总 ──
    print("\n" + "=" * 56)
    if fails:
        print(f"✗ 失败 {len(fails)} 项：")
        for f in fails:
            print(f"   - {f}")
        return 1
    print("✓ 结局解析器全部验证通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
