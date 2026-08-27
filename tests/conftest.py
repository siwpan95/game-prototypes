"""Shared pytest fixtures and helpers for the DOOM raycaster test-suite.

Key environment setup:
  * ``SDL_VIDEODRIVER=dummy`` MUST be set before pygame is first imported so
    that every test runs headless without a real display.
  * The repository root (the directory containing ``doom_game``) is prepended
    to ``sys.path`` so the package is importable regardless of the pytest cwd.
"""
import os
import sys

# Headless video driver must be configured before pygame is imported.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pygame  # noqa: E402  (imported after the env patch above)


@pytest.fixture(scope="session", autouse=True)
def _pygame_initialised():
    """Initialise pygame once for the whole session (headless)."""
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture
def display():
    """A real (dummy) pygame display surface for renderer.draw tests."""
    screen = pygame.display.set_mode((128, 128))
    yield screen
    pygame.display.quit()


@pytest.fixture
def small_map():
    """A 5x5 fully enclosed maze: stone border walls, empty interior."""
    from doom_game.core.types import TextureType
    from doom_game.core.world_map import WorldMap

    wm = WorldMap(5, 5)
    wm.cells = [
        [TextureType.STONE if (x in (0, 4) or y in (0, 4)) else None
         for x in range(5)]
        for y in range(5)
    ]
    return wm


@pytest.fixture
def empty_map():
    """A 3x3 map with no walls at all (every ray escapes -> no hit)."""
    from doom_game.core.world_map import WorldMap

    wm = WorldMap(3, 3)
    wm.cells = [[None for _ in range(3)] for _ in range(3)]
    return wm


@pytest.fixture
def small_renderer():
    """A DOOMRenderer sized 64x64 (few rays, fast) for render/DDA tests."""
    from doom_game.render.renderer import DOOMRenderer

    return DOOMRenderer(screen_width=64, screen_height=64)
