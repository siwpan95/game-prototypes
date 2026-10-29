#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B3 内容满量 验收脚本 (standalone acceptance gate for B3 content files).

用法:
    python tools/validate_b3.py content/cards_dynasty.json
    python tools/validate_b3.py content/cards_modern.json
    python tools/validate_b3.py content/events_early.json
    python tools/validate_b3.py content/events_adult.json

自动识别模式:
    - 顶层含 "cards"        -> 卡牌模式 (15 项 gate)
    - 顶层含 "event_templates" -> 事件模式 (11 项 gate)

退出码: 全部通过 = 0, 有失败 = 1。team-lead 用它作为交付门槛。
"""
import json
import sys
import os

CARD_DIMS = {
    "STRENGTH", "INTELLIGENCE", "CHARISMA", "WEALTH", "MORALITY",
    "STABILITY", "CHURCH", "NOBLES", "COMMONERS", "HEALTH", "HAPPINESS",
}
EVENT_STATS = {
    "strength", "intelligence", "charisma", "wealth", "happiness",
    "luck", "agility", "health",
}
EVENT_MBTI = {"EI", "SN", "TF", "JP"}
EVENT_KEYS = EVENT_STATS | EVENT_MBTI

DONE = []


def ok(cond, name, detail=""):
    DONE.append((bool(cond), name, detail))
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" -- {detail}" if detail else ""))


# ---------------- 卡牌 gate ----------------
def validate_cards(path, expect_prefix, expect_era, expect_total=52):
    data = json.load(open(path, encoding="utf-8"))
    cards = data.get("cards", [])
    n = len(cards)
    ok(n == expect_total, f"count == {expect_total}", f"got {n}")

    ids = [c.get("id") for c in cards]
    ok(len(set(ids)) == n, "ids unique", f"{n - len(set(ids))} dup")

    pf = [i for i in ids if not (isinstance(i, str) and i.startswith(expect_prefix))]
    ok(not pf, f"id prefix == {expect_prefix}", f"bad: {pf[:5]}")

    eras = set(c.get("era") for c in cards)
    ok(eras == {expect_era}, f"era == {expect_era}", f"got {eras}")

    bad_keys, bad_range = [], []
    missing_side = []
    for c in cards:
        for side in ("left_choice", "right_choice"):
            s = c.get(side)
            if not isinstance(s, dict):
                missing_side.append((c.get("id"), side))
                continue
            ef = s.get("effects", {})
            for k, v in ef.items():
                if k not in CARD_DIMS:
                    bad_keys.append((c.get("id"), side, k))
                else:
                    if not (-25 <= v <= 25):
                        bad_range.append((c.get("id"), side, k, v))
    ok(not missing_side, "left/right choice present", f"missing {missing_side[:5]}")
    ok(not bad_keys, "effect keys in 11 UPPERCASE dims", f"bad {bad_keys[:5]}")
    ok(not bad_range, "effect values in [-25,25]", f"bad {bad_range[:5]}")

    # tradeoff: left vs right effects differ
    tradeoff = 0
    for c in cards:
        l = c.get("left_choice", {}).get("effects", {})
        r = c.get("right_choice", {}).get("effects", {})
        if l != r:
            tradeoff += 1
    ok(tradeoff == n, "every card has a real tradeoff (L != R)", f"{tradeoff}/{n}")

    # categories 6 个, 每个 8-10
    from collections import Counter
    cats = Counter(c.get("category") for c in cards)
    ok(len(cats) == 6, "6 categories", f"got {len(cats)}: {dict(cats)}")
    bad_cat = {k: v for k, v in cats.items() if not (8 <= v <= 10)}
    ok(not bad_cat, "each category 8-10 cards", f"off: {bad_cat}")

    # conditions: >=12 张带非空 conditions
    cond = sum(1 for c in cards if c.get("conditions") and (
        c["conditions"].get("required_traits") or
        any(k.startswith("min_") for k in c["conditions"])
    ))
    ok(cond >= 12, ">=12 cards with conditions", f"got {cond}")

    # required fields present
    req = ["title", "description", "weight", "tags"]
    miss = [(c.get("id"), f) for c in cards for f in req if f not in c]
    ok(not miss, "title/description/weight/tags present", f"missing {miss[:5]}")

    # uniqueness of text
    titles = [c.get("title") for c in cards]
    ok(len(set(titles)) == n, "titles unique", f"{n - len(set(titles))} dup")
    descs = [c.get("description") for c in cards]
    ok(len(set(descs)) == n, "descriptions unique", f"{n - len(set(descs))} dup")

    speech = [c.get("left_choice", {}).get("speech") for c in cards]
    ok(all(speech), "speech present on left_choice", f"{sum(1 for s in speech if not s)} missing")


# ---------------- 事件 gate ----------------
def validate_events(path, expect_total):
    data = json.load(open(path, encoding="utf-8"))
    et = data.get("event_templates", {})

    # flatten all events
    all_events = []
    pool_counts = {}
    for grp, val in et.items():
        if isinstance(val, list):
            items = val
        elif isinstance(val, dict):
            items = []
            for sub, lst in val.items():
                items.extend(lst)
                pool_counts[f"{grp}.{sub}"] = len(lst)
        else:
            items = []
        pool_counts[grp] = len(items) if isinstance(val, list) else sum(
            len(x) for x in val.values()) if isinstance(val, dict) else 0
        all_events.extend(items)

    total = len(all_events)
    ok(total >= expect_total, f"total events >= {expect_total}", f"got {total}")
    print("  pool counts:", pool_counts)

    bad_keys, bad_range = [], []
    d_count = 0
    feedback_all = []
    descs = []
    for ev in all_events:
        opts = ev.get("options", {})
        if "D" in opts:
            d_count += 1
        for okey, o in opts.items():
            ef = o.get("effects", {})
            for k, v in ef.items():
                if k not in EVENT_KEYS:
                    bad_keys.append((ev.get("id"), okey, k))
                else:
                    if k in EVENT_STATS:
                        lo, hi = (-10, 10) if k == "health" else (-3, 3)
                    else:
                        lo, hi = -2, 2
                    if not (lo <= v <= hi):
                        bad_range.append((ev.get("id"), okey, k, v))
            fb = o.get("feedback", [])
            feedback_all.extend(fb)
        descs.append(ev.get("desc"))

    ok(not bad_keys, "effect keys lowercase+MBTI only", f"bad {bad_keys[:5]}")
    ok(not bad_range, "effect ranges valid", f"bad {bad_range[:5]}")

    ratio = d_count / total if total else 0
    ok(ratio >= 0.20, ">=20% events have D option", f"{d_count}/{total} = {ratio:.0%}")

    ok(len(set(feedback_all)) == len(feedback_all), "feedback all unique",
       f"{len(feedback_all) - len(set(feedback_all))} dup")

    ok(len(set(descs)) == total, "descriptions unique", f"{total - len(set(descs))} dup")

    # ids unique
    eids = [e.get("id") for e in all_events]
    ok(len(set(eids)) == total, "event ids unique", f"{total - len(set(eids))} dup")


# ---------------- main ----------------
def main():
    if len(sys.argv) < 2:
        print("usage: validate_b3.py <file.json> [expect_total]")
        sys.exit(2)
    path = sys.argv[1]
    expect = int(sys.argv[2]) if len(sys.argv) > 2 else None
    if not os.path.exists(path):
        print(f"FILE NOT FOUND: {path}")
        sys.exit(1)
    data = json.load(open(path, encoding="utf-8"))
    if "cards" in data:
        prefix = "mod_" if "modern" in path else "dyn_"
        era = "modern" if "modern" in path else "dynasty"
        validate_cards(path, prefix, era, expect or 52)
    elif "event_templates" in data:
        validate_events(path, expect or 0)
    else:
        print("UNKNOWN schema (no 'cards' / 'event_templates')")
        sys.exit(1)

    fails = [d for d in DONE if not d[0]]
    print(f"\n=== {len(DONE) - len(fails)}/{len(DONE)} gates passed ===")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
