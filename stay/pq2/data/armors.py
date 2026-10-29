"""护甲数据"""

from ..types import Item

ARMORS = [
    Item("Lace",         1),
    Item("Macrame",      2),
    Item("Burlap",       3),
    Item("Canvas",       4),
    Item("Flannel",      5),
    Item("Chamois",      6),
    Item("Pleathers",    7),
    Item("Leathers",     8),
    Item("Bearskin",     9),
    Item("Ringmail",     10),
    Item("Scale Mail",   12),
    Item("Chainmail",    14),
    Item("Splint Mail",  15),
    Item("Platemail",    16),
    Item("ABS",          17),
    Item("Kevlar",       18),
    Item("Titanium",     19),
    Item("Mithril Mail", 20),
    Item("Diamond Mail", 25),
    Item("Plasma",       30),
]


def get_random_armor(rng):
    return rng.choice(ARMORS)
