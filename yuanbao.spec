# -*- mode: python ; coding: utf-8 -*-
#
# 打包配置：把"细胞工厂"打成单文件 GUI 可执行程序。
#
# 构建：
#   pip install pyinstaller
#   pyinstaller yuanbao.spec
#
# 产物：dist/yuanbao.exe（无控制台窗口，双击即启动 GUI）
#


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='yuanbao',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
