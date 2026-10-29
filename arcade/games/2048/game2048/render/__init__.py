"""表现层：只读取 core 的快照，不参与任何决策。"""

from game2048.render.base import Renderer
from game2048.render.console import ConsoleRenderer
from game2048.render.silent import SilentRenderer

__all__ = ["Renderer", "ConsoleRenderer", "SilentRenderer"]
