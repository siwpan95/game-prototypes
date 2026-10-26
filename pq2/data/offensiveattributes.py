"""攻击属性数据"""

from ..types import Attribute

GOOD_OFFENSIVE_ATTRIBUTES = [
    Attribute("Polished",  1),
    Attribute("Serrated",  1),
    Attribute("Heavy",     1),
    Attribute("Pronged",   2),
    Attribute("Steely",    2),
    Attribute("Vicious",   3),
    Attribute("Venomed",   4),
    Attribute("Stabbity",  4),
    Attribute("Dancing",   5),
    Attribute("Invisible", 6),
    Attribute("Vorpal",    7),
]

BAD_OFFENSIVE_ATTRIBUTES = [
    Attribute("Dull",       -2),
    Attribute("Tarnished",  -1),
    Attribute("Rusty",      -3),
    Attribute("Padded",     -5),
    Attribute("Bent",       -4),
    Attribute("Mini",       -4),
    Attribute("Rubber",     -6),
    Attribute("Nerf",       -7),
    Attribute("Unbalanced", -2),
]


def get_random_good_offensive_attribute(rng):
    return rng.choice(GOOD_OFFENSIVE_ATTRIBUTES)


def get_random_bad_offensive_attribute(rng):
    return rng.choice(BAD_OFFENSIVE_ATTRIBUTES)
