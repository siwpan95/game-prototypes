# -*- coding: utf-8 -*-
"""HUD 目视验证：截一张带血条 / 饥饿条 / hotbar 的图，并顺手验证伤害反馈。

    python examples/shot_hud.py            # 写 shots/phase1_hud.png
    python examples/shot_hud.py --hurt     # 先扣血到半血，看血条真的少一半

判据（人眼可判）：
* 底部 9 格 hotbar，**当前格高亮**；
* 左下 10 段血条、右下 10 段饥饿条，段数与数值对得上；
* `--hurt` 时血条应显示**约一半**（这是"UI 读数与内核状态一致"的证据，
  不是"看起来有条就行"）。
"""
from __future__ import annotations

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_spec = importlib.util.spec_from_file_location('_demo', os.path.join(_HERE, 'mcclone3d.py'))
demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo)

from mcclone3d import blocks as B                            # noqa: E402
from mcclone3d import items as I                             # noqa: E402

OUT = os.path.join(_ROOT, 'shots', 'phase1_hud.png')


class HudShot(demo.McCloneApp):
    def __init__(self, *a, **kw):
        hurt = bool(kw.pop('hurt', False))
        super().__init__(*a, **kw)
        k = self.kernel
        cx, cz = 128, 128
        y = k.world.surface_at(cx, cz)
        # 面前摆一排方块：给 hotbar 背景一点内容，也顺便看材质
        mats = (B.GRASS, B.DIRT, B.STONE, B.SAND, B.LOG, B.PLANKS, B.GLASS,
                B.COBBLE, B.BRICK)
        for j, m in enumerate(mats):
            k.world.set(cx - 4 + j, y + 1, cz - 8, m)
            k.world.set(cx - 4 + j, y + 2, cz - 8, m)
        k.flying = True
        k.pos = [cx + 0.5, y + 2.0, cz - 2.5]
        k.yaw, k.pitch = 0.0, -4.0
        k.select(2)                                   # 高亮第 3 格（石头）
        if hurt:
            # 扣到半血、吃到半饱：**读数是判据**（截图里血条该正好一半）
            k.hurt(k.max_health * 0.5, 'shot')
            k.hunger = k.max_hunger * 0.5
        k.dirty_chunks = set(k.world.chunks)
        print(f'[hud] 血量={k.health}/{k.max_health} 饥饿={k.hunger}/{k.max_hunger} '
              f'选中格={k.selected}（{I.name_of(k.selected_item())}）', flush=True)


def main():
    hurt = '--hurt' in sys.argv
    out = OUT if not hurt else OUT.replace('.png', '_hurt.png')
    app = HudShot(1400, 800, hurt=hurt)
    import pyglet

    state = {'t': 0.0, 'shot': False}

    def _beat(dt):
        state['t'] += dt
        if not state['shot'] and app.meshes_ready() and state['t'] >= 1.0:
            state['shot'] = True
            app._shot_pending = out
            print(f'[hud] 网格就绪（{len(app._verts)} 区块），截图 {out}', flush=True)

    pyglet.clock.schedule_interval(_beat, 0.5)
    pyglet.app.run()
    print(f'== HUD_OK {out} ==', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
