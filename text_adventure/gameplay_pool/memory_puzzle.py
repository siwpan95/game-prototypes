"""MemoryPuzzle: card-matching memory game."""

import random
from .base_puzzle import BasePuzzle

SYMBOLS: list[str] = [
    "star", "heart", "moon", "sun", "bolt", "drop",
    "leaf", "fire", "rock", "wind", "snow", "wave",
    "gem", "ring", "bell", "key",
]


class MemoryPuzzle(BasePuzzle):
    puzzle_name = "Memory Match"
    puzzle_type = "generated"

    def _generate(self) -> None:
        if self.difficulty == "easy":
            pairs = 6
            cols = 4
        elif self.difficulty == "medium":
            pairs = 8
            cols = 4
        else:
            pairs = 12
            cols = 6

        chosen = self._rng().sample(SYMBOLS, pairs)
        cards = chosen * 2
        self._rng().shuffle(cards)

        rows = len(cards) // cols
        grid = []
        idx = 0
        for r in range(rows):
            row = []
            for c in range(cols):
                row.append(cards[idx])
                idx += 1
            grid.append(row)

        self.data = {
            "rows": rows,
            "cols": cols,
            "pairs": pairs,
            "grid": grid,
            "revealed": [[False] * cols for _ in range(rows)],
            "matched": [[False] * cols for _ in range(rows)],
            "selected": [],
            "moves": 0,
            "pairs_found": 0,
        }

    def check_answer(self, answer: Any) -> bool:
        return self.data["pairs_found"] == self.data["pairs"]

    def get_hint(self) -> str:
        rows, cols = self.data["rows"], self.data["cols"]
        for r1 in range(rows):
            for c1 in range(cols):
                if self.data["matched"][r1][c1]:
                    continue
                for r2 in range(rows):
                    for c2 in range(cols):
                        if r1 == r2 and c1 == c2:
                            continue
                        if self.data["matched"][r2][c2]:
                            continue
                        if self.data["grid"][r1][c1] == self.data["grid"][r2][c2]:
                            return f"Match at row {r1 + 1} col {c1 + 1} and row {r2 + 1} col {c2 + 1}"
        return "No more pairs to find!"

    def flip_card(self, row: int, col: int) -> dict:
        """Flip a card and return action info."""
        rows, cols = self.data["rows"], self.data["cols"]
        if not (0 <= row < rows and 0 <= col < cols):
            return {"action": "invalid"}
        if self.data["revealed"][row][col] or self.data["matched"][row][col]:
            return {"action": "invalid"}

        self.data["revealed"][row][col] = True
        self.data["selected"].append((row, col))

        if len(self.data["selected"]) == 2:
            self.data["moves"] += 1
            (r1, c1), (r2, c2) = self.data["selected"]
            if self.data["grid"][r1][c1] == self.data["grid"][r2][c2]:
                self.data["matched"][r1][c1] = True
                self.data["matched"][r2][c2] = True
                self.data["pairs_found"] += 1
                self.data["selected"] = []
                return {"action": "match"}
            else:
                return {"action": "mismatch", "cards": self.data["selected"]}

        return {"action": "first_pick"}

    def hide_unmatched(self) -> None:
        """Hide cards that were selected but not matched."""
        for r, c in self.data["selected"]:
            if not self.data["matched"][r][c]:
                self.data["revealed"][r][c] = False
        self.data["selected"] = []
