"""Dialog Generator — 从故事数据生成对话定义。"""

from __future__ import annotations
from typing import Any


class DialogGenerator:
    """对话数据生成器。"""

    def __init__(self, story_data: Any = None):
        self.story_data = story_data or {}

    def generate(self) -> list[dict]:
        """
        生成对话列表。

        Returns:
            [{"dialog_id": ..., "lines": [...], "speaker": ..., "room_id": ...}, ...]
        """
        dialogs: list[dict] = []
        if isinstance(self.story_data, dict):
            dialogs_data = self.story_data.get("dialogs", {})
            if isinstance(dialogs_data, dict):
                for did, dlines in dialogs_data.items():
                    if isinstance(dlines, (list, str)):
                        lines_list = dlines if isinstance(dlines, list) else [dlines]
                        dialogs.append({
                            "dialog_id": did,
                            "lines": lines_list,
                            "speaker": "",
                            "room_id": "",
                        })
        return dialogs

    def get_dialog_to_chars(self) -> dict[str, list[str]]:
        """返回 dialog_id → [char_ids] 的映射。"""
        mapping: dict[str, list[str]] = {}
        # 子类可根据角色名匹配来填充
        return mapping

    def get_dialog_to_room(self) -> dict[str, str]:
        """返回 dialog_id → room_id 的映射。"""
        mapping: dict[str, str] = {}
        return mapping
