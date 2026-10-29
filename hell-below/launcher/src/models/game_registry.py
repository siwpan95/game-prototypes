"""Game registry - metadata for all 11 games in the Hell Below platform."""

from __future__ import annotations

from src.core.constants import GAMES_BASE_ZH


class GameInfo:
    """Metadata for a single game."""

    def __init__(
        self,
        game_id: str,
        volume: int,
        title_zh: str,
        title_en: str,
        genre_zh: str,
        genre_en: str,
        dir_name_zh: str,
        dir_name_en: str = "",
        main_path: str = "main.py",
    ) -> None:
        self.game_id = game_id
        self.volume = volume
        self.title_zh = title_zh
        self.title_en = title_en
        self.genre_zh = genre_zh
        self.genre_en = genre_en
        self.dir_name_zh = dir_name_zh
        self.dir_name_en = dir_name_en or dir_name_zh  # fallback to zh dir
        self.main_path = main_path

    @property
    def game_dir_zh(self):
        """Absolute path to the Chinese game directory."""
        return GAMES_BASE_ZH / self.dir_name_zh

    @property
    def main_file_zh(self):
        """Absolute path to the game's main.py (Chinese version)."""
        return self.game_dir_zh / self.main_path

    def exists_zh(self) -> bool:
        """Check if the Chinese version's main entry file exists."""
        return self.main_file_zh.exists()

    def title(self, lang: str = "zh") -> str:
        """Get title in specified language."""
        return self.title_zh

    def genre(self, lang: str = "zh") -> str:
        """Get genre in specified language."""
        return self.genre_zh


# ── All 11 games ──────────────────────────────────────────────────────
GAMES: list[GameInfo] = [
    GameInfo(
        game_id="v01", volume=1,
        title_zh="内森·温特斯", title_en="Nathan Winters",
        genre_zh="地底探索", genre_en="Descent",
        dir_name_zh="NathanWinters_CN", dir_name_en="NathanWinters_en",
    ),
    GameInfo(
        game_id="v02", volume=2,
        title_zh="布莱恩·辛普森", title_en="Brian Simpson",
        genre_zh="文字冒险", genre_en="Text Adventure",
        dir_name_zh="BrianSimpson_CN", dir_name_en="BrianSimpson_en",
    ),
    GameInfo(
        game_id="v03", volume=3,
        title_zh="斯托克顿·亚当斯", title_en="Stockton Adams",
        genre_zh="卡牌叙事", genre_en="Card Narrative",
        dir_name_zh="stockton_adams_zh", dir_name_en="stockton_adams_en",
    ),
    GameInfo(
        game_id="v04", volume=4,
        title_zh="艾伦·艾布特", title_en="Allen Abbott",
        genre_zh="文字解密", genre_en="Text Decrypt",
        dir_name_zh="AlenAbot_zh", dir_name_en="AlenAbot_en",
    ),
    GameInfo(
        game_id="v05", volume=5,
        title_zh="盘尼西林·帕金森", title_en="Penicillin Parkinson",
        genre_zh="Roguelike卡牌", genre_en="Roguelike Card",
        dir_name_zh="PenicilinParkinson_zh", dir_name_en="PenicilinParkinson_en",
    ),
    GameInfo(
        game_id="v06", volume=6,
        title_zh="安娜·斯克兰顿", title_en="Anna Scranton",
        genre_zh="文字解密", genre_en="Text Decrypt",
        dir_name_zh="AnaScranton_zh", dir_name_en="AnaScranton_en",
    ),
    GameInfo(
        game_id="v07", volume=7,
        title_zh="孛儿只斤·察合台", title_en="Borjigin Chagatai",
        genre_zh="卡牌对战", genre_en="Card Battle",
        dir_name_zh="BorjiginChagatai_zh", dir_name_en="BorjiginChagatai_en",
    ),
    GameInfo(
        game_id="v09", volume=9,
        title_zh="刘敬宣", title_en="Liu Jingxuan",
        genre_zh="Roguelike卡牌", genre_en="Roguelike Card",
        dir_name_zh="jx_liu_game_zh", dir_name_en="jx_liu_game_en",
    ),
    GameInfo(
        game_id="v10", volume=10,
        title_zh="远坂凛世", title_en="Rinyo Tohsaka",
        genre_zh="战国暗幻", genre_en="Sengoku Dark Fantasy",
        dir_name_zh="RinyoTohsaka_zh", dir_name_en="RinyoTohsaka_en",
    ),
    GameInfo(
        game_id="v11", volume=11,
        title_zh="墟境", title_en="Ruined Realm",
        genre_zh="冥界冒险", genre_en="Underworld Adventure",
        dir_name_zh="RuinedRealm_zh", dir_name_en="RuinedRealm_en",
    ),
    GameInfo(
        game_id="v12", volume=12,
        title_zh="拉姆齐-贝潘", title_en="Georges Ramsay Bepan",
        genre_zh="文字解密", genre_en="Text Decrypt",
        dir_name_zh="GeorgesRamsayBepan_zh", dir_name_en="GeorgesRamsayBepan_en",
    ),
]


def get_game_by_id(game_id: str) -> GameInfo | None:
    """Find a game by its ID."""
    for game in GAMES:
        if game.game_id == game_id:
            return game
    return None


def get_available_games(lang: str = "zh") -> list[GameInfo]:
    """Return only games whose main.py exists on disk."""
    return [g for g in GAMES if g.exists_zh()]
