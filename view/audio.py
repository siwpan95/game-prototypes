"""音频管理器（T4.2）：BGM 播放，无可用播放后端时静默降级

依赖链：pygame（可选）→ 无则静默。BGM 文件位于 assets/music/<name>.mp3，
缺失时跳过不报错（资源可用 scripts/fetch_music.py 一键拉取，CC0）。

挂点：view 层在状态切换时调用 play()；M 键静音切换。
"""
import os


class AudioManager:
    """背景音乐管理器（pygame 后端，静默降级）"""

    def __init__(self, assets_dir: str = None):
        if assets_dir is None:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            assets_dir = os.path.join(root, "assets", "music")
        self._dir = assets_dir
        self._pygame = None
        self._muted = False
        self._current = None
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._pygame = pygame
        except Exception:
            self._pygame = None  # 无 pygame / 无音频设备：静默

    @property
    def available(self) -> bool:
        return self._pygame is not None

    def play(self, name: str, loops: int = -1):
        """循环播放 assets/music/<name>.mp3；同名不重播"""
        if self._pygame is None or self._muted:
            return
        if self._current == name:
            return
        path = os.path.join(self._dir, name + ".mp3")
        if not os.path.exists(path):
            return
        try:
            self._pygame.mixer.music.load(path)
            self._pygame.mixer.music.play(loops=loops)
            self._current = name
        except Exception:
            self._current = None

    def stop(self):
        if self._pygame is None:
            return
        try:
            self._pygame.mixer.music.stop()
            self._current = None
        except Exception:
            pass

    def toggle_mute(self) -> bool:
        """静音切换，返回切换后是否静音"""
        self._muted = not self._muted
        if self._muted:
            self.stop()
        return self._muted

    def state_to_bgm(self, state) -> str:
        """游戏状态 → BGM 名（View 挂点用）；遗迹/神殿类地图由调用方覆盖"""
        from model import GameState
        return {
            GameState.WORLD: "wild", GameState.TOWN: "town",
            GameState.BATTLE: "battle", GameState.SHOP: "town",
            GameState.BOUNTY: "town", GameState.GARAGE: "town",
            GameState.INVENTORY: "battle", GameState.DIALOG: "town",
        }.get(state, "dungeon")
