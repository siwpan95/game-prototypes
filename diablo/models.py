"""游戏数据模型：装备、玩家、敌人"""
import random
from typing import Optional, List


class Equipment:
    def __init__(self, name: str, atk: int, def_: int, value: int, quality: str = "Common"):
        self.name = name
        self.atk = atk
        self.def_ = def_
        self.value = value
        self.quality = quality


class Player:
    def __init__(self, name: str, hp: int, max_hp: int, mp: int, max_mp: int,
                 base_atk: int, base_def: int, level: int, exp: int,
                 gold: int, soul: int, weapon: Equipment, armor: Equipment):
        self.name = name
        self.hp = hp
        self.max_hp = max_hp
        self.mp = mp
        self.max_mp = max_mp
        self.base_atk = base_atk
        self.base_def = base_def
        self.level = level
        self.exp = exp
        self.gold = gold
        self.soul = soul
        self.weapon = weapon
        self.armor = armor
        self.contract_active = False

    def total_atk(self) -> int:
        return self.base_atk + (self.weapon.atk if self.weapon else 0)

    def total_def(self) -> int:
        return self.base_def + (self.armor.def_ if self.armor else 0)

    def take_damage(self, dmg: int):
        self.hp -= dmg
        if self.hp < 0:
            self.hp = 0

    def heal(self, amount: int):
        self.hp = min(self.max_hp, self.hp + amount)

    def is_alive(self) -> bool:
        return self.hp > 0

    def level_up(self):
        self.level += 1
        self.max_hp += 10
        self.hp = self.max_hp
        self.max_mp += 5
        self.mp = self.max_mp
        self.base_atk += 2
        self.base_def += 2


# 敌人ASCII艺术（定义在Enemy类之前，供Enemy.__init__使用）
ENEMY_ASCII = {
    "Fallen": [
        "    /\\    ",
        "   /  \\   ",
        "  / !! \\  ",
        " /  /\\  \\ ",
        "/___/  \\___\\",
        "    |__|    ",
    ],
    "Goatman": [
        "  \\|//    ",
        "  @****@  ",
        "  (====)  ",
        "  /|  |\\  ",
        " / |  | \\ ",
        "   |  |   ",
    ],
    "Corrupt Mage": [
        "    *     ",
        "   ***    ",
        "  *@*@*   ",
        "   |||    ",
        "  /|||\\  ",
        " / ||| \\ ",
    ],
    "Skeleton King": [
        "   ___    ",
        "  /   \\   ",
        " | X X |  ",
        "  \\ = /  ",
        " __\\|/__ ",
        "/|     |\\",
    ],
    "Skeleton": [
        "   .--.  ",
        "  / () \\ ",
        " | >  < |",
        "  \\____/ ",
        "  / || \\ ",
        " /__||__\\",
    ],
    "Zombie": [
        "  ____   ",
        " /    \\  ",
        " | oo |  ",
        " | ^^ |  ",
        "  \\--/   ",
        "  /  \\   ",
    ],
    "Ghoul": [
        "  ,_,    ",
        " ( o.o)  ",
        "  ) ^ (  ",
        " /|   |\\ ",
        " | |_| | ",
        "  \\___/  ",
    ],
    "Imp": [
        "  /\\/\\   ",
        " ( o.o ) ",
        "  ) ^ (  ",
        " /|   |\\ ",
        "  |   |  ",
        "  \\___/  ",
    ],
    "Hellhound": [
        "  /\\_/\\  ",
        " ( o.o ) ",
        "  > ^ <  ",
        " /|   |\\ ",
        "  |   |  ",
        "  \\___/  ",
    ],
    "Gargoyle": [
        "  ____   ",
        " /    \\  ",
        " | >< |  ",
        " |____|  ",
        " /|  |\\  ",
        "/_|  |_\\ ",
    ],
    "Bone Mage": [
        "    *    ",
        "   ***   ",
        "  *o o*  ",
        "   \\||/  ",
        "   /||\\  ",
        "  / || \\ ",
    ],
    "Fallen Shaman": [
        "  \\/\\/   ",
        " ( @ @ ) ",
        "  )==(   ",
        " /|  |\\  ",
        "  |  |   ",
        " /|  |\\  ",
    ],
    "Butcher": [
        "  .----. ",
        " /      \\",
        " | >  < |",
        " | /\\/  |",
        " |_/  \\_|",
        " /|    |\\",
    ],
    "Diablo": [
        " \\  __  /",
        "  \\/  \\/ ",
        "  ( >< ) ",
        "   )()(  ",
        "  /|  |\\ ",
        " /_|  |_\\",
    ],
}


class Enemy:
    def __init__(self, name: str, hp: int, atk: int, def_: int, exp_reward: int,
                 gold_reward: int, soul_reward: int, quality: str = "Common",
                 ascii_art: Optional[List[str]] = None):
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.atk = atk
        self.def_ = def_
        self.exp_reward = exp_reward
        self.gold_reward = gold_reward
        self.soul_reward = soul_reward
        self.quality = quality
        self.ascii_art = ascii_art if ascii_art is not None else ENEMY_ASCII.get(name, ["?    ?"])

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, dmg: int):
        self.hp -= dmg
        if self.hp < 0:
            self.hp = 0

    def attack_damage(self) -> int:
        return max(1, self.atk + random.randint(-2, 2))
