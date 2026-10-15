# -*- coding: utf-8 -*-
"""生物目视：白天一张（羊/猪游荡）、午夜一张（僵尸追击）。

    python examples/shot_mobs.py            # 两张都拍
    python examples/shot_mobs.py --only 0.75

判据（人眼可判，且与内核读数对拍）：
* 白天：生物的顶点色随所处光照变（露天亮、树荫下暗）—— **不许一身死白**
  （光照曾经被烘进顶点色，夜里/洞里全亮，截图一眼穿帮，现在走逐实例 uniform）；
* 午夜：整体压暗但还能看清轮廓（`light_scale` 地板 0.10），暗处偏蓝；
* 僵尸是 5 格高的人形，羊是 3 格高的四足 —— 体型差看得出来。

脚本会打印每种生物的数量与所在格的有效光 —— 截图与数字一起看。
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

from mcclone3d import mobs as MB                            # noqa: E402

SHOTS = (
    (0.25, 'phase2b_day_mobs'),
    (0.75, 'phase2b_night_mobs'),
)


class MobShot(demo.McCloneApp):
    def __init__(self, phase, *a, **kw):
        super().__init__(*a, **kw)
        k = self.kernel
        k.cycle.skip_to_phase(float(phase))
        cx, cz = 128, 128
        # 机位与 shot_day 完全相同（便于与昼夜三张对比）：站在地表上方朝 +z 看
        k.flying = True
        k.pos = [cx + 0.5, k.world.surface_at(cx, cz) + 3.0, cz + 6.5]
        k.yaw, k.pitch = 180.0, -10.0
        # 显式放几只生物在镜头里（自然刷新在 16~48 格外，且可能被地形挡住 ——
        # 截图要的是"一定能看到"，所以显式摆；自然刷的那些是锦上添花）
        near = (('sheep', cx - 6.0, cz + 13.0), ('sheep', cx + 4.0, cz + 17.0),
                ('pig', cx - 1.0, cz + 21.0))
        if k.cycle.is_night():
            near = (('zombie', cx - 6.0, cz + 13.0), ('zombie', cx + 4.0, cz + 17.0),
                    ('zombie', cx - 1.0, cz + 21.0))
        for name, x, z in near:
            k.spawn_mob(name, x, None, z)
        k.dirty_chunks = set(k.world.chunks)
        counts = {}
        for m in k.mobs:
            counts[m.kind.name] = counts.get(m.kind.name, 0) + 1
        print(f'[mobs] 相位={phase} is_night={k.cycle.is_night()} '
              f'day_factor={k.day_factor():.3f} 显式放置后 {counts}', flush=True)

    def _report_mobs(self, tag):
        """把每种生物的数量与所在格有效光打出来（截图与数字一起看）。"""
        k = self.kernel
        out = []
        for m in k.mobs:
            mx, my, mz = int(m.pos[0]), int(m.pos[1]), int(m.pos[2])
            lvl = max(k.light.block(mx, my, mz),
                      int(round(k.light.sky(mx, my, mz) * k.day_factor())))
            out.append(f'{m.kind.name}@({mx},{my},{mz}) 光={lvl}')
        print(f'[mobs] {tag} 共 {len(k.mobs)} 只：{"; ".join(out[:8])}'
              f'{" ..." if len(out) > 8 else ""}', flush=True)


def main():
    only = None
    if '--only' in sys.argv:
        only = float(sys.argv[sys.argv.index('--only') + 1])
    import pyglet
    rc = 0
    for phase, name in [s for s in SHOTS if only is None or abs(s[0] - only) < 1e-9]:
        out = os.path.join(_ROOT, 'shots', f'{name}.png')
        app = MobShot(phase, 1400, 800)
        state = {'t': 0.0, 'shot': False}

        def _beat(dt, _app=app, _out=out, _st=state, _name=name):
            _st['t'] += dt
            # ⚠ 等到网格与生物都就绪再截（生物网格在第一帧 on_draw 才上传）
            if not _st['shot'] and _app.meshes_ready() and _st['t'] >= 2.0:
                _st['shot'] = True
                _app._report_mobs(_name)
                _app._shot_pending = _out
                print(f'[mobs] 截图 {_out}', flush=True)

        pyglet.clock.schedule_interval(_beat, 0.3)
        try:
            pyglet.app.run()
        except Exception as exc:                     # noqa: BLE001
            print(f'[mobs] {name} 失败：{exc}', flush=True)
            rc = 1
        pyglet.clock.unschedule(_beat)
    print('== MOBSHOTS_OK ==', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
