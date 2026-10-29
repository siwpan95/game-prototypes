# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('data', 'data'), ('tools\\allin_engine', 'tools\\allin_engine')]
binaries = []
hiddenimports = ['tkinter', 'tkinter.ttk', 'tkinter.font', 'PIL', 'PIL._tkinter_finder', 'pystray', 'pystray._win32', 'numpy', 'scipy', 'asteval', 'allin_engine', 'allin_engine.core', 'allin_engine.core.ecs', 'allin_engine.core.game_loop', 'allin_engine.core.event_bus', 'allin_engine.core.data_library', 'allin_engine.core.serializable', 'allin_engine.core.deps', 'allin_engine.core.paths', 'allin_engine.systems', 'allin_engine.systems.save_load', 'allin_engine.ai', 'allin_engine.ai.decision', 'allin_engine.ai.decision.behavior_tree', 'allin_engine.ai.decision.brain', 'allin_engine.ai.decision.difference_engine', 'allin_engine.fx', 'allin_engine.fx.particle', 'allin_engine.render', 'allin_engine.utils', 'allin_engine.utils.json_loader', 'allin_engine.utils.logger']
tmp_ret = collect_all('tkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='LazyFishTank',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LazyFishTank',
)
