"""Character Generator — 从故事数据生成角色定义。"""

from __future__ import annotations
from typing import Any, Optional


class CharacterGenerator:
    """角色数据生成器。"""

    def __init__(self, story_data: Any = None, config: Any = None):
        self.story_data = story_data or {}
        self.config = config

    def generate(self) -> list[dict]:
        """
        生成角色列表。

        Returns:
            [{"char_id": ..., "name": ..., "description": ..., "role": ...}, ...]
        """
        characters: list[dict] = []

        # 如果故事数据中已有角色定义，直接使用
        if isinstance(self.story_data, dict):
            chars_data = self.story_data.get("characters", {})
            if isinstance(chars_data, dict):
                for char_id, char_obj in chars_data.items():
                    if isinstance(char_obj, dict):
                        characters.append({
                            "char_id": char_id,
                            "name": char_obj.get("name", char_id),
                            "description": char_obj.get("description", ""),
                            "role": char_obj.get("role", "narrator"),
                            **{k: v for k, v in char_obj.items()
                               if k not in ("name", "description", "role")},
                        })

        # 如果故事文本中有角色名出现记录
        if not characters:
            # 尝试从叙事文本提取角色名
            known_chars = self._extract_from_narratives()
            characters.extend(known_chars)

        return characters

    def _extract_from_narratives(self) -> list[dict]:
        """从叙事文本中尝试提取角色。"""
        # 简化版：返回空列表，子类可覆写
        return []
