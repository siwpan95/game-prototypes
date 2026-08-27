"""存档管理器（桩实现，后续可扩展 JSON/Pickle 序列化）"""
import json
import os
from typing import Any, Dict, Optional


class SaveManager:
    """游戏存档管理"""

    def __init__(self, save_dir: str):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)

    def save(self, slot: int, data: Dict[str, Any]) -> bool:
        """保存游戏到指定槽位"""
        try:
            filepath = os.path.join(self.save_dir, f"save_{slot}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as _e:
            import sys
            print(f"[SaveManager] 存档失败（槽位{slot}）：{_e}", file=sys.stderr)
            return False

    def load(self, slot: int) -> Optional[Dict[str, Any]]:
        """从指定槽位加载存档"""
        filepath = os.path.join(self.save_dir, f"save_{slot}.json")
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as _e:
            import sys
            print(f"[SaveManager] 读档失败（槽位{slot}）：{_e}", file=sys.stderr)
            return None

    def list_saves(self) -> list:
        """列出所有存档槽位"""
        saves = []
        if os.path.isdir(self.save_dir):
            for fname in os.listdir(self.save_dir):
                if fname.startswith("save_") and fname.endswith(".json"):
                    saves.append(int(fname[5:-5]))
        return sorted(saves)
