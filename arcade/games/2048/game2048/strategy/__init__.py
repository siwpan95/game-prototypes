"""决策层：只依赖 core 的纯函数，不做任何 I/O。

导入本包即完成所有内置策略的注册，之后可以通过
:func:`~game2048.strategy.base.create` 按名字取用。
"""

from game2048.strategy.base import (
    REGISTRY,
    Strategy,
    available_names,
    create,
    register,
)

# 下面的导入是有副作用的：@register 装饰器在导入时把策略登记进 REGISTRY。
from game2048.strategy.expectimax import (
    ExpectimaxStrategy,
    GreedyStrategy,
    adaptive_depth,
)
from game2048.strategy.fixed_order import FixedOrderStrategy
from game2048.strategy.heuristics import (
    DEFAULT_WEIGHTS,
    STRONG_WEIGHTS,
    Weights,
    merge_potential_score,
)
from game2048.strategy.mcts import MCTSStrategy
from game2048.strategy.random_walk import RandomStrategy

__all__ = [
    "REGISTRY",
    "Strategy",
    "available_names",
    "create",
    "register",
    "ExpectimaxStrategy",
    "FixedOrderStrategy",
    "GreedyStrategy",
    "MCTSStrategy",
    "RandomStrategy",
    "adaptive_depth",
    "Weights",
    "DEFAULT_WEIGHTS",
    "STRONG_WEIGHTS",
    "merge_potential_score",
]
