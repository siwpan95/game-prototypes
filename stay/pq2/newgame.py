"""新游戏 / 角色创建"""

import threading
import time
from .types import Race, Class, Color
from .character import Character
from .data.races import get_random_race, get_race_list
from .data.classes import get_random_class, get_class_list
from .utils.namegenerator import generate_random_name


class NewGame:
    """新游戏创建流程"""

    def __init__(self, rng, callback):
        """
        Args:
            rng: numpy random Generator
            callback: function(Character) — 确认角色后回调
        """
        self._rng = rng
        self._callback = callback
        self._unroll_buffer = []  # list of tuples (str, con, dex, int, wis, cha)
        self._auto_rolling = False
        self._auto_roll_targets = {}  # {"STR": min_val, "Total": min_val}
        self._on_stats_changed = None  # UI 刷新回调
        self.character = Character()
        self.generate_name()
        self.character.CharacterRace = get_random_race(rng)
        self.character.CharacterClass = get_random_class(rng)
        self._roll_em()

    def _roll_em(self):
        self._roll_stat('STR')
        self._roll_stat('CON')
        self._roll_stat('DEX')
        self._roll_stat('INT')
        self._roll_stat('WIS')
        self._roll_stat('CHA')

    def _roll_stat(self, attr_name):
        """3 + 3d6 (each d6 = 0-5)"""
        value = 3 + self._rng.integers(0, 6) + self._rng.integers(0, 6) + self._rng.integers(0, 6)
        setattr(self.character, attr_name, int(value))

    def generate_name(self):
        self.character.Name = generate_random_name(self._rng)

    def get_name(self) -> str:
        return self.character.Name

    def set_name(self, name: str):
        self.character.Name = name

    @staticmethod
    def get_available_races() -> list:
        return [r.name for r in get_race_list()]

    def get_race(self) -> str:
        return self.character.CharacterRace.name

    def set_race(self, name: str):
        for r in get_race_list():
            if r.name == name:
                self.character.CharacterRace = r
                break

    @staticmethod
    def get_available_classes() -> list:
        return [c.name for c in get_class_list()]

    def get_class(self) -> str:
        return self.character.CharacterClass.name

    def set_class(self, name: str):
        for c in get_class_list():
            if c.name == name:
                self.character.CharacterClass = c
                break

    # ---- 属性投骰 ----

    def re_roll(self):
        """保存当前值到撤销栈，重新投骰"""
        stats = (
            self.character.STR, self.character.CON, self.character.DEX,
            self.character.INT, self.character.WIS, self.character.CHA,
        )
        self._unroll_buffer.append(stats)
        self._roll_em()

    def can_unroll(self) -> bool:
        return len(self._unroll_buffer) > 0

    def un_roll(self):
        if self._unroll_buffer:
            stats = self._unroll_buffer.pop()
            self.character.STR = stats[0]
            self.character.CON = stats[1]
            self.character.DEX = stats[2]
            self.character.INT = stats[3]
            self.character.WIS = stats[4]
            self.character.CHA = stats[5]

    def get_str(self): return self.character.STR
    def get_con(self): return self.character.CON
    def get_dex(self): return self.character.DEX
    def get_int(self): return self.character.INT
    def get_wis(self): return self.character.WIS
    def get_cha(self): return self.character.CHA

    def get_total(self) -> int:
        return (self.character.STR + self.character.CON + self.character.DEX +
                self.character.INT + self.character.WIS + self.character.CHA)

    def get_total_color(self) -> Color:
        total = self.get_total()
        if total >= 81:
            return Color.Red
        elif total >= 73:
            return Color.Yellow
        elif total <= 45:
            return Color.Gray
        elif total <= 53:
            return Color.Silver
        else:
            return Color.White

    def confirm_character(self):
        """确认角色，回调给 Game"""
        self._auto_rolling = False
        self._callback(self.character)

    # ---- 自动投骰 ----

    def set_stats_changed_callback(self, callback):
        """设置属性变化回调（用于UI刷新）"""
        self._on_stats_changed = callback

    def set_auto_roll_targets(self, targets: dict):
        """设置自动投骰目标 {attr_name: min_value, "Total": min_total}"""
        self._auto_roll_targets = targets

    def start_auto_roll(self, interval_ms: int = 10):
        """开始自动投骰，直到达到目标"""
        if self._auto_rolling:
            return
        self._auto_rolling = True
        threading.Thread(target=self._auto_roll_loop, args=(interval_ms / 1000.0,), daemon=True).start()

    def stop_auto_roll(self):
        self._auto_rolling = False

    def is_auto_rolling(self) -> bool:
        return self._auto_rolling

    def _auto_roll_loop(self, interval: float):
        while self._auto_rolling:
            self.re_roll()
            if self._on_stats_changed:
                self._on_stats_changed()
            if self._meets_targets():
                self._auto_rolling = False
                break
            time.sleep(interval)

    def _meets_targets(self) -> bool:
        targets = self._auto_roll_targets
        if not targets:
            return False
        stat_map = {
            "STR": self.get_str(), "CON": self.get_con(), "DEX": self.get_dex(),
            "INT": self.get_int(), "WIS": self.get_wis(), "CHA": self.get_cha(),
            "HP": self.character.MAX_HP, "MP": self.character.MAX_MP,
        }
        for key, min_val in targets.items():
            if key == "Total":
                if self.get_total() < min_val:
                    return False
            elif key in stat_map:
                if stat_map[key] < min_val:
                    return False
        return True
