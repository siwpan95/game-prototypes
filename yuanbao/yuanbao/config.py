"""全局配置与标签系统。

设计说明
--------
早期版本中 ``Config`` 是一个被各模块直接 ``Config.GRID_SIZE`` 引用的全局类，
这导致规则参数无法在不同实例间独立调整，也阻碍了单元测试的隔离。

重构后 ``Config`` 是一个 dataclass：

* 仍可当作"默认配置命名空间"使用——``Config.GRID_SIZE`` 返回默认值；
* 也可实例化后传给各模块以覆盖默认值::

      cfg = Config(GRID_SIZE=30, INIT_DENSITY=0.4)
      ca = CellularAutomaton(cfg)

各模块只持有传入的 ``config`` 实例，不再回引全局类，从而做到依赖注入。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Config:
    """元胞自动机与任务系统的运行参数。"""

    GRID_SIZE: int = 20
    TAGS: List[str] = field(default_factory=lambda: ['red', 'green', 'blue', 'yellow'])

    # Conway 生命游戏经典规则：存活 2~3 邻居，诞生 3 邻居
    SURVIVE_MIN: int = 2
    SURVIVE_MAX: int = 3
    BORN_MIN: int = 3
    BORN_MAX: int = 3

    # CNN 检测卷积核大小（目前为 3x3 邻域）
    KERNEL_SIZE: int = 3

    # 自动挂机步间隔（秒）
    STEP_INTERVAL: float = 0.3

    # 初始存活密度（0~1）
    INIT_DENSITY: float = 0.3

    def tag_index(self, tag: str) -> int:
        """标签名 -> 内部 1-based 索引；找不到返回 0（表示空）。"""
        try:
            return self.TAGS.index(tag) + 1
        except ValueError:
            return 0

    def index_to_tag(self, idx: int) -> Optional[str]:
        """内部索引 -> 标签名；越界返回 None。"""
        if 1 <= idx <= len(self.TAGS):
            return self.TAGS[idx - 1]
        return None
