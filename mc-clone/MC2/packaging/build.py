# -*- coding: utf-8 -*-
"""M5 打包脚本：一行命令产出可分发的 exe（封装 PyInstaller）。

优先调用 PATH 中的 pyinstaller 可执行文件；找不到时回退到 `python -m PyInstaller`。
"""
import os
import sys
import shutil
import subprocess


HERE = os.path.dirname(os.path.abspath(__file__))   # packaging/ 目录（本文件所在）
ROOT = os.path.dirname(HERE)                          # example/ 目录（项目根，注入 M5_ROOT）


def _pyinstaller() -> list:
    """定位 pyinstaller 入口（可执行文件优先，回退模块）。"""
    # 向 build.spec 注入 ROOT，避免 SPECPATH/cwd 歧义导致定位错误。
    os.environ["M5_ROOT"] = ROOT
    exe = shutil.which("pyinstaller")
    if exe:
        return [exe]
    return [sys.executable, "-m", "PyInstaller"]


def main() -> int:
    cmd = _pyinstaller() + [
        "--clean",
        "--noconfirm",
        os.path.join(HERE, "build.spec"),
    ]
    print(">>>", " ".join(cmd))
    return subprocess.check_call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
