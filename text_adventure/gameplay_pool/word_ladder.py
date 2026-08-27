"""WordLadderPuzzle: transform one word into another one letter at a time."""

import random
from collections import deque
from .base_puzzle import BasePuzzle

WORD_POOLS: dict[int, list[str]] = {
    3: [
        "cat", "cot", "cog", "dog", "bat", "rat", "hat", "mat", "sat",
        "run", "fun", "sun", "bug", "rug", "mug", "hug", "cut", "but",
        "put", "pot", "hot", "lot", "dot", "got", "not", "rot", "bit",
        "fit", "hit", "kit", "pit", "sit", "wit", "big", "dig", "fig",
        "pig", "wig", "bin", "fin", "pin", "tin", "win", "dip", "hip",
        "lip", "rip", "sip", "tip", "zip", "aim", "hut", "hum", "sum",
        "sub", "hub", "cub", "cup", "cap", "car", "far", "fan", "man",
        "map", "mop", "top", "tap", "rap", "sap", "van", "can", "ban",
    ],
    4: [
        "cold", "gold", "cord", "word", "worm", "warm", "farm", "form",
        "core", "bore", "bone", "cone", "code", "mode", "node", "ride",
        "hide", "side", "wide", "life", "wife", "knife", "love", "dove",
        "move", "came", "same", "name", "game", "flame", "cure", "pure",
        "lamb", "lamp", "camp", "ramp", "damp", "ship", "shop", "chop",
        "chip", "trip", "trap", "trim", "slip", "slot", "slow", "blow",
        "flow", "glow", "grow", "know", "show", "snow", "west", "test",
        "best", "rest", "nest", "pest", "west", "bold", "hold", "told",
    ],
}

START_END_PAIRS: list[tuple[int, str, str]] = [
    (3, "cat", "dog"),
    (3, "hat", "bit"),
    (3, "cut", "hot"),
    (3, "big", "wig"),
    (4, "cold", "warm"),
    (4, "hide", "side"),
    (4, "shop", "chip"),
    (4, "lamp", "camp"),
    (4, "west", "best"),
]


class WordLadderPuzzle(BasePuzzle):
    puzzle_name = "Word Ladder"
    puzzle_type = "mixed"

    def _generate(self) -> None:
        if self.difficulty == "easy":
            candidates = [(n, s, e) for n, s, e in START_END_PAIRS if n == 3]
        elif self.difficulty == "medium":
            candidates = [(n, s, e) for n, s, e in START_END_PAIRS if n == 4]
        else:
            candidates = START_END_PAIRS

        if not candidates:
            candidates = START_END_PAIRS

        _, start, end = random.choice(candidates)
        word_len = len(start)
        pool = WORD_POOLS.get(word_len, WORD_POOLS[3])
        path = self._bfs(start, end, pool)
        if not path:
            path = [start, end]

        self.data = {
            "start": start,
            "end": end,
            "path": path,
            "word_len": word_len,
            "pool": pool,
            "player_path": [start],
        }

    @staticmethod
    def _bfs(start: str, end: str, pool: list[str]) -> list[str] | None:
        word_set = set(pool)
        queue: deque[tuple[str, list[str]]] = deque()
        queue.append((start, [start]))
        visited = {start}

        while queue:
            current, path = queue.popleft()
            if current == end:
                return path
            for i in range(len(current)):
                for ch in "abcdefghijklmnopqrstuvwxyz":
                    if ch == current[i]:
                        continue
                    neighbor = current[:i] + ch + current[i + 1:]
                    if neighbor in word_set and neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, path + [neighbor]))
        return None

    def check_answer(self, answer: Any) -> bool:
        path = self.data["player_path"]
        return len(path) > 1 and path[-1] == self.data["end"]

    def get_hint(self) -> str:
        path = self.data["path"]
        idx = len(self.data["player_path"]) - 1
        if idx + 1 < len(path):
            next_word = path[idx + 1]
            for i, (a, b) in enumerate(zip(self.data["player_path"][-1], next_word)):
                if a != b:
                    return f"Change position {i + 1} to '{b}'"
        return "You're almost there!"

    def set_step(self, word: str) -> bool:
        """Add a word to the player's ladder path if it's a valid single-letter change."""
        current = self.data["player_path"][-1]
        if len(word) != len(current):
            return False
        diffs = sum(1 for a, b in zip(current, word) if a != b)
        if diffs == 1 and word in self.data["pool"]:
            self.data["player_path"].append(word)
            return True
        return False
