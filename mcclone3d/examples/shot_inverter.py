# -*- coding: utf-8 -*-
"""Phase 3-B 目视：**反相器**（红石火把被强充能 ⇒ 熄灭 ⇒ 灯灭）。

    python examples/shot_inverter.py
    python examples/shot_inverter.py --only on

同一个机位拍两张：**拉杆关**（火把亮 → 反相线通电 → 灯亮）与
**拉杆开**（中继器亮 ⇒ 强充能它正面的实心块 ⇒ 块上的火把熄灭 ⇒ 灯灭）。

判据（人眼可判，且与内核读数对拍）：

* 通电后**块上的火把变成暗灰头**（`redstone_torch` → `redstone_torch_off` 两个状态 id
  各有一张贴图 —— 状态不同、贴图相同的话玩家只能靠猜）；
* 灯跟着灭：火把的输出只进了红石线，线断了灯就灭（反相器把"有电"翻成"没电"）。

为什么这张图值得拍：反相器是这一批的新语义（火把从"常亮电源"变成"反相器"），
而它同时是**时钟**成立的前提（反相器瞬时 + 中继器延迟 = 环形振荡）。

⚠ 时钟本身拍不出来（它是时间上的行为）—— 时钟的判据在
`cli --only tickqueue`（1 档 29 次/3s、3 档 10 次/3s、8s 不漂相位）与
`tests.test_redstone` 的 `t_clock*` / `t_phase_no_drift` 里。
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
#: 用 3 档中继器（0.3s）：延迟长一点，日志里的"待触发事件"读起来更直观
_TIER = 2


def _yaw_to(frm, to) -> float:
    return math.degrees(math.atan2(-(to[0] - frm[0]), -(to[2] - frm[2])))


def _build(k, lever_on: bool, x0: int, y0: int, z0: int) -> str:
    """在平台 (x0, y0, z0) 上摆一台反相器，返回装置摘要。"""
    w = k.world
    put = w.set_generated

    def place(x, y, z, bid):
        """放置 + `mark` —— 网络式重算靠这一手（与 `kernel.place` 同口径）。"""
        put(x, y, z, bid)
        k.redstone.mark(x, y, z)

    # 装置：拉杆 → 线 → 中继器（朝东）→ **实心块** → 块上的火把 → 线 → 灯
    place(x0, y0, z0, B.LEVER_ON if lever_on else B.LEVER_OFF)
    place(x0 + 1, y0, z0, B.REDSTONE_WIRE)
    place(x0 + 2, y0, z0, B.REPEATER_BY_DIR_DELAY[('east', _TIER)][0])
    place(x0 + 3, y0, z0, B.STONE)                     # 会被中继器**强充能**的块
    place(x0 + 3, y0 + 1, z0, B.REDSTONE_TORCH)        # 火把坐在块上（脚底 = 那个块）
    place(x0 + 4, y0, z0, B.COBBLE)                    # 给上面的线一块支撑（别悬空）
    place(x0 + 4, y0 + 1, z0, B.REDSTONE_WIRE)
    place(x0 + 5, y0, z0, B.COBBLE)
    place(x0 + 5, y0 + 1, z0, B.LAMP_OFF)
    # 平台（圆石：比石头暗 ⇒ 火把与灯的明暗对比更明显）。铺大一圈当"画框"。
    for dx in range(-2, 10):
        for dz in range(-3, 4):
            put(x0 + dx, y0 - 1, z0 + dz, B.COBBLE)
    # 结算信号：**必须推进时间**（Phase 3-B 起中继器有延迟，只 step(0.0) 会停在"排队待翻转"）
    k.redstone.run_until_stable(max_ticks=20, dt=0.05)
    torch = w.get(x0 + 3, y0 + 1, z0)
    return (f'拉杆={"开" if lever_on else "关"} '
            f'中继器={B.name_of(w.get(x0 + 2, y0, z0))} '
            f'（{B.REPEATER_DELAY_OF[w.get(x0 + 2, y0, z0)] + 1} 档 / '
            f'{B.repeater_delay(w.get(x0 + 2, y0, z0)):.1f}s 延迟） '
            f'火把={B.name_of(torch)} '
            f'灯={B.name_of(w.get(x0 + 5, y0 + 1, z0))} '
            f'块被强充能={k.redstone.strongly_powered(x0 + 3, y0, z0)} '
            f'待触发事件={k.redstone.pending_count()}')


class InverterShot(demo.McCloneApp):
    def __init__(self, which, *a, **kw):
        super().__init__(*a, **kw)
        k = self.kernel
        k.cycle.skip_to_phase(0.25)                 # 白天（火把/灯的明暗才对比得出来）
        k.weather_kind = 'clear'                    # 固定晴天，别让雨线糊住装置
        w = k.world
        # 场地：**架空到地形之上的干净台面**，并把周围清空。
        # ⚠ 前两版把装置摆在村庄旁边（"有参照物"）—— 结果画面里树/房/山坡占了大半，
        #   装置只占一小块，读数全看不出来。拍小装置的第一原则是**画面里只有装置**。
        x0, z0 = 64, 64
        y0 = int(w.sea_level) + 12
        for dx in range(-7, 14):
            for dz in range(-9, 9):
                for dy in range(-2, 8):
                    w.set_generated(x0 + dx, y0 + dy, z0 + dz, B.AIR)
        tag = _build(k, which == 'on', x0, y0, z0)
        # 机位：站在装置正前方（距 ~4.6 格、比装置高 2.2 格）。
        # ⚠ 机位调了三版才对，三次都是"尺寸没对准"：
        #   ① 6.5 格外 + 3 格高 ⇒ 装置只占一小块，"火把是亮头还是暗头"看不出来；
        #   ② 4.2 格外 + 2.4 格高 ⇒ 又太近，相机几乎贴进装置里（方块被放大成一整屏）；
        #   ③ 5.4 格外 + 2.9 格高 + 俯角 18° ⇒ 整台装置（拉杆→线→中继器→块+火把→线→灯）
        #      一行排开、且"灯的亮黄 vs 暗棕"一眼可辨 —— 那正是反相器的证据。
        #   拍红石这类**小装置**：机位要按"装置尺寸"给，不能按"看的舒服"给。
        k.flying = True
        #   ④ 最终用**垂直俯视**：装置是一行 6 格的小东西，斜视角下"1/8 格高的红石线"
        #      会被看成一大块红板、火把与中继器互相遮挡 —— 俯视把每一格摊平，最好判读。
        k.pos = [x0 + 2.5, y0 + 7.0, z0 + 0.5]
        k.yaw, k.pitch = 0.0, -89.0
        k.dirty_chunks = set(w.chunks)
        print(f'[inverter] {which}: 装置@({x0},{y0},{z0}) 相机={[round(v, 1) for v in k.pos]} '
              f'{tag} 通电格={len(k.redstone.power)}', flush=True)


def main():
    which = 'both'
    if '--only' in sys.argv:
        which = sys.argv[sys.argv.index('--only') + 1]
    import pyglet
    rc = 0
    for name in ([which] if which in SHOTS else list(SHOTS)):
        out = os.path.join(_ROOT, 'shots', f'phase3b_inverter_{name}.png')
        app = InverterShot(name, 1400, 800)
        state = {'t': 0.0, 'shot': False}

        def _beat(dt, _app=app, _out=out, _st=state):
            _st['t'] += dt
            if not _st['shot'] and _app.meshes_ready() and _st['t'] >= 3.5:
                _st['shot'] = True
                _app._shot_pending = _out
                print(f'[inverter] 截图 {_out}', flush=True)

        pyglet.clock.schedule_interval(_beat, 0.3)
        try:
            pyglet.app.run()
        except Exception as exc:                     # noqa: BLE001
            print(f'[inverter] {name} 失败：{exc}', flush=True)
            rc = 1
        pyglet.clock.unschedule(_beat)
    print('== INVERTERSHOTS_OK ==', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
