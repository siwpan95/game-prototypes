# -*- coding: utf-8 -*-
"""Phase 3-C 目视：**顶点级 AO**（平滑光照）。

    python examples/shot_ao.py
    python examples/shot_ao.py --only on

同一个机位拍两张：`smooth=False`（关，旧观感）与 `smooth=True`（开，带 AO）。

判据（人眼可判）：

* **内在角落变暗**：阶梯的每一级与地面交界处、两面墙相交的墙角、立柱的根部；
* **凸出的棱保持亮**：棱上不会出现 AO 变暗（AO 只管"被夹住的角"）；
* 地面这种"开阔"的地方**不该有任何变化**（看着一样才对）。

装置是刻意搭的：阶梯（每级都有内角）+ L 形墙角 + 柱子 + 一个下沉坑。
自然地形上的 AO 要盯很久才看得出来，这类"全是内角"的几何一眼就能分辨。

⚠ AO 是**顶点色**层面的东西：几何、面数、UV 完全不变（有单测钉着）——
所以两张图的差别**只**应该落在明暗上。
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_spec = importlib.util.spec_from_file_location('_demo', os.path.join(_HERE, 'mcclone3d.py'))
demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo)

from mcclone3d import blocks as B                                  # noqa: E402

SHOTS = ('off', 'on')


def _yaw_to(frm, to) -> float:
    return math.degrees(math.atan2(-(to[0] - frm[0]), -(to[2] - frm[2])))


def _build(k, smooth: bool, x0: int, y0: int, z0: int) -> str:
    """搭"内角大全"的场地，返回摘要。"""
    w = k.world
    put = w.set_generated

    # 场地：架空到地形之上并清空周围（画面里只有装置）
    # ⚠ 不要把 `y0` 在这里重算：`__init__` 已经把同一套算法的结果传进来了，
    #   重算一版会让"装置高度"与"相机高度"各按一份口径算（两处漂了就很难查）。
    for dx in range(-4, 18):
        for dz in range(-12, 12):
            for dy in range(-2, 10):
                put(x0 + dx, y0 + dy, z0 + dz, B.AIR)
    # 地板（13×11）
    for dx in range(-4, 16):
        for dz in range(-6, 6):
            put(x0 + dx, y0 - 1, z0 + dz, B.COBBLE)

    # ① 阶梯：三级，每级与地面/下一级交界都是**内角**
    for step in range(3):
        hx = x0 + step * 2
        for dx in range(2):
            for dz in range(-3, 4):
                for dy in range(step + 1):
                    put(hx + dx, y0 + dy, z0 + dz, B.BRICK)
    # ② L 形墙：两条墙相交 ⇒ 那个直角是典型的"内角"
    for dz in range(-5, 6):
        for dy in range(3):
            put(x0 + 12, y0 + dy, z0 + dz, B.PLANKS)
    for dx in range(9, 13):
        for dy in range(3):
            put(x0 + dx, y0 + dy, z0 - 5, B.PLANKS)
    # ③ 立柱：根部四个角都被地面夹住
    for dy in range(3):
        put(x0 + 8, y0 + dy, z0 + 2, B.GLASS)
    # ④ 下沉坑：坑底四角朝上，AO 会把它们压暗
    for dx in range(2, 5):
        for dz in range(2, 4):
            put(x0 + dx, y0 - 1, z0 + dz, B.AIR)
            put(x0 + dx, y0 - 2, z0 + dz, B.STONE)

    # AO 开关：**必须在刷新网格之前**改（它在建网格时烘进顶点色）
    k.smooth = smooth
    k.dirty_chunks = set(w.chunks)
    return (f'smooth={smooth} 装置@{x0},{y0},{z0} '
            f'（阶梯 3 级 / L 形墙 / 玻璃柱 / 下沉坑）')


class AoShot(demo.McCloneApp):
    def __init__(self, which, *a, **kw):
        super().__init__(*a, **kw)
        k = self.kernel
        k.cycle.skip_to_phase(0.25)                 # 正午：AO 的差别最干净
        k.weather_kind = 'clear'
        w = k.world
        x0, z0 = 64, 64
        y0 = int(w.sea_level) + 12                  # 架空高度（与 `_build` 共用同一个）
        tag = _build(k, which == 'on', x0, y0, z0)
        # 机位：斜俯视装置（内角与棱要同框；太高看不出来，太平会互相遮挡）
        k.flying = True
        k.pos = [x0 - 6.5, y0 + 7.5, z0 - 9.5]
        k.yaw = _yaw_to(k.pos, (x0 + 6.0, y0 + 0.6, z0))
        k.pitch = -28.0
        k.dirty_chunks = set(w.chunks)
        print(f'[ao] {which}: {tag} 相机={[round(v, 1) for v in k.pos]}', flush=True)


def main():
    which = 'both'
    if '--only' in sys.argv:
        which = sys.argv[sys.argv.index('--only') + 1]
    import pyglet
    rc = 0
    for name in ([which] if which in SHOTS else list(SHOTS)):
        out = os.path.join(_ROOT, 'shots', f'phase3c_ao_{name}.png')
        app = AoShot(name, 1400, 800)
        state = {'t': 0.0, 'shot': False}

        def _beat(dt, _app=app, _out=out, _st=state):
            _st['t'] += dt
            if not _st['shot'] and _app.meshes_ready() and _st['t'] >= 4.0:
                _st['shot'] = True
                _app._shot_pending = _out
                print(f'[ao] 截图 {_out}', flush=True)

        pyglet.clock.schedule_interval(_beat, 0.3)
        try:
            pyglet.app.run()
        except Exception as exc:                     # noqa: BLE001
            print(f'[ao] {name} 失败：{exc}', flush=True)
            rc = 1
        pyglet.clock.unschedule(_beat)
    print('== AOSHOTS_OK ==', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
