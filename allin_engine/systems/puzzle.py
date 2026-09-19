"""
谜题系统 — 统一谜题定义、验证与奖励管理。

支持从 JSON 数据驱动加载谜题定义。
支持多种谜题类型：文字解密、意象匹配、道德困境、物品使用、战斗、谜语。

核心功能:
- Puzzle: 单个谜题的数据定义
- PuzzleSystem: 注册、加载、呈现、验证谜题
- check_answer(): 模糊匹配（去空格/小写/子串容错）

使用方式:

    sys = PuzzleSystem()
    sys.load_from_json([...])
    result = sys.verify_answer("puzzle_01", "玩家的答案")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------
# Puzzle — 单个谜题定义
# ---------------------------------------------------------------

@dataclass
class Puzzle:
    """单个谜题的数据定义。

    Attributes:
        puzzle_id: 唯一标识符
        title: 谜题标题
        puzzle_type: 类型 — text_decrypt / imagery_match / moral_dilemma /
                     item_use / combat / riddle
        question: 谜题问题/描述
        answer: 可接受的答案列表
        hints: 提示列表
        rewards: 奖励物品/属性的字典
        attempts_allowed: 允许尝试次数
        attempts_used: 已用尝试次数
        required_condition: 前置条件（可选）
        metadata: 扩展元数据
    """

    puzzle_id: str
    title: str
    puzzle_type: str = "text_decrypt"
    description: str = ""
    question: str = ""
    answer: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    rewards: dict[str, Any] = field(default_factory=dict)
    attempts_allowed: int = 3
    attempts_used: int = 0
    required_condition: str = ""
    options: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def check_answer(self, player_input: str) -> bool:
        """检查答案 — 模糊匹配。

        规则：
        1. 去空格、小写后精确匹配
        2. 答案长度 > 10 时，子串匹配
        3. 数字类答案容忍常见变体

        :param player_input: 玩家的回答
        :returns: 是否判定正确
        """
        if not player_input:
            return False

        input_normalized = player_input.strip().lower().replace(" ", "")

        for ans in self.answer:
            ans_normalized = ans.strip().lower().replace(" ", "")

            # 精确匹配
            if input_normalized == ans_normalized:
                return True

            # 子串容错（仅对长答案）
            if len(ans_normalized) > 10 and input_normalized in ans_normalized:
                return True
            if len(input_normalized) > 10 and ans_normalized in input_normalized:
                return True

            # 数字答案容错（忽略逗号、单位符号等）
            if ans_normalized.isdigit() and input_normalized.isdigit():
                if int(input_normalized) == int(ans_normalized):
                    return True

        return False

    def get_hint(self, hint_index: int) -> Optional[str]:
        """获取指定索引的提示。

        :param hint_index: 提示索引（0-based）
        :returns: 提示文本或 None
        """
        if 0 <= hint_index < len(self.hints):
            return self.hints[hint_index]
        return None

    @property
    def is_exhausted(self) -> bool:
        """是否已达到最大尝试次数。"""
        return self.attempts_used >= self.attempts_allowed

    @property
    def remaining_attempts(self) -> int:
        """剩余尝试次数。"""
        return max(0, self.attempts_allowed - self.attempts_used)

    @classmethod
    def from_dict(cls, data: dict) -> "Puzzle":
        """从字典构建 Puzzle。"""
        return cls(
            puzzle_id=data["puzzle_id"],
            title=data.get("title", ""),
            puzzle_type=data.get("puzzle_type", "text_decrypt"),
            description=data.get("description", ""),
            question=data.get("question", ""),
            answer=(
                data["answer"] if isinstance(data.get("answer"), list)
                else [data.get("answer", "")]
            ),
            hints=data.get("hints", []),
            rewards=data.get("rewards", {}),
            attempts_allowed=data.get("attempts_allowed", 3),
            required_condition=data.get("required_condition", ""),
            options=data.get("options", []),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "puzzle_id": self.puzzle_id,
            "title": self.title,
            "puzzle_type": self.puzzle_type,
            "description": self.description,
            "question": self.question,
            "answer": self.answer,
            "hints": self.hints,
            "rewards": self.rewards,
            "attempts_allowed": self.attempts_allowed,
            "attempts_used": self.attempts_used,
            "required_condition": self.required_condition,
            "options": self.options,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------
# PuzzleSystem — 谜题管理器
# ---------------------------------------------------------------

class PuzzleSystem:
    """谜题系统 — 管理谜题的定义、验证和奖励。

    支持两种加载模式：
      1. 数据驱动：从 JSON 列表批量加载（load_from_json）
      2. 代码注册：逐个 register()

    使用方式:

        ps = PuzzleSystem()
        ps.load_from_json(data_list)
        present = ps.present("puzzle_01")
        result = ps.verify_answer("puzzle_01", "42")
    """

    def __init__(self, event_bus=None):
        self._puzzles: dict[str, Puzzle] = {}
        self._solved_ids: set[str] = set()
        self._event_bus = event_bus  # 可选：用于发布谜题事件

    # ---- 注册与加载 ----

    def register(self, puzzle: Puzzle) -> None:
        """注册单个谜题。"""
        self._puzzles[puzzle.puzzle_id] = puzzle

    def load_from_json(self, data: list[dict]) -> None:
        """从 JSON 数据列表批量加载谜题。

        :param data: 谜题字典列表，每个元素包含 puzzle_id, title, type 等字段
        """
        for puzzle_dict in data:
            puzzle = Puzzle.from_dict(puzzle_dict)
            self._puzzles[puzzle.puzzle_id] = puzzle

    def unregister(self, puzzle_id: str) -> bool:
        """移除已注册的谜题。"""
        if puzzle_id in self._puzzles:
            del self._puzzles[puzzle_id]
            self._solved_ids.discard(puzzle_id)
            return True
        return False

    # ---- 查询 ----

    def get_puzzle(self, puzzle_id: str) -> Optional[Puzzle]:
        """获取谜题定义。"""
        return self._puzzles.get(puzzle_id)

    def is_solved(self, puzzle_id: str) -> bool:
        """谜题是否已解答。"""
        return puzzle_id in self._solved_ids

    @property
    def solved_count(self) -> int:
        """已解答谜题数。"""
        return len(self._solved_ids)

    @property
    def total_count(self) -> int:
        """总谜题数。"""
        return len(self._puzzles)

    def all_puzzle_ids(self) -> list[str]:
        """返回所有谜题 ID。"""
        return list(self._puzzles.keys())

    def all_solved_ids(self) -> list[str]:
        """返回已解答谜题 ID 列表。"""
        return list(self._solved_ids)

    # ---- 呈现 ----

    def present(self, puzzle_id: str) -> dict:
        """呈现谜题数据供 UI 渲染。

        Returns:
            {"success": True/False, "message": str, "puzzle": Puzzle|None, "pending": bool}
        """
        puzzle = self._puzzles.get(puzzle_id)
        if not puzzle:
            return {"success": False, "message": f"未知谜题: {puzzle_id}", "puzzle": None}
        if puzzle_id in self._solved_ids:
            return {"success": True, "message": "该谜题已解答。", "puzzle": puzzle, "pending": False}
        return {"success": True, "message": "", "puzzle": puzzle, "pending": True,
                "puzzle_id": puzzle_id}

    # ---- 验证 ----

    def verify_answer(self, puzzle_id: str, player_input: str) -> dict:
        """验证玩家答案并返回结果。

        :param puzzle_id: 谜题 ID
        :param player_input: 玩家的回答
        :returns: 结果字典，包含 success, message, rewards, hints 等字段
        """
        puzzle = self._puzzles.get(puzzle_id)
        if not puzzle:
            return {"success": False, "message": f"未知谜题: {puzzle_id}"}

        puzzle.attempts_used += 1

        # 道德困境特殊处理
        if puzzle.puzzle_type == "moral_dilemma":
            return self._handle_moral_dilemma(puzzle, player_input)

        # 标准答案验证
        if puzzle.check_answer(player_input):
            self._solved_ids.add(puzzle_id)
            if self._event_bus:
                self._event_bus.emit("PUZZLE_SOLVED", {
                    "puzzle_id": puzzle_id,
                    "title": puzzle.title,
                })
            return {
                "success": True,
                "message": f"正确！你解开了谜题「{puzzle.title}」。",
                "rewards": puzzle.rewards,
                "hint": None,
            }

        # 答案错误 — 尝试给提示
        hint_msg: Optional[str] = None
        if puzzle.attempts_used <= len(puzzle.hints):
            hint_msg = puzzle.get_hint(puzzle.attempts_used - 1)

        return {
            "success": False,
            "message": "答案不正确。",
            "rewards": {},
            "hint": hint_msg,
            "remaining_attempts": puzzle.remaining_attempts,
            "is_exhausted": puzzle.is_exhausted,
        }

    def _handle_moral_dilemma(self, puzzle: Puzzle, player_input: str) -> dict:
        """处理道德困境型谜题的选择。"""
        try:
            idx = int(player_input.strip()) - 1
        except (ValueError, IndexError):
            idx = -1

        if 0 <= idx < len(puzzle.options):
            choice = puzzle.options[idx]
            self._solved_ids.add(puzzle.puzzle_id)
            if self._event_bus:
                self._event_bus.emit("PUZZLE_SOLVED", {
                    "puzzle_id": puzzle.puzzle_id,
                    "title": puzzle.title,
                    "choice": choice,
                })
            return {
                "success": True,
                "message": f"你的选择: {choice.get('text', '')}",
                "choice_effect": choice,
                "rewards": choice.get("rewards", {}),
            }
        return {"success": False, "message": "无效的选择。"}

    # ---- 提示 ----

    def get_hints(self, puzzle_id: str) -> list[str]:
        """获取谜题的提示列表。"""
        puzzle = self._puzzles.get(puzzle_id)
        if not puzzle:
            return []
        return list(puzzle.hints)

    def get_available_hints(self, puzzle_id: str) -> list[str]:
        """获取玩家已解锁的提示（根据已使用尝试次数）。

        :returns: 已解锁的提示列表
        """
        puzzle = self._puzzles.get(puzzle_id)
        if not puzzle:
            return []
        used = min(puzzle.attempts_used, len(puzzle.hints))
        return puzzle.hints[:used]

    # ---- 状态 ----

    def reset_puzzle(self, puzzle_id: str) -> bool:
        """重置谜题的尝试计数（不改变已解答状态）。"""
        puzzle = self._puzzles.get(puzzle_id)
        if not puzzle:
            return False
        puzzle.attempts_used = 0
        return True

    def unsolve(self, puzzle_id: str) -> bool:
        """撤销谜题解答状态。"""
        if puzzle_id in self._solved_ids:
            self._solved_ids.discard(puzzle_id)
            puzzle = self._puzzles.get(puzzle_id)
            if puzzle:
                puzzle.attempts_used = 0
            return True
        return False

    def to_dict(self) -> dict:
        """导出为可序列化字典。"""
        return {
            "puzzles": {pid: p.to_dict() for pid, p in self._puzzles.items()},
            "solved_ids": list(self._solved_ids),
        }

    def from_dict(self, data: dict) -> None:
        """从字典恢复状态。"""
        self._puzzles.clear()
        self._solved_ids.clear()
        for pid, pdata in data.get("puzzles", {}).items():
            self._puzzles[pid] = Puzzle.from_dict(pdata)
        self._solved_ids = set(data.get("solved_ids", []))
