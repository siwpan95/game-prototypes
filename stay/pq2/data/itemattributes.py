"""物品属性修饰数据"""

ITEM_ATTRIBUTES = [
    "Golden", "Gilded", "Spectral", "Astral", "Garlanded",
    "Precious", "Crafted", "Dual", "Filigreed", "Cruciate",
    "Arcane", "Blessed", "Reverential", "Lucky", "Enchanted",
    "Gleaming", "Grandiose", "Sacred", "Legendary", "Mythic",
    "Crystalline", "Austere", "Ostentatious", "One True", "Proverbial",
    "Fearsome", "Deadly", "Benevolent", "Unearthly", "Magnificent",
    "Iron", "Ormolu", "Puissant",
]


def get_random_item_attribute(rng):
    return rng.choice(ITEM_ATTRIBUTES)
