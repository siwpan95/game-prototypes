"""编排层：装配 core / strategy / render，对外提供"跑一局"和"跑一批"。"""

from game2048.app.benchmark import BenchmarkSummary, run_batch, summarize
from game2048.app.runner import DEFAULT_MAX_MOVES, GameRunner

__all__ = [
    "BenchmarkSummary",
    "DEFAULT_MAX_MOVES",
    "GameRunner",
    "run_batch",
    "summarize",
]
