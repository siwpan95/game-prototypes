"""头衔数据"""

from ..utils.namegenerator import generate_random_name

TITLES = [
    "Mr.", "Mrs.", "Sir", "Sgt.", "Ms.",
    "Captain", "Chief", "Admiral", "Saint",
]

IMPRESSIVE_TITLES = [
    "King", "Queen", "Lord", "Lady", "Viceroy",
    "Mayor", "Prince", "Princess", "Chief", "Boss", "Archbishop",
]


def get_random_title(rng, low=False):
    if low:
        value = min(rng.integers(0, len(TITLES)), rng.integers(0, len(TITLES)))
    else:
        value = rng.integers(0, len(TITLES))
    return TITLES[value]


def get_random_impressive_title(rng):
    return rng.choice(IMPRESSIVE_TITLES)
