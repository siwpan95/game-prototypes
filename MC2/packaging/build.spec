# -*- coding: utf-8 -*-
"""PyInstaller 打包规格（M5：一键产出可分发的 MC 复刻版 exe）。

用法：
  python packaging/build.py
  # 或等价（在 example 目录下）：
  pyinstaller packaging/build.spec

产物：
  dist/mc_clone_gui.exe  （One-Folder 形态，含全部依赖）

要点（地基零改动 + 外部引擎依赖）：
  - 入口 mcclone/main_gui.py（支持 --no-gui / --seed / --load / --save）。
  - allin_engine 位于 example 的父目录（D:/allin），经 pathex 注入分析器
    并随包捆绑（hiddenimports 显式列出其各子包，避免动态导入漏收集）。
  - data/*.json 经 datas 收集，运行时由 main_gui._THIS_DIR 定位（与开发期一致）。
  - 排除 tkinter（GUI 走 pygame，tkinter 仅 headless 测试用，不需要进包）。
"""
import os

block_cipher = None

# ROOT 优先取 build.py 注入的环境变量 M5_ROOT（最稳健），
# 回退到 SPECPATH（绝对路径传入 build.spec 时通常为 example 目录）。
ROOT = os.environ.get("M5_ROOT") or os.path.dirname(os.path.abspath(SPECPATH))
ENGINE = os.path.dirname(ROOT)                       # allin_engine 所在父目录（D:/allin）

a = Analysis(
    [os.path.join(ROOT, "mcclone", "main_gui.py")],
    pathex=[ROOT, ENGINE],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "data"), "data"),
    ],
    hiddenimports=[
        "allin_engine",
        "allin_engine.core",
        "allin_engine.core.serializable",
        "allin_engine.core.config",
        "allin_engine.core.data_library",
        "allin_engine.core.ecs",
        "allin_engine.core.event_bus",
        "allin_engine.core.game_loop",
        "allin_engine.core.paths",
        "allin_engine.utils",
        "allin_engine.utils.json_loader",
        "allin_engine.utils.logger",
        "allin_engine.utils.text_fmt",
        "allin_engine.utils.font",
        "allin_engine.ai",
        "allin_engine.audio",
        "allin_engine.fx",
        "allin_engine.systems",
        "allin_engine.systems.input",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "tkinter.ttk", "unittest", "pydoc"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="mc_clone_gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                 # 图形界面：不弹控制台窗口
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
