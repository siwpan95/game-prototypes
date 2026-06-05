import json

with open('data/mansion_map.txt', encoding='utf-8') as f:
    lines = f.read().strip('\n').split('\n')

with open('data/mansion_objects.json', encoding='utf-8') as f:
    obj = json.load(f)

card_placements = {
    'old_woman_01': (35, 11), 'strange_symbol_01': (37, 27), 'doll_01': (6, 5),
    'dead_vole_01': (4, 13), 'grave_01': (35, 2), 'hut_01': (2, 15),
    'garden_tools_01': (2, 16), 'owl_01': (35, 6), 'key_01': (34, 17),
    'lizard_01': (30, 15), 'owl_statue_01': (34, 7), 'full_moon_01': (20, 1),
    'treasure_chest_01': (5, 21), 'lavender_01': (12, 8), 'suspicious_hole_01': (20, 15),
    'vole_01': (3, 15), 'wooden_statue_01': (28, 8),
}

print('=== card placements ===')
for cid, (c, r) in card_placements.items():
    if 0 <= r < len(lines) and 0 <= c < len(lines[r]):
        actual = lines[r][c]
        is_space = actual in ['░', '暗', ' ']
        status = 'HIDDEN' if is_space else f'VISIBLE char="{actual}"'
    else:
        status = f'OUT (row len={len(lines[r]) if 0<=r<len(lines) else "N/A"})'
    print(f'  {cid:20} ({c:2},{r:2})  {status}')
