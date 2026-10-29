"""Verify card data loading and description generation."""
from excel_loader import load_cards_by_pool
from card_factory import generate_card_description, KEYWORD_CN_MAP

pools = load_cards_by_pool("config", "data")
total = 0

# Count keyword/bc/dr usage
kw_count = {k: 0 for k in KEYWORD_CN_MAP}
bc_count = {}
dr_count = {}
rarity_count = {}

for pn in ("B", "A", "C"):
    cards = pools.get(pn, [])
    total += len(cards)
    print(f"\n=== Pool {pn} ({len(cards)} 张) ===")
    for c in cards:
        desc = generate_card_description(c)
        kw = c.get("keywords", [])
        bc = c.get("battlecry")
        dr = c.get("deathrattle")
        r = c.get("rarity", "common")
        rarity_count[r] = rarity_count.get(r, 0) + 1

        # Count keywords
        for k in kw:
            kk = k.lower().replace(" ", "_")
            if kk in kw_count:
                kw_count[kk] += 1

        # Count battlecries
        if bc:
            t = bc.get("type", "?")
            bc_count[t] = bc_count.get(t, 0) + 1

        # Count deathrattles
        if dr:
            t = dr.get("type", "?")
            dr_count[t] = dr_count.get(t, 0) + 1

        extras = []
        if kw:
            extras.append(f"kw:[{','.join(kw)}]")
        if bc:
            extras.append(f"bc:{bc}")
        if dr:
            extras.append(f"dr:{dr}")
        ext = " | ".join(extras) if extras else ""
        atk = c.get("attack", 0)
        hp_val = c.get("health", 0)
        print(f"  {c['id']:<20s} {c['name']:<8s} {c['cost']}费 {c['type']:<6s} {r:<8s} "
              f"{atk}/{hp_val}  | {desc} {ext}")

print(f"\n{'='*60}")
print(f"总计: {total} 张卡牌")

print(f"\n稀有度分布: {rarity_count}")

print(f"\n关键词覆盖: {len([v for v in kw_count.values() if v > 0])}/{len(kw_count)}")
for k, v in sorted(kw_count.items()):
    status = "[v]" if v > 0 else "[ ]"
    print(f"  {status} {KEYWORD_CN_MAP[k]:<8s} ({k:<16s}): {v} cards")

print(f"\nbattlecry coverage: {len(bc_count)} types")
for k, v in sorted(bc_count.items()):
    print(f"  [v] {k:<22s}: {v} cards")

print(f"\ndeathrattle coverage: {len(dr_count)} types")
for k, v in sorted(dr_count.items()):
    print(f"  [v] {k:<22s}: {v} cards")
