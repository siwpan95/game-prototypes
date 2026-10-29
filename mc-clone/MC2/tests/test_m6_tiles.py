# -*- coding: utf-8 -*-
"""test_m6_tiles — M6 像素瓦片纹理（fx_tiles，T-M6-01/02/03）。

需要真实 pygame 才能创建 Surface；conftest 默认屏蔽 pygame，故用 real_pygame fixture
临时恢复，测完还原，不污染其他无 pygame 测试。
"""
from __future__ import annotations

import os
import sys

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


@pytest.fixture
def real_pygame():
    """临时恢复真实 pygame（conftest 默认设为 None），测完还原；不可用则用 mock。"""
    import sys
    saved = sys.modules.get("pygame")
    sys.modules.pop("pygame", None)
    try:
        import pygame
        pygame.init()
    except Exception:
        # 真实 pygame 不可用 → 注入 mock（T-M6-12：消除 4 个 skip）
        from _mock_pygame import Surface, PixelArray, draw, init, quit
        import types
        mock = types.ModuleType("pygame")
        mock.Surface = Surface
        mock.PixelArray = PixelArray
        mock.draw = draw
        mock.init = init
        mock.quit = quit
        sys.modules["pygame"] = mock
        TileTextureFactory._CACHE.clear()
        yield mock
        sys.modules["pygame"] = saved
        return
    TileTextureFactory._CACHE.clear()
    yield pygame
    sys.modules["pygame"] = saved


from mcclone.render.fx_tiles import TileTextureFactory
from mcclone.core.block_registry import BlockRegistry


def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def test_make_returns_surface(real_pygame):
    pygame = real_pygame
    reg = _reg()
    surf = TileTextureFactory.make(3, reg, 32)      # grass
    assert isinstance(surf, pygame.Surface)
    assert surf.get_width() == 32 and surf.get_height() == 32


def test_grass_is_textured_not_flat(real_pygame):
    pygame = real_pygame
    reg = _reg()
    surf = TileTextureFactory.make(3, reg, 32)
    pa = pygame.PixelArray(surf)
    colors = {pa[x, y] for x in range(0, 32, 4) for y in range(0, 32, 4)}
    # 草块应同时含草绿与泥棕（非纯色块）
    assert len(colors) > 1


def test_deterministic_same_block(real_pygame):
    pygame = real_pygame
    reg = _reg()
    a = TileTextureFactory.make(1, reg, 32)          # stone
    b = TileTextureFactory.make(1, reg, 32)
    pa, pb = pygame.PixelArray(a), pygame.PixelArray(b)
    assert pa[10, 10] == pb[10, 10]


def test_cache_returns_same_object(real_pygame):
    reg = _reg()
    a = TileTextureFactory.make(2, reg, 32)
    b = TileTextureFactory.make(2, reg, 32)
    assert a is b


def test_unknown_block_flat_no_raise(real_pygame):
    pygame = real_pygame
    reg = _reg()
    surf = TileTextureFactory.make(999, reg, 32)
    assert surf is not None
