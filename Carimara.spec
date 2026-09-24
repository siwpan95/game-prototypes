# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('data', 'data'), ('mods', 'mods')],
    hiddenimports=['pygame'],
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
    name='Carimara',
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
    # 原为 icon=['原路径'] —— 该外部绝对路径已失效，
    # 且仓内无任何 .ico 资源（git ls-files 无命中，已丢失），故移除该项，改用 PyInstaller 默认图标。
    # 如需自定义图标：把 .ico 放进仓库后改为 icon=[os.path.join(SPECPATH, '<文件名>.ico')]。
)
