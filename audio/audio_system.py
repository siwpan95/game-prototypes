"""Audio System for KARD ECS — 核心音频系统。

这是游戏音频工程师设计的核心系统：
- 消费 AudioEventComponent 中的音频事件队列
- 管理 pygame.mixer 的播放
- 根据优先级和语音预算调度音效
- 驱动 MusicController 的更新
- 实现遮挡/空间音频逻辑

遵循音频工程师规范：
- 所有音效通过中间件事件系统（AudioEventComponent）
- 明确的语音预算和抢占策略
- 3D 空间音频支持
- 参数驱动的自适应音乐
"""

import sys
import os
import pygame
import heapq
from typing import Optional
from ecs import System, World
from components import (
    HealthComponent, EnergyComponent,
    CardComponent, EnemyComponent, MinionComponent,
    PlayerComponent, PositionComponent, RenderComponent,
)
from .audio_components import (
    AudioEventComponent, MusicStateComponent, AudioListenerComponent,
    SpatialAudioComponent,
)
from .music_controller import MusicController
from .sfx_bank import SFXBank
from .audio_constants import (
    AudioEventType, DEFAULT_VOLUMES,
    SFX_ROOT, MUSIC_ROOT,
    PYGAME_MIXER_CONFIG,
    get_current_voice_count, get_current_virtual_voices,
)
from game_state import GameState, Phase


class AudioSystem(System):
    """ECS System —— 每帧处理音频事件和音乐更新。

    位置：在系统列表中最后执行（渲染之后），
    这样音频事件可以在一帧中所有游戏逻辑完成后统一处理。
    """

    def __init__(self, game_state: GameState, sfx_root: str = SFX_ROOT, music_root: str = MUSIC_ROOT) -> None:
        # ── 状态 ─────────────────────────────────────────
        self.gs = game_state
        self.sfx_bank = SFXBank(sfx_root)
        self.music_controller = MusicController(music_root)

        # ── pygame.mixer 初始化状态 ────────────────────
        self._mixer_initialized: bool = False
        self._current_music_file: str = ""
        self._music_paused: bool = False

        # ── 语音调度 ────────────────────────────────────
        # 最大语音数（根据平台）
        self.max_voices = get_current_voice_count()
        self.max_virtual = get_current_virtual_voices()

        # 当前活跃的语音：[(-priority, start_time, channel_idx), ...]
        # 使用堆维护，优先级数值越小越优先
        self._active_voices: list[tuple[int, float, int]] = []
        self._channel_last_play: dict[int, float] = {}  # channel_idx → last play time

        # pygame.mixer 频道分配
        self._channels: list[pygame.mixer.Channel] = []
        self._channel_busy: list[bool] = []

        # ── 音频监听器（玩家位置）────────────────────
        self.listener_x: float = 640.0
        self.listener_y: float = 360.0

        # ── 3D 空间音频 ─────────────────────────────
        self.occlusion_results: dict[int, bool] = {}  # entity_id → is_occluded
        self._occlusion_raycast_frame: int = 0
        self._max_raycasts_per_frame: int = 4  # 音频工程师规范

        # ── 音量 ───────────────────────────────────────
        self.volumes = dict(DEFAULT_VOLUMES)

        # ── 调试 ───────────────────────────────────────
        self.debug_audio: bool = False  # 设为 True 可打印音频事件

    # ── 初始化 ─────────────────────────────────────────

    def init_mixer(self) -> bool:
        """初始化 pygame.mixer（在 pygame.init() 之后调用）。"""
        if self._mixer_initialized:
            return True
        try:
            freq = PYGAME_MIXER_CONFIG["frequency"]
            size = PYGAME_MIXER_CONFIG["size"]
            channels = PYGAME_MIXER_CONFIG["channels"]
            buffer = PYGAME_MIXER_CONFIG["buffer"]
            allowed = PYGAME_MIXER_CONFIG["allowedchanges"]

            pygame.mixer.init(
                frequency=freq,
                size=size,
                channels=channels,
                buffer=buffer,
            )
            # 尝试设置允许的配置变更
            # pygame.mixer.get_init() 返回实际配置

            # 分配自定义频道（0 是保留给音乐的）
            self._init_channels()
            self._mixer_initialized = True
            return True
        except Exception as e:
            print(f"[AudioSystem] 初始化 mixer 失败: {e}")
            return False

    def _ensure_audio_entity(self, world: World) -> None:
        """确保世界中存在一个 AudioEventComponent 实体（懒初始化）。"""
        for _ in world.get_entities_with(AudioEventComponent):
            return  # 已存在
        entity = world.create_entity()
        world.add_component(entity, AudioEventComponent())
        if self.debug_audio:
            print("[AudioSystem] 创建了音频事件实体")

    def _init_channels(self) -> None:
        """初始化音频频道池。"""
        # pygame.mixer 默认有 8 个频道
        # 确保有足够的频道
        required = self.max_voices + 1  # +1 for music
        if pygame.mixer.get_num_channels() < required:
            pygame.mixer.set_num_channels(required)

        self._channels = []
        self._channel_busy = []
        for i in range(1, required):  # 0 留给音乐
            self._channels.append(pygame.mixer.Channel(i))
            self._channel_busy.append(False)

    # ── ECS System 更新 ─────────────────────────────────

    def update(self, world: World, dt: float, events: list | None = None) -> None:
        """每帧调用 —— 处理音频事件并更新音乐。

        执行顺序：
        1. 确保音频事件实体存在
        2. 更新音频监听器位置（玩家）
        3. 处理遮挡射线检测（分散到多帧）
        4. 消费所有实体的 AudioEventComponent 事件队列
        5. 更新 MusicController 参数
        6. 应用音乐参数到 pygame.mixer.music
        7. 清理已结束的语音
        """
        if not self._mixer_initialized:
            ok = self.init_mixer()
            if not ok:
                return

        # 0. 确保音频事件实体存在
        self._ensure_audio_entity(world)

        # 1. 更新监听器位置
        self._update_listener(world)

        # 2. 处理遮挡（多帧分散）
        self._update_occlusion(world, dt)

        # 3. 消费音频事件
        self._process_audio_events(world, dt)

        # 4. 更新音乐控制器
        self._update_music(world, dt)

        # 5. 清理已结束的语音
        self._cleanup_voices()

    # ── 音频事件处理 ─────────────────────────────────

    def _process_audio_events(self, world: World, dt: float) -> None:
        """遍历所有 AudioEventComponent，播放排队的音频事件。"""
        for entity in world.get_entities_with(AudioEventComponent):
            audio_comp = world.get_component(entity, AudioEventComponent)
            if not audio_comp or not audio_comp.events:
                continue

            for event_name, volume, pitch in audio_comp.events:
                self._play_sfx_event(
                    world, entity, event_name, volume, pitch,
                )

            # 清空队列（音频工程师规范：消费后清除）
            audio_comp.clear()

    def _play_sfx_event(
        self,
        world: World,
        entity,
        event_name: str,
        volume: float = 1.0,
        pitch: float = 1.0,
    ) -> None:
        """播放一个音效事件。"""
        # 查找音效定义
        sfx_def = self.sfx_bank.get(event_name)
        if not sfx_def:
            if self.debug_audio:
                print(f"[AudioSystem] 未找到音效定义: {event_name}")
            return

        # 获取文件路径
        file_path = sfx_def.get_random_file()
        if not file_path or not os.path.isfile(file_path):
            if self.debug_audio:
                print(f"[AudioSystem] 音效文件不存在: {file_path}")
            return

        # 计算最终音量（含随机化和 3D 衰减）
        final_volume = self._calculate_final_volume(
            world, entity, sfx_def, volume,
        )
        final_pitch = sfx_def.get_random_pitch() * pitch

        # 语音预算检查
        if not self._can_play_voice(sfx_def):
            if self.debug_audio:
                print(f"[AudioSystem] 语音预算已满，跳过: {event_name}")
            return

        # 播放音效
        try:
            sound = pygame.mixer.Sound(file_path)
            sound.set_volume(final_volume)

            # 音调：pygame 不支持直接设置 pitch，需要调整播放速度
            # 这里使用 Sound 的 set_volume 之外的技巧
            # 实际项目中应使用 FMOD/Wwise 或 pygame.mixer.Sound 的数组操作

            channel = self._get_free_channel(sfx_def)
            if channel is not None:
                channel.play(sound)
                self._mark_voice_active(sfx_def.priority, channel)
                if self.debug_audio:
                    print(f"[AudioSystem] 播放音效: {event_name} @ vol={final_volume:.2f}")
        except Exception as e:
            if self.debug_audio:
                print(f"[AudioSystem] 播放音效失败 {event_name}: {e}")

    def _calculate_final_volume(
        self,
        world: World,
        entity,
        sfx_def: "SFXDef",
        base_volume: float,
    ) -> float:
        """计算最终音量（含随机化、3D 衰减、遮挡）。"""
        # 1. 音效定义的基础音量 + 随机化
        vol = sfx_def.get_random_volume() * base_volume

        # 2. 全局音量缩放
        vol *= self.volumes.get("sfx", 0.8)
        vol *= self.volumes.get("master", 1.0)

        # 3. 3D 空间音频衰减
        if sfx_def.is_3d:
            spatial_comp = world.get_component(entity, SpatialAudioComponent)
            if spatial_comp:
                atten = spatial_comp.calculate_volume(self.listener_x, self.listener_y)
                vol *= atten

                # 4. 遮挡衰减
                entity_id = getattr(entity, "id", hash(str(entity)))
                if self.occlusion_results.get(entity_id, False):
                    vol *= 0.3  # 遮挡后音量降为 30%

        return max(0.0, min(1.0, vol))

    # ── 语音调度 ───────────────────────────────────────

    def _can_play_voice(self, sfx_def: "SFXDef") -> bool:
        """检查是否可以在预算内播放此音效。"""
        active_count = sum(1 for _ in self._active_voices)
        if active_count < self.max_voices:
            return True

        # 超出真实语音数：检查是否可以抢占最低优先级的语音
        if active_count < self.max_voices + self.max_virtual:
            # 检查是否有更低优先级的语音可以抢占
            if self._active_voices:
                lowest_priority, _, _ = self._active_voices[0]
                if lowest_priority > sfx_def.priority:
                    return True  # 可以抢占

        return False

    def _get_free_channel(self, sfx_def: "SFXDef") -> pygame.mixer.Channel | None:
        """获取一个空闲频道，必要时根据抢占策略回收。"""
        # 1. 尝试找空闲频道
        for i, busy in enumerate(self._channel_busy):
            if not busy:
                self._channel_busy[i] = True
                return self._channels[i]

        # 2. 没有空闲频道：根据抢占策略回收
        return self._steal_channel(sfx_def)

    def _steal_channel(self, sfx_def: "SFXDef") -> pygame.mixer.Channel | None:
        """根据抢占策略回收频道。"""
        steal_mode = sfx_def.steal_mode

        if steal_mode == "NEVER_STEAL":
            return None

        # 找到最合适的 victim 频道
        victim_idx = -1
        if steal_mode == "STEAL_QUIETEST":
            # 找音量最低的
            min_vol = float("inf")
            for i, ch in enumerate(self._channels):
                if ch.get_busy():
                    v = ch.get_sound().get_volume() if ch.get_sound() else 1.0
                    if v < min_vol:
                        min_vol = v
                        victim_idx = i
        elif steal_mode == "STEAL_FARTHEST":
            # 3D 音效：找距离最远的
            # 这里简化处理
            victim_idx = 0
        elif steal_mode == "STEAL_OLDEST":
            # 找最早播放的
            oldest_time = float("inf")
            for idx, (pri, t, ch_idx) in enumerate(self._active_voices):
                if t < oldest_time:
                    oldest_time = t
                    victim_idx = ch_idx

        if victim_idx >= 0 and victim_idx < len(self._channels):
            self._channels[victim_idx].stop()
            self._channel_busy[victim_idx] = False
            return self._channels[victim_idx]

        return None

    def _mark_voice_active(self, priority: int, channel: pygame.mixer.Channel) -> None:
        """标记一个语音为活跃。"""
        import time
        heapq.heappush(self._active_voices, (priority, time.time(), id(channel)))

    def _cleanup_voices(self) -> None:
        """清理已结束的语音。"""
        active_new = []
        for priority, t, ch_id in self._active_voices:
            # 找到对应的 channel 对象
            found = False
            for i, ch in enumerate(self._channels):
                if id(ch) == ch_id:
                    found = True
                    if not ch.get_busy():
                        self._channel_busy[i] = False
                    else:
                        active_new.append((priority, t, ch_id))
                    break
            if not found:
                pass  # channel 已被回收
        self._active_voices = active_new

    # ── 3D 空间音频 / 遮挡 ─────────────────────────

    def _update_listener(self, world: World) -> None:
        """更新音频监听器位置（跟随玩家）。"""
        # 简化：监听器始终在屏幕中心
        # 实际项目中可以从 PlayerComponent + PositionComponent 获取
        self.listener_x = 640.0  # SCREEN_WIDTH / 2
        self.listener_y = 360.0  # SCREEN_HEIGHT / 2

        # 如果有 AudioListenerComponent
        for e in world.get_entities_with(AudioListenerComponent):
            listener = world.get_component(e, AudioListenerComponent)
            if listener:
                self.listener_x = listener.x
                self.listener_y = listener.y
                break

    def _update_occlusion(self, world: World, dt: float) -> None:
        """更新遮挡状态（分散到多帧，每帧最多 4 次射线检测）。

        音频工程师规范：max 4 raycasts per frame，分散到多帧。
        """
        spatial_entities = list(world.get_entities_with(SpatialAudioComponent))
        if not spatial_entities:
            return

        # 每帧最多处理 N 个实体
        start_idx = self._occlusion_raycast_frame % max(1, len(spatial_entities))
        end_idx = min(start_idx + self._max_raycasts_per_frame, len(spatial_entities))

        for i in range(start_idx, end_idx):
            entity = spatial_entities[i]
            spatial = world.get_component(entity, SpatialAudioComponent)
            if not spatial:
                continue

            # 射线检测：listener → source
            is_occluded = self._raycast_occlusion(
                self.listener_x, self.listener_y,
                spatial.x, spatial.y,
            )

            entity_id = getattr(entity, "id", hash(str(entity)))
            self.occlusion_results[entity_id] = is_occluded

        self._occlusion_raycast_frame += self._max_raycasts_per_frame

    def _raycast_occlusion(self, lx: float, ly: float, sx: float, sy: float) -> bool:
        """简单的射线遮挡检测。

        在 KARD 这种 2D 卡牌游戏中，遮挡通常
        不是基于物理射线，而是基于：
        - 敌人是否在屏幕上方（被 UI 遮挡）
        - 是否有障碍物实体在中间

        这里返回一个简化结果（实际项目中应接入游戏的碰撞/遮挡系统）。
        """
        # 简化：卡牌游戏通常不需要复杂的 3D 遮挡
        # 返回 False（无遮挡）
        return False

    # ── 音乐更新 ───────────────────────────────────────

    def _update_music(self, world: World, dt: float) -> None:
        """更新音乐控制器并应用参数。"""
        mc = self.music_controller

        # 1. 从游戏状态同步参数
        self._sync_music_parameters(world, mc)

        # 2. 更新音乐控制器
        mc.update(dt)

        # 3. 应用音乐参数
        self._apply_music_parameters(mc)

        # 4. 处理音乐过渡
        self._handle_music_transition(mc)

    def _sync_music_parameters(self, world: World, mc: MusicController) -> None:
        """从游戏状态同步音乐参数到 MusicController。"""
        gs = self.gs

        # CombatIntensity
        intensity = 0.0
        if gs.phase == Phase.PLAYER_TURN or gs.phase == Phase.ENEMY_TURN:
            # 计算战斗强度
            enemy_count = len(list(world.get_entities_with(EnemyComponent, HealthComponent)))
            minion_count = len(list(world.get_entities_with(MinionComponent, HealthComponent)))
            total = enemy_count + minion_count
            intensity = min(1.0, total / 5.0)  # 5 个敌人 = 最大强度
            if gs.is_elite_room:
                intensity = max(intensity, 0.6)
        mc.set_combat_intensity(intensity)

        # PlayerHealth
        for e in world.entities:
            h = world.get_component(e, HealthComponent)
            p = world.get_component(e, PlayerComponent)
            if h and p:
                health_ratio = h.hp / max(1, h.max_hp)
                mc.set_player_health(health_ratio)
                break

        # GamePhase
        phase_map = {
            Phase.MENU: "MENU",
            Phase.SETTINGS: "MENU",
            Phase.PLAYER_TURN: "BATTLE",
            Phase.ENEMY_TURN: "BATTLE",
            Phase.ROOM_COMPLETE: "BATTLE",
            Phase.REWARD: "EVENT",  # 复用 event 音乐
            Phase.EVENT: "EVENT",
            Phase.MERCHANT: "MERCHANT",
            Phase.CAMPFIRE: "CAMPFIRE",
            Phase.GAME_OVER: "GAME_OVER",
        }
        game_phase = phase_map.get(gs.phase, "MENU")
        mc.set_game_phase(game_phase)

    def _apply_music_parameters(self, mc: MusicController) -> None:
        """将 MusicController 参数应用到 pygame.mixer.music。"""
        # 低通滤波器（玩家低血量时）
        # pygame.mixer.music 不直接支持 DSP，需要自定义
        # 这里仅打印参数（实际项目中应使用 FMOD/Wwise）
        if self.debug_audio:
            print(f"[Music] intensity={mc.combat_intensity:.2f}, "
                  f"health={mc.player_health:.2f}, "
                  f"lowpass={mc.lowpass_cutoff:.0f}Hz")

    def _handle_music_transition(self, mc: MusicController) -> None:
        """处理音乐过渡（淡入淡出）。"""
        target_file = mc.get_target_track_file()
        if not target_file:
            return

        if target_file != self._current_music_file:
            # 需要切换音乐
            if mc.is_on_beat() or not mc.is_beat_sync_enabled:
                self._fade_music(target_file, fade_ms=1000)
                self._current_music_file = target_file
                mc.current_track = mc.target_track

    def _fade_music(self, new_file: str, fade_ms: int = 1000) -> None:
        """淡入淡出切换到新音乐。"""
        if not os.path.isfile(new_file):
            if self.debug_audio:
                print(f"[AudioSystem] 音乐文件不存在: {new_file}")
            return

        try:
            pygame.mixer.music.fadeout(fade_ms)
            pygame.mixer.music.load(new_file)
            pygame.mixer.music.set_volume(self.volumes.get("music", 0.6))
            pygame.mixer.music.play(-1)  # 循环播放
        except Exception as e:
            if self.debug_audio:
                print(f"[AudioSystem] 切换音乐失败: {e}")

    # ── 公共 API（游戏逻辑调用）────────────────────

    def play_sfx(self, event_name: str, volume: float = 1.0, pitch: float = 1.0) -> None:
        """立即播放一个音效（绕过 ECS，用于简单场景）。

        注意：正式项目中应优先使用 AudioEventComponent 事件系统。
        """
        if not self._mixer_initialized:
            return
        sfx_def = self.sfx_bank.get(event_name)
        if not sfx_def:
            return
        file_path = sfx_def.get_random_file()
        if not file_path or not os.path.isfile(file_path):
            return
        try:
            sound = pygame.mixer.Sound(file_path)
            sound.set_volume(sfx_def.volume * volume * self.volumes.get("sfx", 0.8))
            sound.play()
        except Exception:
            pass

    def set_volume(self, category: str, volume: float) -> None:
        """设置音量。category: 'master'|'sfx'|'music'|'ui'|'ambience'"""
        self.volumes[category] = max(0.0, min(1.0, volume))
        if category == "music" or category == "master":
            final_music = (self.volumes.get("music", 0.6) *
                           self.volumes.get("master", 1.0))
            pygame.mixer.music.set_volume(final_music)

    def get_volume(self, category: str) -> float:
        """获取音量。"""
        return self.volumes.get(category, 1.0)

    def pause_music(self) -> None:
        """暂停音乐。"""
        pygame.mixer.music.pause()
        self._music_paused = True

    def resume_music(self) -> None:
        """恢复音乐。"""
        pygame.mixer.music.unpause()
        self._music_paused = False

    def stop_all_sfx(self) -> None:
        """停止所有音效。"""
        for ch in self._channels:
            ch.stop()
        self._channel_busy = [False] * len(self._channel_busy)
        self._active_voices.clear()

    def validate_audio_files(self) -> dict:
        """验证所有音频文件是否存在。"""
        result = {
            "sfx_missing": self.sfx_bank.validate_files(),
            "music_missing": self.music_controller.validate_files(),
        }
        return result
