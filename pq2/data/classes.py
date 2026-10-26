"""职业数据"""

from ..types import Class

CLASSES = [
    Class("Ur-Paladin",       ["WIS", "CON"]),
    Class("Voodoo Princess",  ["INT", "CHA"]),
    Class("Robot Monk",       ["STR"]),
    Class("Mu-Fu Monk",       ["DEX"]),
    Class("Mage Illusioner",  ["INT", "MP Max"]),
    Class("Shiv-Knight",      ["DEX"]),
    Class("Inner Mason",      ["CON"]),
    Class("Fighter/Organist", ["CHA", "STR"]),
    Class("Puma Burgular",    ["DEX"]),
    Class("Runeloremaster",   ["WIS"]),
    Class("Hunter Strangler", ["DEX", "INT"]),
    Class("Battle-Felon",     ["STR"]),
    Class("Tickle-Mimic",     ["WIS", "INT"]),
    Class("Slow Poisoner",    ["CON"]),
    Class("Bastard Lunatic",  ["CON"]),
    Class("Jungle Clown",     ["DEX", "CHA"]),
    Class("Birdrider",        ["WIS"]),
    Class("Vermineer",        ["INT"]),
]


def get_class_list():
    return list(CLASSES)


def get_random_class(rng):
    return rng.choice(CLASSES)
