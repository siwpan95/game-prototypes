"""
allin_engine.render — 渲染层子包

提供:
  - ConsoleRenderer: 终端 ANSI 文字渲染器
  - BaseWindow / StatusPanel: Tkinter GUI 基类与面板组件（需 tkinter）
  - Styles: 主题样式管理 (dark/light)
  - ColorGenerator / SolidColor / HSVFlowColor / EnergyColor / RainbowColor: 颜色系统
  - FormulaEngine: 安全数学公式求值引擎（需 numpy）
  - Animation: 非阻塞动画效果 (typewriter/fade/shake/pulse)
"""

import logging

logger = logging.getLogger(__name__)

from allin_engine.render.console_renderer import ConsoleRenderer

# Tkinter GUI 组件（可选，无 tkinter 时设为 None）
try:
    from allin_engine.render.gui_base import BaseWindow, StatusPanel, Styles
except ImportError as _e:
    logger.warning("tkinter 不可用，Tkinter GUI 功能已禁用（BaseWindow/StatusPanel/Styles = None）：%s", _e)
    BaseWindow = None
    StatusPanel = None
    Styles = None

# 颜色系统（无硬依赖）
from allin_engine.render.color_system import (
    ColorGenerator, SolidColor, HSVFlowColor, EnergyColor, RainbowColor,
)

# 公式引擎（可选，无 numpy 时设为 None）
try:
    from allin_engine.render.formula_engine import FormulaEngine
except ImportError:
    logger.warning("numpy 不可用，FormulaEngine 已禁用（回退为纯 Python 实现）")
    FormulaEngine = None

# 动画系统（无硬依赖）
from allin_engine.render.animation import Animation

# 游戏 UI 组件（来自 Minecraft 实战沉淀，需 tkinter）
try:
    from allin_engine.render.widgets import (
        GameLogPanel, StatusBar, QuickCommandBar, GameInputBar,
        GameWindow, GameTheme,
    )
except ImportError as _e2:
    logger.warning("tkinter 不可用，Game UI 组件已禁用：%s", _e2)
    GameLogPanel = None
    StatusBar = None
    QuickCommandBar = None
    GameInputBar = None
    GameWindow = None
    GameTheme = None

__all__ = [
    "ConsoleRenderer",
    "BaseWindow",
    "StatusPanel",
    "Styles",
    "ColorGenerator",
    "SolidColor",
    "HSVFlowColor",
    "EnergyColor",
    "RainbowColor",
    "FormulaEngine",
    "Animation",
    "GameLogPanel",
    "StatusBar",
    "QuickCommandBar",
    "GameInputBar",
    "GameWindow",
    "GameTheme",
]
