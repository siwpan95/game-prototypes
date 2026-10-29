# -*- coding: utf-8 -*-
"""取一张能看清渲染真相的截图：飞到空中俯视 + 人工摆几组方块做对比。

    python examples/shot_vista.py            # 写 shots/phase0_vista.png
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
# ⚠ 本文件与 demo 同目录、而 demo 与**包**同名（`examples/mcclone3d.py` vs `mcclone3d/`）。
# 所以这里**把 demo 按文件路径加载成独立模块名**（`_demo`），既拿到 `McCloneApp`，
# 又不会让 `sys.path` 上出现 `examples/` 而遮蔽真正的包（实测踩过这个遮蔽）。
import importlib.util                                        # noqa: E402

_spec = importlib.util.spec_from_file_location(
    '_demo', os.path.join(_HERE, 'mcclone3d.py'))
demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo)

from mcclone3d import blocks as B                            # noqa: E402

OUT = os.path.join(_ROOT, 'shots', 'phase0_vista.png')


class Vista(demo.McCloneApp):
    """把相机放到空中，并在出生点附近摆一组"材质样张"。"""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        k = self.kernel
        cx, cz = 128, 128
        # 地面：铺一块 20×20 的平台，方便看清材质与 UV 连续性
        y = k.world.surface_at(cx, cz) + 1
        mats = (B.GRASS, B.DIRT, B.STONE, B.SAND, B.LOG, B.PLANKS,
                B.GLASS, B.COBBLE, B.BRICK, B.SNOW)
        for i in range(20):
            for j in range(20):
                k.world.set(cx - 10 + i, y, cz - 10 + j, mats[(i // 2) % len(mats)])
        # 一堵高墙 + 两根柱子：看侧面的 UV 走向与明暗
        for h in range(1, 9):
            for j in range(-10, 11):
                k.world.set(cx - 12, y + h, cz + j, B.STONE if h % 2 else B.BRICK)
        for h in range(1, 7):
            k.world.set(cx + 12, y + h, cz - 8, B.LOG)
            k.world.set(cx + 12, y + h, cz + 8, B.COBBLE)
        # 玻璃塔（半透明）与雪块（高对比）
        for h in range(1, 5):
            for d in range(-1, 2):
                k.world.set(cx + 6 + d, y + h, cz + 6, B.GLASS)
        k.world.set(cx - 6, y + 1, cz - 6, B.SNOW)
        k.world.set(cx - 6, y + 2, cz - 6, B.SNOW)
        # 相机：站到平台上朝**自然地形**看（平台只是材质样张，别把它当主体）
        # yaw=0 朝 -z；平台在 z∈[118,137]，所以站到平台南缘之外一点再回看。
        k.flying = True
        k.pos = [cx - 2, y + 6, cz - 26]
        k.yaw, k.pitch = 186.0, -14.0
        k.dirty_chunks = set(k.world.chunks)
        print(f'[vista] 平台 y={y} 相机={[round(v, 1) for v in k.pos]} '
              f'yaw={k.yaw} pitch={k.pitch}', flush=True)


def main():
    app = Vista(1600, 900, verbose=True)
    import pyglet

    state = {'t': 0.0, 'shot': False}

    def _beat(dt):
        # ⚠ **等到网格全部上传再截**：首帧是分帧上传的（16 区块/帧），
        # 早截会拍到"还没传完的世界"，看着像渲染丢了地形（实测踩过）。
        state['t'] += dt
        app.sanity_report('vista')
        if not state['shot'] and app.meshes_ready() and state['t'] >= 1.0:
            state['shot'] = True
            app._shot_pending = OUT
            print(f'[vista] 网格就绪（{len(app._verts)} 区块），开始截图', flush=True)

    pyglet.clock.schedule_interval(_beat, 1.0)
    pyglet.app.run()
    print(f'== VISTA_OK {OUT} ==', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
