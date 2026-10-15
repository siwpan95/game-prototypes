# -*- coding: utf-8 -*-
"""Phase 3 目视：一条完整的红石线路（拉杆 → 线 → 灯 / 门 / 活塞）。

    python examples/shot_redstone.py
    python examples/shot_redstone.py --only on

同一个机位拍两张：**拉杆关**（全暗）与**拉杆开**（灯亮、门开、活塞推出）。
判据（人眼可判，且与内核读数对拍）：

* 红石线的亮度**顺着信号衰减**（离拉杆越远越暗）—— 顶点色把信号强度画出来了；
* 拉杆开 ⇒ 红石灯亮（**它同时是光源**：周围地面被照亮，这是 Phase 2-A × Phase 3 的联动）；
* 铁门通电**打开**（中间镂空、能穿过去）；活塞通电**推出臂**并把石头顶开一格。

脚本会打印装置每一格的信号强度与关键方块的状态 —— 图和数字一起看。
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
#: 演示平台的地基高度（在地表之上找一块空地）
_Y_OFF = 4


def _yaw_to(frm, to) -> float:
    return math.degrees(math.atan2(-(to[0] - frm[0]), -(to[2] - frm[2])))


def _build(k, lever_on: bool, x0: int, y0: int, z0: int) -> str:
    """在平台 (x0, y0, z0) 上摆一条完整线路，返回装置摘要。"""
    w = k.world
    put = w.set_generated

    def line(x, z, n=1):
        for i in range(n):
            put(x + i, y0, z, B.REDSTONE_WIRE)

    # 主线：拉杆 → 3 格线 → 中继器 → 2 格线 → 灯（**总共 8 格**）
    # ⚠ 刻意做短：装置越长，远处的线在 FOV + mipmap 下越淡（贴图是透明背景的细线，
    #   远处被 mip 平均后 alpha 掉到 discard 阈值以下 ⇒ 那几格"看不见"）——
    #   实测 11 格的版本拍出来只有近处 3~4 格可见。8 格 + 近机位才整条都看得清。
    put(x0, y0, z0, B.LEVER_ON if lever_on else B.LEVER_OFF)
    line(x0 + 1, z0, 4)                            # 4 格：衰减看得见（15→12）
    put(x0 + 5, y0, z0, B.REPEATER_E_OFF)          # 朝东（输出朝 +x）
    line(x0 + 6, z0, 4)                            # 4 格：中继器**续满**（15→12）
    put(x0 + 10, y0, z0, B.LAMP_OFF)
    # 支线 1：门（挨着主线第 2 格）
    put(x0 + 2, y0, z0 - 1, B.REDSTONE_WIRE)
    put(x0 + 3, y0, z0 - 1, B.DOOR_LOWER)
    put(x0 + 3, y0 + 1, z0 - 1, B.DOOR_UPPER)
    # 支线 2：活塞（把石头顶开一格）
    put(x0 + 7, y0, z0 + 1, B.REDSTONE_WIRE)
    put(x0 + 7, y0, z0 + 2, B.BLOCK_IDS['piston_east_off'])
    put(x0 + 8, y0, z0 + 2, B.STONE)
    # 平台（圆石，比石头暗 ⇒ 红石线与灯亮起来的对比更明显）。
    # ⚠ 平台只比装置大一圈：早先铺 14×9，装置在画面上只占一小块（实测）。
    for dx in range(0, 12):
        for dz in range(-2, 4):
            put(x0 + dx, y0 - 1, z0 + dz, B.COBBLE)
    k.redstone.mark(x0, y0, z0)
    # 立即算一轮（不等每帧预算）
    for _ in range(8):
        if not k.redstone.dirty:
            break
        k.redstone.step(0.0, budget=99)
    lv = [k.redstone.power_at(x0 + i, y0, z0) for i in range(1, 11)]
    return (f'拉杆={"开" if lever_on else "关"} '
            f'主线信号={lv} '
            f'灯={B.name_of(w.get(x0 + 10, y0, z0))} '
            f'门={B.name_of(w.get(x0 + 3, y0, z0 - 1))} '
            f'门上={B.name_of(w.get(x0 + 3, y0 + 1, z0 - 1))} '
            f'活塞={B.name_of(w.get(x0 + 7, y0, z0 + 2))} '
            f'臂={B.name_of(w.get(x0 + 8, y0, z0 + 2))} '
            f'石头={B.name_of(w.get(x0 + 9, y0, z0 + 2))}')


class RedstoneShot(demo.McCloneApp):
    def __init__(self, which, *a, **kw):
        super().__init__(*a, **kw)
        k = self.kernel
        k.cycle.skip_to_phase(0.25)                 # 白天（灯的照明效果要能对比出来）
        k.weather_kind = 'clear'                    # 固定晴天，别让雨线糊住装置
        w = k.world
        # 找一块空地：村庄旁边最好（有参照物），没有就退到世界中部
        if getattr(w, 'villages', None):
            vx, vy, vz = w.villages[0]
            x0, y0, z0 = vx + 20, vy + _Y_OFF, vz - 4
        else:
            x0, y0, z0 = 40, int(w.sea_level) + _Y_OFF, 40
        tag = _build(k, which == 'on', x0, y0, z0)
        # ⚠ 机位要**靠近**：红石线是 1/16 格的扁盒，站远了只看得到一条细线
        #   （实测 13 格外的俯拍像"石板上几个小点"，判据全看不出来）。
        # 这里用"站在装置前的玩家视角"（距 ~6.5 格、比装置高 2.4 格）：
        # 近到细线不会被 mip 吃掉，又整条线、灯、门、活塞同框。
        k.flying = True
        k.pos = [x0 + 5.0, y0 + 4.2, z0 - 8.0]
        k.yaw = _yaw_to(k.pos, (x0 + 5.0, y0 + 0.6, z0 + 0.5))
        k.pitch = -22.0
        k.dirty_chunks = set(w.chunks)
        print(f'[redstone] {which}: 装置@({x0},{y0},{z0}) 相机={[round(v,1) for v in k.pos]} '
              f'{tag} 通电格={len(k.redstone.power)}', flush=True)


def main():
    which = 'both'
    if '--only' in sys.argv:
        which = sys.argv[sys.argv.index('--only') + 1]
    import pyglet
    rc = 0
    for name in ([which] if which in SHOTS else list(SHOTS)):
        out = os.path.join(_ROOT, 'shots', f'phase3_redstone_{name}.png')
        app = RedstoneShot(name, 1400, 800)
        state = {'t': 0.0, 'shot': False}

        def _beat(dt, _app=app, _out=out, _st=state):
            _st['t'] += dt
            if not _st['shot'] and _app.meshes_ready() and _st['t'] >= 3.5:
                _st['shot'] = True
                _app._shot_pending = _out
                print(f'[redstone] 截图 {_out}', flush=True)

        pyglet.clock.schedule_interval(_beat, 0.3)
        try:
            pyglet.app.run()
        except Exception as exc:                     # noqa: BLE001
            print(f'[redstone] {name} 失败：{exc}', flush=True)
            rc = 1
        pyglet.clock.unschedule(_beat)
    print('== REDSTONESHOTS_OK ==', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
