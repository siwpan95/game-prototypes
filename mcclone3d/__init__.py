# -*- coding: utf-8 -*-
"""mcclone3d —— 《我的世界》风格 3D 体素沙盒（引擎：siwpan/3dworld 的 world3d）。

**导入本包不会去找引擎**（`_engine` 用的是模块级惰性转发）：只有真正取用
`world` / `mesh` / `kernel` 这些模块时才需要引擎在场。这样 `--help` 与文档
生成这类场景不必先装好 3dworld。
"""
__all__ = ['__version__', 'ROOT']

__version__ = '0.1.0'

import os as _os

#: 本仓根（本文件在 <仓根>/mcclone3d/__init__.py）
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
