# -*- coding: utf-8 -*-
"""资源包（resource pack）：用外部 PNG **覆盖**程序化贴图，可换分辨率。

## 一句话说清它改了什么、没改什么

改的：**贴图像素从哪来**。基线永远在 `textures.PAINTERS`（程序化、逐字节确定），
资源包只是在这层之上"名字对上的就换掉"。

没改：
* **玩法一行都不动**（碰撞、光照、红石、存档全按方块 **id** 走，与贴图无关）；
* **格号（图集里的位置）不动** —— 资源包**不能新增贴图**，只能覆盖已存在的名字。
  原因见下（这是本模块最重要的约束）。

## 目录格式

```
packs/<id>/
  pack.json          # 清单（可选字段都有默认值）
  tiles/             # 想覆盖哪张就放哪张，其余自动落回程序化基线
    stone.png
    grass_top.png
    ...
```

`pack.json`（全部字段可选）：

```json
{"name": "秋色", "description": "把草木染成暖色", "resolution": 32}
```

* **`resolution`**：一张贴图的边长（像素）。不写就从第一张 PNG 推断。
  **必须全体一致**（见"为什么分辨率必须一致"）。
* 未知字段忽略；`name` 缺省取目录名。

## 为什么资源包不能新增贴图 / 不能混分辨率

图集是**一张**均匀网格纹理，UV 是"格号 / 列数"算出来的（`textures.LAYOUT.uv_rect`），
而 `mesh.py` 在 **import 期**就把这些 UV 烘进了顶点数据。于是：

* **新增/删除贴图 ⇒ 格号全变 ⇒ 已经烘好的 UV 全错位**（症状不是"新贴图不显示"，
  而是"整个世界都换成了别的贴图" —— Phase 3 真踩过一次同款，见 `phase3_设计.md` §十）。
* **某张图 32×32、另一张 16×16 ⇒ 网格不再均匀**：要么重采样（引入插值、破坏
  "逐字节确定"），要么破坏 UV 假设。所以干脆**要求全体一致**，不一致就报错。

**没被覆盖的贴图怎么办**：基线是 16px，包声明 32px 时落回基线的那几张会
**按最近邻补到 32px**（`textures.scale_rgba`）——所以"只覆盖一部分"仍然成立。
这条不做的话，16px 的回落图会被塞进 32px 的格子，`build_atlas` 里那句
`bytearray[a:b] = 更短的 bytes` 会**静默把图集缩短**（本批实测：262144 → 157056
字节），GL 拿到"尺寸与数据对不上"的纹理 ⇒ 整片花屏。现在那条路径已被
硬长度核对挡住（见 `textures.build_atlas`）。

两条都收在 `load()` 里**响亮报错**，不是静默兜底 —— 静默兜底的后果是
"改了包却没生效"，那比报错难查得多。

## 分辨率变了，`mesh.py` 为什么一行都不用改

这是本设计最省事的一点，值得单独写出来：UV 矩形是**归一化**的 ——
`u0 = 列号 × tile / (列数 × tile) = 列号 / 列数`，`tile` 约掉了。
所以 16px 的包和 64px 的包，**UV 完全相同**，只有上传给 GL 的那张纹理的
像素尺寸变了。⇒ 换分辨率只影响 `build_atlas()` 的输出与纹理上传，
几何/UV/剔除这套东西一个字节都不用动。

## 与"磁盘上只有生成规则"这条纪律的关系

`textures.py` 的纪律是"仓里不放二进制素材"。资源包是**这条纪律的唯一豁免口**，
而且豁免得很小心：仓里**默认一个包都不带**（`packs/` 不进版本库），
演示/截图用的包由 `write_demo_pack()` **当场算出来**（同一套 LCG，逐字节确定）。
也就是说：想验"包生效了"不需要先下载任何东西。
"""
from __future__ import annotations

import colorsys
import json
import os

from . import mcpng, textures

__all__ = [
    'PackError', 'PACK_MANIFEST', 'TILE_DIR', 'PACK_ROOT', 'Pack',
    'load', 'resolve', 'discover', 'write_pack', 'demo_pack_tiles',
    'write_demo_pack', 'DEMO_KINDS', 'AUTUMN_WINDOW', 'AUTUMN_SOFT',
]

#: 清单文件名
PACK_MANIFEST = 'pack.json'
#: 贴图子目录名
TILE_DIR = 'tiles'
#: 默认包目录（仓根下 `packs/`）。**不进版本库**：演示包当场生成。
PACK_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'packs')

#: 演示包的两种风格（见 `demo_pack_tiles`）
DEMO_KINDS = ('autumn', 'retro')

#: `autumn` 包改的色相区间（`(lo, hi)`，绕圈；这里 ≈ 绿→青绿）。
#: **为什么必须是"按原色相开窗"而不是"整张图一起转"** —— 这是本批最实的一条坑：
#:
#: * 整张转 -0.25 时，**底色偏暖的木料/砖/小麦**（`log_side` h≈0.088、`crop`≈0.12）
#:   会落到 h≈0.84 ⇒ **洋红/紫**；实测截图里砖墙、木料、平台上的 `log_top`
#:   全变成紫红色，一眼假；
#: * 更隐蔽的一处：`grass_side` 这张图**同时含草（绿）与土（棕）** ——
#:   整张转会把土的那半张也转成紫的，于是"梯田侧面"出现一圈紫色腰带。
#:
#: ⇒ 只对**落在这个窗口里**的像素转。好处是连"该染哪几张贴图"的白名单都不需要了：
#: 一张图里绿的变秋色、其余原样，行为自然就对。
AUTUMN_WINDOW = (0.20, 0.45)
#: 窗口边缘的过渡宽度（色相单位）。**没有它就会出现"斑点"**：噪声贴图的色相
#: 天然在区间边界附近抖动，硬切会把一张草地切成"转了/没转"的棋盘格。
AUTUMN_SOFT = 0.06


class PackError(ValueError):
    """资源包读不了 / 不合规时抛这个。消息里带**是哪个文件哪一行**与**怎么改**。"""


class Pack:
    """一个已加载的资源包：`name → RGBA 字节`。

    对外只需三个成员：`tile`（分辨率）、`has(name)`、`get(name)` ——
    `textures.tile_pixels(name, pack=...)` 只按这三个取用（鸭子类型，
    所以 `textures` **不需要** import 本模块，也就没有循环依赖）。
    """

    __slots__ = ('path', 'id', 'name', 'description', 'tile', 'tiles')

    def __init__(self, path, tiles, *, id=None, name=None, description='', tile=None):
        self.path = path
        self.id = id if id is not None else os.path.basename(path)
        self.name = name if name is not None else self.id
        self.description = description
        self.tiles = dict(tiles)
        if tile is None:
            tile = len_of_first(self.tiles) if self.tiles else textures.TILE
        self.tile = int(tile)

    # --- 取用接口（textures 只认这三个） -------------------------------
    def has(self, name: str) -> bool:
        return name in self.tiles

    def get(self, name: str) -> bytes:
        return self.tiles[name]

    # --- 便利 ---------------------------------------------------------
    @property
    def count(self) -> int:
        return len(self.tiles)

    @property
    def missing(self):
        """**没有**被覆盖的贴图名（这些会落回程序化基线）。"""
        return tuple(n for n in textures.ATLAS_TILE_NAMES if n not in self.tiles)

    def report(self) -> str:
        base = textures.TILE
        res = (f'{self.tile}px'
               + ('' if self.tile == base
                  else f'（基线 {base}px，×{self.tile / base:g}）'))
        return (f'资源包 {self.id!r}（{self.name}）：{self.count}/'
                f'{len(textures.ATLAS_TILE_NAMES)} 张覆盖，分辨率 {res}'
                + (f'；{self.description}' if self.description else ''))

    def __repr__(self):
        return f'<Pack {self.id!r} tiles={self.count} res={self.tile}>'


def len_of_first(tiles) -> int:
    """从 `name → rgba` 里推出一张图的边长（`len = tile²×4` ⇒ `tile = √(len/4)`）。

    先做**整数自检**（平方数），不是直接开方取整 —— 开方取整会把
    "字节数被截断的坏图"悄悄读成一张正确的图（这是最坏的一类错：
    读进来是对的，只有看图时才觉得"怎么糊了"）。
    """
    for blob in tiles.values():
        n = len(blob) // 4
        side = int(n ** 0.5)
        if side <= 0 or side * side != n:
            raise PackError(f'贴图字节数 {len(blob)} 不是 4×边长² 的形状（推不出分辨率）')
        return side
    return textures.TILE


# ------------------------------------------------------------------ 读取
def _has_png(directory: str) -> bool:
    """目录里有没有 `.png`（不递归）。"""
    try:
        return any(f.lower().endswith('.png') for f in os.listdir(directory))
    except OSError:
        return False


def _read_manifest(path: str) -> dict:
    """读 `pack.json`；**不存在也算合法**（纯 PNG 目录，用默认值）。"""
    mf = os.path.join(path, PACK_MANIFEST)
    if not os.path.isfile(mf):
        return {}
    try:
        with open(mf, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise PackError(f'{mf} 不是合法 JSON：{exc}') from None
    except OSError as exc:
        raise PackError(f'{mf} 读不了：{exc}') from None
    if not isinstance(data, dict):
        raise PackError(f'{mf} 的顶层必须是一个对象（{{...}}），得到 {type(data).__name__}')
    return data


def load(path: str) -> Pack:
    """加载一个资源包目录。**任何不合规都抛 `PackError`**（不静默兜底）。"""
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise PackError(f'资源包目录不存在：{path}')
    meta = _read_manifest(path)
    tdir = os.path.join(path, TILE_DIR)
    if not _has_png(tdir):
        # 允许"把 PNG 直接放在包根"（没有 tiles/ 子目录）。两种都放会歧义，
        # 所以只在 tiles/ 里**没有** PNG 时才退回包根 —— 这样"只写了几张图、
        # tiles/ 空着"也不会静默变成空包（那种错要查到很晚）。
        if _has_png(path):
            tdir = path
        elif not os.path.isdir(tdir):
            raise PackError(f'{path} 里既没有 {TILE_DIR}/ 子目录，根下也没有 PNG')
        else:
            raise PackError(f'{path}/{TILE_DIR}/ 里一张 PNG 都没有，'
                            f'包根也没有（至少要覆盖一张贴图）')

    valid = set(textures.ATLAS_TILE_NAMES)
    declared = meta.get('resolution')
    if declared is not None:
        try:
            declared = int(declared)
        except (TypeError, ValueError):
            raise PackError(f'{PACK_MANIFEST} 的 resolution 必须是整数，得到 {declared!r}') from None
        if declared <= 0 or declared & (declared - 1):
            # 2 的幂：图集边长 = 列数×tile，mipmap 与老驱动都对 2 的幂最友好
            raise PackError(f'resolution={declared} 不是 2 的幂（16/32/64/128…）')

    tiles = {}
    for fname in sorted(os.listdir(tdir)):
        if not fname.lower().endswith('.png'):
            continue
        name = fname[:-4]
        fp = os.path.join(tdir, fname)
        if name not in valid:
            raise PackError(
                f'资源包 {os.path.basename(path)!r} 里有个贴图名不认识：{fname}\n'
                f'  ⚠ 资源包**只能覆盖**已存在的贴图，不能新增（新增会改格号 ⇒ 全部 UV 错位）。\n'
                f'  合法名字（{len(valid)} 个）：{", ".join(textures.ATLAS_TILE_NAMES)}')
        try:
            with open(fp, 'rb') as fh:
                blob = fh.read()
        except OSError as exc:
            raise PackError(f'{fp} 读不了：{exc}') from None
        try:
            w, h, rgba = mcpng.decode(blob)
        except mcpng.PngError as exc:
            raise PackError(f'{fp} 不是能读的 PNG：{exc}') from None
        if w != h:
            raise PackError(f'{fp} 是 {w}×{h}，贴图必须是正方形')
        if declared is not None and w != declared:
            raise PackError(
                f'{fp} 是 {w}px，但 {PACK_MANIFEST} 声明 resolution={declared}。\n'
                f'  ⚠ 一个包内**所有贴图必须同分辨率**（网格要均匀，否则 UV 假设不成立）。')
        if name in tiles and len(tiles[name]) != len(rgba):
            raise PackError(f'{fp} 与同名的另一张尺寸不同')
        tiles[name] = rgba
        declared = declared if declared is not None else w

    if not tiles:
        raise PackError(f'{path} 里一张 PNG 都没有（至少要覆盖一张贴图）')

    return Pack(path, tiles,
                id=os.path.basename(path),
                name=str(meta.get('name') or os.path.basename(path)),
                description=str(meta.get('description') or ''),
                tile=declared)


def resolve(spec, root: str | None = None):
    """把配置里的 `pack` 值解析成目录路径。

    * 空 / `None` / `'none'` ⇒ `None`（= 纯程序化，不发警告：这是默认玩法）；
    * 含路径分隔符、或指向已存在的目录 ⇒ 当路径用；
    * 否则当**包 id**，到 `packs/<id>` 找。

    找不到时**列出所有能找到的包** —— "我明明放了包怎么没生效"十有八九是
    目录放错了地方，把候选列出来比让人猜强。
    """
    if spec is None:
        return None
    s = str(spec).strip()
    if not s or s.lower() in ('none', 'off', 'default'):
        return None
    if os.sep in s or (os.altsep and os.altsep in s) or os.path.isabs(s):
        return os.path.abspath(s)
    base = PACK_ROOT if root is None else root
    cand = os.path.join(base, s)
    if os.path.isdir(cand):
        return cand
    found = discover(base)
    hint = ('；'.join(f'{i} → {p}' for i, _n, p in found) if found
            else f'{base} 下还没有任何包')
    raise PackError(f'找不到资源包 {s!r}：既不是路径，{base} 下也没有这个目录。\n'
                    f'  现有的包：{hint}')


def discover(root: str | None = None):
    """列出 `packs/` 下的包：`[(id, name, path), ...]`（名字取自清单，读不了就跳过）。"""
    base = PACK_ROOT if root is None else root
    out = []
    if not os.path.isdir(base):
        return out
    for entry in sorted(os.listdir(base)):
        p = os.path.join(base, entry)
        if not os.path.isdir(p):
            continue
        try:
            meta = _read_manifest(p)
        except PackError:
            meta = {}
        out.append((entry, str(meta.get('name') or entry), p))
    return out


# ------------------------------------------------------------------ 写入
def write_pack(path: str, tiles, *, name=None, description='', resolution=None) -> str:
    """把 `name → RGBA 字节` 写成资源包（PNG 走本仓的 `mcpng.encode`）。返回目录。"""
    if not tiles:
        raise PackError('write_pack：没有贴图可写')
    tile = int(resolution) if resolution else len_of_first(tiles)
    tdir = os.path.join(path, TILE_DIR)
    os.makedirs(tdir, exist_ok=True)
    for tname, rgba in sorted(tiles.items()):
        if tname not in textures.TILE_INDEX:
            raise PackError(f'write_pack：未知贴图名 {tname!r}')
        if len(rgba) != tile * tile * 4:
            raise PackError(f'write_pack：{tname} 的字节数与分辨率 {tile} 不符')
        with open(os.path.join(tdir, tname + '.png'), 'wb') as fh:
            fh.write(mcpng.encode(tile, tile, rgba))
    meta = {'name': name or os.path.basename(path),
            'description': description, 'resolution': tile}
    with open(os.path.join(path, PACK_MANIFEST), 'w', encoding='utf-8') as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write('\n')
    return path


# ------------------------------------------------------------------ 演示包
def _upscale(rgba: bytes, src: int, dst: int) -> bytes:
    """最近邻放大 `src→dst` —— 直接转发 `textures.scale_rgba`（同一份实现）。

    单独留这个薄壳是为了让"演示包怎么放大"这件事在本模块里一眼可见；
    真正做事的只有一处，免得两个模块的放大口径漂开。
    """
    return textures.scale_rgba(rgba, src, dst)


def _detail(rgba: bytes, tile: int, seed: int, amp: int) -> bytes:
    """放大之后补一层逐像素细噪。

    没有这一步，"高清包"只是**方块更大的同一张图**（窗口里看着更糊）。
    噪声用 `textures._rng`（同一个 LCG）⇒ 演示包也**逐字节确定**，
    截图与单测才可复现。
    """
    rnd = textures._rng(seed)
    out = bytearray(rgba)
    for i in range(0, len(out), 4):
        if out[i + 3] == 0:                       # 透空像素不动（否则作物/红石线会长出毛边）
            continue
        d = rnd(2 * amp + 1) - amp
        for c in range(3):
            v = out[i + c] + d
            out[i + c] = 0 if v < 0 else (255 if v > 255 else v)
    return bytes(out)


def _window_weight(h: float, lo: float, hi: float, soft: float) -> float:
    """色相 `h` 落在（可绕圈的）区间 `[lo, hi]` 内的权重，边缘 `soft` 宽度内平滑过渡。

    返回值 0 = 完全不动，1 = 完全按 `shift` 转，中间是过渡带。
    """
    span = (hi - lo) % 1.0
    if span <= 0.0:
        span += 1.0
    if span >= 1.0:
        return 1.0
    d = (h - lo) % 1.0
    if d > span:
        return 0.0
    if soft <= 0.0:
        return 1.0
    edge = d if d < span - d else span - d
    return 1.0 if edge >= soft else edge / soft


def _hue_shift(rgba: bytes, shift: float, sat: float = 1.0,
               window=None, soft: float = 0.0) -> bytes:
    """按色相旋转改色（`shift` ∈ [-1, 1]，单位=一圈）。

    走 `colorsys`（stdlib、纯 Python ⇒ 跨平台逐位一致）。两个关键取舍：

    * **`window` 不是可选项而是必需**：整张图一起转会连暖色（木料/砖）一起转到洋红，
      而且会把 `grass_side` 里的**土**也染紫（详见 `AUTUMN_WINDOW` 的说明）；
    * **`soft` 过渡带**：硬切会让噪声贴图出现"转了/没转"的棋盘格斑点。
    * 低饱和像素（`s≈0`，如石头）**原样保留**：色相对灰是没有意义的，
      硬转会凭空引入颜色（石头变紫之类）。
    """
    out = bytearray(rgba)
    for i in range(0, len(out), 4):
        if out[i + 3] == 0:
            continue
        r, g, b = out[i] / 255.0, out[i + 1] / 255.0, out[i + 2] / 255.0
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        if s <= 0.0:
            continue
        w = 1.0 if window is None else _window_weight(h, window[0], window[1], soft)
        if w <= 0.0:
            continue
        h = (h + shift * w) % 1.0
        s = min(1.0, s * (1.0 + (sat - 1.0) * w))
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        out[i] = int(r * 255 + 0.5)
        out[i + 1] = int(g * 255 + 0.5)
        out[i + 2] = int(b * 255 + 0.5)
    return bytes(out)


def _quantize(rgba: bytes, levels: int = 4) -> bytes:
    """每通道压到 `levels` 档（默认 4 ⇒ 全图 64 色），做成"复古低色"观感。"""
    step = 255 // (levels - 1)
    out = bytearray(rgba)
    for i in range(0, len(out), 4):
        if out[i + 3] == 0:
            continue
        for c in range(3):
            v = out[i + c]
            out[i + c] = min(255, int(v / step + 0.5) * step)
    return bytes(out)


def demo_pack_tiles(kind: str = 'autumn') -> dict:
    """生成演示包的全部贴图（**从程序化基线现算**，零外部素材）。

    * `autumn`：**32×32**（放大 2 倍）+ 把**绿**像素的色相转 -0.25（绿→橙红）
      + 提饱和 + 细噪 ⇒ 同时演示"换分辨率"与"换配色"两件事。
      ⚠ 色相是**按窗口选择性**转的（`AUTUMN_WINDOW`），不是整张转 —— 理由见那里。
    * `retro` ：**16×16**（不动分辨率）+ 每通道压到 4 档
      ⇒ 演示"只换像素、不换分辨率"这条（也是最轻的一种包）。
    """
    if kind not in DEMO_KINDS:
        raise PackError(f'未知演示包风格 {kind!r}；可选：{", ".join(DEMO_KINDS)}')
    base = textures.TILE
    out = {}
    for i, name in enumerate(textures.ATLAS_TILE_NAMES):
        px = textures.tile_pixels(name)
        if kind == 'autumn':
            px = _upscale(px, base, base * 2)
            px = _hue_shift(px, -0.25, sat=1.18,
                            window=AUTUMN_WINDOW, soft=AUTUMN_SOFT)
            px = _detail(px, base * 2, 9001 + i * 17, 10)
        else:                                     # retro
            px = _quantize(px, 4)
        out[name] = px
    return out


def write_demo_pack(path: str, kind: str = 'autumn') -> Pack:
    """把演示包写到 `path` 并加载回来（脚本/截图/单测共用这一条）。"""
    tiles = demo_pack_tiles(kind)
    titles = {'autumn': '秋色（32×32）', 'retro': '复古四档色（16×16）'}
    desc = {'autumn': '绿→橙红的色相旋转 + 2 倍分辨率',
            'retro':  '每通道 4 档量化，分辨率不变'}
    write_pack(path, tiles, name=titles[kind], description=desc[kind])
    return load(path)
