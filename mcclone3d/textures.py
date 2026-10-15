# -*- coding: utf-8 -*-
"""程序化方块贴图：16×16 像素 → 图集（**零外部素材**，确定可复现）。

三层职责严格分开，只有最后一层碰 GL：

1. `tile_pixels(name)` —— 纯字节：16×16 RGBA（确定性，可逐像素断言）；
2. `build_atlas()`     —— 把全部贴图排成一张网格图集（`AtlasLayout`）；
3. `atlas_texture()`   —— 上传成 pyglet 纹理（**需要 GL 上下文**，单测不碰）。

为什么全部现算而不是带 PNG：与 .kkrieger 同一条路子 —— 磁盘上只存**生成规则**，
首次用到才出像素。好处是仓里没有二进制素材、没有授权问题（MIT 干净），
而且"同一张图在任何机器上逐字节相同"这件事**可以被单测钉死**。

像素质感对齐 MC 的读法：底色 + 逐像素噪声 + 少量结构线（草叶、木纹、砖缝、矿斑）。
所有噪声都走本模块的 `_rng`（自写 LCG，**不用 `random`**）—— 跨 Python 版本逐位一致，
否则"图集逐像素一致"这条断言会在换环境后随机失败。
"""
from __future__ import annotations

__all__ = [
    'TILE', 'TILES', 'ATLAS_COLS', 'ATLAS_ROWS', 'ATLAS_SIZE',
    'TILE_INDEX', 'tile_pixels', 'build_atlas', 'AtlasLayout',
    'tile_uv_rect', 'ATLAS_TILE_NAMES',
]

#: 单张贴图边长（像素）
TILE = 16


def _rng(seed: int):
    """确定性伪随机（自写 LCG）。

    刻意**不用 `random`**：那要赌"跨平台 / 跨 Python 版本逐位一致"，
    而图集一致性断言（`test_textures`）全靠这条。
    """
    state = int(seed) & 0x7FFFFFFF

    def nxt(n: int) -> int:
        nonlocal state
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        return (state >> 7) % max(1, n)

    return nxt


def _clamp(v, lo=0, hi=255):
    return lo if v < lo else (hi if v > hi else int(v))


def _shade(rgb, d):
    return tuple(_clamp(c + d) for c in rgb)


class _Canvas:
    """16×16 RGBA 画布。坐标 (x, y)，y=0 在上（贴图行序）。"""

    def __init__(self, rgba=(0, 0, 0, 0)):
        self.px = [tuple(rgba) for _ in range(TILE * TILE)]

    def set(self, x, y, rgb, a=255):
        if 0 <= x < TILE and 0 <= y < TILE:
            self.px[y * TILE + x] = (rgb[0], rgb[1], rgb[2], a)

    def get(self, x, y):
        return self.px[(y % TILE) * TILE + (x % TILE)]

    def fill(self, rgb, a=255):
        for i in range(TILE * TILE):
            self.px[i] = (rgb[0], rgb[1], rgb[2], a)

    def noise(self, rgb, amp, seed, a=255):
        """逐像素加噪（平铺用：不按坐标取模，因为逐像素本来就是局部的）。"""
        rnd = _rng(seed)
        for i in range(TILE * TILE):
            d = rnd(2 * amp + 1) - amp
            c = _shade(rgb, d)
            self.px[i] = (c[0], c[1], c[2], a)

    def speckle(self, rgb, count, seed, a=255):
        """撒点（矿斑、砂砾颗粒）。"""
        rnd = _rng(seed)
        for _ in range(count):
            x, y = rnd(TILE), rnd(TILE)
            self.set(x, y, rgb, a)

    def bytes(self) -> bytes:
        out = bytearray()
        for (r, g, b, a) in self.px:
            out += bytes((r, g, b, a))
        return bytes(out)


# ------------------------------------------------------------------ 画法
def _paint_stone(c):
    c.noise((128, 128, 130), 16, 11)


def _paint_cobble(c):
    c.noise((120, 120, 122), 12, 21)
    rnd = _rng(22)
    for _ in range(14):                       # 石块边界
        x, y = rnd(TILE), rnd(TILE)
        w, h = 2 + rnd(3), 2 + rnd(2)
        for dy in range(h):
            for dx in range(w):
                c.set((x + dx) % TILE, (y + dy) % TILE, _shade((120, 120, 122), -26))


def _paint_dirt(c):
    c.noise((134, 96, 67), 18, 31)
    c.speckle((110, 78, 54), 26, 32)


def _paint_grass_top(c):
    c.noise((106, 170, 80), 18, 41)
    c.speckle((88, 150, 66), 22, 42)


def _paint_grass_side(c):
    _paint_dirt(c)
    rnd = _rng(51)
    for x in range(TILE):                     # 顶部草皮 + 参差草叶
        h = 3 + rnd(3)
        for y in range(h):
            c.set(x, y, _shade((106, 170, 80), rnd(21) - 10))


def _paint_sand(c):
    c.noise((219, 205, 152), 12, 61)
    c.speckle((200, 186, 134), 30, 62)


def _paint_water(c):
    c.noise((58, 108, 200), 10, 71, a=190)
    rnd = _rng(72)
    for y in range(0, TILE, 4):               # 横向波纹
        for x in range(TILE):
            c.set(x, y + (x // 4 + y // 4) % 2, _shade((58, 108, 200), 26), 200)


def _paint_log_side(c):
    c.noise((124, 92, 56), 12, 81)
    rnd = _rng(82)
    for x in range(TILE):                     # 竖向木纹
        if rnd(3) == 0:
            for y in range(TILE):
                c.set(x, y, _shade((124, 92, 56), -22))


def _paint_log_top(c):
    c.noise((152, 118, 74), 10, 91)
    rnd = _rng(92)
    for y in range(TILE):                     # 年轮（同心方块）
        for x in range(TILE):
            r = max(abs(x - 7.5), abs(y - 7.5))
            if int(r) % 3 == 0:
                c.set(x, y, _shade((152, 118, 74), -18 - rnd(6)))


def _paint_leaves(c):
    c.noise((60, 130, 62), 26, 101, a=255)
    rnd = _rng(102)
    for _ in range(30):                       # 透光孔（画成深色，读起来像叶隙）
        x, y = rnd(TILE), rnd(TILE)
        c.set(x, y, (40, 92, 44), 255)


def _paint_planks(c):
    base = (166, 128, 78)
    c.noise(base, 10, 111)
    for y in (0, 5, 10, 15):                  # 板缝
        for x in range(TILE):
            c.set(x, y % TILE, _shade(base, -34))


def _paint_glass(c):
    c.fill((198, 224, 235), 70)               # 半透明底
    edge = (236, 248, 252)
    for i in range(TILE):                     # 边框
        c.set(i, 0, edge, 235)
        c.set(i, TILE - 1, edge, 235)
        c.set(0, i, edge, 235)
        c.set(TILE - 1, i, edge, 235)
    for i in range(3, 8):                     # 高光斜线
        c.set(i, i + 2, (255, 255, 255), 190)


def _paint_brick(c):
    base = (150, 76, 62)
    c.noise(base, 8, 121)
    mortar = (196, 190, 182)
    for y in range(TILE):
        if y % 4 == 3:
            for x in range(TILE):
                c.set(x, y, mortar)
        else:
            off = 0 if (y // 4) % 2 == 0 else 4    # 错缝
            for x in range(TILE):
                if (x + off) % 8 == 7:
                    c.set(x, y, mortar)


def _paint_snow(c):
    c.noise((242, 246, 252), 8, 131)
    c.speckle((222, 230, 244), 20, 132)


def _paint_gravel(c):
    c.noise((138, 134, 128), 22, 141)
    c.speckle((104, 100, 96), 40, 142)
    c.speckle((176, 172, 166), 26, 143)


def _paint_craft_top(c):
    _paint_planks(c)
    dark = (92, 66, 38)                       # 3×3 网格
    for i in (5, 10):
        for k in range(TILE):
            c.set(i, k, dark)
            c.set(k, i, dark)


def _paint_craft_side(c):
    _paint_planks(c)
    dark = (92, 66, 38)
    for i in range(TILE):                     # 台面下方一圈工具影
        c.set(i, 6, dark)
    for x in (3, 6, 9, 12):
        for y in range(8, 13):
            c.set(x, y, dark)


def _paint_furnace_side(c):
    _paint_cobble(c)
    for y in range(6, 12):                    # 炉口
        for x in range(4, 12):
            c.set(x, y, (40, 38, 38))
    for x in range(5, 11):                    # 火光
        c.set(x, 11, (208, 120, 44))
        c.set(x, 10, (232, 158, 62))


def _paint_furnace_top(c):
    _paint_cobble(c)
    for y in range(4, 12):
        for x in range(4, 12):
            if (x + y) % 2 == 0:
                c.set(x, y, _shade((120, 120, 122), -18))


def _paint_coal_ore(c):
    _paint_stone(c)
    c.speckle((34, 34, 36), 22, 151)
    c.speckle((58, 58, 60), 14, 152)


def _paint_iron_ore(c):
    _paint_stone(c)
    c.speckle((196, 152, 116), 20, 161)
    c.speckle((224, 186, 150), 10, 162)


def _paint_gold_ore(c):
    _paint_stone(c)
    c.speckle((238, 198, 78), 20, 191)
    c.speckle((252, 232, 150), 10, 192)


def _paint_diamond_ore(c):
    _paint_stone(c)
    c.speckle((92, 222, 216), 18, 195)
    c.speckle((204, 250, 250), 8, 196)


def _paint_bedrock(c):
    c.noise((70, 70, 74), 26, 171)
    c.speckle((40, 40, 44), 34, 172)


def _paint_wool(c):
    """羊毛：**生物部件的默认贴图**。

    为什么要一张"没有花纹"的贴图：生物的颜色是**顶点色**给的
    （羊白、猪粉、僵尸绿），如果底下还压着一层草地/木头花纹，
    远看就是一团杂色。羊毛的细密绒面正好——近看有材质、远看是纯色。
    """
    c.noise((236, 236, 232), 10, 181)
    c.speckle((214, 214, 210), 22, 182)


def _paint_torch(c):
    c.fill((0, 0, 0), 0)
    for y in range(7, TILE):                  # 木杆
        c.set(7, y, (124, 92, 56))
        c.set(8, y, (146, 110, 68))
    for y in range(4, 7):                     # 火头
        for x in range(6, 10):
            c.set(x, y, (240, 176, 60) if (x + y) % 2 else (252, 226, 120))


def _paint_crop(c):
    """作物（麦子）：**透空**背景 + 三根竖直麦秆与金黄穗头。

    为什么必须透空：麦子是"长在地面上的细秆"，画成不透明的板会在田里
    立起一块方块状的东西。`opaque=False` 同理（它不该挡住邻块的面）。
    """
    c.fill((0, 0, 0), 0)
    for x in (3, 7, 11):                       # 三根麦秆（错开高度，看着不像栅栏）
        for y in range(4 + (x % 3), TILE):
            col = (96, 138, 62) if y % 3 else (120, 162, 76)
            c.set(x, y, col)
            c.set(x + 1, y, (108, 150, 68))
        for y in range(3, 8):                  # 穗头
            c.set(x, y, (214, 186, 74) if y % 2 else (234, 208, 98))
            c.set(x + 1, y, (224, 196, 84))



# ---------------------------------------------------------------- Phase 3：红石
#: 红石元件的贴图（17 张）。**默认透明背景**（`fill(..., 0)`）：
#: 拉杆/按钮/火把/中继器都是"立在地面上的小物件"，不透明的话会变成一整块方砖。
def _paint_redstone_wire(c):
    """红石线：透明背景 + 居中十字红线（**未通电是暗红**：亮度靠顶点色随信号变）。

    ⚠ 十字要画**粗**（4 格像素 ≈ 1/4 格宽）：红石线本体只有 1/16 格高，
    贴图再细到 2px 的话，从 9 格外的正常视角看只有一两个像素 ——
    截图里"整条线看不见"（实测踩过）。MC 的红石线也细，但它的方块尺度更大。
    """
    c.fill((0, 0, 0), 0)
    dark, mid, hot = (96, 22, 20), (152, 34, 28), (198, 56, 38)
    arms = (6, 7, 8, 9)
    for i in range(TILE):
        for w in arms:
            col = hot if i % 5 == 0 else mid
            c.set(i, w, col)
            c.set(w, i, col)
    for y in range(6, 10):                    # 中心亮块（"这里有个结点"）
        for x in range(6, 10):
            c.set(x, y, hot if (x + y) % 2 else dark)


def _paint_lever(c):
    """拉杆（关）：透明背景 + 石座 + 竖直的木杆。"""
    c.fill((0, 0, 0), 0)
    for x in range(5, 11):
        for y in range(12, TILE):
            c.set(x, y, (128, 128, 124) if (x + y) % 2 else (108, 108, 104))
    for y in range(5, 13):
        c.set(7, y, (146, 110, 64))
        c.set(8, y, (166, 126, 74))
    for x in range(6, 10):
        c.set(x, 4, (120, 88, 52))


def _paint_lever_on(c):
    """拉杆（开）：杆压向一侧且偏亮红 —— 一眼看出状态变了。"""
    c.fill((0, 0, 0), 0)
    for x in range(5, 11):
        for y in range(12, TILE):
            c.set(x, y, (128, 128, 124) if (x + y) % 2 else (108, 108, 104))
    for i in range(9):
        c.set(4 + i, 11 - i // 3, (198, 62, 44))
        c.set(5 + i, 11 - i // 3, (222, 84, 58))


def _paint_button(c):
    """按钮（未按）：透明背景 + 石座 + 凸出的一块。"""
    c.fill((0, 0, 0), 0)
    for x in range(5, 11):
        for y in range(9, TILE):
            c.set(x, y, (138, 138, 132) if (x + y) % 2 else (118, 118, 112))
    for x in range(6, 10):
        for y in range(7, 10):
            c.set(x, y, (172, 172, 164))


def _paint_button_on(c):
    """按钮（按下）：凸出那块被压回去，中心偏红。"""
    c.fill((0, 0, 0), 0)
    for x in range(5, 11):
        for y in range(9, TILE):
            c.set(x, y, (138, 138, 132) if (x + y) % 2 else (118, 118, 112))
    for x in range(6, 10):
        c.set(x, 10, (196, 82, 60))


def _paint_redstone_torch(c):
    """红石火把：木杆 + **暗红发光头**（结构与火把同款，颜色区分"信号源"）。"""
    c.fill((0, 0, 0), 0)
    for y in range(7, TILE):
        c.set(7, y, (104, 78, 48))
        c.set(8, y, (124, 96, 60))
    for y in range(4, 7):
        for x in range(6, 10):
            c.set(x, y, (216, 48, 40) if (x + y) % 2 else (250, 96, 72))


def _paint_redstone_torch_off(c):
    """红石火把（灭）：同款木杆，但**头部是暗灰**（一眼看出它被反相了）。

    反相器是这一批的核心新语义（火把脚下被强充能 ⇒ 自己熄灭），
    所以"灭"必须有独立的贴图：状态 id 不同、贴图相同的话，玩家只能靠猜。
    """
    c.fill((0, 0, 0), 0)
    for y in range(7, TILE):
        c.set(7, y, (104, 78, 48))
        c.set(8, y, (124, 96, 60))
    for y in range(4, 7):
        for x in range(6, 10):
            c.set(x, y, (86, 74, 70) if (x + y) % 2 else (62, 54, 52))


def _paint_repeater(c):
    """中继器（未通电）：透明背景 + 石台 + 中央暗红点。"""
    c.fill((0, 0, 0), 0)
    for x in range(2, 14):
        for y in range(9, TILE):
            c.set(x, y, (146, 146, 140) if (x + y) % 3 else (126, 126, 120))
    for x in (4, 11):
        for y in range(6, 10):
            c.set(x, y, (86, 60, 44))
    for x in range(6, 10):
        for y in range(6, 10):
            c.set(x, y, (108, 30, 24))


def _paint_repeater_on(c):
    """中继器（通电）：中央红点变亮橙红。"""
    c.fill((0, 0, 0), 0)
    for x in range(2, 14):
        for y in range(9, TILE):
            c.set(x, y, (146, 146, 140) if (x + y) % 3 else (126, 126, 120))
    for x in (4, 11):
        for y in range(6, 10):
            c.set(x, y, (86, 60, 44))
    for x in range(6, 10):
        for y in range(6, 10):
            c.set(x, y, (236, 92, 52))


def _paint_lamp_off(c):
    """红石灯（灭）：暗棕红的不透光块。"""
    c.noise((92, 40, 34), 12, 301)
    c.speckle((72, 30, 26), 20, 302)


def _paint_lamp_on(c):
    """红石灯（亮）：暖橙黄亮面（与 `emissive=1.0` 配套）。"""
    c.noise((228, 176, 96), 12, 303)
    c.speckle((252, 226, 150), 26, 304)


def _paint_door_lower(c):
    """铁门下半（关）：木框 + 金属门板。"""
    for x in range(TILE):
        for y in range(TILE):
            frame = x < 2 or x > 13 or y < 2 or y > 13
            c.set(x, y, (128, 96, 62) if frame else (166, 130, 88))
    for x in range(4, 12):
        for y in range(4, 12):
            c.set(x, y, (188, 168, 132) if (x + y) % 4 else (168, 148, 112))


def _paint_door_upper(c):
    """铁门上半（关）：下部同木框，上部留一块**铁窗格**。"""
    for x in range(TILE):
        for y in range(TILE):
            frame = x < 2 or x > 13 or y < 2 or y > 13
            c.set(x, y, (128, 96, 62) if frame else (166, 130, 88))
    for x in range(4, 12):
        for y in range(3, 9):
            c.set(x, y, (152, 152, 158) if (x % 3 and y % 3) else (116, 116, 122))


def _paint_door_open_lower(c):
    """铁门下半（开）：**只在左右两侧留门框**，中间镂空 ⇒ 能看见对面。"""
    c.fill((0, 0, 0), 0)
    for x in list(range(0, 3)) + list(range(13, TILE)):
        for y in range(TILE):
            c.set(x, y, (128, 96, 62) if y % 4 else (150, 116, 76))


def _paint_door_open_upper(c):
    """铁门上半（开）：两侧门框 + 顶部横梁。"""
    c.fill((0, 0, 0), 0)
    for x in list(range(0, 3)) + list(range(13, TILE)):
        for y in range(TILE):
            c.set(x, y, (128, 96, 62) if y % 4 else (150, 116, 76))
    for x in range(TILE):
        for y in range(0, 3):
            c.set(x, y, (128, 96, 62))


def _paint_piston_side(c):
    """活塞侧面：木板主体 + 下缘一圈铁边。"""
    for x in range(TILE):
        for y in range(TILE):
            c.set(x, y, (196, 152, 96) if (x // 4 + y // 4) % 2 else (176, 134, 82))
    for y in range(11, TILE):
        for x in range(TILE):
            c.set(x, y, (168, 168, 172) if x % 4 else (140, 140, 146))


def _paint_piston_top(c):
    """活塞顶面（推出时朝外那面）：整块铁面。"""
    for x in range(TILE):
        for y in range(TILE):
            c.set(x, y, (172, 172, 176) if (x + y) % 5 else (150, 150, 156))
    for x in range(2, 14):
        c.set(x, 2, (198, 198, 202))
        c.set(x, 13, (126, 126, 132))


def _paint_piston_arm(c):
    """活塞臂：木色长条（伸出时占据前方那一格）。"""
    for x in range(3, 13):
        for y in range(2, 14):
            c.set(x, y, (198, 154, 98) if (x + y) % 6 else (178, 136, 84))
    for x in range(3, 13):
        c.set(x, 2, (166, 126, 76))
        c.set(x, 13, (166, 126, 76))


PAINTERS = {
    'stone': _paint_stone,
    'cobble': _paint_cobble,
    'dirt': _paint_dirt,
    'grass_top': _paint_grass_top,
    'grass_side': _paint_grass_side,
    'sand': _paint_sand,
    'water': _paint_water,
    'log_side': _paint_log_side,
    'log_top': _paint_log_top,
    'leaves': _paint_leaves,
    'planks': _paint_planks,
    'glass': _paint_glass,
    'brick': _paint_brick,
    'snow': _paint_snow,
    'gravel': _paint_gravel,
    'craft_top': _paint_craft_top,
    'craft_side': _paint_craft_side,
    'furnace_side': _paint_furnace_side,
    'furnace_top': _paint_furnace_top,
    'coal_ore': _paint_coal_ore,
    'iron_ore': _paint_iron_ore,
    'gold_ore': _paint_gold_ore,
    'diamond_ore': _paint_diamond_ore,
    'bedrock': _paint_bedrock,
    'torch': _paint_torch,
    'crop': _paint_crop,
    'wool': _paint_wool,
    'redstone_wire': _paint_redstone_wire,
    'lever': _paint_lever,
    'lever_on': _paint_lever_on,
    'button': _paint_button,
    'button_on': _paint_button_on,
    'redstone_torch': _paint_redstone_torch,
    'redstone_torch_off': _paint_redstone_torch_off,
    'repeater': _paint_repeater,
    'repeater_on': _paint_repeater_on,
    'lamp_off': _paint_lamp_off,
    'lamp_on': _paint_lamp_on,
    'door_lower': _paint_door_lower,
    'door_upper': _paint_door_upper,
    'door_open_lower': _paint_door_open_lower,
    'door_open_upper': _paint_door_open_upper,
    'piston_side': _paint_piston_side,
    'piston_top': _paint_piston_top,
    'piston_arm': _paint_piston_arm,
}
#: 图集里的贴图顺序（**顺序即格号**，改顺序会让 UV 全变 ⇒ 有单测钉住）
ATLAS_TILE_NAMES = tuple(sorted(PAINTERS))
TILE_INDEX = {name: i for i, name in enumerate(ATLAS_TILE_NAMES)}

#: 图集网格（列 × 行）。26 张 → 6×5=30 格（够放）；按需向上取整，改动时 UV 换算跟着走。
#: ⚠ **列数只增不减**（Phase 2-C 从 5 提到 6；Phase 3 因红石元件从 6 提到 8 ——
#:   边长 = `COLS × TILE` 是正方形假设，44 张要 6 行，列数 6 时第 7 行会溢出到图集外）：`ATLAS_SIZE = ATLAS_COLS * TILE`
#: 是**正方形**假设 —— 行数增加而列数不变的话，第 6 行会落到图集**外面**，
#: 那两张新矿石贴图会采样到错的东西（`test_atlas_layout` 的
#: "矩形必须落在图集内"就是盯着这条）。改列数会让**所有贴图的 UV 变**，
#: 这是安全的：贴图是程序化重建的，存档里只存方块名。
ATLAS_COLS = 8
ATLAS_ROWS = (len(ATLAS_TILE_NAMES) + ATLAS_COLS - 1) // ATLAS_COLS
ATLAS_SIZE = ATLAS_COLS * TILE           # 正方形图集边长（像素）

TILES = ATLAS_TILE_NAMES                 # 复数别名（对外更常见）


def tile_pixels(name: str) -> bytes:
    """单张贴图的 16×16 RGBA 字节（确定性）。未知名字抛 KeyError。"""
    try:
        painter = PAINTERS[name]
    except KeyError:
        raise KeyError(f'未知贴图 {name!r}；合法：{sorted(PAINTERS)}') from None
    c = _Canvas()
    painter(c)
    return c.bytes()


class AtlasLayout:
    """图集几何：格号 → 像素矩形 / UV 矩形。**UV 的 v 轴与 GL 一致（向上为正）**。"""

    __slots__ = ('cols', 'rows', 'tile', 'size', 'names')

    def __init__(self, cols=ATLAS_COLS, rows=ATLAS_ROWS, tile=TILE,
                 names=ATLAS_TILE_NAMES):
        self.cols = int(cols)
        self.rows = int(rows)
        self.tile = int(tile)
        self.size = self.cols * self.tile
        self.names = tuple(names)

    def cell(self, name: str):
        """贴图名 → (列, 行)。行号从上往下数。"""
        idx = TILE_INDEX[name]
        return idx % self.cols, idx // self.cols

    def pixel_rect(self, name: str):
        """像素矩形 (x, y, w, h)，y 从上往下（与 `build_atlas` 的写入顺序一致）。"""
        cx, cy = self.cell(name)
        return cx * self.tile, cy * self.tile, self.tile, self.tile

    def uv_rect(self, name: str):
        """UV 矩形 (u0, v0, u1, v1)。

        v 轴**翻转**：贴图第 0 行在上，而 GL 的 v=0 在下 —— 所以上边对应 v1。
        """
        x, y, w, h = self.pixel_rect(name)
        u0 = x / self.size
        u1 = (x + w) / self.size
        v1 = 1.0 - y / self.size
        v0 = 1.0 - (y + h) / self.size
        return u0, v0, u1, v1


#: 默认图集几何（与 `build_atlas()` 的输出严格对应）
LAYOUT = AtlasLayout()


def tile_uv_rect(name: str):
    """便捷函数：默认图集里某张贴图的 UV 矩形。"""
    return LAYOUT.uv_rect(name)


def build_atlas(layout: AtlasLayout | None = None) -> bytes:
    """把全部贴图排成一张 RGBA 图集（行优先，逐张贴上去）。

    返回 `layout.size × layout.size × 4` 字节。**格号顺序即 `ATLAS_TILE_NAMES`**，
    所以本函数的输出对"顺序"极其敏感 —— 有单测逐像素核对任意两张贴图的位置。
    """
    lay = layout or LAYOUT
    size = lay.size
    out = bytearray(size * size * 4)
    for name in lay.names:
        px = tile_pixels(name)
        x0, y0, w, h = lay.pixel_rect(name)
        for ty in range(h):
            row_dst = ((y0 + ty) * size + x0) * 4
            row_src = ty * w * 4
            out[row_dst:row_dst + w * 4] = px[row_src:row_src + w * 4]
    return bytes(out)


def atlas_texture(layout: AtlasLayout | None = None):
    """上传成 pyglet 纹理（**需要 GL 上下文**；单测不碰这一层）。

    NEAREST 过滤是有意的：像素材质放大后要保住硬边（线性过滤会糊成一团）。
    """
    lay = layout or LAYOUT
    from pyglet import image
    blob = build_atlas(lay)
    img = image.ImageData(lay.size, lay.size, 'RGBA', blob)
    return img.get_texture()
