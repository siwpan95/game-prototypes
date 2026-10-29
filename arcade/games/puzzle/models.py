"""
Model 层 —— 数据模型与业务逻辑
包含原有图像风格转换（ImageModel）和新增拼图游戏（PuzzleModel）两个模块。
纯数据操作，不依赖 View / ViewModel，不涉及 UI 或线程。
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError as e:
    print(f"导入库失败: {e}")
    print("请确保已安装所需库: pip install pygame-ce Pillow")
    sys.exit(1)


# ======================================================================
# 原有模块：艺术风格转换
# ======================================================================

class ArtStyle(Enum):
    """艺术风格枚举 —— 按分类组织，用  ·  分隔主风格与子流派"""

    # ── 原始 ──
    ORIGINAL = "原始"

    # ── 像素 / 马赛克 ──
    PIXEL = "像素画"
    MOSAIC = "像素画 · 马赛克"
    PIXEL_LARGE = "像素画 · 大色块"

    # ── 油画 ──
    OIL_PAINTING = "油画 · 古典写实"
    OIL_IMPRESSIONISM = "油画 · 印象派"
    OIL_POST_IMPRESSIONISM = "油画 · 后印象派"
    OIL_EXPRESSIONISM = "油画 · 表现主义"
    OIL_PALETTE_KNIFE = "油画 · 刮刀效果"

    # ── 素描 / 线稿 ──
    SKETCH = "素描 · 炭笔"
    SKETCH_PENCIL = "素描 · 铅笔"
    SKETCH_CONTOUR = "素描 · 轮廓线"
    SKETCH_INK = "素描 · 钢笔速写"

    # ── 水彩 / 水墨 ──
    WATERCOLOR = "水彩画"
    INK_WASH = "水墨画"

    # ── 插画 / 漫画 ──
    CARTOON = "插画 · 卡通"
    COMIC_HALFTONE = "插画 · 半色调漫画"
    POSTERIZE = "插画 · 波普海报"

    # ── 复古 / 胶片 ──
    SEPIA = "复古 · 怀旧棕色"
    VINTAGE = "复古 · 老照片"
    NEGATIVE = "复古 · 负片"

    # ── 特效 ──
    EMBOSS = "特效 · 浮雕"
    GLASS = "特效 · 毛玻璃"
    EDGE_DETECT = "特效 · 边缘检测"
    BLUR_DREAM = "特效 · 梦幻柔焦"


@dataclass
class ImageModel:
    """图像数据模型 —— 负责图片的加载、风格处理与保存（原有功能）"""

    original_image: Optional[Image.Image] = None
    processed_image: Optional[Image.Image] = None
    current_style: ArtStyle = ArtStyle.ORIGINAL
    file_path: Optional[str] = None

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------
    def load_image(self, path: str) -> bool:
        """从磁盘加载图片"""
        try:
            self.original_image = Image.open(path).convert("RGB")
            self.processed_image = self.original_image.copy()
            self.file_path = path
            self.current_style = ArtStyle.ORIGINAL
            return True
        except Exception as e:
            print(f"加载图片失败: {e}")
            return False

    def save_image(self, path: str) -> bool:
        """保存处理后的图片到磁盘"""
        if self.processed_image is None:
            return False
        try:
            self.processed_image.save(path)
            return True
        except Exception as e:
            print(f"保存图片失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 风格处理（纯业务逻辑，无副作用）
    # ------------------------------------------------------------------
    def apply_style(self, style: ArtStyle) -> None:
        """对 original_image 应用指定风格，结果写入 processed_image"""
        if self.original_image is None:
            return

        handler = {
            ArtStyle.ORIGINAL:                self._copy_original,
            ArtStyle.PIXEL:                   self._create_pixel_art,
            ArtStyle.MOSAIC:                  self._create_mosaic,
            ArtStyle.PIXEL_LARGE:             self._create_pixel_large,
            ArtStyle.OIL_PAINTING:            self._oil_classical,
            ArtStyle.OIL_IMPRESSIONISM:       self._oil_impressionism,
            ArtStyle.OIL_POST_IMPRESSIONISM:  self._oil_post_impressionism,
            ArtStyle.OIL_EXPRESSIONISM:       self._oil_expressionism,
            ArtStyle.OIL_PALETTE_KNIFE:       self._oil_palette_knife,
            ArtStyle.SKETCH:                  self._sketch_charcoal,
            ArtStyle.SKETCH_PENCIL:           self._sketch_pencil,
            ArtStyle.SKETCH_CONTOUR:          self._sketch_contour,
            ArtStyle.SKETCH_INK:              self._sketch_ink,
            ArtStyle.WATERCOLOR:              self._watercolor,
            ArtStyle.INK_WASH:                self._ink_wash,
            ArtStyle.CARTOON:                 self._cartoon,
            ArtStyle.COMIC_HALFTONE:          self._comic_halftone,
            ArtStyle.POSTERIZE:               self._posterize,
            ArtStyle.SEPIA:                   self._sepia,
            ArtStyle.VINTAGE:                 self._vintage,
            ArtStyle.NEGATIVE:                self._negative,
            ArtStyle.EMBOSS:                  self._emboss,
            ArtStyle.GLASS:                   self._glass,
            ArtStyle.EDGE_DETECT:             self._edge_detect,
            ArtStyle.BLUR_DREAM:              self._blur_dream,
        }

        self.processed_image = handler.get(style, self._copy_original)()
        self.current_style = style

    # ==================================================================
    # 通用工具方法
    # ==================================================================
    def _copy_original(self) -> Image.Image:
        return self.original_image.copy()

    @staticmethod
    def _boost_saturation(img: Image.Image, factor: float) -> Image.Image:
        return ImageEnhance.Color(img).enhance(factor)

    @staticmethod
    def _boost_contrast(img: Image.Image, factor: float) -> Image.Image:
        return ImageEnhance.Contrast(img).enhance(factor)

    @staticmethod
    def _boost_brightness(img: Image.Image, factor: float) -> Image.Image:
        return ImageEnhance.Brightness(img).enhance(factor)

    @staticmethod
    def _add_noise(img: Image.Image, intensity: int = 20) -> Image.Image:
        img = img.copy()
        pixels = img.load()
        for y in range(img.height):
            for x in range(img.width):
                r, g, b = pixels[x, y]
                r = min(255, max(0, r + random.randint(-intensity, intensity)))
                g = min(255, max(0, g + random.randint(-intensity, intensity)))
                b = min(255, max(0, b + random.randint(-intensity, intensity)))
                pixels[x, y] = (r, g, b)
        return img

    @staticmethod
    def _add_vignette(img: Image.Image, darkness: float = 0.5) -> Image.Image:
        img = img.copy()
        w, h = img.width, img.height
        cx, cy = w / 2.0, h / 2.0
        max_dist = (cx**2 + cy**2) ** 0.5
        pixels = img.load()
        for y in range(h):
            for x in range(w):
                dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / max_dist
                factor = 1.0 - darkness * (dist**1.5)
                factor = max(0.3, factor)
                r, g, b = pixels[x, y]
                pixels[x, y] = (
                    int(r * factor),
                    int(g * factor),
                    int(b * factor),
                )
        return img

    # ==================================================================
    # 像素 / 马赛克
    # ==================================================================
    def _create_pixel_art(self, pixel_size: int = 10) -> Image.Image:
        img = self.original_image.copy()
        small = img.resize(
            (max(1, img.width // pixel_size), max(1, img.height // pixel_size)),
            resample=Image.NEAREST,
        )
        return small.resize((img.width, img.height), resample=Image.NEAREST)

    def _create_mosaic(self, block_size: int = 15) -> Image.Image:
        img = self.original_image.copy()
        small = img.resize(
            (max(1, img.width // block_size), max(1, img.height // block_size)),
            resample=Image.NEAREST,
        )
        return small.resize((img.width, img.height), resample=Image.NEAREST)

    def _create_pixel_large(self, block_size: int = 30) -> Image.Image:
        img = self.original_image.copy()
        small = img.resize(
            (max(1, img.width // block_size), max(1, img.height // block_size)),
            resample=Image.NEAREST,
        )
        result = small.resize((img.width, img.height), resample=Image.NEAREST)
        return result.filter(ImageFilter.SHARPEN)

    # ==================================================================
    # 油画流派
    # ==================================================================
    def _oil_classical(self, radius: int = 5) -> Image.Image:
        img = self.original_image.copy()
        result = img.filter(ImageFilter.MedianFilter(size=radius))
        result = self._boost_brightness(result, 0.90)
        result = self._boost_saturation(result, 0.85)
        return result

    def _oil_impressionism(self, radius: int = 3) -> Image.Image:
        img = self.original_image.copy()
        result = img.filter(ImageFilter.MedianFilter(size=radius))
        result = self._boost_saturation(result, 1.25)
        result = self._boost_brightness(result, 1.05)
        result = result.filter(ImageFilter.GaussianBlur(radius=0.5))
        return result

    def _oil_post_impressionism(self) -> Image.Image:
        img = self.original_image.copy()
        ratio = max(1, min(img.width, img.height) // 120)
        small = img.resize(
            (img.width // ratio, img.height // ratio),
            resample=Image.BILINEAR,
        )
        result = small.resize((img.width, img.height), resample=Image.BILINEAR)
        result = self._boost_saturation(result, 1.6)
        result = self._boost_contrast(result, 1.3)
        edges = result.filter(ImageFilter.FIND_EDGES).convert("RGB")
        result = Image.blend(result, edges, alpha=0.10)
        return result

    def _oil_expressionism(self) -> Image.Image:
        img = self.original_image.copy()
        result = img.filter(ImageFilter.MedianFilter(size=3))
        result = self._boost_saturation(result, 1.8)
        result = self._boost_contrast(result, 1.4)
        hsv = result.convert("HSV")
        h, s, v = hsv.split()
        h = h.point(lambda x: (x + random.randint(-8, 8)) % 256)
        result = Image.merge("HSV", (h, s, v)).convert("RGB")
        result = self._add_noise(result, intensity=8)
        return result

    def _oil_palette_knife(self) -> Image.Image:
        img = self.original_image.copy()
        result = img.filter(ImageFilter.MedianFilter(size=5))
        result = ImageOps.posterize(result, bits=4)
        edges = img.filter(ImageFilter.FIND_EDGES).convert("RGB")
        edges = edges.filter(ImageFilter.GaussianBlur(radius=0.5))
        result = Image.blend(result, edges, alpha=0.15)
        return self._boost_saturation(result, 1.1)

    # ==================================================================
    # 素描 / 线稿
    # ==================================================================
    def _sketch_charcoal(self) -> Image.Image:
        gray = self.original_image.convert("L")
        inverted = ImageOps.invert(gray)
        blurred = inverted.filter(ImageFilter.GaussianBlur(radius=5))
        result = Image.blend(gray, blurred, alpha=0.45)
        result = self._boost_contrast(result.convert("RGB"), 1.5)
        result = self._add_noise(result, intensity=12)
        return result

    def _sketch_pencil(self) -> Image.Image:
        gray = self.original_image.convert("L")
        inverted = ImageOps.invert(gray)
        blurred = inverted.filter(ImageFilter.GaussianBlur(radius=2))
        result = Image.blend(gray, blurred, alpha=0.5)
        result = self._boost_brightness(result.convert("RGB"), 1.15)
        return result

    def _sketch_contour(self) -> Image.Image:
        gray = self.original_image.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edges = ImageOps.invert(edges)
        edges = edges.point(lambda x: 255 if x > 80 else x)
        return edges.convert("RGB")

    def _sketch_ink(self) -> Image.Image:
        gray = self.original_image.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edges = edges.filter(ImageFilter.MaxFilter(size=3))
        edges = ImageOps.invert(edges)
        result = edges.point(lambda x: 255 if x > 120 else 0)
        return result.convert("RGB")

    # ==================================================================
    # 水彩 / 水墨
    # ==================================================================
    def _watercolor(self) -> Image.Image:
        img = self.original_image.copy()
        result = img.filter(ImageFilter.GaussianBlur(radius=1.5))
        result = self._boost_contrast(result, 0.8)
        result = self._boost_brightness(result, 1.1)
        result = self._boost_saturation(result, 1.1)
        result = self._add_noise(result, intensity=4)
        return result

    def _ink_wash(self) -> Image.Image:
        gray = self.original_image.convert("L")
        blurred = gray.filter(ImageFilter.GaussianBlur(radius=4))
        result = Image.blend(gray, blurred, alpha=0.6)
        result = ImageEnhance.Contrast(result).enhance(1.3)
        result = self._boost_brightness(result.convert("RGB"), 1.1)
        pixels = result.load()
        for y in range(result.height):
            for x in range(result.width):
                r, g, b = pixels[x, y]
                r = min(255, int(r * 1.02))
                g = min(255, int(g * 1.01))
                pixels[x, y] = (r, g, b)
        return result

    # ==================================================================
    # 插画 / 漫画
    # ==================================================================
    def _cartoon(self) -> Image.Image:
        img = self.original_image.copy()
        smoothed = img.filter(ImageFilter.MedianFilter(size=7))
        posterized = ImageOps.posterize(smoothed, bits=4)
        edges = img.filter(ImageFilter.FIND_EDGES).convert("L")
        edges = edges.point(lambda x: 0 if x > 30 else 255)
        edges_rgb = edges.convert("RGB")
        result = Image.blend(posterized, edges_rgb, alpha=0.3)
        return self._boost_saturation(result, 1.15)

    def _comic_halftone(self) -> Image.Image:
        gray = self.original_image.convert("L")
        gray = ImageEnhance.Contrast(gray).enhance(2.0)
        result = ImageOps.posterize(gray, bits=3)
        result = self._add_noise(result.convert("RGB"), intensity=15)
        return self._boost_contrast(result, 1.2)

    def _posterize(self) -> Image.Image:
        img = self.original_image.copy()
        result = ImageOps.posterize(img, bits=3)
        result = self._boost_saturation(result, 2.0)
        result = self._boost_contrast(result, 1.3)
        result = result.filter(ImageFilter.SHARPEN)
        return result

    # ==================================================================
    # 复古 / 胶片
    # ==================================================================
    def _sepia(self) -> Image.Image:
        gray = self.original_image.convert("L")
        r = gray.point(lambda x: min(x * 1.05, 255))
        g = gray.point(lambda x: min(x * 0.95, 255))
        b = gray.point(lambda x: min(x * 0.75, 255))
        return Image.merge("RGB", (r, g, b))

    def _vintage(self) -> Image.Image:
        img = self.original_image.copy()
        gray = img.convert("L")
        r = gray.point(lambda x: min(x * 1.0, 255))
        g = gray.point(lambda x: min(x * 0.9, 255))
        b = gray.point(lambda x: min(x * 0.65, 255))
        result = Image.merge("RGB", (r, g, b))
        result = self._boost_contrast(result, 0.85)
        result = self._boost_brightness(result, 0.9)
        result = self._add_noise(result, intensity=20)
        result = self._add_vignette(result, darkness=0.45)
        return result

    def _negative(self) -> Image.Image:
        return ImageOps.invert(self.original_image.copy())

    # ==================================================================
    # 特效
    # ==================================================================
    def _emboss(self) -> Image.Image:
        img = self.original_image.copy()
        result = img.filter(ImageFilter.EMBOSS)
        return result.convert("L").convert("RGB")

    def _glass(self) -> Image.Image:
        img = self.original_image.copy()
        result = img.filter(ImageFilter.GaussianBlur(radius=5))
        result = self._boost_brightness(result, 1.05)
        return result

    def _edge_detect(self) -> Image.Image:
        img = self.original_image.copy()
        edges = img.filter(ImageFilter.FIND_EDGES)
        edges = ImageOps.invert(edges)
        return edges

    def _blur_dream(self) -> Image.Image:
        img = self.original_image.copy()
        blurred = img.filter(ImageFilter.GaussianBlur(radius=8))
        result = Image.blend(img, blurred, alpha=0.6)
        result = self._boost_brightness(result, 1.15)
        result = self._boost_saturation(result, 1.05)
        return result


# ======================================================================
# 新增模块：拼图游戏
# ======================================================================

@dataclass
class Tile:
    """单个拼图块的数据模型"""
    id: int               # 块的编号（0 ~ total-1），也代表正确位置
    row: int              # 当前所在行
    col: int              # 当前所在列
    image: Image.Image    # 该块的 PIL 图像碎片


@dataclass
class PuzzleModel:
    """
    拼图状态模型
    - original_image: 原始加载的图片
    - tiles:          所有拼图块列表（按 id 索引）
    - rows / cols:    行列数
    - tile_width / tile_height: 每块像素尺寸
    - completed:      是否已完成
    """
    original_image: Optional[Image.Image] = None
    tiles: List[Tile] = field(default_factory=list)
    rows: int = 0
    cols: int = 0
    tile_width: int = 0
    tile_height: int = 0
    completed: bool = False
    file_path: Optional[str] = None

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------
    def load_image(self, path: str) -> bool:
        """从磁盘加载图片（拼图用）"""
        try:
            self.original_image = Image.open(path).convert("RGB")
            self.file_path = path
            self.tiles = []
            self.completed = False
            return True
        except Exception as e:
            print(f"加载图片失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 拼图制作
    # ------------------------------------------------------------------
    def create_puzzle(self, rows: int, cols: int) -> bool:
        """将 original_image 切分为 rows × cols 块"""
        if self.original_image is None:
            return False
        if rows < 2 or cols < 2:
            return False

        self.rows = rows
        self.cols = cols
        img = self.original_image

        # 调整图片尺寸为行列的整数倍
        disp_w = (img.width // cols) * cols
        disp_h = (img.height // rows) * rows
        img = img.resize((disp_w, disp_h), Image.Resampling.LANCZOS)

        self.tile_width = disp_w // cols
        self.tile_height = disp_h // rows

        self.tiles.clear()
        tile_id = 0
        for r in range(rows):
            for c in range(cols):
                crop_box = (
                    c * self.tile_width,
                    r * self.tile_height,
                    (c + 1) * self.tile_width,
                    (r + 1) * self.tile_height,
                )
                tile_img = img.crop(crop_box)
                self.tiles.append(Tile(
                    id=tile_id,
                    row=r,
                    col=c,
                    image=tile_img,
                ))
                tile_id += 1

        self.completed = False
        return True

    # ------------------------------------------------------------------
    # 打乱
    # ------------------------------------------------------------------
    def shuffle_tiles(self) -> None:
        """打乱所有拼图块的位置"""
        if not self.tiles:
            return
        positions = [(r, c) for r in range(self.rows) for c in range(self.cols)]
        shuffled = positions.copy()
        random.shuffle(shuffled)
        for i, tile in enumerate(self.tiles):
            tile.row, tile.col = shuffled[i]
        self.completed = False

    # ------------------------------------------------------------------
    # 移动 / 交换
    # ------------------------------------------------------------------
    def move_tile(self, tile_id: int, target_row: int, target_col: int) -> bool:
        """
        将指定块移动到目标格位。
        若目标格位已有其他块，则交换两者位置。
        """
        if tile_id < 0 or tile_id >= len(self.tiles):
            return False
        if not (0 <= target_row < self.rows and 0 <= target_col < self.cols):
            return False

        tile = self.tiles[tile_id]
        existing = self._get_tile_at(target_row, target_col)
        if existing is not None and existing.id != tile_id:
            existing.row, existing.col = tile.row, tile.col

        tile.row, tile.col = target_row, target_col
        self._check_completion()
        return True

    def swap_tiles(self, tile_id_a: int, tile_id_b: int) -> bool:
        """交换两个块的位置"""
        if tile_id_a < 0 or tile_id_a >= len(self.tiles):
            return False
        if tile_id_b < 0 or tile_id_b >= len(self.tiles):
            return False
        a = self.tiles[tile_id_a]
        b = self.tiles[tile_id_b]
        a.row, a.col, b.row, b.col = b.row, b.col, a.row, a.col
        self._check_completion()
        return True

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def get_tile_at(self, row: int, col: int) -> Optional[Tile]:
        """返回位于指定格位的拼图块"""
        for tile in self.tiles:
            if tile.row == row and tile.col == col:
                return tile
        return None

    def _get_tile_at(self, row: int, col: int) -> Optional[Tile]:
        for tile in self.tiles:
            if tile.row == row and tile.col == col:
                return tile
        return None

    def is_completed(self) -> bool:
        """检查是否所有块都在正确位置"""
        return all(
            tile.row == tile.id // self.cols and tile.col == tile.id % self.cols
            for tile in self.tiles
        )

    def _check_completion(self) -> None:
        self.completed = self.is_completed()

    def get_completed_count(self) -> int:
        """返回已归位的块数"""
        return sum(
            1 for tile in self.tiles
            if tile.row == tile.id // self.cols and tile.col == tile.id % self.cols
        )

    def get_total_tiles(self) -> int:
        return len(self.tiles)

    def get_image_info(self) -> str:
        if self.original_image and self.file_path:
            import os
            return (
                f"文件: {os.path.basename(self.file_path)}"
                f" | 尺寸: {self.original_image.width} x {self.original_image.height}"
                f" | 拼图: {self.rows} x {self.cols}"
            )
        return "未加载图片"
