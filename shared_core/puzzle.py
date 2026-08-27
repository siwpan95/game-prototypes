"""
Puzzle System — 统一谜题系统。

支持从 JSON 数据驱动加载谜题定义（替代硬编码）。
支持多种谜题类型：文本解密、意象匹配、道德困境、物品使用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Puzzle:
    """单个谜题定义。"""
    puzzle_id: str
    title: str
    puzzle_type: str  # text_decrypt, imagery_match, moral_dilemma, item_use, combat
    description: str
    question: str
    answer: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    sanity_reward: int = 5
    sanity_penalty: int = 8
    corruption_gain: int = 2
    imagery_unlocked: list[str] = field(default_factory=list)
    options: list[dict] = field(default_factory=list)  # for moral_dilemma
    attempts_allowed: int = 3
    attempts_used: int = 0
    required_chapter: str = ""
    metadata: dict = field(default_factory=dict)

    def check_answer(self, player_input: str) -> bool:
        """检查答案（模糊匹配）。"""
        input_normalized = player_input.strip().lower().replace(" ", "")
        for ans in self.answer:
            ans_normalized = ans.strip().lower().replace(" ", "")
            if input_normalized == ans_normalized:
                return True
            if len(ans_normalized) > 10 and input_normalized in ans_normalized:
                return True
            if len(input_normalized) > 10 and ans_normalized in input_normalized:
                return True
        return False

    def get_hint(self, hint_index: int) -> Optional[str]:
        if 0 <= hint_index < len(self.hints):
            return self.hints[hint_index]
        return None

    @property
    def is_exhausted(self) -> bool:
        return self.attempts_used >= self.attempts_allowed

    @classmethod
    def from_dict(cls, data: dict) -> "Puzzle":
        return cls(
            puzzle_id=data["puzzle_id"],
            title=data.get("title", ""),
            puzzle_type=data.get("puzzle_type", "text_decrypt"),
            description=data.get("description", ""),
            question=data.get("question", ""),
            answer=data.get("answer", []) if isinstance(data.get("answer"), list) else [data.get("answer", "")],
            hints=data.get("hints", []),
            sanity_reward=data.get("sanity_reward", 5),
            sanity_penalty=data.get("sanity_penalty", 8),
            corruption_gain=data.get("corruption_gain", 2),
            imagery_unlocked=data.get("imagery_unlocked", []),
            options=data.get("options", []),
            attempts_allowed=data.get("attempts_allowed", 3),
            required_chapter=data.get("required_chapter", ""),
            metadata=data.get("metadata", {}),
        )


class PuzzleSystem:
    """
    谜题系统 — 管理谜题的定义、验证和奖励。

    支持两种模式：
      1. 数据驱动：从 JSON 文件加载谜题定义
      2. 代码注册：通过 register() 手动注册
    """

    def __init__(self, state=None, settings=None):
        from shared_core.game_state import GameState as _GS
        self.state: Any = state or _GS()
        self.settings: Any = settings
        self._puzzles: dict[str, Puzzle] = {}
        self._solved_ids: set[str] = set()

    def register(self, puzzle: Puzzle) -> None:
        """注册一个谜题。"""
        self._puzzles[puzzle.puzzle_id] = puzzle

    def load_from_json(self, data: list[dict]) -> None:
        """从 JSON 数据批量加载谜题。"""
        for pd in data:
            p = Puzzle.from_dict(pd)
            self._puzzles[p.puzzle_id] = p

    def get_puzzle(self, puzzle_id: str) -> Optional[Puzzle]:
        return self._puzzles.get(puzzle_id)

    def present_puzzle(self, puzzle_id: str) -> dict:
        """呈现谜题数据供 UI 渲染。"""
        puzzle = self._puzzles.get(puzzle_id)
        if not puzzle:
            return {"success": False, "message": f"未知谜题: {puzzle_id}"}
        if puzzle_id in self._solved_ids:
            return {"success": True, "message": "该谜题已解答。"}
        return {"puzzle": puzzle, "pending": True, "puzzle_id": puzzle_id}

    def verify_answer(self, puzzle_id: str, player_input: str) -> dict:
        """验证答案并返回结果。"""
        puzzle = self._puzzles.get(puzzle_id)
        if not puzzle:
            return {"success": False, "message": f"未知谜题: {puzzle_id}"}

        puzzle.attempts_used += 1
        self.state.player.puzzles_attempted += 1

        # 道德困境特殊处理
        if puzzle.puzzle_type == "moral_dilemma":
            return self._handle_moral_dilemma(puzzle, player_input)

        # 标准答案验证
        if puzzle.check_answer(player_input):
            self._solved_ids.add(puzzle_id)
            self.state.player.solved_puzzles.append(puzzle_id)
            self.state.player.puzzles_solved += 1
            self.state.record_event("puzzle_solved", f"Puzzle {puzzle.title} solved")
            return {
                "success": True,
                "message": f"正确！{puzzle.description[:30]}……",
                "sanity_reward": puzzle.sanity_reward,
                "imagery_unlocked": puzzle.imagery_unlocked,
            }

        # 答案错误
        penalty = puzzle.sanity_penalty
        hint_msg = ""
        if puzzle.attempts_used <= len(puzzle.hints):
            hint_msg = puzzle.get_hint(puzzle.attempts_used - 1) or ""
        return {
            "success": False,
            "message": "答案不正确。",
            "sanity_penalty": penalty,
            "corruption_gain": puzzle.corruption_gain,
            "hint": hint_msg,
            "is_exhausted": puzzle.is_exhausted,
        }

    def _handle_moral_dilemma(self, puzzle: Puzzle, player_input: str) -> dict:
        """处理道德困境型谜题。"""
        try:
            idx = int(player_input.strip()) - 1
        except (ValueError, IndexError):
            idx = -1

        if 0 <= idx < len(puzzle.options):
            choice = puzzle.options[idx]
            self._solved_ids.add(puzzle.puzzle_id)
            self.state.player.solved_puzzles.append(puzzle.puzzle_id)
            self.state.player.puzzles_solved += 1
            delta_s = choice.get("sanity_delta", 0)
            delta_c = choice.get("corruption_delta", 0)
            self.state.player.adjust_sanity(delta_s)
            self.state.player.adjust_corruption(delta_c)
            unlocked = choice.get("imagery_discovery", [])
            for img in (unlocked or []):
                self.state.imagery_network.discover(img)
                self.state.player.discover_imagery(img)
            return {
                "success": True,
                "message": f"你的选择: {choice['text']}",
                "choice_effect": choice,
                "imagery_unlocked": unlocked or [],
            }
        return {"success": False, "message": "无效的选择。"}

    def get_available_hints(self, puzzle_id: str) -> list[str]:
        puzzle = self._puzzles.get(puzzle_id)
        if not puzzle:
            return []
        used = min(puzzle.attempts_used, len(puzzle.hints))
        return puzzle.hints[:used]

    def sync_state(self, state) -> None:
        self.state = state

    @property
    def solved_count(self) -> int:
        return len(self._solved_ids)

    @property
    def total_count(self) -> int:
        return len(self._puzzles)
