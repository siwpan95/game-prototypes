# -*- coding: utf-8 -*-
"""资源包单测（文件都在临时目录里造，零 GL、不碰仓内文件）。

跑：`python -m tests.test_packs`
"""
from __future__ import annotations

import colorsys
import json
import os
import shutil
import sys
import tempfile

from tests._util import make_suite

from mcclone3d import mcpng as P
from mcclone3d import packs as PK
from mcclone3d import textures as T

test, main = make_suite('ALL_PACKS_TESTS_PASSED', '资源包')

_TMP = None


def _tmp():
    global _TMP
    if _TMP is None:
        _TMP = tempfile.mkdtemp(prefix='mc3d_packs_')
    return _TMP


def _mk(name, *, manifest=None, tiles=None, raw_files=None, tile=16):
    """在临时目录里造一个包目录，返回路径。"""
    d = os.path.join(_tmp(), name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, PK.TILE_DIR), exist_ok=True)
    if manifest is not None:
        with open(os.path.join(d, PK.PACK_MANIFEST), 'w', encoding='utf-8') as fh:
            if isinstance(manifest, str):
                fh.write(manifest)
            else:
                json.dump(manifest, fh, ensure_ascii=False)
    for tname, rgba in (tiles or {}).items():
        with open(os.path.join(d, PK.TILE_DIR, tname + '.png'), 'wb') as fh:
            fh.write(P.encode(tile, tile, rgba))
    for rel, blob in (raw_files or {}).items():
        fp = os.path.join(d, rel)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, 'wb') as fh:
            fh.write(blob)
    return d


def _solid(n, rgba):
    return bytes(rgba) * (n * n)


# ------------------------------------------------------------------ 加载
@test('加载：覆盖的用包的像素，没覆盖的落回程序化基线')
def t_load_partial():
    d = _mk('partial', manifest={'name': '只改石头'},
            tiles={'stone': _solid(16, (1, 2, 3, 255))})
    q = PK.load(d)
    assert q.name == '只改石头' and q.tile == 16
    assert q.has('stone') and not q.has('dirt')
    assert T.tile_pixels('stone', q) == _solid(16, (1, 2, 3, 255))
    assert T.tile_pixels('dirt', q) == T.tile_pixels('dirt'), '未覆盖的贴图必须落回基线'
    assert len(q.missing) == len(T.ATLAS_TILE_NAMES) - 1


@test('分辨率：从 PNG 推断 / 清单声明都可以，且**必须全体一致**')
def t_resolution():
    d = _mk('res32', manifest=None, tiles={'stone': _solid(32, (9, 9, 9, 255))},
            tile=32)
    q = PK.load(d)
    assert q.tile == 32, q.tile
    # 清单写了 32，文件却是 16 ⇒ 报错
    bad = _mk('res_mismatch', manifest={'resolution': 32},
              tiles={'stone': _solid(16, (9, 9, 9, 255))})
    try:
        PK.load(bad)
    except PK.PackError as exc:
        assert '同分辨率' in str(exc) or '分辨率' in str(exc), str(exc)
    else:
        raise AssertionError('声明与文件不符应当报错')
    # 包内两张图不同尺寸 ⇒ 报错
    mixed = _mk('res_mixed', manifest=None,
                tiles={'stone': _solid(16, (1, 1, 1, 255))})
    with open(os.path.join(mixed, PK.TILE_DIR, 'dirt.png'), 'wb') as fh:
        fh.write(P.encode(32, 32, _solid(32, (2, 2, 2, 255))))
    try:
        PK.load(mixed)
    except PK.PackError:
        pass
    else:
        raise AssertionError('混分辨率应当报错')
    # 非 2 的幂 ⇒ 报错
    try:
        PK.load(_mk('res24', manifest={'resolution': 24},
                    tiles={'stone': _solid(16, (1, 1, 1, 255))}))
    except PK.PackError as exc:
        assert '2 的幂' in str(exc), str(exc)
    else:
        raise AssertionError('非 2 的幂应当报错')


@test('未知贴图名必须报错（资源包**不能新增**贴图 ⇒ 否则全部 UV 错位）')
def t_unknown_tile():
    d = _mk('typo', manifest=None, tiles={'stoen': _solid(16, (1, 1, 1, 255))})
    try:
        PK.load(d)
    except PK.PackError as exc:
        msg = str(exc)
        assert 'stoen' in msg and '不能新增' in msg, msg
        assert 'stone' in msg, '报错里应当顺便列出合法名字'
    else:
        raise AssertionError('拼错贴图名必须报错，不能静默忽略')


@test('坏清单 / 空包 / 目录不存在都要报错（且消息说到点上）')
def t_bad_packs():
    for why, fn in (
        ('清单不是 JSON', lambda: PK.load(_mk('badjson', manifest='{oops',
                                                       tiles={'stone': _solid(16, (1, 1, 1, 255))}))),
        ('一张 PNG 都没有', lambda: PK.load(_mk('empty', manifest={'name': 'x'}))),
        ('目录不存在', lambda: PK.load(os.path.join(_tmp(), 'no_such_dir'))),
        ('不是 PNG', lambda: PK.load(_mk('notpng', manifest=None,
                                         raw_files={'tiles/stone.png': b'GIF89a...'}))),
    ):
        try:
            fn()
        except PK.PackError:
            pass
        else:
            raise AssertionError(f'{why} 应当抛 PackError')


# ------------------------------------------------------------------ 解析
@test('resolve：空/None/none ⇒ None；包 id ⇒ packs/<id>；路径 ⇒ 绝对路径')
def t_resolve():
    root = _tmp()
    _mk('autumn_x', manifest={'name': 'a'}, tiles={'stone': _solid(16, (1, 1, 1, 255))})
    for empty in (None, '', '  ', 'none', 'OFF', 'default'):
        assert PK.resolve(empty, root=root) is None
    got = PK.resolve('autumn_x', root=root)
    assert os.path.isdir(got) and got.endswith('autumn_x'), got
    assert os.path.isabs(PK.resolve('./some/rel', root=root))
    # 未知 id：消息里要列出候选（"我明明放了包"多半是放错地方）
    try:
        PK.resolve('nope', root=root)
    except PK.PackError as exc:
        assert 'autumn_x' in str(exc), str(exc)
    else:
        raise AssertionError('未知包 id 应当报错')


@test('discover 列出目录下的包（名字取自清单，坏包不炸）')
def t_discover():
    root = _tmp()
    _mk('d_one', manifest={'name': '第一个'}, tiles={'stone': _solid(16, (1, 1, 1, 255))})
    _mk('d_bad', manifest='{oops')
    got = dict((i, n) for i, n, _p in PK.discover(root))
    assert got.get('d_one') == '第一个', got
    assert 'd_bad' in got, '读不了清单的目录也要列出来（名字退回目录名）'


# ------------------------------------------------------------------ 图集
@test('图集：按包的分辨率出图，且格子里的像素就是包里的像素')
def t_atlas_with_pack():
    d = _mk('atlas_pack', manifest=None,
            tiles={'stone': _solid(16, (11, 22, 33, 255))}, tile=16)
    q = PK.load(d)
    lay = T.layout_for(q)
    assert lay.size == T.ATLAS_COLS * 16
    blob = T.build_atlas(q, lay)
    assert len(blob) == lay.size * lay.size * 4
    x0, y0, w, h = lay.pixel_rect('stone')
    off = ((y0 + 1) * lay.size + x0 + 1) * 4
    assert blob[off:off + 4] == bytes((11, 22, 33, 255)), blob[off:off + 4]
    # 未覆盖的贴图在包里也应落回基线像素
    x1, y1, _w, _h = lay.pixel_rect('dirt')
    off2 = ((y1 + 1) * lay.size + x1 + 1) * 4
    base = T.build_atlas()
    boff = ((y1 + 1) * T.LAYOUT.size + x1 + 1) * 4
    assert blob[off2:off2 + 4] == base[boff:boff + 4]


@test('高分辨率包：图集边长放大，但 **UV 一个字节都不变**')
def t_uv_resolution_invariant():
    d = _mk('hi', manifest=None, tiles={'stone': _solid(32, (7, 7, 7, 255))}, tile=32)
    q = PK.load(d)
    lay = T.layout_for(q)
    assert lay.size == T.ATLAS_COLS * 32 and lay.tile == 32
    assert len(T.build_atlas(q, lay)) == (T.ATLAS_COLS * 32) ** 2 * 4
    for name in T.ATLAS_TILE_NAMES:
        assert T.tile_uv_rect(name, lay) == T.tile_uv_rect(name), \
            f'{name} 的 UV 随分辨率变了（应当无关）'


@test('pack 与 layout 的 tile 不一致 ⇒ 响亮报错（不许默默花屏）')
def t_layout_mismatch():
    d = _mk('mm', manifest=None, tiles={'stone': _solid(32, (1, 1, 1, 255))}, tile=32)
    q = PK.load(d)
    try:
        T.build_atlas(q, T.LAYOUT)                 # 32px 的包配 16px 的几何
    except ValueError:
        pass
    else:
        raise AssertionError('分辨率和几何不符应当抛 ValueError')


@test('基线不受影响：仓里不带包时，图集与 Phase 3-C 逐字节相同')
def t_baseline_intact():
    assert T.layout_for(None) is T.LAYOUT
    lay = T.layout_for(PK.Pack('<none>', {}, tile=T.TILE))
    assert lay is T.LAYOUT, '分辨率等于基线时必须复用 LAYOUT（不是新对象）'
    assert T.build_atlas(None) == T.build_atlas()
    assert T.build_atlas(None, T.LAYOUT) == T.build_atlas()


# ------------------------------------------------------------------ 演示包
@test('演示包：两种风格、确定性、分辨率对、覆盖全部贴图')
def t_demo():
    a1 = PK.demo_pack_tiles('autumn')
    a2 = PK.demo_pack_tiles('autumn')
    assert a1 == a2, '演示包必须逐字节可复现'
    assert len(a1) == len(T.ATLAS_TILE_NAMES)
    for name, px in a1.items():
        assert len(px) == 32 * 32 * 4, f'{name} 应当是 32px'
    r1 = PK.demo_pack_tiles('retro')
    for name, px in r1.items():
        assert len(px) == 16 * 16 * 4, f'{name} 应当是 16px'
    try:
        PK.demo_pack_tiles('nope')
    except PK.PackError:
        pass
    else:
        raise AssertionError('未知演示包风格应当报错')


@test('演示包：autumn 结构 = 源像素的 2× 放大 + 小幅细噪，α 逐像素不变')
def t_demo_colors():
    a = PK.demo_pack_tiles('autumn')
    base = T.tile_pixels('grass_top')              # 16×16 全不透明
    g = a['grass_top']                             # 32×32

    def px32(x, y):
        i = (y * 32 + x) * 4
        return g[i:i + 4]

    # 结构必须保住：每个 2×2 块 = 同一个源像素（放大后才加细噪）
    # 所以块内某通道的极差 ≤ 2×噪幅 = 20。**这条才是有意义的判据** ——
    # "块内完全相同"会被细噪破坏，而那正是高清包该有的样子。
    for by in range(16):
        for bx in range(16):
            block = [px32(bx * 2 + dx, by * 2 + dy) for dy in (0, 1) for dx in (0, 1)]
            for ch in range(3):
                vals = [b[ch] for b in block]
                spread = max(vals) - min(vals)
                assert spread <= 21, f'({bx},{by}) 通道 {ch} 的块内极差 {spread} 过大'
    # α 逐像素不变（_detail 只碰 RGB，且透明像素整个跳过）
    def up_alpha(x, y):
        return base[((y // 2) * 16 + (x // 2)) * 4 + 3]

    for y in range(32):
        for x in range(32):
            assert px32(x, y)[3] == up_alpha(x, y), f'({x},{y}) 的 α 变了'
    # 色相 -0.25：草地整体偏红、绿分量下降
    def means(px, tile, ch):
        return sum(px[i * 4 + ch] for i in range(tile * tile)) / (tile * tile)
    assert means(g, 32, 0) > means(base, 16, 0) + 20, '秋色应当把红分量推上去'
    assert means(g, 32, 1) < means(base, 16, 1), '秋色应当把绿分量压下去'
    # 灰度贴图旋转色相**几乎不该变色**（饱和度≈0）：石头底色是 (128,128,130)，
    # 严格来说不是纯灰，所以判据用"偏离量远小于彩色贴图"而不是"完全相等"。
    def mean_abs_delta(tile_name, tile=32):
        b = T.tile_pixels(tile_name)
        ref = T.scale_rgba(b, 16, tile)            # 只放大、不旋转的参照
        got = a[tile_name]
        n = tile * tile * 3
        return sum(abs(got[i * 4 + c] - ref[i * 4 + c])
                   for i in range(tile * tile) for c in range(3)) / n

    d_stone = mean_abs_delta('stone')
    d_grass = mean_abs_delta('grass_top')
    d_brick = mean_abs_delta('brick')
    assert d_stone < 8, f'石头（灰、无饱和度）只该有细噪：{d_stone:.1f}'
    assert d_brick < 8, f'砖不在绿色窗口里，只该有细噪：{d_brick:.1f}'
    assert d_grass > 20, f'草地应该被明显改色：{d_grass:.1f}'
    assert d_grass > 4 * max(d_stone, d_brick), '只有绿的东西才该被明显改色'
    assert PK.AUTUMN_WINDOW == (0.20, 0.45), PK.AUTUMN_WINDOW
    # 色相窗口是**绕圈**的，边缘还有过渡带
    soft = PK.AUTUMN_SOFT
    assert PK._window_weight(0.29, 0.20, 0.45, soft) == 1.0, '草地（h≈0.29）必须整份被转'
    assert PK._window_weight(0.07, 0.20, 0.45, soft) == 0.0, '暖棕（h≈0.07）必须完全不动'
    assert PK._window_weight(0.60, 0.20, 0.45, soft) == 0.0, '蓝色（h≈0.60，水）必须不动'
    assert 0.0 < PK._window_weight(0.21, 0.20, 0.45, soft) < 1.0, '窗口边缘要有过渡带'
    # **最实的一条**：`grass_side` 同一张图里有草（绿）也有土（棕）——
    # 整张转会把土也染紫（实测就是"梯田侧面出现一条紫色腰带"）。
    # 这里逐像素验：绿的变暖、棕的基本没动。
    gs_base = T.tile_pixels('grass_side')          # 16×16
    gs_pack = a['grass_side']                      # 32×32

    def rgb_at(px, k):
        return px[k * 4] / 255, px[k * 4 + 1] / 255, px[k * 4 + 2] / 255

    def greenish(k):
        h, s, _v = colorsys.rgb_to_hsv(*rgb_at(gs_base, k))
        return s > 0.2 and 0.20 <= h <= 0.45

    def h_of(px, k):
        return colorsys.rgb_to_hsv(*rgb_at(px, k))[0]

    n_grass = n_brown = 0
    for by in range(16):
        for bx in range(16):
            k = by * 16 + bx
            j = (by * 2) * 32 + bx * 2            # 放大后对应的那个像素
            if greenish(k):
                n_grass += 1
                assert 0.0 <= h_of(gs_pack, j) <= 0.12, \
                    f'草像素应当变橙红，得到 {h_of(gs_pack, j):.3f}'
            else:
                n_brown += 1
                assert abs(h_of(gs_pack, j) - h_of(gs_base, k)) < 0.04, \
                    f'土像素不该被染色：{h_of(gs_base, k):.3f} -> {h_of(gs_pack, j):.3f}'
    assert n_grass > 20 and n_brown > 20, (n_grass, n_brown)
    # 草地染完必须是**橙红**（h≈0.04），不是洋红（h≈0.84）——
    # 这条就是 `AUTUMN_WINDOW` 那段"色相环"推理的判据
    # （没它就只能靠肉眼看截图像不像秋天，而"紫色草地"看着也挺"有风格"）。
    h_base = h_of(base, 0)
    h_pack = h_of(g, 0)
    assert 0.25 < h_base < 0.35, h_base
    assert 0.0 <= h_pack <= 0.12, f'秋色草地的色相应当落在橙红区间，得到 {h_pack:.3f}'
    # 透明像素不许被染色（作物/红石线靠透空立起来）
    crop = a['crop']
    for i in range(0, len(crop), 4):
        if crop[i + 3] == 0:
            assert crop[i] == 0 and crop[i + 1] == 0 and crop[i + 2] == 0, \
                '透空像素的 RGB 必须保持 0（否则会渗出毛边）'
    # retro：每通道只剩 4 档
    r = PK.demo_pack_tiles('retro')['dirt']
    vals = {r[i] for i in range(0, len(r), 4)}
    assert vals <= {0, 85, 170, 255}, sorted(vals)


@test('write_demo_pack / write_pack：落盘后加载回来一致（往返）')
def t_write_roundtrip():
    d = os.path.join(_tmp(), 'written')
    shutil.rmtree(d, ignore_errors=True)
    pk = PK.write_demo_pack(d, 'retro')
    assert pk.tile == 16 and pk.count == len(T.ATLAS_TILE_NAMES)
    again = PK.load(d)
    for name in T.ATLAS_TILE_NAMES:
        assert again.get(name) == pk.get(name), f'{name} 落盘往返不一致'
    # 清单里的 resolution / name 都写对了
    with open(os.path.join(d, PK.PACK_MANIFEST), encoding='utf-8') as fh:
        meta = json.load(fh)
    assert meta['resolution'] == 16 and meta['name']
    # 不合规的写入都要报错
    bad = [
        ('字节数与分辨率不符', os.path.join(_tmp(), 'badwrite'),
         {'stone': _solid(16, (1, 1, 1, 255))}, {'resolution': 32}),
        ('未知贴图名', os.path.join(_tmp(), 'badname'),
         {'nope': _solid(16, (1, 1, 1, 255))}, {}),
        ('空包', os.path.join(_tmp(), 'emptywrite'), {}, {}),
    ]
    for why, path, tiles, kw in bad:
        shutil.rmtree(path, ignore_errors=True)
        try:
            PK.write_pack(path, tiles, **kw)
        except PK.PackError:
            pass
        else:
            raise AssertionError(f'{why} 应当报错')


@test('目录形态：PNG 直接放在包根也认（没有 tiles/ 子目录）')
def t_flat_layout():
    d = _mk('flat', manifest={'name': '平铺'})
    with open(os.path.join(d, 'stone.png'), 'wb') as fh:
        fh.write(P.encode(16, 16, _solid(16, (5, 6, 7, 255))))
    q = PK.load(d)
    assert q.has('stone') and T.tile_pixels('stone', q) == _solid(16, (5, 6, 7, 255))


@test('report() 说清覆盖数与分辨率（体检要看得出包生效）')
def t_report():
    d = _mk('rep', manifest={'name': '报告包', 'description': '一句话'},
            tiles={'stone': _solid(32, (1, 1, 1, 255))}, tile=32)
    s = PK.load(d).report()
    assert '报告包' in s and '32px' in s and '1/' in s and '一句话' in s, s
    assert PK.Pack('<none>', {}, tile=16).report().startswith('资源包')


if __name__ == '__main__':
    sys.exit(main())
