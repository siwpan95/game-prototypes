"""Cocos 素材复用校验 —— 无头运行。

验证:
  - 34 张标准牌都有对应的 Cocos 精灵与语音文件
  - TileRenderer 能将 Cocos 精灵贴到 3D 牌体上（PIL 模式）
  - 季/花在素材缺失时正确回退到程序化绘制
  - AudioController 可在无 pygame 显示环境下安全实例化并响应事件

运行：python tests/test_assets.py   （在 G:/mahjong 根目录下）
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image  # noqa: E402

from models.tile import Suit, Tile  # noqa: E402
from services.deck import build_standard_deck  # noqa: E402
from views.audio_controller import AudioController, _cocos_voice_code  # noqa: E402
from views.tile_renderer import TileRenderer, _cocos_sprite_code  # noqa: E402


def _unique_tiles(deck):
    """按 tile.short 去重，保留一张代表。"""
    seen = {}
    for t in deck:
        if t.short not in seen:
            seen[t.short] = t
    return list(seen.values())


def test_all_standard_tiles_have_sprite():
    missing = []
    for t in _unique_tiles(build_standard_deck()):
        if t.suit in (Suit.SEASON, Suit.FLOWER):
            continue
        code = _cocos_sprite_code(t)
        if code is None:
            missing.append(t)
            continue
        path = os.path.join(ROOT, "assets", "cocos_sprites", f"{code}.png")
        if not os.path.exists(path):
            missing.append(f"{t} -> {code}.png")
    assert not missing, f"缺少 Cocos 精灵: {missing}"
    print("PASS [A1] 34 张标准牌精灵文件齐全")


def test_all_standard_tiles_have_voice():
    missing = []
    for t in _unique_tiles(build_standard_deck()):
        if t.suit in (Suit.SEASON, Suit.FLOWER):
            continue
        code = _cocos_voice_code(t)
        if code is None:
            missing.append(t)
            continue
        path = os.path.join(ROOT, "assets", "cocos_audio", code)
        if not os.path.exists(path):
            missing.append(f"{t} -> {code}")
    assert not missing, f"缺少 Cocos 语音: {missing}"
    print("PASS [A2] 34 张标准牌语音文件齐全")


def test_cocos_sprite_rendering():
    """使用 Cocos 精灵渲染 34 张标准牌，输出尺寸正确。"""
    renderer = TileRenderer(tile_size=56, thickness=15, shadow=7)
    deck = build_standard_deck()
    for t in _unique_tiles(deck):
        pil = renderer.get_pil(t)
        assert pil.size == (renderer.img_w, renderer.img_h), \
            f"{t} 渲染尺寸异常: {pil.size}"
        # 非全透明（说明贴图/绘制确实发生）
        assert pil.getextrema()[3][1] > 0, f"{t} 渲染结果全透明"
    print("PASS [A3] Cocos 精灵渲染 34 张标准牌尺寸与非透明性正常")


def test_season_flower_fallback():
    """季/花无 Cocos 精灵，验证程序化回退仍可渲染。"""
    renderer = TileRenderer(tile_size=56, thickness=15, shadow=7)
    for name, suit in [("春", Suit.SEASON), ("梅", Suit.FLOWER)]:
        tile = Tile(name=name, short=name, suit=suit, rank=1, group=suit.value)
        assert _cocos_sprite_code(tile) is None
        pil = renderer.get_pil(tile)
        assert pil.size == (renderer.img_w, renderer.img_h)
    print("PASS [A4] 季/花无 Cocos 精灵时程序化回退正常")


def test_audio_controller_headless():
    """无显示环境下 AudioController 可实例化，事件映射不抛错。"""
    events = []

    class DummyVM:
        def __init__(self):
            self.listeners = []

        def add_listener(self, fn):
            self.listeners.append(fn)

    vm = DummyVM()
    ctrl = AudioController(vm)
    assert len(vm.listeners) == 1

    from viewmodel.game_viewmodel import GameEvent

    # 模拟 select 事件（带 tile）
    tile = Tile(name="一筒", short="1筒", suit=Suit.DOTS, rank=1)
    ev = GameEvent("select", {"pos": (0, 0, 0), "tile": tile})
    vm.listeners[0](ev)

    # 模拟 match / win 事件
    vm.listeners[0](GameEvent("match", {"pos_a": (0, 0, 0), "pos_b": (0, 0, 1)}))
    vm.listeners[0](GameEvent("win", {"time_bonus": 0, "final_score": 100, "moves": 1}))

    events.append("ok")
    print("PASS [A5] AudioController 无头实例化 + 事件映射不抛错")


def generate_tileset_preview():
    """生成 34 张标准牌的视觉预览图并保存到 tests/output/cocos_tileset.png。"""
    renderer = TileRenderer(tile_size=64, thickness=16, shadow=8)
    tiles = _unique_tiles(build_standard_deck())
    # 过滤季/花（无精灵），按花色分组排序
    order = {
        Suit.DOTS: 0, Suit.CHAR: 1, Suit.BAMBOO: 2,
        Suit.WIND: 3, Suit.DRAGON: 4, Suit.SEASON: 5, Suit.FLOWER: 6,
    }
    tiles.sort(key=lambda t: (order[t.suit], t.rank))
    cols = 9
    rows = (len(tiles) + cols - 1) // cols
    pad = 8
    W = cols * (renderer.img_w + pad) + pad
    H = rows * (renderer.img_h + pad) + pad
    canvas = Image.new("RGBA", (W, H), (45, 80, 30, 255))
    for i, t in enumerate(tiles):
        pil = renderer.get_pil(t)
        x = pad + (i % cols) * (renderer.img_w + pad)
        y = pad + (i // cols) * (renderer.img_h + pad)
        canvas.paste(pil, (x, y), pil)
    out_dir = os.path.join(ROOT, "tests", "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "cocos_tileset.png")
    canvas.save(out_path)
    print(f"PREVIEW {out_path}")


if __name__ == "__main__":
    test_all_standard_tiles_have_sprite()
    test_all_standard_tiles_have_voice()
    test_cocos_sprite_rendering()
    test_season_flower_fallback()
    test_audio_controller_headless()
    generate_tileset_preview()
    print("ASSET_TESTS_PASS")
