"""
Save/Load — 统一存档管理器。

支持多槽位存档、自动存档、版本兼容性检查。
所有存档以 UTF-8 JSON 格式存储。
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from shared_core.game_state import GameState


class SaveLoadManager:
    """统一存档管理器。"""

    def __init__(self, save_dir: str, version: int = 1):
        self.save_dir = save_dir
        self.version = version
        os.makedirs(save_dir, exist_ok=True)

    def _slot_path(self, slot: int) -> str:
        return os.path.join(self.save_dir, f"save_{slot:02d}.json")

    def _auto_path(self) -> str:
        return os.path.join(self.save_dir, "autosave.json")

    def save(self, state: GameState, slot: int = 0) -> bool:
        """保存游戏到指定槽位 (0-9)。"""
        if not 0 <= slot < 10:
            return False
        try:
            data = {
                "version": self.version,
                "timestamp": time.time(),
                "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                "state_data": state.to_dict(),
            }
            path = self._slot_path(slot)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except (OSError, TypeError) as e:
            print(f"[SaveLoad] 保存失败: {e}")
            return False

    def load(self, slot: int = 0) -> Optional[GameState]:
        """从指定槽位加载。"""
        if not 0 <= slot < 10:
            return None
        path = self._slot_path(slot)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version", 0) != self.version:
                print(f"[SaveLoad] 版本不匹配 (v{data.get('version')} vs v{self.version})")
            return GameState.from_dict(data["state_data"])
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[SaveLoad] 加载失败: {e}")
            return None

    def auto_save(self, state: GameState) -> bool:
        """自动存档。"""
        try:
            data = {
                "version": self.version,
                "timestamp": time.time(),
                "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                "state_data": state.to_dict(),
            }
            with open(self._auto_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    def load_auto(self) -> Optional[GameState]:
        path = self._auto_path()
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return GameState.from_dict(data["state_data"])
        except (json.JSONDecodeError, KeyError):
            return None

    def delete_save(self, slot: int) -> bool:
        if not 0 <= slot < 10:
            return False
        path = self._slot_path(slot)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def get_slot_info(self, slot: int) -> Optional[dict]:
        if not 0 <= slot < 10:
            return None
        path = self._slot_path(slot)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sd = data.get("state_data", {}).get("player", {})
            return {
                "slot": slot,
                "timestamp": data.get("timestamp"),
                "time_str": data.get("time_str", "Unknown"),
                "sanity": sd.get("sanity", "?"),
                "corruption": sd.get("corruption", "?"),
                "chapter": sd.get("current_chapter", "?"),
            }
        except (json.JSONDecodeError, KeyError):
            return None

    def list_saves(self) -> list[dict]:
        saves = []
        for i in range(10):
            info = self.get_slot_info(i)
            if info:
                saves.append(info)
        return saves
