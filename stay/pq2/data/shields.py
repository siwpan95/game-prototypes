"""盾牌数据"""

from ..types import Item

SHIELDS = [
    Item("Parasol",         0),
    Item("Pie Plate",       1),
    Item("Garbage Can Lid", 2),
    Item("Buckler",         3),
    Item("Plexiglass",      4),
    Item("Fender",          4),
    Item("Round Shield",    5),
    Item("Carapace",        5),
    Item("Scutum",          6),
    Item("Propugner",       6),
    Item("Kite Shield",     7),
    Item("Pavise",          8),
    Item("Tower Shield",    9),
    Item("Baroque Shield",  11),
    Item("Aegis",           12),
    Item("Magnetic Field",  18),
]


def get_random_shield(rng):
    return rng.choice(SHIELDS)
