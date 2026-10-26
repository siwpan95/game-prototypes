"""防御属性数据"""

from ..types import Attribute

GOOD_DEFENSIVE_ATTRIBUTES = [
    Attribute("Studded",    1),
    Attribute("Banded",     2),
    Attribute("Gilded",     2),
    Attribute("Festooned",  3),
    Attribute("Holy",       4),
    Attribute("Cambric",    1),
    Attribute("Fine",       4),
    Attribute("Impressive", 5),
    Attribute("Custom",     3),
]

BAD_DEFENSIVE_ATTRIBUTES = [
    Attribute("Holey",      -1),
    Attribute("Patched",    -1),
    Attribute("Threadbare", -2),
    Attribute("Faded",      -1),
    Attribute("Rusty",      -3),
    Attribute("Motheaten",  -3),
    Attribute("Mildewed",   -2),
    Attribute("Torn",       -3),
    Attribute("Dented",     -3),
    Attribute("Cursed",     -5),
    Attribute("Plastic",    -4),
    Attribute("Cracked",    -4),
    Attribute("Warped",     -3),
    Attribute("Corroded",   -3),
]


def get_random_good_defensive_attribute(rng):
    return rng.choice(GOOD_DEFENSIVE_ATTRIBUTES)


def get_random_bad_defensive_attribute(rng):
    return rng.choice(BAD_DEFENSIVE_ATTRIBUTES)
