"""
ViewModel 层 —— 视图模型
连接 Model 与 View：持有 Model 实例，封装命令，通过消息队列通知 View。

流程：加载图片 → 画风处理（可选）→ 制作为拼图 → 打乱 → 用户拼合
"""

from __future__ import annotations

import os
import queue
import threading
from typing import List, Optional, Tuple

from models import ArtStyle, ImageModel, PuzzleModel, Tile


class ImageViewModel:
    """
    视图模型 —— 支持完整拼图游戏流程：
    1. 加载图片（同时供给 art_model 和 puzzle_model）
    2. 应用画风（处理 art_model.processed_image）
    3. 用 puzzle_model.original_image 制作拼图
    4. 打乱拼图，用户交互拼合
    """

    def __init__(self) -> None:
        self.art_model = ImageModel()
        self.puzzle_model = PuzzleModel()

        # 风格命令映射
        self._style_commands = {
            ArtStyle.ORIGINAL:                lambda: self.art_model.apply_style(ArtStyle.ORIGINAL),
            ArtStyle.PIXEL:                   lambda: self.art_model.apply_style(ArtStyle.PIXEL),
            ArtStyle.MOSAIC:                  lambda: self.art_model.apply_style(ArtStyle.MOSAIC),
            ArtStyle.PIXEL_LARGE:             lambda: self.art_model.apply_style(ArtStyle.PIXEL_LARGE),
            ArtStyle.OIL_PAINTING:            lambda: self.art_model.apply_style(ArtStyle.OIL_PAINTING),
            ArtStyle.OIL_IMPRESSIONISM:       lambda: self.art_model.apply_style(ArtStyle.OIL_IMPRESSIONISM),
            ArtStyle.OIL_POST_IMPRESSIONISM:  lambda: self.art_model.apply_style(ArtStyle.OIL_POST_IMPRESSIONISM),
            ArtStyle.OIL_EXPRESSIONISM:       lambda: self.art_model.apply_style(ArtStyle.OIL_EXPRESSIONISM),
            ArtStyle.OIL_PALETTE_KNIFE:       lambda: self.art_model.apply_style(ArtStyle.OIL_PALETTE_KNIFE),
            ArtStyle.SKETCH:                  lambda: self.art_model.apply_style(ArtStyle.SKETCH),
            ArtStyle.SKETCH_PENCIL:           lambda: self.art_model.apply_style(ArtStyle.SKETCH_PENCIL),
            ArtStyle.SKETCH_CONTOUR:          lambda: self.art_model.apply_style(ArtStyle.SKETCH_CONTOUR),
            ArtStyle.SKETCH_INK:              lambda: self.art_model.apply_style(ArtStyle.SKETCH_INK),
            ArtStyle.WATERCOLOR:              lambda: self.art_model.apply_style(ArtStyle.WATERCOLOR),
            ArtStyle.INK_WASH:                lambda: self.art_model.apply_style(ArtStyle.INK_WASH),
            ArtStyle.CARTOON:                 lambda: self.art_model.apply_style(ArtStyle.CARTOON),
            ArtStyle.COMIC_HALFTONE:          lambda: self.art_model.apply_style(ArtStyle.COMIC_HALFTONE),
            ArtStyle.POSTERIZE:               lambda: self.art_model.apply_style(ArtStyle.POSTERIZE),
            ArtStyle.SEPIA:                   lambda: self.art_model.apply_style(ArtStyle.SEPIA),
            ArtStyle.VINTAGE:                 lambda: self.art_model.apply_style(ArtStyle.VINTAGE),
            ArtStyle.NEGATIVE:                lambda: self.art_model.apply_style(ArtStyle.NEGATIVE),
            ArtStyle.EMBOSS:                  lambda: self.art_model.apply_style(ArtStyle.EMBOSS),
            ArtStyle.GLASS:                   lambda: self.art_model.apply_style(ArtStyle.GLASS),
            ArtStyle.EDGE_DETECT:             lambda: self.art_model.apply_style(ArtStyle.EDGE_DETECT),
            ArtStyle.BLUR_DREAM:              lambda: self.art_model.apply_style(ArtStyle.BLUR_DREAM),
        }

        # 后台线程 → 主线程 消息队列
        self.message_queue: queue.Queue = queue.Queue()

    # ==================================================================
    # 图片加载（同时供给画风模式和拼图模式）
    # ==================================================================
    def load_image_command(self, file_path: str) -> Tuple[bool, str]:
        """加载图片到 art_model 和 puzzle_model"""
        ok1 = self.art_model.load_image(file_path)
        ok2 = self.puzzle_model.load_image(file_path)
        if ok1 and ok2:
            msg = f"图片加载成功: {os.path.basename(file_path)}"
        else:
            msg = "图片加载失败"
        return ok1, msg

    def reload_original_image(self) -> Tuple[bool, str]:
        """重新加载原图（用于「重置为原图」按钮）"""
        if not self.art_model.file_path:
            return False, "没有已加载的图片"
        return self.load_image_command(self.art_model.file_path)

    # ==================================================================
    # 画风转换命令
    # ==================================================================
    def apply_style_command(self, style: ArtStyle) -> None:
        """异步应用风格（后台线程执行）"""
        if self.art_model.original_image is None:
            return

        def task() -> None:
            self._style_commands[style]()
            self.message_queue.put(("style_applied", style))

        thread = threading.Thread(target=task, daemon=True)
        thread.start()

    def save_art_image(self, path: str) -> bool:
        return self.art_model.save_image(path)

    def save_image_command(self) -> Tuple[bool, str]:
        """获取保存图片的默认文件名建议"""
        if self.art_model.processed_image is None or self.art_model.file_path is None:
            return False, "没有可保存的图片"
        default_name = (
            f"styled_{self.art_model.current_style.value}_"
            f"{os.path.basename(self.art_model.file_path)}"
        )
        return True, default_name

    # ==================================================================
    # 拼图游戏命令
    # ==================================================================
    def create_puzzle_command(self, rows: int, cols: int) -> Tuple[bool, str]:
        """
        用 art_model.processed_image（画风处理后的图）制作拼图。
        如果 processed_image 为 None，则使用 original_image。
        """
        src_img = self.art_model.processed_image or self.art_model.original_image
        if src_img is None:
            return False, "请先加载一张图片"

        # 把当前效果图写入 puzzle_model，再切分
        self.puzzle_model.original_image = src_img.copy()
        ok = self.puzzle_model.create_puzzle(rows, cols)
        if ok:
            return True, f"拼图已生成: {rows} x {cols}"
        return False, "制作拼图失败（行列数必须 ≥ 2）"

    def shuffle_puzzle_command(self) -> Tuple[bool, str]:
        if not self.puzzle_model.tiles:
            return False, "请先制作拼图"
        self.puzzle_model.shuffle_tiles()
        return True, "拼图已打乱，开始游戏！"

    def move_tile_command(self, tile_id: int, target_row: int, target_col: int) -> Tuple[bool, str]:
        ok = self.puzzle_model.move_tile(tile_id, target_row, target_col)
        if not ok:
            return False, "移动失败"
        if self.puzzle_model.completed:
            return True, "拼图完成！恭喜！"
        completed = self.puzzle_model.get_completed_count()
        total = self.puzzle_model.get_total_tiles()
        return True, f"已归位: {completed}/{total}"

    def swap_tiles_command(self, tile_id_a: int, tile_id_b: int) -> Tuple[bool, str]:
        ok = self.puzzle_model.swap_tiles(tile_id_a, tile_id_b)
        if not ok:
            return False, "交换失败"
        if self.puzzle_model.completed:
            return True, "拼图完成！恭喜！"
        return True, "交换成功"

    def reset_puzzle_command(self) -> Tuple[bool, str]:
        """重置拼图到正确位置"""
        if not self.puzzle_model.tiles:
            return False, "没有可重置的拼图"
        for tile in self.puzzle_model.tiles:
            tile.row = tile.id // self.puzzle_model.cols
            tile.col = tile.id % self.puzzle_model.cols
        self.puzzle_model.completed = True
        return True, "拼图已重置为完成状态"

    # ==================================================================
    # 查询（供 View 读取状态）
    # ==================================================================
    def has_image(self) -> bool:
        return self.art_model.original_image is not None

    def get_current_image_for_display(self) -> Optional["Image.Image"]:
        """返回当前应显示的 PIL 图像（画风预览用）"""
        return self.art_model.processed_image or self.art_model.original_image

    def get_current_style(self) -> ArtStyle:
        return self.art_model.current_style

    def get_image_info(self) -> str:
        img = self.get_current_image_for_display()
        if img and self.art_model.file_path:
            return (
                f"文件: {os.path.basename(self.art_model.file_path)}"
                f" | 风格: {self.art_model.current_style.value}"
                f" | 尺寸: {img.width} x {img.height}"
            )
        return "未加载图片"

    # ------------------------------------------------------------------
    # 拼图状态查询
    # ------------------------------------------------------------------
    def get_puzzle_tiles(self) -> List[Tile]:
        return self.puzzle_model.tiles

    def get_puzzle_grid_size(self) -> Tuple[int, int]:
        return self.puzzle_model.rows, self.puzzle_model.cols

    def get_puzzle_tile_pixel_size(self) -> Tuple[int, int]:
        return self.puzzle_model.tile_width, self.puzzle_model.tile_height

    def is_puzzle_completed(self) -> bool:
        return self.puzzle_model.is_completed()

    def get_puzzle_completed_count(self) -> Tuple[int, int]:
        return self.puzzle_model.get_completed_count(), self.puzzle_model.get_total_tiles()

    def get_puzzle_file_path(self) -> Optional[str]:
        return self.puzzle_model.file_path
