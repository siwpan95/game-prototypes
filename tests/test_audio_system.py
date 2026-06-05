"""AudioSystem 测试 — 事件响应、BGM 切换、音量控制。

用 unittest.mock.patch 屏蔽 pygame.mixer 真实初始化。
"""
import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

import pygame

from core.ecs import World, Entity
from core.event_bus import EventBus
from components.sanity import Sanity
from systems.audio_system import AudioSystem


# ── Fixtures ──────────────────────────────────────

@pytest.fixture(autouse=True)
def _mock_mixer():
    """所有测试自动 mock pygame.mixer。"""
    with patch("pygame.mixer.get_init", return_value=None), \
         patch("pygame.mixer.init") as mock_init, \
         patch("pygame.mixer.Sound") as mock_sound_cls, \
         patch("pygame.mixer.music") as mock_music, \
         patch("pygame.mixer.get_busy", return_value=False):
        mock_sound = MagicMock()
        mock_sound_cls.return_value = mock_sound
        mock_music.get_busy.return_value = False
        yield {
            "init": mock_init,
            "Sound": mock_sound_cls,
            "sound": mock_sound,
            "music": mock_music,
        }


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def audio_sys(bus):
    """创建 AudioSystem，跳过真实文件加载。"""
    with patch.object(AudioSystem, "_load_sfx"), \
         patch.object(AudioSystem, "_load_music"):
        sys = AudioSystem(event_bus=bus)
        sys.current_bgm = None
        sys._sanity_low_active = False
        sys._memory_bgm_timer = 0
        sys._prev_bgm = None
        sys.master_bgm = 1.0
        sys.master_sfx = 1.0
        sys.sfx = {
            "explore/step": MagicMock(),
            "memory/memory_touch": MagicMock(),
            "memory/sanity_cost": MagicMock(),
            "sanity/sanity_low": MagicMock(),
            "sanity/sanity_recover": MagicMock(),
            "sanity/sanity_zero": MagicMock(),
            "card/card_collect": MagicMock(),
            "card/card_all": MagicMock(),
            "mechanism/mech_trigger": MagicMock(),
        }
        sys.music = {
            "mansion_explore": "/fake/explore.wav",
            "memory_ambience": "/fake/ambience.wav",
            "sanity_drain": "/fake/drain.wav",
            "game_over": "/fake/game_over.wav",
            "victory": "/fake/victory.wav",
        }
        return sys


@pytest.fixture
def world_with_sanity():
    w = World()
    e = Entity(eid="player")
    e.add(Sanity(value=50, max_value=100))
    w.add_entity(e)
    return w


# ── 初始化 ──────────────────────────────────────

class TestInit:
    def test_subscribes_events(self, bus):
        with patch.object(AudioSystem, "_load_sfx"), \
             patch.object(AudioSystem, "_load_music"):
            sys = AudioSystem(event_bus=bus)
            bus.emit("PLAYER_MOVE", {})
            bus.emit("MEMORY_TRIGGERED", {})
            bus.emit("CARD_COLLECTED", {})
            bus.emit("SANITY_RECOVER", {})
            bus.emit("GAME_OVER", {})
            bus.emit("GAME_WIN", {})
            bus.emit("MECHANISM_TRIGGERED", {})


# ── play_sfx ──────────────────────────────────────

class TestPlaySFX:
    def test_play_existing(self, audio_sys):
        snd = audio_sys.sfx["explore/step"]
        audio_sys.play_sfx("explore/step")
        snd.set_volume.assert_called_once()
        snd.play.assert_called_once()

    def test_play_nonexistent(self, audio_sys):
        audio_sys.play_sfx("nonexistent/sfx")

    def test_volume_multiplier(self, audio_sys):
        snd = audio_sys.sfx["explore/step"]
        audio_sys.master_sfx = 0.5
        audio_sys.play_sfx("explore/step", volume=0.8)
        call_args = snd.set_volume.call_args
        assert abs(call_args[0][0] - 0.4) < 0.01


# ── play_bgm / stop_bgm ──────────────────────────────────────

class TestPlayBGM:
    def test_play_existing(self, audio_sys, _mock_mixer):
        audio_sys.play_bgm("memory_ambience", volume=0.7)
        assert audio_sys.current_bgm == "memory_ambience"

    def test_play_nonexistent(self, audio_sys):
        old = audio_sys.current_bgm
        audio_sys.play_bgm("nonexistent_bgm")
        assert audio_sys.current_bgm == old

    def test_stop_bgm(self, audio_sys, _mock_mixer):
        audio_sys.current_bgm = "mansion_explore"
        audio_sys.stop_bgm()
        assert audio_sys.current_bgm is None

    def test_volume_multiplier(self, audio_sys, _mock_mixer):
        audio_sys.master_bgm = 0.6
        audio_sys.play_bgm("mansion_explore", volume=0.8)
        _mock_mixer["music"].set_volume.assert_called()
        call_args = _mock_mixer["music"].set_volume.call_args
        assert abs(call_args[0][0] - 0.48) < 0.01


# ── 音量控制 ──────────────────────────────────────

class TestVolumeControl:
    def test_set_bgm_volume_clamps_high(self, audio_sys):
        audio_sys.set_bgm_volume(1.5)
        assert audio_sys.master_bgm == 1.0

    def test_set_bgm_volume_clamps_low(self, audio_sys):
        audio_sys.set_bgm_volume(-0.3)
        assert audio_sys.master_bgm == 0.0

    def test_set_bgm_volume_normal(self, audio_sys):
        audio_sys.set_bgm_volume(0.7)
        assert audio_sys.master_bgm == 0.7

    def test_set_sfx_volume_clamps_high(self, audio_sys):
        audio_sys.set_sfx_volume(2.0)
        assert audio_sys.master_sfx == 1.0

    def test_set_sfx_volume_clamps_low(self, audio_sys):
        audio_sys.set_sfx_volume(-1.0)
        assert audio_sys.master_sfx == 0.0

    def test_set_sfx_volume_normal(self, audio_sys):
        audio_sys.set_sfx_volume(0.3)
        assert audio_sys.master_sfx == 0.3

    def test_set_bgm_volume_affects_current(self, audio_sys, _mock_mixer):
        audio_sys.current_bgm = "mansion_explore"
        _mock_mixer["music"].get_busy.return_value = True
        audio_sys.set_bgm_volume(0.8)
        _mock_mixer["music"].set_volume.assert_called_once_with(0.8)


# ── 事件响应 ──────────────────────────────────────

class TestEventResponses:
    def test_player_move_plays_step(self, audio_sys):
        audio_sys.bus.emit("PLAYER_MOVE", {"col": 1, "row": 1})
        snd = audio_sys.sfx["explore/step"]
        snd.play.assert_called()

    def test_memory_triggered_switches_bgm(self, audio_sys):
        audio_sys.current_bgm = "mansion_explore"
        audio_sys.bus.emit("MEMORY_TRIGGERED", {"id": "test", "name": "t"})
        assert audio_sys.current_bgm == "memory_ambience"
        assert audio_sys._memory_bgm_timer > 0

    def test_memory_triggered_saves_prev_bgm(self, audio_sys):
        audio_sys.current_bgm = "mansion_explore"
        audio_sys.bus.emit("MEMORY_TRIGGERED", {"id": "test", "name": "t"})
        assert audio_sys._prev_bgm == "mansion_explore"

    def test_card_collected_plays_sfx(self, audio_sys):
        audio_sys.bus.emit("CARD_COLLECTED", {"card_id": "key_01", "name": "钥匙"})
        snd = audio_sys.sfx["card/card_collect"]
        snd.play.assert_called_once()

    def test_sanity_recover_plays_sfx(self, audio_sys):
        audio_sys.bus.emit("SANITY_RECOVER", {"amount": 15})
        snd = audio_sys.sfx["sanity/sanity_recover"]
        snd.play.assert_called_once()

    def test_game_over_stops_bgm(self, audio_sys, _mock_mixer):
        audio_sys.current_bgm = "mansion_explore"
        audio_sys.bus.emit("GAME_OVER", {"reason": "sanity_zero"})
        assert audio_sys.current_bgm == "game_over"
        _mock_mixer["music"].fadeout.assert_called()

    def test_game_win_plays_victory(self, audio_sys, _mock_mixer):
        audio_sys.current_bgm = "mansion_explore"
        audio_sys.bus.emit("GAME_WIN", {})
        assert audio_sys.current_bgm == "victory"
        _mock_mixer["music"].fadeout.assert_called()

    def test_mechanism_triggered_plays_sfx(self, audio_sys):
        audio_sys.bus.emit("MECHANISM_TRIGGERED", {"id": "test"})
        snd = audio_sys.sfx["mechanism/mech_trigger"]
        snd.play.assert_called_once()


# ── 理智低 BGM 切换 ──────────────────────────────────────

class TestSanityLowBGM:
    def test_low_sanity_switches_to_drain(self, audio_sys, world_with_sanity):
        w = world_with_sanity
        player = w.get_entity("player")
        s = player.get(Sanity)
        if s:
            s.value = 20
        audio_sys.current_bgm = "mansion_explore"
        audio_sys.update(w, 0)
        assert audio_sys._sanity_low_active is True

    def test_recover_switches_back(self, audio_sys, world_with_sanity):
        w = world_with_sanity
        audio_sys._sanity_low_active = True
        audio_sys.current_bgm = "sanity_drain"
        player = w.get_entity("player")
        s = player.get(Sanity)
        if s:
            s.value = 50
        audio_sys.update(w, 0)
        assert audio_sys._sanity_low_active is False

    def test_no_player_no_crash(self, audio_sys):
        w = World()
        audio_sys.update(w, 0)

    def test_no_sanity_component_no_crash(self, audio_sys):
        w = World()
        e = Entity(eid="player")
        w.add_entity(e)
        audio_sys.update(w, 0)


# ── 记忆 BGM 倒计时恢复 ──────────────────────────────────────

class TestMemoryBGMRecovery:
    def test_timer_counts_down(self, audio_sys):
        audio_sys._memory_bgm_timer = 2000
        w = World()  # 无 player → 理智检查跳过
        audio_sys.update(w, 500)
        assert audio_sys._memory_bgm_timer == 1500

    def test_timer_expiry_restores_bgm(self, audio_sys):
        audio_sys._memory_bgm_timer = 100
        audio_sys._prev_bgm = "mansion_explore"
        audio_sys.current_bgm = "memory_ambience"
        w = World()  # 无 player
        with patch.object(audio_sys, "play_bgm") as mock_play:
            audio_sys.update(w, 200)
            assert audio_sys._memory_bgm_timer <= 0
            assert audio_sys._prev_bgm is None
            mock_play.assert_called_once()
