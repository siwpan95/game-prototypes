# -*- coding: utf-8 -*-
"""Phase 3-D 目视：**同一机位、同一世界**，只换资源包，拍三张对照。

    python examples/shot_pack.py               # 无包 / autumn / retro 三张
    python examples/shot_pack.py --only autumn

判据（人眼可判，且与内核读数对拍）：
* **同一机位**：三张的地形轮廓、远近关系、光照必须**完全一致** —— 资源包是纯外观层，
  几何/UV/剔除一个字节都没动（`--only default` 与 `--only autumn` 的差异图应当
  **只落在贴图纹理上**，不落在轮廓上）；
* **autumn**：草木从绿变橙红、水变绿调，且因为 32px 分辨率所以**细节更细**；
* **retro**：颜色仍在**同一色相**，但只剩每通道 4 档 ⇒ 出现明显的**色阶块**
  （分辨率没变，所以颗粒大小与"无包"一致 —— 这两张对照能证明"换分辨率"与
  "换像素"是两条独立的轴）。

日志里每张都带 `资源包=Npx(名字)`，与画面一起看 —— "看着像高清包"不算判据。
"""
from __future__ import annotations

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
# ⚠ 本文件与 demo 同目录、而 demo 与**包**同名（`examples/mcclone3d.py` vs `mcclone3d/`），
# 所以按文件路径把 demo 加载成独立模块名（`_demo`），不让 `examples/` 进 sys.path。
_spec = importlib.util.spec_from_file_location('_demo', os.path.join(_HERE, 'mcclone3d.py'))
demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo)

from mcclone3d import blocks as B                    # noqa: E402
from mcclone3d import packs as PK                    # noqa: E402

#: `(包 id | None, 输出文件名)`
SHOTS = ((None, 'phase3d_pack_default.png'),
         ('autumn', 'phase3d_pack_autumn.png'),
         ('retro', 'phase3d_pack_retro.png'))


class PackShot(demo.McCloneApp):
    """材质样张机位：贴近看一片"每种材质一条"的样张 + 背后留出自然地形。

    为什么要在镜头里**同时拍到样张与自然地形**：只看样张会漏掉"这个包在某类方块上
    出问题"（例如只改了草木、没改矿石）；只看自然地形又没法逐格比较。
    时刻固定在**正午**（`--phase 0.25`）：贴图差异要在明亮、无长阴影的条件下比。
    """

    PHASE = 0.25                       # 正午（截图可复现；与 shot_weather 同一口径）

    def __init__(self, pack_spec, *a, **kw):
        super().__init__(*a, pack=pack_spec, **kw)
        k = self.kernel
        k.cycle.skip_to_phase(self.PHASE)
        # 天气固定成晴：自然天气每 90s 换一段，雨丝会盖在贴图上，
        # "这张是高清包"与"这张在下雨"就分不清了（截图必须可复现）。
        k.weather_kind = 'clear'
        cx, cz = 128, 128
        y = k.world.surface_at(cx, cz) + 1
        mats = (B.GRASS, B.DIRT, B.STONE, B.SAND, B.LOG, B.PLANKS,
                B.GLASS, B.COBBLE, B.BRICK, B.SNOW, B.COAL_ORE, B.DIAMOND_ORE)
        for i in range(24):
            for j in range(24):
                k.world.set(cx - 12 + i, y, cz - 12 + j, mats[(i // 2) % len(mats)])
        # 一排"高处样张"：矿脉与木料，让高分辨率包的细节看得出来
        for h in range(1, 7):
            for j in range(-12, 13, 4):
                k.world.set(cx - 14, y + h, cz + j,
                            (B.COAL_ORE, B.IRON_ORE, B.GOLD_ORE, B.DIAMOND_ORE,
                             B.BRICK, B.STONE, B.SNOW)[h % 7])
        for h in range(1, 5):
            k.world.set(cx + 14, y + h, cz - 8, B.LOG)
            k.world.set(cx + 14, y + h, cz + 8, B.LEAVES)
        # 水：放进样张里当一格。⚠ 必须重标"源"，否则它是玩家放的非源水，
        # 会按 `fluid` 的模型向外流并干涸（样张自己会烂掉）。
        for i in range(24):
            k.world.set(cx - 12 + i, y, cz + 11, B.WATER)
        k.fluid.mark_sources(k.world)
        # 清一条**观察走廊**：样张南侧几排地形起伏不定，高一点的地块会把样张
        # 整条挡住（实测：相机挪远 4 格就撞上土坡，"材质对比图"变成了"草地特写"）。
        # 与其碰运气找机位，不如把走廊削平 —— 三张的取景因此**逐像素一致**，
        # 差异图就只剩贴图本身（这才是这张图要证明的东西）。
        for z in range(cz - 20, cz - 12):
            for x in range(cx - 15, cx + 16):
                for h in range(1, 24):
                    k.world.set(x, y + h, z, B.AIR)
        k.flying = True
        k.pos = [cx + 0.5, y + 3.2, cz - 14.0]
        k.yaw, k.pitch = 180.0, -17.0
        k.dirty_chunks = set(k.world.chunks)
        print(f'[pack] {k.pack_report()} 时刻={k.cycle.time:.1f}s '
              f'day_factor={k.day_factor():.3f} '
              f'相机={[round(v, 1) for v in k.pos]} yaw={k.yaw} pitch={k.pitch} '
              f'图集={self.atlas_layout.size}px', flush=True)


def _ensure_packs():
    """把演示包写到 `packs/`（已存在就跳过）—— 不依赖仓里带二进制。"""
    need = {s for s, _f in SHOTS if s}
    have = {pid for pid, _n, _p in PK.discover()}
    for kind in sorted(need - have):
        pk = PK.write_demo_pack(os.path.join(PK.PACK_ROOT, kind), kind)
        print(f'[pack] 生成演示包：{pk.report()}', flush=True)


def main():
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    _ensure_packs()
    import pyglet

    rc = 0
    for spec, fname in SHOTS:
        tag = spec or 'default'
        if only and only != tag:
            continue
        out = os.path.join(_ROOT, 'shots', fname)
        try:
            app = PackShot(spec, 1600, 900, verbose=True)
        except Exception as exc:                     # noqa: BLE001
            print(f'[pack] {tag} 装配失败：{exc}', flush=True)
            rc = 1
            continue
        state = {'t': 0.0, 'shot': False}

        def _beat(dt, _app=app, _out=out, _st=state, _k=tag):
            _st['t'] += dt
            _app.sanity_report(f'pack/{_k}')
            # ⚠ 等网格**全部**上传再截：首帧分帧上传，早截会拍到没传完的世界。
            if not _st['shot'] and _app.meshes_ready() and _st['t'] >= 2.0:
                _st['shot'] = True
                _app._shot_pending = _out
                print(f'[pack] 截图 {_out}（{_k}）', flush=True)

        pyglet.clock.schedule_interval(_beat, 1.0)
        try:
            pyglet.app.run()
        except Exception as exc:                     # noqa: BLE001
            print(f'[pack] {tag} 渲染失败：{exc}', flush=True)
            rc = 1
        pyglet.clock.unschedule(_beat)
    print('== PACKSHOTS_OK ==', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
