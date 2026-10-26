"""名称与冠词格式化（#13 从 game.py 巨型类抽取的纯函数模块）。

这些函数无状态、不依赖 Game/Character，便于独立测试与复用。
"""

from .utils.plural import plural

VOWELS = "AEIOUÜaeiouü"


def indefinite(name: str, count: int) -> str:
    """不定冠词"""
    if count == 1:
        if name and name[0] in VOWELS:
            return f"an {name}"
        return f"a {name}"
    return f"{count} {plural(name)}"


def definite(name: str, count: int) -> str:
    """定冠词"""
    if count > 1:
        name = f"{count} {plural(name)}"
    return f"the {name}"


def format_sick(level, name):
    abs_level = abs(level)
    if abs_level == 5:
        return f"dead {name}"
    if abs_level == 4:
        return f"comatose {name}"
    if abs_level == 3:
        return f"crippled {name}"
    if abs_level == 2:
        return f"sick {name}"
    if abs_level == 1:
        return f"undernourished {name}"
    return f"{level}{name}"


def format_young(level, name):
    abs_level = abs(level)
    if abs_level == 5:
        return f"foetal {name}"
    if abs_level == 4:
        return f"baby {name}"
    if abs_level == 3:
        return f"preadolescent {name}"
    if abs_level == 2:
        return f"teenage {name}"
    if abs_level == 1:
        return f"underage {name}"
    return f"{level}{name}"


def format_big(level, name):
    abs_level = abs(level)
    if abs_level == 1:
        return f"greater {name}"
    if abs_level == 2:
        return f"massive {name}"
    if abs_level == 3:
        return f"enormous {name}"
    if abs_level == 4:
        return f"giant {name}"
    if abs_level == 5:
        return f"titanic {name}"
    return f"{level}{name}"


def format_special(level, name):
    abs_level = abs(level)
    if abs_level == 1:
        if ' ' in name:
            return f"veteran {name}"
        return f"Battle-{name}"
    if abs_level == 2:
        return f"cursed {name}"
    if abs_level == 3:
        if ' ' in name:
            return f"warrior {name}"
        return f"Ware-{name}"
    if abs_level == 4:
        return f"undead {name}"
    if abs_level == 5:
        return f"demon {name}"
    return name
