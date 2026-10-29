# -*- coding: utf-8 -*-
"""PNG 编解码单测（纯字节，零 GL、零外部文件）。

跑：`python -m tests.test_mcpng`

**判据的核心是"编码→解码往返逐字节一致"**，不是"看起来对" ——
filter 的参考行写错时，图像前几行完全正常、越往下越偏，只像"噪点有点大"，
肉眼根本抓不住（见 `mcpng` 模块说明的坑 1）。
"""
from __future__ import annotations

import struct
import sys
import zlib

from tests._util import make_suite

from mcclone3d import mcpng as P
from mcclone3d import textures as T

test, main = make_suite('ALL_MCPNG_TESTS_PASSED', 'PNG 编解码')


# ------------------------------------------------------------------ 夹具
def _chunk(tag: bytes, data: bytes) -> bytes:
    """独立组一个区块（**不复用被测模块的私有函数** —— 否则 CRC 写错会两边一起错）。"""
    return (struct.pack('>I', len(data)) + tag + data
            + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))


def _hand_png(width, height, depth, ctype, raw, *, extra=b'', interlace=0):
    """手搓一张 PNG（`raw` 是**已带 filter 字节**的原始扫描行）。"""
    ihdr = struct.pack('>IIBBBBB', width, height, depth, ctype, 0, 0, interlace)
    body = P.PNG_SIG + _chunk(b'IHDR', ihdr)
    for tag, data in extra:
        body += _chunk(tag, data)
    return body + _chunk(b'IDAT', zlib.compress(raw)) + _chunk(b'IEND', b'')


def _forward_filter(rows, bpp, ftype):
    """按 PNG 规范**正向**做 filter（独立的第二实现，用来对拍解码器）。

    ⚠ 关键点：`Up`/`Average`/`Paeth` 的参考行是**上一行的原始（未过滤）字节**，
    不是压缩流里的原始行 —— 写错这一条，下面 `t_filters` 会失败。
    """
    stride = len(rows[0])
    out = bytearray()
    prev = bytes(stride)
    for row in rows:
        out.append(ftype)
        enc = bytearray(stride)
        for i in range(stride):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if ftype == 0:
                pr = 0
            elif ftype == 1:
                pr = a
            elif ftype == 2:
                pr = b
            elif ftype == 3:
                pr = (a + b) >> 1
            else:
                pr = P._paeth(a, b, c)
            enc[i] = (row[i] - pr) & 0xFF
        out += enc
        prev = row                          # ← 原始行（不是 enc）
    return bytes(out)


def _rgba(w, h, seed):
    """确定性造一张 RGBA 图（用项目自带的 LCG，跨版本逐位一致）。"""
    rnd = T._rng(seed)
    return bytes(rnd(256) for _ in range(w * h * 4))


# ------------------------------------------------------------------ 用例
@test('往返：encode → decode 逐字节一致（多种尺寸）')
def t_roundtrip():
    for (w, h) in ((1, 1), (3, 2), (16, 16), (32, 7)):
        src = _rgba(w, h, 100 + w * 31 + h)
        w2, h2, back = P.decode(P.encode(w, h, src))
        assert (w2, h2) == (w, h), f'{w}×{h} 解出来是 {w2}×{h2}'
        assert back == src, f'{w}×{h} 往返不一致（{len(back)} vs {len(src)} 字节）'


@test('确定性：同一输入两次编码逐字节相同')
def t_encode_deterministic():
    src = _rgba(16, 16, 7)
    assert P.encode(16, 16, src) == P.encode(16, 16, src)


@test('filter 0-4 全部能读（参考行必须是**已还原**的上一行）')
def t_filters():
    w, h, bpp = 5, 4, 4
    stride = w * bpp
    src = _rgba(w, h, 55)
    rows = [src[y * stride:(y + 1) * stride] for y in range(h)]
    for ft in range(5):
        raw = _forward_filter(rows, bpp, ft)
        blob = _hand_png(w, h, 8, 6, raw)
        gw, gh, back = P.decode(blob)
        assert (gw, gh) == (w, h)
        assert back == src, f'filter {ft} 解出来不对（参考行用错了？）'


@test('真彩（type 2）无 α 通道 ⇒ 必须补 255，否则贴图全透明')
def t_rgb_alpha_fill():
    raw = b'\x00' + bytes([10, 20, 30, 40, 50, 60])         # 2 像素 RGB
    _, _, px = P.decode(_hand_png(2, 1, 8, 2, raw))
    assert px == bytes([10, 20, 30, 255, 40, 50, 60, 255]), list(px)


@test('灰度（type 0）复制三通道；灰度+α（type 4）保留 α')
def t_gray():
    _, _, g = P.decode(_hand_png(2, 1, 8, 0, b'\x00\x07\x09'))
    assert g == bytes([7, 7, 7, 255, 9, 9, 9, 255]), list(g)
    _, _, ga = P.decode(_hand_png(2, 1, 8, 4, b'\x00\x07\x80\x09\x10'))
    assert ga == bytes([7, 7, 7, 128, 9, 9, 9, 16]), list(ga)


@test('调色板（type 3）：位深 8/4/2/1 都要能解 + tRNS 给 α')
def t_palette():
    plte = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    flat = bytes(c for rgb in plte for c in rgb)
    # 每种位深都构一张 **4 像素宽**、索引恰好 0,1,2,3 的图
    o = lambda c: (c[0], c[1], c[2], 255)          # noqa: E731  不透明 4 元组
    cases = [
        (8, bytes([0, 1, 2, 3]), [], [o(c) for c in plte]),
        (4, bytes([0x01, 0x23]), [(b'tRNS', bytes([255, 128]))],
         [(255, 0, 0, 255), (0, 255, 0, 128), o(plte[2]), o(plte[3])]),
        (2, bytes([0b00011011]), [], [o(c) for c in plte]),
        (1, bytes([0b01011100]), [], [o(plte[0]), o(plte[1]),
                                      o(plte[0]), o(plte[1])]),
    ]
    for depth, packed, extra, want in cases:
        blob = _hand_png(4, 1, depth, 3, b'\x00' + packed,
                         extra=[(b'PLTE', flat)] + extra)
        _, _, px = P.decode(blob)
        got = [(px[i * 4], px[i * 4 + 1], px[i * 4 + 2], px[i * 4 + 3])
               for i in range(4)]
        assert got == want, f'位深 {depth}: {got} != {want}'


@test('调色板索引越界 / 缺 PLTE 都要报错')
def t_palette_guard():
    plte = bytes([255, 0, 0, 0, 255, 0])
    bad = _hand_png(4, 1, 8, 3, b'\x00' + bytes([0, 1, 9, 2]),
                    extra=[(b'PLTE', plte)])
    try:
        P.decode(bad)
    except P.PngError:
        pass
    else:
        raise AssertionError('索引越界应当抛 PngError')
    try:
        P.decode(_hand_png(4, 1, 8, 3, b'\x00' + bytes([0, 1, 0, 1])))
    except P.PngError:
        pass
    else:
        raise AssertionError('缺 PLTE 应当抛 PngError')


@test('坏输入必须响亮报错（不静默给空图）')
def t_errors():
    good = P.encode(2, 2, _rgba(2, 2, 3))
    cases = {
        '非 PNG': b'GIF89a....',
        '截断': good[:-6],
        'CRC 坏': good[:20] + bytes([good[20] ^ 0xFF]) + good[21:],
        '隔行': _hand_png(1, 1, 8, 6, b'\x00\x01\x02\x03\x04', interlace=1),
        '16 位': _hand_png(1, 1, 16, 6, b'\x00' + bytes(8)),
        '颜色类型 5': _hand_png(1, 1, 8, 5, b'\x00' + bytes(4)),
    }
    for why, blob in cases.items():
        try:
            P.decode(blob)
        except P.PngError:
            pass
        else:
            raise AssertionError(f'{why} 应当抛 PngError')


@test('编码参数校验：字节数与尺寸不符 → PngError')
def t_encode_guard():
    for (w, h, n) in ((2, 2, 15), (0, 2, 0), (2, 2, 0)):
        try:
            P.encode(w, h, bytes(n))
        except P.PngError:
            pass
        else:
            raise AssertionError(f'encode({w},{h},{n}) 应当抛 PngError')


@test('size_of 只读 IHDR（不解压像素）⇒ 坏 IDAT 也能拿到尺寸')
def t_size_of():
    blob = _hand_png(7, 3, 8, 6, zlib.compress(b'\x00' * (7 * 4)))
    assert P.size_of(blob) == (7, 3)


@test('逐行 filter 手算对拍：Up + Paeth 的已知答案')
def t_filter_handcheck():
    """1 行宽 1 像素、两行：手算一遍 Up 与 Paeth，钉死"参考行"这条。"""
    # 第 0 行（原始）: (10, 20, 30, 40)；第 1 行（原始）: (50, 20, 30, 40)
    # Up  : raw[4..7] = (50-10, 20-20, 30-30, 40-40) = (40, 0, 0, 0)
    blob = _hand_png(1, 2, 8, 6, b'\x00\x0a\x14\x1e\x28' + b'\x02\x28\x00\x00\x00')
    _, _, px = P.decode(blob)
    assert px == bytes([10, 20, 30, 40, 50, 20, 30, 40]), list(px)
    # Paeth: a=0(无左邻), b=上一行同列, c=0 ⇒ 预测值取 b ⇒ 同 Up
    blob2 = _hand_png(1, 2, 8, 6, b'\x00\x0a\x14\x1e\x28' + b'\x04\x28\x00\x00\x00')
    _, _, px2 = P.decode(blob2)
    assert px2 == px, list(px2)


if __name__ == '__main__':
    sys.exit(main())
