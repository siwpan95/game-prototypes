# -*- coding: utf-8 -*-
"""昼夜色板：**同一机位**在不同时刻各截一张，用来看"光照真的在变"。

    python examples/shot_day.py            # 正午 / 日落 / 午夜 三张
    python examples/shot_day.py --only 0.75

判据（人眼可判，且与内核读数对拍）：
* 正午：地表明亮、阴影短、天空蓝；
* 日落：天色转暖、地面偏橙、影子区变暗；
* 午夜：整体压暗但**还能看清轮廓**（`light_scale` 的地板 0.10，不是全黑），
  暗处应带一点**蓝**（`light_color` 的夜色混合）。

脚本会顺手打印每张图的 `day_factor` —— 截图与数字一起看，避免"看着像夜里"就下结论。
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
from mcclone3d import sun as S                               # noqa: E402

SHOTS = (
    (0.25, 'phase2_noon'),
    (0.52, 'phase2_dusk'),
    (0.75, 'phase2_midnight'),
)


class DayShot(demo.McCloneApp):
    def __init__(self, phase, *a, **kw):
        super().__init__(*a, **kw)
        k = self.kernel
        k.cycle.skip_to_phase(float(phase))
        cx, cz = 128, 128
        y = k.world.surface_at(cx, cz)
        # 机位：站在地表上方、朝一片开阔地看（三张图机位完全相同，便于对比）
        k.flying = True
        k.pos = [cx + 0.5, y + 3.0, cz + 6.5]
        k.yaw, k.pitch = 180.0, -10.0
        k.select(2)
        k.dirty_chunks = set(k.world.chunks)
        print(f'[day] 相位={phase} {S.describe(k.cycle.time)} '
              f'day_factor={k.day_factor():.3f}', flush=True)


def main():
    only = None
    if '--only' in sys.argv:
        only = float(sys.argv[sys.argv.index('--only') + 1])
    import pyglet
    shots = [s for s in SHOTS if only is None or abs(s[0] - only) < 1e-9]
    rc = 0
    for phase, name in shots:
        out = os.path.join(_ROOT, 'shots', f'{name}.png')
        app = DayShot(phase, 1400, 800)
        state = {'t': 0.0, 'shot': False}

        def _beat(dt, _app=app, _out=out, _st=state):
            _st['t'] += dt
            if not _st['shot'] and _app.meshes_ready() and _st['t'] >= 1.0:
                _st['shot'] = True
                _app._shot_pending = _out
                print(f'[day] 截图 {_out}', flush=True)

        pyglet.clock.schedule_interval(_beat, 0.3)
        try:
            pyglet.app.run()
        except Exception as exc:                     # noqa: BLE001
            print(f'[day] {name} 失败：{exc}', flush=True)
            rc = 1
        pyglet.clock.unschedule(_beat)
    print('== DAYSHOTS_OK ==', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
