"""
纪元系统 Mixin — 纪元检测、进度计算、解锁判定。
"""
import time
from config import ERAS
from .types import EraDef


class _EraMixin:
    """提供给 GameEngine 的纪元相关方法。"""

    _era_index: int
    state: object  # GameState

    def _update_era(self):
        old_max = self.state.max_era_index
        for i, era in enumerate(ERAS):
            if self.state.total_gold >= era["threshold"]:
                self._era_index = i
        if self._era_index > self.state.max_era_index:
            self.state.max_era_index = self._era_index
        # 记录每个纪元首次达成时间（用于统计页面）
        for i in range(old_max + 1, self._era_index + 1):
            self.state.era_first_times.setdefault(i, time.time())

    def get_current_era(self) -> EraDef:
        return ERAS[self._era_index]

    def get_next_era(self) -> EraDef | None:
        if self._era_index + 1 < len(ERAS):
            return ERAS[self._era_index + 1]
        return None

    def get_era_progress(self) -> float:
        nxt = self.get_next_era()
        if nxt is None:
            return 1.0
        cur = self.get_current_era()
        total = nxt["threshold"] - cur["threshold"]
        if total <= 0:
            return 1.0
        progress = (self.state.total_gold - cur["threshold"]) / total
        return min(max(progress, 0.0), 1.0)

    def is_era_unlocked(self, era_key: str) -> bool:
        for i, era in enumerate(ERAS):
            if era["key"] == era_key:
                return i <= self._era_index
        return True
