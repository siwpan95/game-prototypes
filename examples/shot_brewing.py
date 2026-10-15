# -*- coding: utf-8 -*-
"""Phase 3-F 目视：**酿造台**（新方块）与 HUD 上的**药水效果格**。

    python examples/shot_brewing.py
    python examples/shot_brewing.py --only pad

为什么是这两张：本批只有一个新方块（酿造台），而"药水生效了"在画面上唯一的痕迹
就是 HUD 底部那排色块 —— 所以一张**近看方块**、一张**看着 HUD 读数**，
各盯一件事。两处都刻意**同时**出现（近景那张也有 HUD、远景那张也看得见酿造台）。

判据（人眼可判，且与内核读数对拍）：
* **近景**：石台上一台酿造台 —— 顶面是"三个瓶位"，侧面是石座 + 中间的玻璃缸与药液；
* **HUD**：经验条上面出现**五个格子**，只有生效的那几个点亮成对应颜色
  （迅捷=青、力量=橙红、抗性=蓝、剧毒=绿），宽度 = **剩余时长比例**；
* 日志里 `效果=…` 与画面上的色块**对得上** —— "看着像有 buff"不算判据。
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

from mcclone3d import blocks as B                # noqa: E402
from mcclone3d import brewing as BW              # noqa: E402
from mcclone3d import items as I                 # noqa: E402

SHOTS = (('pad', 'phase3f_brewing_pad.png'), ('buff', 'phase3f_brewing_buff.png'))

#: 让效果格**各自停在不同进度**上，一眼看出"宽度 = 剩余时长"这件事
EFFECTS = {'swiftness': 30.0,          # 满格
           'strength': 30.0 * 0.72,    # 七成
           'resistance': 30.0 * 0.45,  # 四成半
           'poison': 10.0 * 0.25}      # 两成半


class BrewingShot(demo.McCloneApp):
    def __init__(self, view, *a, **kw):
        super().__init__(*a, **kw)
        k = self.kernel
        k.cycle.skip_to_phase(0.25)          # 正午：贴图差异要在明亮条件下看
        k.weather_kind = 'clear'             # 雨丝会盖在贴图上（截图必须可复现）
        cx, cz = 128, 128
        y = k.world.surface_at(cx, cz) + 1
        # 一层石台 + 台中央的酿造台（+ 旁边一台附魔台作对照，一眼看出"这两个不一样"）
        for dx in range(-4, 5):
            for dz in range(-4, 5):
                k.world.set(cx + dx, y, cz + dz, B.STONE)
        for dy in (1, 2, 3):
            for dx in range(-4, 5):
                for dz in range(1, 6):
                    k.world.set_generated(cx + dx, y + dy, cz + dz, B.AIR)
        k.world.set(cx, y + 1, cz, B.BREWING_STAND)
        k.world.set(cx - 3, y + 1, cz, B.ENCHANT_TABLE)
        k.flying = True
        # 手里拿一瓶迅捷药水（"正在喝"的语境）
        sp = I.item_by_name('swiftness_potion')
        k.give(sp.id, 3)
        k.hotbar[0] = sp.id
        k.select(0)
        if view == 'pad':
            # 近景：贴着台子南侧、视线几乎垂直于侧面（看玻璃缸）
            k.pos = [cx + 0.5, y + 1.0, cz + 2.6]
            self._aim(k, (cx, y + 1, cz))
        else:
            # 远景：退后一点，把 HUD 与整片台子一起收进来
            k.pos = [cx + 0.5, y + 3.0, cz + 6.5]
            self._aim(k, (cx, y + 1, cz))
        # 效果与经验条：都设成"看得见"的状态（HUD 判据靠这一排色块）
        k.effects = dict(EFFECTS)
        want = 60
        while k.xp < want:
            k.add_xp(min(20, want - k.xp))
        k.dirty_chunks = set(k.world.chunks)
        print(f'[brewing] {view} 视角 pos={[round(v, 1) for v in k.pos]} '
              f'效果={k.effects_desc()} ｜ {k.xp_report()}', flush=True)

    @staticmethod
    def _aim(k, target):
        """把视线对准某格中心（**别手写角度** —— 算错会静默变成"没对着"）。"""
        ex, ey, ez = k.eye_pos()
        dx, dy, dz = target[0] + 0.5 - ex, target[1] + 0.5 - ey, target[2] + 0.5 - ez
        k.yaw = math.degrees(math.atan2(-dx, -dz))
        k.pitch = math.degrees(math.atan2(dy, math.hypot(dx, dz)))


def main():
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    import pyglet
    rc = 0
    for view, fname in SHOTS:
        if only and only != view:
            continue
        out = os.path.join(_ROOT, 'shots', fname)
        try:
            app = BrewingShot(view, 1400, 800, verbose=True)
        except Exception as exc:                     # noqa: BLE001
            print(f'[brewing] {view} 装配失败：{exc}', flush=True)
            rc = 1
            continue
        # 顺手把"喝药水"这条链路真的跑一遍（截图脚本也是验收的一部分）
        ok, why = app.kernel.drink()
        print(f'[brewing] 喝药水：{ok} {why} ｜ 效果 {app.kernel.effects_desc()}', flush=True)
        state = {'t': 0.0, 'shot': False}

        def _beat(dt, _app=app, _out=out, _st=state, _v=view):
            _st['t'] += dt
            _app.sanity_report(f'brewing/{_v}')
            if not _st['shot'] and _app.meshes_ready() and _st['t'] >= 2.0:
                _st['shot'] = True
                _app._shot_pending = _out
                print(f'[brewing] 截图 {_out}（{_v}）', flush=True)

        pyglet.clock.schedule_interval(_beat, 1.0)
        try:
            pyglet.app.run()
        except Exception as exc:                     # noqa: BLE001
            print(f'[brewing] {view} 渲染失败：{exc}', flush=True)
            rc = 1
        pyglet.clock.unschedule(_beat)
    print('== BREWINGSHOTS_OK ==', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
