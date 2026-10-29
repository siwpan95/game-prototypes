"""普通物品数据"""

BORING_ITEMS = [
    "nail", "lunchpail", "sock", "I.O.U.", "cookie",
    "pint", "toothpick", "writ", "newspaper", "letter",
    "plank", "hat", "egg", "coin", "needle",
    "bucket", "ladder", "chicken", "twig", "dirtclod",
    "counterpane", "vest", "teratoma", "bunny", "rock",
    "pole", "carrot", "canoe", "inkwell", "hoe",
    "bandage", "trowel", "towel", "planter box", "anvil",
    "axle", "tuppence", "casket", "nosegay", "trinket",
    "credenza", "writ",
]


def get_random_boring_item(rng):
    return rng.choice(BORING_ITEMS)
