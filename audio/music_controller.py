"""Music Controller for KARD — 自适应音乐系统。

实现音频工程师规范中的自适应音乐架构：
- 参数驱动的音乐过渡
- 节拍同步切换
- 参数平滑插值
- 支持横向重排序（stem-based）和纵向分层

音乐系统不直接播放音频，而是通过 FMOD/Wwise 风格的参数
控制中间件中的音乐事件。
"""

import sys
import os

# 获取项目根目录
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
MUSIC_DIR = os.path.join(_PROJECT_ROOT, "assets", "audio", "music")


class MusicController:
    """自适应音乐控制器 —— 管理所有音乐状态和参数。

    设计原则（音频工程师规范）：
    1. 音乐过渡必须节拍同步
    2. 所有过渡由参数驱动（CombatIntensity, PlayerHealth, GamePhase）
    3. 优先使用 stem-based 横向重排序（内存效率）
    4. 仅在需要时才使用纵向分层
    """

    def __init__(self, music_dir: str = MUSIC_DIR) -> None:
        self.music_dir: str = music_dir

        # ── 音乐状态（与 MusicStateComponent 同步）────────────
        self.current_track: str = "menu"
        self.target_track: str = "menu"
        self.is_transitioning: bool = False
        self.transition_progress: float = 0.0
        self.transition_duration: float = 2.0  # 秒

        # ── 自适应参数 ─────────────────────────────────────
        self.combat_intensity: float = 0.0
        self.target_combat_intensity: float = 0.0

        self.player_health: float = 1.0
        self.target_player_health: float = 1.0

        self.game_phase: str = "MENU"
        self.target_game_phase: str = "MENU"

        # ── 节拍同步 ─────────────────────────────────────
        self.current_beat: int = 0
        self.beat_duration: float = 0.5  # 120 BPM = 0.5s/beat
        self.beat_timer: float = 0.0
        self.tempo: float = 120.0  # BPM
        self.is_beat_sync_enabled: bool = True

        # ── 低通滤波器（玩家低血量时）─────────────────
        self.lowpass_cutoff: float = 22050.0
        self.lowpass_target: float = 22050.0

        # ── pygame.mixer.music 状态 ────────────────────
        self._current_music_file: str = ""
        self._next_music_file: str = ""
        self._is_fading: bool = False
        self._fade_start_time: float = 0.0
        self._fade_duration: float = 0.0

        # ── 音乐片段定义（stem-based）────────────────────
        # 使用横向重排序：不同强度播放不同 stem 组合
        self.stem_tracks: dict[str, dict] = {
            "menu": {
                "file": os.path.join(self.music_dir, "menu.ogg"),
                "stems": [],  # 单轨，无 stem
                "loop": True,
            },
            "exploration": {
                "file": os.path.join(self.music_dir, "exploration.ogg"),
                "stems": ["melody", "pad"],  # 探索时只有旋律+铺底
                "loop": True,
            },
            "battle_low": {
                "file": os.path.join(self.music_dir, "battle_low.ogg"),
                "stems": ["melody", "pad", "percussion"],  # +打击乐
                "loop": True,
            },
            "battle_high": {
                "file": os.path.join(self.music_dir, "battle_high.ogg"),
                "stems": ["melody", "pad", "percussion", "bass", "fx"],  # 全编制
                "loop": True,
            },
            "boss": {
                "file": os.path.join(self.music_dir, "boss.ogg"),
                "stems": ["melody", "pad", "percussion", "bass", "fx", "choir"],
                "loop": True,
            },
            "event": {
                "file": os.path.join(self.music_dir, "event.ogg"),
                "stems": ["pad", "melody"],
                "loop": True,
            },
            "merchant": {
                "file": os.path.join(self.music_dir, "merchant.ogg"),
                "stems": ["melody", "pad"],
                "loop": True,
            },
            "campfire": {
                "file": os.path.join(self.music_dir, "campfire.ogg"),
                "stems": ["melody", "pad"],
                "loop": True,
            },
            "game_over": {
                "file": os.path.join(self.music_dir, "game_over.ogg"),
                "stems": [],
                "loop": False,
            },
        }

        # ── 参数 → 音轨映射 ────────────────────────────
        # CombatIntensity 映射到不同战斗强度音轨
        self._intensity_to_track: list[tuple[float, str]] = [
            (0.0, "exploration"),   # 0.0 → 探索
            (0.3, "battle_low"),    # 0.3 → 低强度战斗
            (0.6, "battle_high"),  # 0.6 → 高强度战斗
            (1.0, "boss"),            # 1.0 → 首领战
        ]

    # ── 公共 API ─────────────────────────────────────

    def set_combat_intensity(self, value: float) -> None:
        """设置目标战斗强度（0.0 - 1.0）。"""
        self.target_combat_intensity = max(0.0, min(1.0, value))
        self._update_track_from_intensity()

    def set_player_health(self, value: float) -> None:
        """设置目标玩家生命值（0.0 - 1.0）。"""
        self.target_player_health = max(0.0, min(1.0, value))

    def set_game_phase(self, phase: str) -> None:
        """设置游戏阶段（立即切换或节拍同步）。"""
        self.target_game_phase = phase
        self._update_track_from_phase()

    def update(self, dt: float) -> None:
        """每帧调用，更新所有平滑插值和音乐状态。"""
        # 1. 战斗强度插值
        diff = self.target_combat_intensity - self.combat_intensity
        if abs(diff) > 0.001:
            lerp_speed = 2.0 * dt
            self.combat_intensity += diff * min(1.0, lerp_speed)
            self._update_track_from_intensity()

        # 2. 生命值插值
        diff = self.target_player_health - self.player_health
        if abs(diff) > 0.001:
            lerp_speed = 1.0 * dt
            self.player_health += diff * min(1.0, lerp_speed)

        # 3. 低通滤波器（生命 < 0.2 时激活）
        if self.player_health < 0.2:
            self.lowpass_target = 800.0  # Hz，音频工程师规范
        else:
            self.lowpass_target = 22050.0

        # 4. 节拍计时
        if self.is_beat_sync_enabled:
            self.beat_timer += dt
            if self.beat_timer >= self.beat_duration:
                self.beat_timer -= self.beat_duration
                self.current_beat += 1

        # 5. 处理过渡淡入淡出
        if self._is_fading:
            elapsed = self._fade_start_time
            elapsed += dt
            self._fade_start_time = elapsed
            progress = min(1.0, elapsed / self._fade_duration)
            self.transition_progress = progress
            if progress >= 1.0:
                self._is_fading = False
                self.current_track = self.target_track
                self.is_transitioning = False

    def is_on_beat(self) -> bool:
        """返回当前是否在节拍边界上（用于节拍同步过渡）。"""
        if not self.is_beat_sync_enabled:
            return True
        return self.beat_timer < 0.05  # 50ms 窗口

    def get_beat_phase(self) -> float:
        """返回当前节拍相位（0.0 = 节拍起点，1.0 = 下一节拍起点）。"""
        return self.beat_timer / max(0.001, self.beat_duration)

    def get_current_track_file(self) -> str:
        """返回当前音轨的文件路径。"""
        track_info = self.stem_tracks.get(self.current_track)
        if track_info:
            return track_info["file"]
        return ""

    def get_target_track_file(self) -> str:
        """返回目标音轨的文件路径。"""
        track_info = self.stem_tracks.get(self.target_track)
        if track_info:
            return track_info["file"]
        return ""

    def should_transition_now(self) -> bool:
        """返回是否应该立即执行过渡（节拍同步）。"""
        if not self.is_beat_sync_enabled:
            return True
        return self.is_on_beat()

    def start_transition(self, duration: float = 2.0) -> None:
        """开始音乐过渡淡入淡出。"""
        self.is_transitioning = True
        self.transition_progress = 0.0
        self._is_fading = True
        self._fade_start_time = 0.0
        self._fade_duration = duration

    def get_music_parameters(self) -> dict[str, float]:
        """返回当前所有音乐参数（用于传递给 FMOD/Wwise）。"""
        return {
            "CombatIntensity": self.combat_intensity,
            "PlayerHealth": self.player_health,
            "LowpassCutoff": self.lowpass_cutoff,
            "BeatPhase": self.get_beat_phase(),
            "CurrentBeat": float(self.current_beat),
        }

    def get_lowpass_cutoff(self) -> float:
        """返回当前低通滤波器截止频率。"""
        # 平滑插值
        diff = self.lowpass_target - self.lowpass_cutoff
        if abs(diff) > 1.0:
            self.lowpass_cutoff += diff * 0.1  # 每帧 10% 靠近目标
        return self.lowpass_cutoff

    def set_tempo(self, bpm: float) -> None:
        """设置音乐速度（BPM）。"""
        self.tempo = max(60.0, min(200.0, bpm))
        self.beat_duration = 60.0 / self.tempo

    # ── 内部方法 ─────────────────────────────────────

    def _update_track_from_intensity(self) -> None:
        """根据 combat_intensity 自动选择目标音轨。"""
        target = "exploration"
        for threshold, track_name in self._intensity_to_track:
            if self.combat_intensity >= threshold:
                target = track_name
        if target != self.target_track:
            self.target_track = target
            if self.should_transition_now():
                self.start_transition()

    def _update_track_from_phase(self) -> None:
        """根据 game_phase 切换到对应音轨。"""
        phase_to_track = {
            "MENU": "menu",
            "BATTLE": self.target_track,  # 由 intensity 决定
            "EVENT": "event",
            "MERCHANT": "merchant",
            "CAMPFIRE": "campfire",
            "GAME_OVER": "game_over",
        }
        track = phase_to_track.get(self.target_game_phase, "menu")
        if track != self.target_track and track != self.current_track:
            self.target_track = track
            if self.should_transition_now():
                self.start_transition()

    def get_stem_info(self, track_name: str | None = None) -> dict:
        """返回指定音轨的 stem 信息。"""
        if track_name is None:
            track_name = self.current_track
        return self.stem_tracks.get(track_name, {})

    def validate_files(self) -> dict[str, str]:
        """验证所有音乐文件是否存在，返回缺失文件列表。"""
        missing = {}
        for name, info in self.stem_tracks.items():
            fp = info.get("file", "")
            if fp and not os.path.isfile(fp):
                missing[name] = fp
        return missing
