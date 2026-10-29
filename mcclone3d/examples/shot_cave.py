# -*- coding: utf-8 -*-
"""Phase 2-C 目视：洞口一眼 + 地下洞穴一张（洞里放一支火把）。

    python examples/shot_cave.py
    python examples/shot_cave.py --only deep

判据（人眼可判，且与内核读数对拍）：
* **洞口**：地表上有个黑洞，洞里**明显比地面暗**（天光进不去）；
* **洞穴内部**：四周是石头，**火把周围有一圈暖光**、远处仍是黑的
  —— 这是 Phase 2-A 光照与 2-C 洞穴的联动（洞里天光 = 0，光只来自火把）。
* 矿物：洞穴壁上是**带彩色斑点的矿石**（煤黑/铁橙/金黄/钻石青）。

脚本会打印相机位置、所在格的天光/方块光与附近矿石统计 —— 截图与数字一起看。
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

from mcclone3d import blocks as B                                  # noqa: E402
from mcclone3d import caves as CV                                  # noqa: E402

SHOTS = ('hole', 'deep')


def _yaw_to(frm, to) -> float:
    """游戏 yaw 约定（与 `mobs.step_mob` 同一套）：`yaw = atan2(-dx, -dz)`。"""
    import math
    return math.degrees(math.atan2(-(to[0] - frm[0]), -(to[2] - frm[2])))


def _find_biggest_pocket(k, need_air=40):
    """找一个**中心格确实是空气**的大空腔（5×5×5 里空气格够多）。

    ⚠ 初版只按"5×5×5 空气数"取最大，结果**中心格可能是石头** ⇒ 相机埋在方块里，
    画面看到的是被背面剔除掉的石面（实测：拍出一张草地纹理，洞穴完全没出现）。
    """
    best, best_n = None, need_air
    w = k.world
    for x in range(4, k.size - 6, 2):
        for z in range(4, k.size - 6, 2):
            for y in range(4, k.world.sea_level - 2):
                if w.get(x, y, z) != B.AIR or w.get(x, y + 1, z) != B.AIR:
                    continue                      # 相机要站得下（脚下+一格）
                n = 0
                for dx in (-2, -1, 0, 1, 2):
                    for dy in (-2, -1, 0, 1, 2):
                        for dz in (-2, -1, 0, 1, 2):
                            if w.get(x + dx, y + dy, z + dz) == B.AIR:
                                n += 1
                if n > best_n:
                    best, best_n = (x, y, z), n
                    if n > 70:                    # 够大就收手
                        return best, n
                break                             # 每列只看最上面那格可站的空气
    return best, best_n


def _ores_near(w, x, y, z, r=6):
    from mcclone3d.blocks import BLOCK_IDS
    names = {n: 0 for n in ('coal_ore', 'iron_ore', 'gold_ore', 'diamond_ore')}
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            for dz in range(-r, r + 1):
                bid = w.get(x + dx, y + dy, z + dz)
                for n in names:
                    if bid == BLOCK_IDS[n]:
                        names[n] += 1
    return {n: c for n, c in names.items() if c}


class CaveShot(demo.McCloneApp):
    def __init__(self, which, *a, **kw):
        super().__init__(*a, **kw)
        k = self.kernel
        k.cycle.skip_to_phase(0.25)                   # 白天：洞里的黑才对比得出来
        w = k.world

        if which == 'hole':
            holes = CV.tunnels(k.seed, k.size, k.height, w.sea_level).holes
            spot = None
            for (x, z), h in sorted(holes.items()):
                if w.get(x, h, z) == B.AIR and w.get(x, h - 1, z) == B.AIR \
                        and w.get(x, h - 2, z) == B.AIR:
                    spot = (x, h, z)
                    break
            if spot is None:
                raise RuntimeError('一个 worm 洞口都没找到')
            x, h, z = spot
            # 相机放在洞口**正上方**、垂直俯视：先前"退到 6 格外平视"会被近处
            # 草坡整个挡住（实测：拍出来一张草地纹理，洞口完全不在画面里）。
            # 俯视是唯一能稳定"一眼看到洞"的机位。
            k.flying = True
            k.pos = [x + 0.5, float(h + 2.0), z + 0.5]
            k.yaw, k.pitch = 0.0, -89.0
            tag = f'洞口({x},{h},{z})'
        else:
            pocket, n_air = _find_biggest_pocket(k)
            if pocket is None:
                raise RuntimeError('没找到够大的洞穴空腔')
            x, y, z = pocket
            # 相机退到空腔**边缘**、朝里俯视 ⇒ 画面有纵深（站在正中心会拍成
            # "四面都是墙"）。火把放 5 格外：太近会把石头照成一片死白。
            k.flying = True
            k.pos = [x + 0.5, float(y + 0.05), z + 0.5]
            k.yaw = _yaw_to(k.pos, (float(x), float(y), float(z)))
            k.pitch = -2.0
            tx, tz = x, z
            ty = y
            while ty > 2 and w.get(tx, ty, tz) == B.AIR:
                ty -= 1
            w.set(tx, ty + 1, tz, B.TORCH)
            tag = f'空腔({x},{y},{z}) 空气{n_air}/125 火把@({tx},{ty + 1},{tz})'

        k.dirty_chunks = set(w.chunks)
        mx, my, mz = int(k.pos[0]), int(k.pos[1]), int(k.pos[2])
        print(f'[cave] {which}: {tag} 相机={[round(v, 1) for v in k.pos]} '
              f'yaw={k.yaw} 天光={k.light.sky(mx, my, mz)} '
              f'方块光={k.light.block(mx, my, mz)} '
              f'附近矿石={_ores_near(w, mx, my, mz)}', flush=True)


def main():
    which = 'both'
    if '--only' in sys.argv:
        which = sys.argv[sys.argv.index('--only') + 1]
    import pyglet
    rc = 0
    for name in ([which] if which in SHOTS else list(SHOTS)):
        out = os.path.join(_ROOT, 'shots', f'phase2c_{name}.png')
        app = CaveShot(name, 1400, 800)
        state = {'t': 0.0, 'shot': False}

        def _beat(dt, _app=app, _out=out, _st=state, _name=name):
            _st['t'] += dt
            # 等网格 + 光照都就绪（洞穴让世界更大，首帧上传更久）
            if not _st['shot'] and _app.meshes_ready() and _st['t'] >= 3.0:
                _st['shot'] = True
                _app._shot_pending = _out
                print(f'[cave] 截图 {_out}', flush=True)

        pyglet.clock.schedule_interval(_beat, 0.3)
        try:
            pyglet.app.run()
        except Exception as exc:                     # noqa: BLE001
            print(f'[cave] {name} 失败：{exc}', flush=True)
            rc = 1
        pyglet.clock.unschedule(_beat)
    print('== CAVESHOTS_OK ==', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
