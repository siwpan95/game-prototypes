"""资源路径工具 — 兼容开发环境 和 PyInstaller 打包环境。

打包后用 sys._MEIPASS 定位资源根目录；
开发时回退到项目根目录（core/ 的父目录）。
"""

import sys
from pathlib import Path


def get_resource_root() -> Path:
    """返回资源根目录。

    - 打包后（PyInstaller）：sys._MEIPASS
    - 开发时：项目根目录
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


ROOT = get_resource_root()
