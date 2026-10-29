"""MinesweeperPuzzle: classic minesweeper with random mine placement."""

import random
from .base_puzzle import BasePuzzle


class MinesweeperPuzzle(BasePuzzle):
    kind = "minesweeper"
    puzzle_name = "扫雷"  # default language; overridden per instance
    puzzle_type = "generated"

    def _generate(self) -> None:
        if self.difficulty == "easy":
            rows, cols, mines = 6, 6, 6
        elif self.difficulty == "medium":
            rows, cols, mines = 8, 8, 12
        else:
            rows, cols, mines = 10, 10, 20

        grid = [[0] * cols for _ in range(rows)]
        mine_positions: set[tuple[int, int]] = set()

        positions = [(r, c) for r in range(rows) for c in range(cols)]
        self._rng().shuffle(positions)
        for r, c in positions[:mines]:
            grid[r][c] = -1
            mine_positions.add((r, c))

        for r, c in positions[mines:]:
            count = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == -1:
                        count += 1
            grid[r][c] = count

        self.data = {
            "rows": rows,
            "cols": cols,
            "mines": mines,
            "grid": grid,
            "revealed": [[False] * cols for _ in range(rows)],
            "flagged": [[False] * cols for _ in range(rows)],
            "mine_positions": mine_positions,
            "game_over": False,
            "win": False,
        }

    def recalculate_adjacency(self) -> None:
        """Recalculate adjacency numbers after moving a mine."""
        rows, cols = self.data["rows"], self.data["cols"]
        for r in range(rows):
            for c in range(cols):
                if self.data["grid"][r][c] == -1:
                    continue
                count = 0
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols and self.data["grid"][nr][nc] == -1:
                            count += 1
                self.data["grid"][r][c] = count

    def check_answer(self, answer: Any) -> bool:
        return self.data["win"]

    def get_hint(self) -> str:
        rows, cols = self.data["rows"], self.data["cols"]
        for r in range(rows):
            for c in range(cols):
                if self.data["grid"][r][c] == -1 and not self.data["flagged"][r][c]:
                    return self.msg("minesweeper_hint", row=r + 1, col=c + 1)
        return self.word("all_mines_flagged")

    def ensure_safe_first_click(self, row: int, col: int) -> None:
        """Regenerate the board so (row, col) and its neighbors are mine-free."""
        rows, cols = self.data["rows"], self.data["cols"]
        mines = self.data["mines"]
        # Collect cells that must be safe: the clicked cell and its 8 neighbors
        safe_zone: set[tuple[int, int]] = {(row, col)}
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = row + dr, col + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    safe_zone.add((nr, nc))

        positions = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in safe_zone]
        # If we don't have enough non-safe cells for all mines, reduce safe zone
        if len(positions) < mines:
            extra = safe_zone - {(row, col)}
            positions = [(r, c) for r in range(rows) for c in range(cols) if (r, c) != (row, col)]

        self._rng().shuffle(positions)

        # Clear everything
        grid = [[0] * cols for _ in range(rows)]
        mine_positions: set[tuple[int, int]] = set()
        for r, c in positions[:mines]:
            grid[r][c] = -1
            mine_positions.add((r, c))

        for r in range(rows):
            for c in range(cols):
                if grid[r][c] != -1:
                    count = 0
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            if dr == 0 and dc == 0:
                                continue
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == -1:
                                count += 1
                    grid[r][c] = count

        self.data["grid"] = grid
        self.data["mine_positions"] = mine_positions

    def reveal(self, row: int, col: int) -> None:
        rows, cols = self.data["rows"], self.data["cols"]
        if not (0 <= row < rows and 0 <= col < cols):
            return
        if self.data["revealed"][row][col] or self.data["flagged"][row][col]:
            return
        if self.data["game_over"]:
            return

        # Use a stack-based flood fill instead of recursion
        stack = [(row, col)]
        while stack:
            r, c = stack.pop()
            if not (0 <= r < rows and 0 <= c < cols):
                continue
            if self.data["revealed"][r][c] or self.data["flagged"][r][c]:
                continue

            self.data["revealed"][r][c] = True

            if self.data["grid"][r][c] == -1:
                self.data["game_over"] = True
                for mr, mc in self.data["mine_positions"]:
                    self.data["revealed"][mr][mc] = True
                return

            if self.data["grid"][r][c] == 0:
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            stack.append((nr, nc))

        self._check_win()

    def toggle_flag(self, row: int, col: int) -> None:
        rows, cols = self.data["rows"], self.data["cols"]
        if not (0 <= row < rows and 0 <= col < cols):
            return
        if self.data["revealed"][row][col]:
            return
        self.data["flagged"][row][col] = not self.data["flagged"][row][col]
        self._check_win()

    def _check_win(self) -> None:
        rows, cols = self.data["rows"], self.data["cols"]
        for r in range(rows):
            for c in range(cols):
                if self.data["grid"][r][c] != -1 and not self.data["revealed"][r][c]:
                    return
        self.data["win"] = True
