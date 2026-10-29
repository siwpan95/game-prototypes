# -*- coding: utf-8 -*-
"""最小 PNG 编解码（**只用 stdlib 的 `zlib`**，不引入 Pillow）。

为什么自己写而不是依赖 Pillow
------------------------------
资源包（见 `packs.py`）要给美术/玩家改贴图，那就必然要读 PNG —— 这是"外部素材"
唯一的入口。而本仓的纪律是**磁盘上只有生成规则**（`textures.py` 的模块说明）：

* 为了读一张 16×16 的 PNG 拖进一整个 Pillow（C 扩展 + 一堆解码器）不划算，
  而且会把"图集逐像素一致"这条可复现性从纯 Python 挪到一个二进制依赖上；
* PNG 里我们真正需要的子集**很小**：8 位、非隔行、filter 0–4。剩下那些
  （16 位、Adam7 隔行）一辈子也用不到 ⇒ 遇到就**响亮报错**，不静默给半个答案。

## 支持面（说清楚边界，别让调用方猜）

| 维度 | 支持 | 不支持（抛 `PngError`） |
| --- | --- | --- |
| 位深 | 8；调色板额外支持 1/2/4 | 16 位 |
| 颜色类型 | 0 灰度 / 2 真彩 / 3 调色板 / 4 灰度+α / 6 真彩+α | 其他 |
| 隔行 | 非隔行（`interlace=0`） | Adam7（`interlace=1`） |
| 编码 | **只写** RGBA8（color type 6，filter 0） | —— |

调色板（type 3）为什么也做：真实资源包多半是美术用工具导出的**索引色**小图
（16×16 像素 art 就是典型场景），不支持的话"拿一张现成图当贴图"这条最自然的用法
会直接撞墙。它只多出 PLTE + 可选 tRNS + 位解包三小段。

## 两个必须写明的坑（都在这一个模块里）

1. **filter 是逐行的，而且参考行是"上一行的原始字节"**（filter 类型里的
   `Up`/`Average`/`Paeth` 都拿它当基准）。这里的"上一行"指**已反过滤后的输出行**，
   不是压缩流里的原始行 —— 写反了的话图像**前几行完全正常、越往下越偏**，
   看着只像"噪点有点大"，靠肉眼极难发现。所以本模块的判据必须是
   **编码→解码往返逐字节一致**（`test_mcpng` 钉着这条），不是"看起来对"。
2. **PNG 的 α 不是预乘的**，`textures._Canvas` 存的也是直通 RGBA ⇒ 两边语义一致，
   不需要任何转换。**但 type 2（真彩，无 α 通道）必须补 `a=255`**：忘了补的话
   资源包里的不透明贴图会变成**全透明**（图集里看着像"这个方块消失了"）。
"""
from __future__ import annotations

import struct
import zlib

__all__ = ['PngError', 'PNG_SIG', 'decode', 'encode', 'size_of', 'is_png']

#: PNG 文件签名（8 字节）
PNG_SIG = b'\x89PNG\r\n\x1a\n'

#: 颜色类型 → 每像素通道数（调色板算 1 个"索引"通道）
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class PngError(ValueError):
    """PNG 读不了 / 写不了时抛这个 —— 消息里带着**为什么**与**怎么绕**。"""


def is_png(blob: bytes) -> bool:
    """是不是 PNG（只看签名）。资源包加载时用它给"这文件根本不是 PNG"一个清楚的错。"""
    return bytes(blob[:8]) == PNG_SIG


# ------------------------------------------------------------------ 区块
def _chunk(tag: bytes, data: bytes) -> bytes:
    """组一个 PNG 区块：长度 + 类型 + 数据 + CRC32（CRC 覆盖**类型和数据**）。"""
    return (struct.pack('>I', len(data)) + tag + data
            + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))


def _iter_chunks(blob: bytes):
    """逐个吐出 `(tag, data)`；CRC 不对就抛（CRC 是"文件被截断/改坏"的第一道警报）。"""
    if not is_png(blob):
        raise PngError('不是 PNG：签名不对（文件头 8 字节不匹配）')
    pos = 8
    n = len(blob)
    while pos + 8 <= n:
        (length,) = struct.unpack('>I', blob[pos:pos + 4])
        tag = blob[pos + 4:pos + 8]
        end = pos + 8 + length
        if end + 4 > n:
            raise PngError(f'PNG 截断：区块 {tag!r} 声明 {length} 字节，文件不够长')
        data = blob[pos + 8:end]
        (want,) = struct.unpack('>I', blob[end:end + 4])
        got = zlib.crc32(tag + data) & 0xFFFFFFFF
        if got != want:
            raise PngError(f'PNG 区块 {tag!r} 的 CRC 不对（文件被改坏或截断）')
        yield tag, data
        pos = end + 4
        if tag == b'IEND':
            return
    # 走到这里 = 数据用完了却没见到 IEND：**截断**。
    # 不许静默当"读完了"：截断的图会被读成一张**尺寸正确、下半截是空的**图，
    # 看着只像"贴图被裁了一半"，比报错难查得多。
    raise PngError('PNG 截断：区块序列没有以 IEND 收尾（文件被截断？）')


# ------------------------------------------------------------------ 反过滤
def _paeth(a: int, b: int, c: int) -> int:
    """Paeth 预测器（PNG 规范原文照抄；三个候选里挑最接近 `a+b-c` 的那个）。"""
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw: bytes, width: int, height: int, bpp: int) -> bytes:
    """把"带 filter 字节的行"还原成连续像素字节。

    `bpp` = 每像素字节数（**不是**位深）：filter 的 `a`/`c` 按**字节**回溯，
    灰度+α 是 2、真彩是 3、真彩+α 是 4。写成"位深"是最常见的错法，
    症状是图像**横向错位**（看着像斜切）。
    """
    stride = width * bpp
    out = bytearray(stride * height)
    prev = bytearray(stride)                      # 第 0 行的参考行=全 0（规范如此）
    pos = 0
    for y in range(height):
        if pos >= len(raw):
            raise PngError(f'PNG 数据不足：期望 {height} 行，第 {y} 行没数据')
        ft = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        if len(line) != stride:
            raise PngError(f'PNG 第 {y} 行数据不足（要 {stride} 字节，只有 {len(line)}）')
        pos += stride
        if ft == 0:
            pass
        elif ft == 1:                             # Sub：左邻
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ft == 2:                             # Up：上邻
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:                             # Average：左与上的均值
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:                             # Paeth
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                c = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(a, prev[i], c)) & 0xFF
        else:
            raise PngError(f'PNG 第 {y} 行的 filter 类型 {ft} 不认识（只有 0-4）')
        out[y * stride:(y + 1) * stride] = line
        prev = line                               # ⚠ 参考行是**已经还原的**这一行
    return bytes(out)


def _unpack_bits(line: bytes, count: int, depth: int) -> list:
    """按 1/2/4 位深把一行解包成索引列表（调色板图专用）。"""
    if depth == 8:
        return list(line[:count])
    out = []
    per = 8 // depth
    mask = (1 << depth) - 1
    for i in range(count):
        byte = line[i // per]
        shift = 8 - depth * (i % per + 1)
        out.append((byte >> shift) & mask)
    return out


# ------------------------------------------------------------------ 解码
def decode(blob: bytes):
    """PNG 字节 → `(width, height, rgba_bytes)`。

    `rgba_bytes` 恒为 `width * height * 4`，直通（非预乘）RGBA8 ——
    与 `textures._Canvas` 同一口径，调用方拿到就能直接当贴图用。
    """
    ihdr = None
    idat = bytearray()
    plte = None
    trns = None
    for tag, data in _iter_chunks(blob):
        if tag == b'IHDR':
            ihdr = data
        elif tag == b'IDAT':
            idat += data
        elif tag == b'PLTE':
            plte = data
        elif tag == b'tRNS':
            trns = data
        # 其余区块（gAMA / pHYs / tEXt / iCCP …）一律忽略：贴图不关心元数据
    if ihdr is None or len(ihdr) != 13:
        raise PngError('PNG 缺少 IHDR 或长度不对')
    if not idat:
        raise PngError('PNG 没有任何 IDAT 数据')
    width, height, depth, ctype, comp, filt, interlace = struct.unpack('>IIBBBBB', ihdr)
    if width <= 0 or height <= 0:
        raise PngError(f'PNG 尺寸非法：{width}×{height}')
    if interlace != 0:
        raise PngError('PNG 是隔行（Adam7）的，本模块不支持 —— '
                       '导出时选"非隔行 / None"即可')
    if ctype not in _CHANNELS:
        raise PngError(f'PNG 颜色类型 {ctype} 不认识（支持 0/2/3/4/6）')
    if depth != 8 and not (ctype == 3 and depth in (1, 2, 4)):
        raise PngError(f'PNG 位深 {depth}（颜色类型 {ctype}）不支持；'
                       f'只有 8 位、以及调色板的 1/2/4 位可以')

    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise PngError(f'PNG 的 IDAT 解压失败（zlib）：{exc}') from None

    if ctype == 3:
        if plte is None:
            raise PngError('PNG 是调色板图却没有 PLTE 区块')
        return _decode_palette(width, height, depth, raw, plte, trns)

    bpp = _CHANNELS[ctype]
    rows = _unfilter(raw, width, height, bpp)
    return width, height, _to_rgba(rows, width * height, ctype)


def _decode_palette(width, height, depth, raw, plte, trns):
    """调色板图：先按位深解出索引，再查 PLTE（可选 tRNS 给每个索引的 α）。"""
    stride = (width * depth + 7) // 8
    npal = len(plte) // 3
    rgb = [(plte[i * 3], plte[i * 3 + 1], plte[i * 3 + 2]) for i in range(npal)]
    alpha = list(trns[:npal]) if trns else [255] * npal
    if len(alpha) < npal:                         # tRNS 可以只给前几个
        alpha += [255] * (npal - len(alpha))
    # 调色板图按"每像素 1 字节"反过滤（规范：filter 的 bpp 至少 1）
    rows = _unfilter(raw, stride, height, 1)
    out = bytearray(width * height * 4)
    for y in range(height):
        idxs = _unpack_bits(rows[y * stride:(y + 1) * stride], width, depth)
        base = y * width * 4
        for x, ix in enumerate(idxs):
            if ix >= npal:
                raise PngError(f'调色板索引越界：像素 ({x},{y}) 用了 {ix}，'
                               f'PLTE 只有 {npal} 项')
            r, g, b = rgb[ix]
            o = base + x * 4
            out[o] = r
            out[o + 1] = g
            out[o + 2] = b
            out[o + 3] = alpha[ix]
    return width, height, bytes(out)


def _to_rgba(rows: bytes, count: int, ctype: int) -> bytes:
    """灰度/真彩/带 α 的几种排布统一成 RGBA8。"""
    if ctype == 6:
        return rows
    out = bytearray(count * 4)
    if ctype == 0:                                # 灰度
        for i in range(count):
            v = rows[i]
            out[i * 4:i * 4 + 4] = bytes((v, v, v, 255))
    elif ctype == 4:                              # 灰度 + α
        for i in range(count):
            v = rows[i * 2]
            out[i * 4:i * 4 + 4] = bytes((v, v, v, rows[i * 2 + 1]))
    else:                                         # ctype == 2：真彩，⚠ α 必须补 255
        for i in range(count):
            out[i * 4:i * 4 + 4] = bytes(rows[i * 3:i * 3 + 3]) + b'\xff'
    return bytes(out)


def size_of(blob: bytes):
    """只读 IHDR 拿 `(width, height)`（不解压像素）—— 资源包做一致性校验时用它。"""
    for tag, data in _iter_chunks(blob):
        if tag == b'IHDR':
            w, h = struct.unpack('>II', data[:8])
            return w, h
    raise PngError('PNG 缺少 IHDR')


# ------------------------------------------------------------------ 编码
def encode(width: int, height: int, rgba: bytes) -> bytes:
    """RGBA8 字节 → PNG（color type 6，filter 0）。

    只写最简单的一档是**有意的**：本模块的编码器只服务两个用途 ——
    ① 把程序化贴图导出成 PNG（给美术当"改图模板"）；
    ② 单测里造/验往返。
    两个用途都不需要 filter 压缩（16×16~64×64 的图，filter 0 的体积完全够用），
    但**解码器必须会读全部 5 种 filter** —— 因为外部资源包是别人编的。
    """
    width, height = int(width), int(height)
    if width <= 0 or height <= 0:
        raise PngError(f'编码尺寸非法：{width}×{height}')
    need = width * height * 4
    if len(rgba) != need:
        raise PngError(f'像素字节数不对：要 {need}（{width}×{height}×4），得到 {len(rgba)}')
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    stride = width * 4
    raw = bytearray((stride + 1) * height)
    for y in range(height):
        dst = y * (stride + 1)
        raw[dst] = 0                              # filter 0 = None
        raw[dst + 1:dst + 1 + stride] = rgba[y * stride:(y + 1) * stride]
    return (PNG_SIG
            + _chunk(b'IHDR', ihdr)
            + _chunk(b'IDAT', zlib.compress(bytes(raw), 9))
            + _chunk(b'IEND', b''))
