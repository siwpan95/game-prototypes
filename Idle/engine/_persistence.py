"""
存档系统 Mixin — 游戏进度保存与加载。
"""
import base64
import json
import os
import time
from config import SAVE_FILE, PRESTIGE_UPGRADES
from .state import GameState


class _PersistenceMixin:
    """提供给 GameEngine 的存档相关方法。"""

    state: GameState
    _defs: dict

    def save(self):
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state.to_dict(), f)

    def _load(self):
        if not os.path.exists(SAVE_FILE):
            return
        with open(SAVE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        loaded = GameState.from_dict(data)
        for key in self._defs:
            loaded.upgrades.setdefault(key, 0)
            loaded.empowered.setdefault(key, 0)
        for pk in PRESTIGE_UPGRADES:
            loaded.prestige_upgrades.setdefault(pk["key"], 0)
        self.state = loaded
        self.state.last_tick = time.time()

    # ==================== 存档导出/导入（base64 字符串） ====================

    def export_save(self) -> str:
        """将当前进度序列化为 base64 字符串，便于备份/换机。"""
        raw = json.dumps(self.state.to_dict(), ensure_ascii=False)
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")

    def import_save(self, b64: str) -> None:
        """从 base64 字符串恢复进度（不写文件，调用方自行 save）。"""
        raw = base64.b64decode(b64.strip())
        data = json.loads(raw)
        loaded = GameState.from_dict(data)
        for key in self._defs:
            loaded.upgrades.setdefault(key, 0)
            loaded.empowered.setdefault(key, 0)
        for pk in PRESTIGE_UPGRADES:
            loaded.prestige_upgrades.setdefault(pk["key"], 0)
        self.state = loaded
        self.state.last_tick = time.time()
        self._init_state()
        self._init_heroes()
        self._init_events()
        self._update_era()
        self._recalc()
        self._schedule_golden_button()
