"""
alloy.utils — 工具层子包

提供:
  - load_cjk_font:      CJK 字体加载（多平台 + 本地优先）
  - load_local_font:   从本地 fonts/ 目录加载 pygame 字体
  - load_local_tk_font: 从本地 fonts/ 目录加载 tkinter 字体
  - discover_local_fonts / register_local_font: 本地字体发现与注册
  - JSONLoader:        JSON 文件加载（带缓存）
  - Logger:            文件+控制台日志
  - TextFormatter:     文本格式化工具
"""

from alloy.utils.font import (
    load_cjk_font,
    load_cjk_tk_font,
    load_local_font,
    load_local_tk_font,
    discover_local_fonts,
    register_local_font,
    get_local_fonts_dir,
    get_default_local_font_name,
    list_local_fonts,
    clear_font_cache,
)
from alloy.utils.json_loader import JSONLoader
from alloy.utils.logger import Logger
from alloy.utils.text_fmt import TextFormatter

__all__ = [
    "load_cjk_font",
    "load_cjk_tk_font",
    "load_local_font",
    "load_local_tk_font",
    "discover_local_fonts",
    "register_local_font",
    "get_local_fonts_dir",
    "get_default_local_font_name",
    "list_local_fonts",
    "clear_font_cache",
    "JSONLoader",
    "Logger",
    "TextFormatter",
]
