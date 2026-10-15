"""存档管理器 — JSON 序列化，支持多槽位"""
import json
import os
from typing import Any, Dict, List, Optional


class SaveManager:
    """游戏存档管理

    - 存档写入 ``save_dir/save_<slot>.json``（UTF-8 JSON）
    - 槽位为 1..MAX_SLOTS 的整数，越界操作直接拒绝
    """

    MAX_SLOTS = 3

    def __init__(self, save_dir: str):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)

    def _slot_path(self, slot: int) -> str:
        return os.path.join(self.save_dir, f"save_{slot}.json")

    def _valid_slot(self, slot: Any) -> bool:
        return isinstance(slot, int) and 1 <= slot <= self.MAX_SLOTS

    def has_save(self, slot: int) -> bool:
        """指定槽位是否存在存档"""
        if not self._valid_slot(slot):
            return False
        return os.path.exists(self._slot_path(slot))

    def save(self, slot: int, data: Dict[str, Any]) -> bool:
        """保存游戏到指定槽位"""
        if not self._valid_slot(slot):
            print(f"[SaveManager] 非法槽位: {slot!r}（有效范围 1-{self.MAX_SLOTS}）")
            return False
        try:
            filepath = self._slot_path(slot)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as _e:
            import sys
            print(f"[SaveManager] 存档失败（槽位{slot}）：{_e}", file=sys.stderr)
            return False

    def load(self, slot: int) -> Optional[Dict[str, Any]]:
        """从指定槽位加载存档"""
        if not self._valid_slot(slot):
            return None
        filepath = self._slot_path(slot)
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as _e:
            import sys
            print(f"[SaveManager] 读档失败（槽位{slot}）：{_e}", file=sys.stderr)
            return None

    def list_saves(self) -> List[int]:
        """列出所有存在存档的槽位号（升序）"""
        saves = []
        if os.path.isdir(self.save_dir):
            for fname in os.listdir(self.save_dir):
                if fname.startswith("save_") and fname.endswith(".json"):
                    try:
                        saves.append(int(fname[5:-5]))
                    except ValueError:
                        continue
        return sorted(saves)
