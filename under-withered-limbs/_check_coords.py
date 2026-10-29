import json

with open('data/mansion_map.txt', encoding='utf-8') as f:
    lines = f.read().strip('\n').split('\n')

with open('data/mansion_objects.json', encoding='utf-8') as f:
    obj = json.load(f)

print('=== interactives ===')
for item in obj['interactives']:
    c, r = item['col'], item['row']
    char = item['char']
    if 0 <= r < len(lines) and c + len(char) <= len(lines[r]):
        actual = lines[r][c:c+len(char)]
    else:
        actual = 'OUT'
    status = 'OK' if actual == char else f'MISMATCH actual="{actual}"'
    print(f'  {item["id"]:20} JSON=({c:2},{r:2})  char="{char}"  {status}')

print()
print('=== memory_questions ===')
for item in obj['memory_questions']:
    c, r = item['col'], item['row']
    char = item['char']
    actual = lines[r][c] if 0 <= r < len(lines) and 0 <= c < len(lines[r]) else 'OUT'
    status = 'OK' if actual == char else f'MISMATCH actual="{actual}"'
    print(f'  {item["id"]:20} JSON=({c:2},{r:2})  char="{char}"  {status}')

print()
print('=== cards on map ===')
card_placements = {
    "old_woman_01": (35, 11),
    "strange_symbol_01": (37, 27),
    "doll_01": (6, 5),
    "dead_vole_01": (4, 13),
    "grave_01": (35, 2),
    "hut_01": (2, 15),
    "garden_tools_01": (2, 16),
    "owl_01": (35, 6),
    "key_01": (34, 17),
    "lizard_01": (30, 15),
    "owl_statue_01": (34, 7),
    "full_moon_01": (20, 1),
    "treasure_chest_01": (5, 21),
    "lavender_01": (12, 8),
    "suspicious_hole_01": (20, 15),
    "vole_01": (3, 15),
    "wooden_statue_01": (28, 8),
}
for cid, (c, r) in card_placements.items():
    actual = lines[r][c] if 0 <= r < len(lines) and 0 <= c < len(lines[r]) else 'OUT'
    print(f'  {cid:20} ({c:2},{r:2})  map_char="{actual}"')
