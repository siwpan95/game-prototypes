# -*- coding: utf-8 -*-
"""Phase 2-C 第二批 目视：雨天一张 + 雪天一张（同一机位，只差天气）。

    python examples/shot_weather.py
    python examples/shot_weather.py --only rain

判据（人眼可判，且与内核读数对拍）：
* **雨**：屏幕有**竖直雨线**，且**整体天光比晴天暗**（`day_factor` ×0.72）；
* **雪**：雨线变成**短而带横向摆动的白点**，天光比雨天亮（×0.80 vs ×0.72）；
* 画面**不该整块发黑** —— 天气只压到 0.72/0.80，不是 0（`light_scale` 还有 0.10 地板）。

脚本用 `weather='rain'/'snow'` 配置口**固定天气**（自然天气每 90s 一段，
截图不可复现），日志带 `day_factor` 与天气强度。
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

SHOTS = (('rain', 0.25), ('snow', 0.25))


class WeatherShot(demo.McCloneApp):
    def __init__(self, kind, phase, *a, **kw):
        super().__init__(*a, **kw)
        k = self.kernel
        k.cycle.skip_to_phase(float(phase))          # 白天：雨 vs 雪差别最明显
        k.weather_kind = kind                         # 固定天气（截图可复现）
        cx, cz = 128, 128
        k.flying = True
        k.pos = [cx + 0.5, k.world.surface_at(cx, cz) + 6.0, cz + 0.5]
        k.yaw, k.pitch = 180.0, -12.0
        k.dirty_chunks = set(k.world.chunks)
        st = k.weather_state()
        print(f'[weather] {kind}: 天光={k.day_factor():.3f} '
              f'（晴天基准 {k.cycle.sky()["day_factor"]:.3f} ×{st["light_scale"]:.2f}）'
              f' 强度={st["intensity"]:.2f}', flush=True)


def main():
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    import pyglet
    rc = 0
    for kind, phase in [s for s in SHOTS if only is None or s[0] == only]:
        out = os.path.join(_ROOT, 'shots', f'phase2c_{kind}.png')
        app = WeatherShot(kind, phase, 1400, 800)
        state = {'t': 0.0, 'shot': False}

        def _beat(dt, _app=app, _out=out, _st=state, _k=kind):
            _st['t'] += dt
            if not _st['shot'] and _app.meshes_ready() and _st['t'] >= 2.5:
                _st['shot'] = True
                _app._shot_pending = _out
                print(f'[weather] 截图 {_out}', flush=True)

        pyglet.clock.schedule_interval(_beat, 0.3)
        try:
            pyglet.app.run()
        except Exception as exc:                     # noqa: BLE001
            print(f'[weather] {kind} 失败：{exc}', flush=True)
            rc = 1
        pyglet.clock.unschedule(_beat)
    print('== WEATHERSHOTS_OK ==', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
