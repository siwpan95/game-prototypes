# -*- coding: utf-8 -*-
"""Phase 2-C 目视：村庄（白天全景 / 夜里灯火）两张。

    python examples/shot_village.py
    python examples/shot_village.py --only night

判据（人眼可判，且与内核读数对拍）：
* **白天**：一眼看到一座村 —— 四栋房子（木板墙 + 玻璃窗 + 挑檐屋顶）、
  十字砂砾路、中间一口井、两块围着田埂的农田（麦子长在土上）；
* **夜里**：村里**只有火把这一圈暖光**、房子窗里透光，而村外一片黑
  —— 这就是"灯火即安全区"的机制（`cli --only village` 里"村内暗格 0"那条）。
  照片里站着几个村民（脚本显式放的，不是随机刷的）。

脚本会打印村庄坐标、相机读数、四栋房门洞/火把的实测值与村民位置 —— 图与数字一起看。
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
from mcclone3d import structures as ST                             # noqa: E402

SHOTS = ('day', 'night')


def _yaw_to(frm, to) -> float:
    """游戏 yaw 约定（与 `mobs.step_mob` 同一套）：`yaw = atan2(-dx, -dz)`。"""
    return math.degrees(math.atan2(-(to[0] - frm[0]), -(to[2] - frm[2])))


def _village_report(k, vx, vy, vz) -> str:
    w = k.world
    doors = torches = 0
    for (sx, sz) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        hx, hz = vx + sx * ST.HOUSE_OFF, vz + sz * ST.HOUSE_OFF
        ddx = -sx
        cells = [(hx + ddx * ST.HOUSE_HW, vy + dy, hz) for dy in (1, 2)]
        doors += all(w.get(*c) == B.AIR for c in cells)
        torches += any(w.get(x, y, z) == B.TORCH
                       for x in range(hx - ST.HOUSE_HW, hx + ST.HOUSE_HW + 1)
                       for y in range(vy + 1, vy + ST.HOUSE_WALL + 1)
                       for z in range(hz - ST.HOUSE_HW, hz + ST.HOUSE_HW + 1))
    crops = sum(1 for x in range(vx - 3, vx + 4)
                for z in range(vz - ST.HOUSE_OFF - 3, vz + ST.HOUSE_OFF + 4)
                if w.get(x, vy + 1, z) == B.CROP)
    return f'门洞通 {doors}/4 屋内有火把 {torches}/4 田里作物 {crops} 株'


class VillageShot(demo.McCloneApp):
    def __init__(self, which, *a, **kw):
        super().__init__(*a, **kw)
        k = self.kernel
        w = k.world
        if not w.villages:
            raise RuntimeError(f'seed={k.seed} size={k.size} 没有村庄（换个种子或更大的世界）')
        vx, vy, vz = w.villages[0]

        if which == 'day':
            k.cycle.skip_to_phase(0.25)                 # 白天：建筑细节看得清
            # ⚠ 固定晴天（`weather_kind` 是内核的固定天气口）：自然天气有 40% 时段在下雨，
            #   雨线糊在画面上会挡住建筑细节（实测拍到过满屏雨丝的村庄图）。
            k.weather_kind = 'clear'
            # **垂直俯视整村**：斜视会被最近那栋的挑檐屋顶挡住其余三栋（实测：
            # 斜视只能确认"有一栋房子"，看不出这是一座村）。俯视能一次收齐
            # 四栋房 + 十字路 + 井 + 两块田 + 门廊火把 —— 验收图要的是布局，不是氛围。
            # 氛围交给 night 那张（斜俯视看灯火）。
            k.flying = True
            k.pos = [vx + 0.5, float(vy + 24.0), vz + 0.5]
            k.yaw, k.pitch = 0.0, -89.0
        else:
            k.cycle.skip_to_phase(0.75)                 # 午夜：只剩火把
            k.weather_kind = 'clear'
            # ⚠ 机位不能离房子太近：初版站在 (+6.5,+6.5)，那正好是东北那栋房的**墙里**
            #   ⇒ 拍出一张全黑（贴在墙面上）。现在悬在村庄中心上空、斜俯视，
            #   画面里同时有：井口四支火把、两栋房的门廊火把与窗、以及暗处的村民剪影。
            k.flying = True
            k.pos = [vx - 4.0, float(vy + 6.5), vz - 4.0]
            k.yaw = _yaw_to(k.pos, (float(vx + 6), float(vy + 1), float(vz + 6)))
            k.pitch = -26.0
            # 村里站几个村民（显式放，截图要可复现；随机刷怪要等 tick）
            for i, (dx, dz) in enumerate(((3, -1), (-2, 3), (1, 4), (-4, -2))):
                k.spawn_mob('villager', vx + dx + 0.5, float(vy + 1), vz + dz + 0.5)

        k.dirty_chunks = set(w.chunks)
        mx, my, mz = int(k.pos[0]), int(k.pos[1]), int(k.pos[2])
        vs = [m for m in k.mobs if m.kind.name == 'villager']
        print(f'[village] {which}: 村庄({vx},{vy},{vz}) 相机={[round(v, 1) for v in k.pos]} '
              f'yaw={k.yaw:.1f} 天光={k.light.sky(mx, my, mz)} '
              f'方块光={k.light.block(mx, my, mz)} 玩家所在格光='
              f'{max(k.light.block(mx, my, mz), int(round(k.light.sky(mx, my, mz) * k.day_factor())))} '
              f'| {_village_report(k, vx, vy, vz)} '
              f'| 村民 {len(vs)} 只 {[ (round(m.pos[0],1), round(m.pos[2],1)) for m in vs ]}',
              flush=True)


def main():
    which = 'both'
    if '--only' in sys.argv:
        which = sys.argv[sys.argv.index('--only') + 1]
    import pyglet
    rc = 0
    for name in ([which] if which in SHOTS else list(SHOTS)):
        out = os.path.join(_ROOT, 'shots', f'phase2c_village_{name}.png')
        app = VillageShot(name, 1400, 800)
        state = {'t': 0.0, 'shot': False}

        def _beat(dt, _app=app, _out=out, _st=state):
            _st['t'] += dt
            if not _st['shot'] and _app.meshes_ready() and _st['t'] >= 3.0:
                _st['shot'] = True
                _app._shot_pending = _out
                print(f'[village] 截图 {_out}', flush=True)

        pyglet.clock.schedule_interval(_beat, 0.3)
        try:
            pyglet.app.run()
        except Exception as exc:                     # noqa: BLE001
            print(f'[village] {name} 失败：{exc}', flush=True)
            rc = 1
        pyglet.clock.unschedule(_beat)
    print('== VILLAGESHOTS_OK ==', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
