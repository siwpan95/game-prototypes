# -*- coding: utf-8 -*-
"""Phase 3-E 目视：**同一个附魔台的两个角度** + 附魔前后（HUD 经验条）。

    python examples/shot_enchant.py
    python examples/shot_enchant.py --only top

为什么是"两个角度"而不是"随便找张图"：附魔台是本批唯一的**新方块**，而它
三面贴图不同（顶面摊开的书 / 侧面书脊）—— 这是"这个方块长得像它自己"的最低成本做法
（草方块/熔炉/工作台同一套路）。一张平视图只能证明"有个方块在那儿"，
平视 + 俯视才能证明**面映射真的接对了**。

判据（人眼可判，且与内核读数对拍）：
* **平视**：侧面是深紫黑带金属包边 + 中间一列书脊；HUD 底部出现**绿色经验条**；
* **俯视**：顶面是深色台面 + 一本摊开的书（两侧浅色书页 + 中间中缝）；
* 日志里两句话对得上：`附魔台 → 第 1/2/3 档…` 与 `附魔成功：效率 III ｜ 等级 12 → 11`。
  等级**掉 1 级**这件事在画面上只是经验条按比例缩短（本级进度按比例保留），
  所以真正的判据是日志里的等级数字，不是"看着短了没有"。
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

from mcclone3d import blocks as B                # noqa: E402
from mcclone3d import enchant as EN              # noqa: E402
from mcclone3d import items as I                 # noqa: E402

SHOTS = (('side', 'phase3e_enchant_side.png'), ('top', 'phase3e_enchant_top.png'))

#: 目标等级（经验条要有内容可看 ⇒ 给到第 12 级再补 2/3 条）
LEVEL = 12


class EnchantShot(demo.McCloneApp):
    """一小片石台 + 台中央的附魔台 + 旁边几块"参照物"，站远处平视 / 站高处俯视。"""

    def __init__(self, view, *a, **kw):
        super().__init__(*a, **kw)
        k = self.kernel
        k.cycle.skip_to_phase(0.25)          # 正午：贴图差异要在明亮条件下看
        k.weather_kind = 'clear'             # 雨丝会盖在贴图上（截图必须可复现）
        cx, cz = 128, 128
        y = k.world.surface_at(cx, cz) + 1
        # 一层石台 + 台中央的附魔台（台子只有 1 格厚 —— 3 格厚的石柱会喧宾夺主）
        for dx in range(-3, 4):
            for dz in range(-3, 4):
                k.world.set(cx + dx, y, cz + dz, B.STONE)
        for dy in (1, 2, 3):                 # 观察走廊（同上：地形台阶会挡住镜头）
            for dx in range(-3, 4):
                for dz in range(1, 5):
                    k.world.set_generated(cx + dx, y + dy, cz + dz, B.AIR)
        k.world.set(cx, y + 1, cz, B.ENCHANT_TABLE)
        k.flying = True
        # 手里拿一把铁镐（附魔对象）
        pick = I.item_by_name('iron_pickaxe')
        k.give(pick.id, 1)
        k.hotbar[0] = pick.id
        k.select(0)
        tbl = (cx, y + 1, cz)
        if view == 'side':
            # 平视：站在台上、离台子 2 格、眼睛略高于台面中心 ⇒ 视线几乎垂直于
            # **南侧面**（看侧面书脊）。⚠ 别俯得太狠：面越斜，斜视角下 mip 会挑到
            # 更粗的一级，1~2 像素宽的细节（书脊/包边）会被抹平。
            k.pos = [cx + 0.5, y + 1.0, cz + 2.5]
        else:
            # 俯视：斜上方看**顶面那本书**。
            # ⚠ 相机不能落在**格子的整数边界**上（x/z 都是 .0）：起点正好在体素角上时，
            # DDA 的第一步会把"当前格"判成旁边那一列，射线于是**擦着台子掉进石台**
            # （实测：准星报 (129,32,129) stone，而台子就在 (128,33,128)）。
            # 取一个非整数偏移即可，顺便让构图也自然些。
            k.pos = [cx + 1.6, y + 2.6, cz + 1.4]
        self._aim(k, tbl)
        # ⚠ `add_xp` 有单次上限（`enchant.XP_GAIN_CAP`：一次最多 50 点，防"一笔巨款跳几十级"）
        # ⇒ 想给到第 12 级要**分几次给**，不能一次塞满。
        want = EN.xp_total(LEVEL) + EN.xp_span(LEVEL) * 2 // 3
        while k.xp < want:
            k.add_xp(min(EN.XP_GAIN_CAP, want - k.xp))
        k.dirty_chunks = set(k.world.chunks)
        # 打印本批的判据（画面之外的东西靠这几行对上）
        hit = k.raycast()
        print(f'[enchant] {view} 视角 pos={[round(v, 1) for v in k.pos]} '
              f'准星={None if hit is None else (hit[0], B.name_of(k.world.get(*hit[0])))} '
              f'{k.xp_report()} 手持={k.held_enchant_desc()}', flush=True)
        for o in k.enchant_offers():
            print(f'[enchant]   报价 {o.label()}', flush=True)

    @staticmethod
    def _aim(k, target):
        """把视线对准某格中心（**别手写角度** —— 算错就会静默变成"没对着台子"）。"""
        import math
        ex, ey, ez = k.eye_pos()
        dx, dy, dz = target[0] + 0.5 - ex, target[1] + 0.5 - ey, target[2] + 0.5 - ez
        k.yaw = math.degrees(math.atan2(-dx, -dz))
        k.pitch = math.degrees(math.atan2(dy, math.hypot(dx, dz)))

    def enchant_now(self):
        """对准台子执行附魔，并把"附魔前后"的等级/附魔名打到日志。"""
        k = self.kernel
        before = (k.level, k.xp)
        ok, why = k.enchant_apply()
        print(f'[enchant] 附魔{"成功" if ok else "未成"}：{why} ｜ '
              f'等级 {before[0]} → {k.level}（经验 {before[1]} → {k.xp}）｜ '
              f'手持 {k.held_enchant_desc()}', flush=True)


def main():
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    import pyglet
    rc = 0
    for view, fname in SHOTS:
        if only and only != view:
            continue
        out = os.path.join(_ROOT, 'shots', fname)
        try:
            app = EnchantShot(view, 1400, 800, verbose=True)
        except Exception as exc:                     # noqa: BLE001
            print(f'[enchant] {view} 装配失败：{exc}', flush=True)
            rc = 1
            continue
        if view == 'top':
            # 俯视那张才动手附魔：这样"平视=报价 / 俯视=结果"两张图各自有独立判据
            app.enchant_now()
        state = {'t': 0.0, 'shot': False}

        def _beat(dt, _app=app, _out=out, _st=state, _v=view):
            _st['t'] += dt
            _app.sanity_report(f'enchant/{_v}')
            # ⚠ 等网格**全部**上传再截（首帧分帧上传，早截会拍到没传完的世界）
            if not _st['shot'] and _app.meshes_ready() and _st['t'] >= 2.0:
                _st['shot'] = True
                _app._shot_pending = _out
                print(f'[enchant] 截图 {_out}（{_v}）', flush=True)

        pyglet.clock.schedule_interval(_beat, 1.0)
        try:
            pyglet.app.run()
        except Exception as exc:                     # noqa: BLE001
            print(f'[enchant] {view} 渲染失败：{exc}', flush=True)
            rc = 1
        pyglet.clock.unschedule(_beat)
    print('== ENCHANTSHOTS_OK ==', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
