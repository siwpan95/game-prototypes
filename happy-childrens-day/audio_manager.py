"""
音频管理器 - 桥接 faatt.py 音频工作站与游戏系统
运行时合成并播放音效，无需预导出 WAV 文件。
依赖: sounddevice, numpy, scipy (缺省时静默降级)
"""
import threading
import numpy as np


class AudioManager:
    """
    懒加载 faatt 模块，合成+播放音效。
    如果 faatt 依赖不可用，自动降级为静默模式。
    """

    _INSTANCE = None

    def __new__(cls):
        if cls._INSTANCE is None:
            cls._INSTANCE = super().__new__(cls)
            cls._INSTANCE._initialized = False
        return cls._INSTANCE

    def _init(self):
        if self._initialized:
            return
        self._initialized = True
        self._available = False
        self._cache = {}  # name -> np.ndarray
        try:
            from faatt import (
                synthesize_voice, PreviewPlayer,
                COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS,
                UI_FX_PRESETS, CARD_FX_PRESETS,
            )
            self._synthesize = synthesize_voice
            self._presets = {
                "combat/heal": COMBAT_FX_PRESETS["heal"],
                "combat/damage_taken": COMBAT_FX_PRESETS["damage_taken"],
                "combat/critical_hit": COMBAT_FX_PRESETS["critical_hit"],
                "combat/block_hit": COMBAT_FX_PRESETS["block_hit"],
                "system/game_over": SYSTEM_FX_PRESETS["game_over"],
                "system/level_up": SYSTEM_FX_PRESETS["level_up"],
                "system/item_pickup": SYSTEM_FX_PRESETS["item_pickup"],
                "system/gold_pickup": SYSTEM_FX_PRESETS["gold_pickup"],
                "system/achievement": SYSTEM_FX_PRESETS["achievement"],
                "ui/button_click": UI_FX_PRESETS["button_click"],
                "ui/button_hover": UI_FX_PRESETS["button_hover"],
                "ui/confirm": UI_FX_PRESETS["confirm"],
                "ui/menu_open": UI_FX_PRESETS["menu_open"],
                "card/card_play": CARD_FX_PRESETS["card_play"],
                "card/card_draw": CARD_FX_PRESETS["card_draw"],
            }
            self._player = PreviewPlayer()
            self._available = True
            # 预合成常用音效
            for key in ("combat/heal", "combat/damage_taken",
                        "system/game_over", "system/item_pickup",
                        "system/level_up", "ui/button_click"):
                self._cache[key] = self._synthesize(self._presets[key])
        except ImportError:
            print("[Audio] faatt.py 或其依赖不可用，音效已禁用")
        except Exception as e:
            print(f"[Audio] 初始化失败: {e}")

    @property
    def available(self):
        self._init()
        return self._available

    def play(self, sfx_name: str):
        """播放指定音效（非阻塞）"""
        self._init()
        if not self._available:
            return
        audio = self._cache.get(sfx_name)
        if audio is None:
            voice = self._presets.get(sfx_name)
            if voice:
                audio = self._synthesize(voice)
                self._cache[sfx_name] = audio
        if audio is not None:
            threading.Thread(target=self._safe_play, args=(audio,), daemon=True).start()

    def _safe_play(self, audio):
        try:
            self._player.play(audio)
        except Exception:
            pass
