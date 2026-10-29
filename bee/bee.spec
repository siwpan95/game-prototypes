# -*- mode: python ; coding: utf-8 -*-
# bee 安装包样板 spec（2026-08-25）
a = Analysis(
    ['G:/repos/bee/main.pyw'],
    pathex=['G:/repos/bee'],
    binaries=[],
    datas=[
        ('G:/repos/bee/src/resources', 'src/resources'),
        ('G:/repos/bee/src/resources', 'resources'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # scipy 的 array_api_compat.common._helpers 顶层 import torch/cupy/dask/jax/ndonnx/sparse；
    # scipy.stats._fit/_survival 的字节码 import matplotlib（matplotlib.pyplot 又 import pandas），
    # 会把整个 ML/科学计算生态拖进依赖图；运行时均不加载，安全排除。
    excludes=['torch', 'cupy', 'dask', 'jax', 'ndonnx', 'sparse', 'sqlalchemy', 'matplotlib', 'pandas'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='bee',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    contents_directory='.',
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='bee')
