"""麻将牌面渲染器 (PIL) — 实体 3D 方块。

每张牌渲染为一块有厚度的立体麻将牌:
  - 正面: 圆角象牙白底 + 牌面图案 (筒/条/万/风/箭/季/花)
  - 右侧面 / 底面: 45° 斜切的平行四边形 (受光较少 -> 更暗)，
    即"三视图"中的侧面，赋予明显的实体厚度与立体堆叠感
  - 投影: 落在下层牌上，强化"上层压住下层"的遮挡关系

渲染结果按 tile.short 缓存为 ImageTk.PhotoImage (供 Tk Canvas 使用)，
同时缓存 PIL 原图 (供离屏合成/截图自检)。

单张牌图像尺寸 = 正面(sz) + 右/下侧面(th) + 投影偏移(sh)。
正面左上角固定在图像 (0,0)，因此棋盘放置时只需把图像 NW 角
对齐到牌的正面左上屏幕坐标即可。
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageTk

from allin_engine.utils.font import discover_local_fonts
from models.tile import Suit, Tile

# 数字 1..9 -> 中文
_CN = "零一二三四五六七八九"

# Cocos 麻将精灵目录（相对于项目根目录）
_COCOS_SPRITE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "cocos_sprites"
)


def _cocos_sprite_code(tile: Tile) -> Optional[str]:
    """把 Tile 映射到 Cocos 精灵文件名（不含 .png）。

    映射规则来自 cocostudio-mahjong-master:
      筒子(DOTS) -> mingmah_1x, 万子(CHAR) -> mingmah_2x,
      条子(BAMBOO)-> mingmah_3x, 风牌(WIND) -> mingmah_41..44,
      箭牌(DRAGON)-> mingmah_45..47。
    季/花及异常 rank 返回 None（使用程序化回退）。
    """
    if tile.suit == Suit.DOTS and 1 <= tile.rank <= 9:
        cc, vv = 1, tile.rank
    elif tile.suit == Suit.CHAR and 1 <= tile.rank <= 9:
        cc, vv = 2, tile.rank
    elif tile.suit == Suit.BAMBOO and 1 <= tile.rank <= 9:
        cc, vv = 3, tile.rank
    elif tile.suit == Suit.WIND and 1 <= tile.rank <= 4:
        cc, vv = 4, tile.rank
    elif tile.suit == Suit.DRAGON and 1 <= tile.rank <= 3:
        cc, vv = 4, tile.rank + 4
    else:
        return None
    return f"mingmah_{cc}{vv}"


def _circle_layout(n: int, w: int, h: int) -> List[Tuple[float, float, int]]:
    """返回 n 个圆的 (cx, cy, radius) 列表，居于 (w,h) 区域内。
    采用经典麻将筒子排列。
    """
    cx, cy = w / 2, h / 2
    r = max(3, min(w, h) // 9)
    R = r * 2  # 间距
    layouts = {
        1: [(cx, cy, r + 2)],
        2: [(cx, cy - R, r), (cx, cy + R, r)],
        3: [(cx - R, cy - R, r), (cx, cy, r), (cx + R, cy + R, r)],
        4: [(cx - R, cy - R, r), (cx + R, cy - R, r),
            (cx - R, cy + R, r), (cx + R, cy + R, r)],
        5: [(cx - R, cy - R, r), (cx + R, cy - R, r),
            (cx, cy, r),
            (cx - R, cy + R, r), (cx + R, cy + R, r)],
        6: [(cx - R, cy - R, r), (cx + R, cy - R, r),
            (cx - R, cy, r), (cx + R, cy, r),
            (cx - R, cy + R, r), (cx + R, cy + R, r)],
        7: [(cx, cy - R, r),
            (cx - R, cy, r), (cx + R, cy, r),
            (cx - R, cy + R, r), (cx, cy + R, r), (cx + R, cy + R, r),
            (cx, cy + R * 2, r)],
        8: [(cx - R, cy - R, r), (cx + R, cy - R, r),
            (cx - R, cy - 0, r), (cx + R, cy - 0, r),
            (cx - R, cy + R, r), (cx + R, cy + R, r),
            (cx - R, cy + R * 2, r), (cx + R, cy + R * 2, r)],
        9: [(cx - R, cy - R, r), (cx, cy - R, r), (cx + R, cy - R, r),
            (cx - R, cy, r), (cx, cy, r), (cx + R, cy, r),
            (cx - R, cy + R, r), (cx, cy + R, r), (cx + R, cy + R, r)],
    }
    base = layouts.get(n, [])
    # 7 的排列修正 (上1 + 中3 + 下3)
    if n == 7:
        return [
            (cx, cy - R, r),
            (cx - R, cy, r), (cx + R, cy, r),
            (cx - R, cy + R, r), (cx, cy + R, r), (cx + R, cy + R, r),
            (cx, cy + R * 2, r) if (cy + R * 2) < h else (cx, cy + R - 1, r),
        ]
    # 8 的排列修正 (两列四行)
    if n == 8:
        ys = [cy - R * 1.2, cy - R * 0.4, cy + R * 0.4, cy + R * 1.2]
        out = []
        for yy in ys:
            out.append((cx - R, yy, r))
            out.append((cx + R, yy, r))
        return out
    return base


class TileRenderer:
    def __init__(self, tile_size: int = 56, thickness: int = 15,
                 shadow: int = 7) -> None:
        """thickness = 牌的侧面厚度(45°立体感); shadow = 投影偏移像素。"""
        self.sz = tile_size
        self.th = thickness
        self.sh = shadow
        # 单张牌图像尺寸 = 正面 + 右/下侧面 + 投影
        self.img_w = tile_size + thickness + shadow
        self.img_h = tile_size + thickness + shadow
        self._pil_cache: Dict[str, Image.Image] = {}
        self._photo_cache: Dict[str, ImageTk.PhotoImage] = {}
        self._sprite_cache: Dict[str, Image.Image] = {}
        self._sprites_available = os.path.isdir(_COCOS_SPRITE_DIR)
        self._font_main: Optional[str] = None
        self._font_symbol: Optional[str] = None
        self._load_fonts()

    # ---- 字体（交给引擎字体发现机制托管）-------------------
    def _load_fonts(self) -> None:
        # 引擎已把 SimHei.ttf / Arial.ttf 并入 allin_engine/fonts/，
        # discover_local_fonts() 按文件名 stem 给出别名 (simhei / arial)。
        table = {alias: str(path) for alias, path in discover_local_fonts()}
        self._font_main = table.get("simhei")
        self._font_symbol = table.get("arial")

    def _font(self, size: int, symbol: bool = False) -> ImageFont.FreeTypeFont:
        path = (self._font_symbol if symbol else self._font_main)
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()

    # ---- Cocos 精灵贴图 ------------------------------------------
    def _load_cocos_face(self, code: str) -> Optional[Image.Image]:
        """加载并裁剪 Cocos 牌面精灵；缓存原始图，返回 RGBA Image。"""
        if code in self._sprite_cache:
            return self._sprite_cache[code]
        path = os.path.join(_COCOS_SPRITE_DIR, f"{code}.png")
        if not os.path.exists(path):
            return None
        try:
            im = Image.open(path).convert("RGBA")
            w, h = im.size
            # 裁掉底部绿色装饰条并保留居中牌面（经验比例，适配 120x114 精灵）
            left = int(w * 0.083)
            top = 0
            right = int(w * 0.917)
            bottom = int(h * 0.825)
            face = im.crop((left, top, right, bottom))
            self._sprite_cache[code] = face
            return face
        except Exception:
            return None

    # ---- 缓存入口 ------------------------------------------------
    def get_pil(self, tile: Tile) -> Image.Image:
        """返回 PIL 原图 (供离屏合成/截图自检)。"""
        key = tile.short
        if key not in self._pil_cache:
            self._pil_cache[key] = self._render(tile)
        return self._pil_cache[key]

    def get_image(self, tile: Tile) -> ImageTk.PhotoImage:
        key = tile.short
        if key not in self._photo_cache:
            pil = self.get_pil(tile)
            self._photo_cache[key] = ImageTk.PhotoImage(pil)
        return self._photo_cache[key]

    # ---- 渲染主体 (实体 3D 方块) ---------------------------------
    def _render(self, tile: Tile) -> Image.Image:
        sz = self.sz
        th = self.th
        sh = self.sh
        W, H = self.img_w, self.img_h
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # 1) 投影: 落在下层牌上，制造"被压住"的遮挡立体感 (仅厚度牌需要)
        if sh > 0:
            d.rounded_rectangle([sh, sh, sh + sz + th, sh + sz + th],
                                radius=8, fill=(0, 0, 0, 55))

        # 2/3) 侧面立体厚度 (平面模式 th=0 时跳过, 得到扁平牌以节省棋盘空间)
        if th > 0:
            # 右侧面 (朝右，受光较少 -> 偏暗) — 45° 斜切平行四边形
            d.polygon([(sz, 0), (sz + th, th),
                       (sz + th, sz + th), (sz, sz)],
                      fill=(196, 186, 156, 255))
            # 底面 (朝下，最暗) — 45° 斜切平行四边形
            d.polygon([(0, sz), (th, sz + th),
                       (sz + th, sz + th), (sz, sz)],
                      fill=(170, 160, 130, 255))
            # 侧面受光高光 (上沿亮线，强化 45° 立体厚度)
            d.line([(sz, 0), (sz + th, th)], fill=(234, 226, 202, 255), width=2)
            d.line([(0, sz), (th, sz + th)], fill=(224, 215, 190, 255), width=2)

        # 4) 正面牌体: 圆角象牙白
        d.rounded_rectangle([1, 1, sz - 1, sz - 1], radius=8,
                            fill=(247, 242, 228, 255),
                            outline=(150, 125, 92, 255), width=1)
        # 正面微凸 bevel: 左上高光 / 右下阴影
        d.line([(3, sz - 4), (3, 3), (sz - 4, 3)],
               fill=(255, 252, 244, 200), width=2)
        d.line([(sz - 3, 4), (sz - 3, sz - 3), (4, sz - 3)],
               fill=(120, 100, 70, 180), width=2)

        # 5) 牌面内容 (绘制于正面区域 [0..sz])
        self._draw_face(d, tile, img)
        return img

    def _draw_face(self, d: ImageDraw.Draw, tile: Tile, img: Image.Image) -> None:
        sz = self.sz

        # 优先使用 Cocos 精灵贴图（34 张标准牌），失败时回退到程序化绘制
        if self._sprites_available:
            code = _cocos_sprite_code(tile)
            if code:
                sprite = self._load_cocos_face(code)
                if sprite is not None:
                    face = sprite.resize((sz - 2, sz - 2), Image.LANCZOS)
                    img.paste(face, (1, 1), face)
                    return

        # 程序化回退：季/花、素材缺失、或精灵目录不存在时绘制
        cx, cy = sz / 2, sz / 2

        if tile.suit == Suit.DOTS:
            self._draw_dots(d, tile.rank, sz)
        elif tile.suit == Suit.BAMBOO:
            self._draw_bamboo(d, tile.rank, sz)
        elif tile.suit == Suit.CHAR:
            self._draw_char(d, tile.rank, sz)
        elif tile.suit == Suit.WIND:
            self._draw_text_centered(d, tile.short, sz, "#222", 24)
        elif tile.suit == Suit.DRAGON:
            self._draw_dragon(d, tile.short, sz)
        elif tile.suit in (Suit.SEASON, Suit.FLOWER):
            self._draw_text_centered(d, tile.short, sz, "#c60", 24)
            # 季花小角标
            d.rounded_rectangle([3, 3, 9, 9], radius=2,
                                fill=(198, 96, 0, 255) if tile.suit == Suit.SEASON
                                else (180, 80, 120, 255))

    # ---- 筒子 ----------------------------------------------------
    def _draw_dots(self, d: ImageDraw.Draw, rank: int, sz: int) -> None:
        circles = _circle_layout(rank, sz - 10, sz - 10)
        ox, oy = 5, 5
        # 1筒用大花圆，其余红/绿混色
        for i, (cx, cy, r) in enumerate(circles):
            color = "#c33"
            if rank == 1:
                color = "#c33"
            elif (i % 2) == 1:
                color = "#2a7d2a"
            d.ellipse([cx - r + ox, cy - r + oy, cx + r + ox, cy + r + oy],
                      fill=color, outline="#400", width=1)
            # 圆心高光
            d.ellipse([cx - 1 + ox, cy - 1 + oy, cx + 1 + ox, cy + 1 + oy],
                      fill="#fff8")

    # ---- 条子 ----------------------------------------------------
    def _draw_bamboo(self, d: ImageDraw.Draw, rank: int, sz: int) -> None:
        if rank == 1:
            # 1条: 画鸟 (简化为红圆 + 尖喙 + 幺字)
            self._draw_text_centered(d, "幺", sz, "#c33", 20)
            return
        # 竖条排列 (复用圆布局的位置，画竖条)
        positions = _circle_layout(rank, sz - 10, sz - 10)
        ox, oy = 5, 5
        bw = 4
        bh = 11
        for (cx, cy, _) in positions:
            x0 = cx - bw // 2 + ox
            y0 = cy - bh // 2 + oy
            d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=2,
                                fill="#2a7d2a", outline="#1a4d1a", width=1)

    # ---- 万子 ----------------------------------------------------
    def _draw_char(self, d: ImageDraw.Draw, rank: int, sz: int) -> None:
        num = _CN[rank]
        # 上方数字 (黑)
        fnum = self._font(16)
        bbox = d.textbbox((0, 0), num, font=fnum)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        d.text(((sz - w) / 2, 8), num, fill="#222", font=fnum)
        # 下方"万" (红)
        fwan = self._font(15)
        bbox2 = d.textbbox((0, 0), "万", font=fwan)
        w2 = bbox2[2] - bbox2[0]
        d.text(((sz - w2) / 2, sz - 22), "万", fill="#c00", font=fwan)

    # ---- 箭牌 ----------------------------------------------------
    def _draw_dragon(self, d: ImageDraw.Draw, name: str, sz: int) -> None:
        if name == "白":
            # 白板: 蓝色边框矩形
            d.rounded_rectangle([10, 12, sz - 11, sz - 13], radius=3,
                                outline="#04c", width=2)
            return
        color = "#c00" if name == "中" else "#080"
        self._draw_text_centered(d, name, sz, color, 26)

    # ---- 工具 ----------------------------------------------------
    def _draw_text_centered(self, d: ImageDraw.Draw, text: str,
                            sz: int, color: str, size: int) -> None:
        f = self._font(size)
        bbox = d.textbbox((0, 0), text, font=f)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (sz - w) / 2 - bbox[0]
        y = (sz - h) / 2 - bbox[1]
        d.text((x, y), text, fill=color, font=f)
