"""
音频系统 — BGM 循环 + SFX 单次播放
==================================
纯键盘驱动的文字冒险游戏，无鼠标音效。
根据理智值自动切换背景音乐。
"""
import random
import pygame
from core.ecs import System
from components.sanity import Sanity
from core.paths import ROOT
AUDIO_DIR = ROOT / "assets" / "audio"
SFX_DIR = AUDIO_DIR / "sfx"
MUSIC_DIR = AUDIO_DIR / "music"


class AudioSystem(System):
    """游戏音频系统：BGM + SFX，根据理智值动态切换氛围。
    master_bgm / master_sfx 为 0.0-1.0 的全局音量乘数，
    play_sfx / play_bgm 内部会乘以对应乘数。"""

    SANITY_LOW_RATIO = 0.30

    def __init__(self, event_bus):
        self.bus = event_bus
        self.current_bgm = None
        self._sanity_low_active = False
        self._memory_bgm_timer = 0
        self._prev_bgm = None

        # ── 全局音量乘数 ──
        self.master_bgm = 1.0   # 0.0 ~ 1.0
        self.master_sfx = 1.0   # 0.0 ~ 1.0

        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(22050, -16, 2, 512)
            except Exception as _e:
                import sys
                print(f"[AudioSystem] pygame.mixer 初始化失败，音频已禁用：{_e}", file=sys.stderr)
                pass

        self.sfx = {}
        self._load_sfx()
        self.music = {}
        self._load_music()

        self.bus.subscribe("PLAYER_MOVE", self._on_player_move)
        self.bus.subscribe("MEMORY_TRIGGERED", self._on_memory_triggered)
        self.bus.subscribe("CARD_COLLECTED", self._on_card_collected)
        self.bus.subscribe("SANITY_RECOVER", self._on_sanity_recover)
        self.bus.subscribe("GAME_OVER", self._on_game_over)
        self.bus.subscribe("GAME_WIN", self._on_game_win)
        self.bus.subscribe("MECHANISM_TRIGGERED", self._on_mechanism)

        self.play_bgm("mansion_explore")

    def _load_sfx(self):
        if not SFX_DIR.exists():
            return
        for wav in SFX_DIR.rglob("*.wav"):
            key = str(wav.relative_to(SFX_DIR).with_suffix(""))
            try:
                self.sfx[key] = pygame.mixer.Sound(str(wav))
            except Exception as _e:
                import sys
                print(f"[AudioSystem] SFX 加载失败 {wav}：{_e}", file=sys.stderr)

    def _load_music(self):
        if not MUSIC_DIR.exists():
            return
        for wav in MUSIC_DIR.glob("*.wav"):
            self.music[wav.stem] = str(wav)

    def play_sfx(self, name, volume=0.7):
        snd = self.sfx.get(name)
        if snd:
            snd.set_volume(volume * self.master_sfx)
            snd.play()

    def play_bgm(self, name, volume=0.5, loops=-1):
        path = self.music.get(name)
        if not path:
            return
        try:
            if self.current_bgm and pygame.mixer.music.get_busy():
                pygame.mixer.music.fadeout(1000)
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(volume * self.master_bgm)
            pygame.mixer.music.play(loops, fade_ms=2000)
            self.current_bgm = name
        except Exception as _e:
            import sys
            print(f"[AudioSystem] BGM 播放失败 {name}：{_e}", file=sys.stderr)
            pass

    def stop_bgm(self, fade_ms=1000):
        try:
            pygame.mixer.music.fadeout(fade_ms)
        except Exception as _e:
            import sys
            print(f"[AudioSystem] BGM 停止失败：{_e}", file=sys.stderr)
            pass
        self.current_bgm = None

    # ── 全局音量控制（设置面板调用） ──

    def set_bgm_volume(self, v):
        """设置 BGM 全局音量乘数 (0.0-1.0)，立即生效于当前播放。"""
        self.master_bgm = round(max(0.0, min(1.0, v)), 2)
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.set_volume(self.master_bgm)

    def set_sfx_volume(self, v):
        """设置 SFX 全局音量乘数 (0.0-1.0)，下次 play_sfx 生效。"""
        self.master_sfx = round(max(0.0, min(1.0, v)), 2)

    def update(self, world, dt):
        # 记忆 BGM 倒计时
        if self._memory_bgm_timer > 0:
            self._memory_bgm_timer -= dt
            if self._memory_bgm_timer <= 0:
                # 恢复之前的 BGM
                restore = self._prev_bgm or "mansion_explore"
                self.play_bgm(restore)
                self._prev_bgm = None

        # 理智低沉 BGM 切换
        player = world.entities.get("player")
        if player:
            s = player.get(Sanity)
            if s:
                ratio = s.value / s.max_value
                if ratio < self.SANITY_LOW_RATIO and not self._sanity_low_active:
                    self._sanity_low_active = True
                    self.play_sfx("sanity/sanity_low")
                    self.play_bgm("sanity_drain", volume=0.4)
                elif ratio >= self.SANITY_LOW_RATIO and self._sanity_low_active:
                    self._sanity_low_active = False
                    self.play_bgm("mansion_explore")

    # ── 事件处理 ──

    def _on_player_move(self, data):
        """玩家移动 → 脚步声（随机音量）。"""
        vol = random.uniform(0.3, 0.5)
        self.play_sfx("explore/step", volume=vol)

    def _on_memory_triggered(self, data):
        """记忆触发 → 记忆音效 + 暂时切换 BGM。"""
        self.play_sfx("memory/memory_touch")
        self.play_sfx("memory/sanity_cost", volume=0.4)
        # 保存当前 BGM，4 秒后恢复
        if self.current_bgm != "memory_ambience":
            self._prev_bgm = self.current_bgm
            self.play_bgm("memory_ambience", volume=0.35)
            self._memory_bgm_timer = 4000  # ms

    def _on_card_collected(self, data):
        """卡牌收集音效。"""
        self.play_sfx("card/card_collect")

    def _on_sanity_recover(self, data):
        """理智恢复音效。"""
        self.play_sfx("sanity/sanity_recover")

    def _on_game_over(self, data):
        """游戏结束 → 停止 BGM，播放绝望音效。"""
        self.stop_bgm()
        self.play_sfx("sanity/sanity_zero")
        self.play_bgm("game_over", volume=0.6, loops=0)

    def _on_game_win(self, data):
        """游戏胜利 → 停止 BGM，播放胜利音效。"""
        self.stop_bgm()
        self.play_sfx("card/card_all")
        self.play_bgm("victory", volume=0.6, loops=0)

    def _on_mechanism(self, data):
        """机关触发音效。"""
        self.play_sfx("mechanism/mech_trigger")
