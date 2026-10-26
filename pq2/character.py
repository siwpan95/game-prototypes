"""角色数据结构与哈希计算"""

import hashlib
from .types import (
    Race, Class, Stack, Monster, Quest, QueueItem,
    Equipment, CurrentActionType,
)


def _hash_obj(obj):
    """使用 hashlib 对对象做确定性哈希"""
    h = hashlib.md5()
    _hash_val(obj, h)
    return int(h.hexdigest(), 16)


def _hash_val(val, h):
    """递归哈希任意值"""
    if isinstance(val, str):
        h.update(val.encode('utf-8'))
    elif isinstance(val, int):
        h.update(str(val).encode('utf-8'))
    elif isinstance(val, float):
        h.update(str(val).encode('utf-8'))
    elif isinstance(val, Race):
        h.update(val.name.encode('utf-8'))
        for a in val.attributes:
            h.update(a.encode('utf-8'))
    elif isinstance(val, Class):
        h.update(val.name.encode('utf-8'))
        for a in val.attributes:
            h.update(a.encode('utf-8'))
    elif isinstance(val, Stack):
        h.update(val.name.encode('utf-8'))
        h.update(str(val.count).encode('utf-8'))
    elif isinstance(val, Monster):
        h.update(val.name.encode('utf-8'))
        h.update(str(val.level).encode('utf-8'))
        h.update(val.drop.encode('utf-8'))
    elif isinstance(val, Quest):
        h.update(val.label.encode('utf-8'))
        if val.monster is not None:
            _hash_val(val.monster, h)
    elif isinstance(val, QueueItem):
        h.update(val.label.encode('utf-8'))
        h.update(str(val.ms).encode('utf-8'))
        h.update(str(val.type).encode('utf-8'))
    elif isinstance(val, list):
        for item in val:
            _hash_val(item, h)
    elif isinstance(val, dict):
        for k in sorted(val.keys()):
            h.update(k.encode('utf-8'))
            _hash_val(val[k], h)
    elif isinstance(val, bool):
        h.update(b'1' if val else b'0')
    elif isinstance(val, (CurrentActionType,)):
        h.update(str(val.value).encode('utf-8'))
    elif val is None:
        h.update(b'None')
    else:
        h.update(str(val).encode('utf-8'))


class Character:
    """角色数据类"""

    def __init__(self):
        self.Name = ""
        self.CharacterRace = Race("")
        self.CharacterClass = Class("")
        self.Level = 0
        self.Experience = 0
        self.STR = 0
        self.CON = 0
        self.DEX = 0
        self.INT = 0
        self.WIS = 0
        self.CHA = 0
        self.MAX_HP = 0
        self.MAX_MP = 0
        self.Gold = 0
        self.Spells: list = []          # list of Stack
        self.Equipment: list = [""] * 11  # 11 个装备槽位
        self.Inventory: list = []       # list of Stack
        self.Plot: list = []            # list of str
        self.Quests: list = []          # list of Quest
        self.Queue: list = []           # list of QueueItem
        self.CurrentAction = CurrentActionType.Loading
        self.CurrentActionLabel = "Loading."
        self.CurrentMonster = Monster("", 0, "")
        self.CurrentProgress = 0
        self.MaxProgress = 2000
        self.CurrentPlotProgress = 0
        self.CurrentQuestProgress = 0
        self.MaxQuestProgress = 0

    def calculate_hash(self) -> int:
        """计算完整性校验哈希"""
        h = hashlib.md5()
        _hash_val(self.Name, h)
        _hash_val(self.CharacterRace, h)
        _hash_val(self.CharacterClass, h)
        _hash_val(self.Level, h)
        _hash_val(self.Experience, h)
        _hash_val(self.STR, h)
        _hash_val(self.CON, h)
        _hash_val(self.DEX, h)
        _hash_val(self.INT, h)
        _hash_val(self.WIS, h)
        _hash_val(self.CHA, h)
        _hash_val(self.MAX_HP, h)
        _hash_val(self.MAX_MP, h)
        _hash_val(self.Gold, h)
        for spell in self.Spells:
            _hash_val(spell, h)
        for equip in self.Equipment:
            h.update(equip.encode('utf-8'))
        for item in self.Inventory:
            _hash_val(item, h)
        for p in self.Plot:
            h.update(p.encode('utf-8'))
        for q in self.Quests:
            _hash_val(q, h)
        for qi in self.Queue:
            _hash_val(qi, h)
        _hash_val(self.CurrentAction, h)
        _hash_val(self.CurrentActionLabel, h)
        _hash_val(self.CurrentMonster, h)
        _hash_val(self.CurrentProgress, h)
        _hash_val(self.MaxProgress, h)
        _hash_val(self.CurrentPlotProgress, h)
        _hash_val(self.CurrentQuestProgress, h)
        _hash_val(self.MaxQuestProgress, h)
        return int(h.hexdigest(), 16)
