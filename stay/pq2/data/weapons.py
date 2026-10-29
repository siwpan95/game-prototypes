"""武器数据"""

from ..types import Item

WEAPONS = [
    Item("Stick",         0),
    Item("Broken Bottle", 1),
    Item("Shiv",          1),
    Item("Sprig",         1),
    Item("Oxgoad",        1),
    Item("Eelspear",      2),
    Item("Bowie Knife",   2),
    Item("Claw Hammer",   2),
    Item("Handpeen",      2),
    Item("Andiron",       3),
    Item("Hatchet",       3),
    Item("Tomahawk",      3),
    Item("Hackbarm",      3),
    Item("Crowbar",       4),
    Item("Mace",          4),
    Item("Battleadze",    4),
    Item("Leafmace",      5),
    Item("Shortsword",    5),
    Item("Longiron",      5),
    Item("Poachard",      5),
    Item("Baselard",      5),
    Item("Whinyard",      6),
    Item("Blunderbuss",   6),
    Item("Longsword",     6),
    Item("Crankbow",      6),
    Item("Blibo",         7),
    Item("Broadsword",    7),
    Item("Kreen",         7),
    Item("Morning Star",  8),
    Item("Pole-adze",     8),
    Item("Spontoon",      8),
    Item("Bastard Sword", 9),
    Item("Peen-arm",      9),
    Item("Culverin",      10),
    Item("Lance",         10),
    Item("Halberd",       11),
    Item("Poleax",        12),
    Item("Bandyclef",     15),
]


def get_random_weapon(rng):
    return rng.choice(WEAPONS)
