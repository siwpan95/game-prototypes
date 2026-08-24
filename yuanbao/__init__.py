"""细胞工厂 - 元胞自动机 × CNN 标签任务系统。

一个把 Conway 生命游戏式元胞自动机与卷积模式检测结合的轻量"挂机收集"沙盒：
- :class:`CellularAutomaton` 维护带标签的网格并按规则演化；
- :class:`CNNDetector` 用固定卷积核扫描空间模式（如"红心 + 1 个绿邻居"）；
- :class:`Task` / :class:`TaskRequirement` 描述收集目标；
- :class:`AutoRunner` 把演化与收集串成自动化循环，可阻塞或后台线程运行。
"""

from yuanbao.config import Config
from yuanbao.core.automaton import CellularAutomaton
from yuanbao.core.detector import CNNDetector
from yuanbao.tasks.requirement import TaskRequirement
from yuanbao.tasks.task import Task
from yuanbao.engine.auto_runner import AutoRunner

__version__ = "1.1.0"

__all__ = [
    "Config",
    "CellularAutomaton",
    "CNNDetector",
    "TaskRequirement",
    "Task",
    "AutoRunner",
    "__version__",
]
