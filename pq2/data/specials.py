"""特殊物品数据"""

SPECIALS = [
    "Diadem", "Festoon", "Gemstone", "Phial", "Tiara",
    "Scabbard", "Arrow", "Lens", "Lamp", "Hymnal",
    "Fleece", "Laurel", "Brooch", "Gimlet", "Cobble",
    "Albatross", "Brazier", "Bandolier", "Tome", "Garnet",
    "Amethyst", "Candelabra", "Corset", "Sphere", "Sceptre",
    "Ankh", "Talisman", "Orb", "Gammel", "Ornament",
    "Brocade", "Galoon", "Bijou", "Spangle", "Gimcrack",
    "Hood", "Vulpeculum",
]


def get_random_special(rng):
    return rng.choice(SPECIALS)
