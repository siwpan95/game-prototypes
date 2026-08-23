"""Cocos 音频控制器 —— 将 ViewModel 事件映射到 Cocos 真人语音/音效。

使用 alloy.audio.AudioSystem 作为播放器，自动处理 pygame 不可用、
文件缺失等异常（无头/静默环境不崩溃、不抛错）。
"""
from __future__ import annotations

import os
from typing import Optional

from models.tile import Suit, Tile
from viewmodel.game_viewmodel import GameEvent

_COCOS_AUDIO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "cocos_audio"
)


def _cocos_voice_code(tile: Tile) -> Optional[str]:
    """把 Tile 映射到 Cocos 语音文件名 mjt{cc}_{vv}.mp3。

    与精灵映射保持一致：筒/万/条/风/箭共 34 张标准牌。
    季/花返回 None（无对应语音）。
    """
    if tile.suit == Suit.DOTS and 1 <= tile.rank <= 9:
        cc, vv = 1, tile.rank
    elif tile.suit == Suit.CHAR and 1 <= tile.rank <= 9:
        cc, vv = 2, tile.rank
    elif tile.suit == Suit.BAMBOO and 1 <= tile.rank <= 9:
        cc, vv = 3, tile.rank
    elif tile.suit == Suit.WIND and 1 <= tile.rank <= 4:
        cc, vv = 4, tile.rank
    elif tile.suit == Suit.DRAGON and 1 <= tile.rank <= 3:
        cc, vv = 4, tile.rank + 4
    else:
        return None
    return f"mjt{cc}_{vv}.mp3"


class AudioController:
    """监听 GameViewModel 事件并播放对应 Cocos 音效。

    构造函数即完成事件订阅；销毁时无需手动取消。
    """

    def __init__(
        self,
        vm,
        master_volume: float = 0.5,
        sfx_volume: float = 1.0,
    ) -> None:
        self._vm = vm
        from alloy.audio import AudioSystem

        self._audio = AudioSystem(master_volume=master_volume)
        self._audio.set_sfx_volume(sfx_volume)
        self._enabled = os.path.isdir(_COCOS_AUDIO_DIR)
        vm.add_listener(self._on_event)

    def _play(self, filename: str, volume: float = 1.0) -> None:
        if not self._enabled:
            return
        path = os.path.join(_COCOS_AUDIO_DIR, filename)
        if not os.path.exists(path):
            return
        self._audio.play_sfx(path, volume=volume)

    def _on_event(self, ev: GameEvent) -> None:
        t = ev.type
        if t == "select":
            # 选中时读出该牌名称（沉浸感）
            tile = ev.data.get("tile")
            if isinstance(tile, Tile):
                code = _cocos_voice_code(tile)
                if code:
                    self._play(code, volume=0.55)
        elif t == "match":
            # "碰" 作为配对成功的麻将味音效
            self._play("peng.mp3", volume=0.65)
        elif t == "win":
            # "胡" 作为通关音效
            self._play("hu.mp3", volume=0.85)
