"""Verify maze dimensions"""
def row(chars):
    assert len(chars) == 20, f'Row has {len(chars)} characters: {repr(chars)}'
    return chars

maze = [
    row('####################'),  # 0
    row('#..................#'),  # 1
    row('#.##..####..##..##.#'),  # 2
    row('#.##.#......#...#..#'),  # 3
    row('#....######.......##'),  # 4
    row('###.#......#.#...###'),  # 5
    row('#...#.####.#.#.....#'),  # 6
    row('#..................#'),  # 7
    row('#....######.#..#...#'),  # 8
    row('###.#......#.#...###'),  # 9
    row('#....######.......##'),  # 10
    row('#.##.#......#...#..#'),  # 11
    row('#.##..####..##.##..#'),  # 12
    row('#..................#'),  # 13
    row('####################'),  # 14
]

print(f'Total rows: {len(maze)}')
for i, r in enumerate(maze):
    print(f'  "{r}",  # {i}')
print('All verified!')

# Print as Python list
print('\nMAZE = [')
for i, r in enumerate(maze):
    comma = ',' if i < len(maze) - 1 else ','
    print(f'    "{r}"{comma}  # {i}')
print(']')
