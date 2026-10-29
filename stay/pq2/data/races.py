"""种族数据"""

from ..types import Race

RACES = [
    Race("Half Orc",             ["HP Max"]),
    Race("Half Man",             ["CHA"]),
    Race("Half Halfling",        ["DEX"]),
    Race("Double Hobbit",        ["STR"]),
    Race("Hob-Hobbit",           ["DEX", "CON"]),
    Race("Low Elf",              ["CON"]),
    Race("Dung Elf",             ["WIS"]),
    Race("Talking Pony",         ["MP Max", "INT"]),
    Race("Gyrognome",            ["DEX"]),
    Race("Lesser Dwarf",         ["CON"]),
    Race("Crested Dwarf",        ["CHA"]),
    Race("Eel Man",              ["DEX"]),
    Race("Panda Man",            ["CON", "STR"]),
    Race("Trans-Kobold",         ["WIS"]),
    Race("Enchanted Motorcycle", ["MP Max"]),
    Race("Will o' the Wisp",     ["WIS"]),
    Race("Battle-Finch",         ["DEX", "INT"]),
    Race("Double Wookiee",       ["STR"]),
    Race("Skraeling",            ["WIS"]),
    Race("Demicanadian",         ["CON"]),
    Race("Land Squid",           ["STR", "HP Max"]),
]


def get_race_list():
    return list(RACES)


def get_random_race(rng):
    return rng.choice(RACES)
