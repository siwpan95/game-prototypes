"""View 层 - 纯渲染与事件转发，不持有游戏状态。

- tile_renderer : PIL 绘制麻将牌面 (圆角象牙底 + 正宗图案)
- board_canvas  : Canvas 棋盘视图 (绘制/点击/动画)
- hud           : 顶栏信息 + 按钮栏
"""
from .tile_renderer import TileRenderer
from .board_canvas import BoardCanvas
from .hud import Hud

__all__ = ["TileRenderer", "BoardCanvas", "Hud"]
