# -*- mode: python ; coding: utf-8 -*-
# yuanbao 细胞工厂安装包 spec（2026-08-27，pywallpaper 样板同款；onedir contents_directory=.；目录重构更新路径）
a = Analysis(
    ['G:/repos/yuanbao/main.py'],
    pathex=['G:/repos/yuanbao'],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='yuanbao',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    contents_directory='.',
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='yuanbao')
