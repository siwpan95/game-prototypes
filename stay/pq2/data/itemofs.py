"""物品 of 后缀数据"""

ITEM_OFS = [
    "Foreboding", "Foreshadowing", "Nervousness", "Happiness", "Torpor",
    "Danger", "Craft", "Silence", "Invisibility", "Rapidity",
    "Pleasure", "Practicality", "Hurting", "Joy", "Petulance",
    "Intrusion", "Chaos", "Suffering", "Extroversion", "Frenzy",
    "Solitude", "Punctuality", "Efficiency", "Comfort", "Patience",
    "Internment", "Incarceration", "Misapprehension", "Loyalty", "Envy",
    "Acrimony", "Worry", "Fear", "Awe", "Guile",
    "Prurience", "Fortune", "Perspicacity", "Domination", "Submission",
    "Fealty", "Hunger", "Despair", "Cruelty", "Grob",
    "Dignard", "Ra", "the Bone", "Diamonique", "Electrum", "Hydragyrum",
]


def get_random_item_of(rng):
    return rng.choice(ITEM_OFS)
