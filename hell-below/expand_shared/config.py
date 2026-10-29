"""expand_shared 配置模板 — 每个游戏通过覆写来定制。"""

from __future__ import annotations
import os


class ExpanderConfig:
    """扩充工具配置。"""

    def __init__(self, data_dir: str = "", game_name: str = ""):
        # 数据目录（指向游戏的 assets/data/）
        self.data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "assets", "data"
        )
        self.game_name = game_name

        # 备份设置
        self.backup_enabled: bool = True
        self.max_backups: int = 20  # 保留最近 N 个备份

        # 术语映射（用于翻译项目）
        self.terminology: dict[str, str] = {}
        # 示例：{"暗纹": "Dark Vein", "清晰度": "Sanity", "浑浊度": "Corruption"}

        # 要处理的文件列表
        self.target_files: list[str] = [
            "rooms.json", "items.json", "characters.json",
            "dialogs.json", "narratives.json", "puzzles.json",
            "story.json",
        ]

    def get_path(self, filename: str) -> str:
        return os.path.join(self.data_dir, filename)

    def file_exists(self, filename: str) -> bool:
        return os.path.exists(self.get_path(filename))
