"""随机名字生成器"""

VOWELS = "aeiou"

PARTS1 = ["br", "cr", "dr", "fr", "gr", "j", "kr", "l", "m", "n",
          "pr", "r", "sh", "tr", "v", "wh", "x", "y", "z"]
PARTS2 = ["a", "a", "e", "e", "i", "i", "o", "o", "u", "u",
          "ae", "ie", "oo", "ou"]
PARTS3 = ["b", "ck", "d", "g", "k", "m", "n", "p", "t", "v", "x", "z"]


def _is_vowel(c):
    return c.lower() in VOWELS


def generate_random_name(rng):
    parts = [
        rng.choice(PARTS1),
        rng.choice(PARTS2),
        rng.choice(PARTS3),
        rng.choice(PARTS1),
        rng.choice(PARTS2),
        rng.choice(PARTS3),
    ]
    result = "".join(parts)
    return result[0].upper() + result[1:]
