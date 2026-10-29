"""Game class - main loop, state machine host, and game orchestration."""

from __future__ import annotations

import sys
import os

import pygame

from game.state import GameStateMachine
from game.event_bus import EventBus
from game.input_handler import InputHandler
from models.player import Player
from models.enemy import Enemy
from services.data_loader import DataLoader
from services.renderer import Renderer
from controllers.battle_controller import BattleController
from controllers.map_controller import MapController, MapNode
from controllers.event_controller import EventController
from screens.title_screen import TitleScreen
from screens.battle_screen import BattleScreen
from screens.map_screen import MapScreen
from screens.event_screen import EventScreen
from screens.loot_screen import LootScreen
from screens.game_over_screen import GameOverScreen
from screens.settings_screen import SettingsScreen


class Game:
    """Main game class that owns all core objects and runs the game loop.

    Responsibilities:
        - Initialize pygame and create the display
        - Own all core objects (Renderer, EventBus, DataLoader, InputHandler, etc.)
        - Host the GameStateMachine
        - Coordinate screen transitions
        - Run the main loop
    """

    FPS = 60

    def __init__(self, base_path: str = "") -> None:
        self._base_path = base_path or os.path.dirname(os.path.abspath(__file__))
        self._running: bool = False

        # Initialize pygame
        pygame.init()
        pygame.display.set_caption("Dark Souls: Card Chronicles")

        # Force fullscreen
        self._fullscreen: bool = True
        self._screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self._info = pygame.display.Info()
        self._width = self._info.current_w
        self._height = self._info.current_h

        # Core objects
        self.event_bus = EventBus()
        self.data_loader = DataLoader(self._base_path)
        self.renderer = Renderer(self._screen, self._base_path)
        self.input_handler = InputHandler()
        self.state_machine = GameStateMachine()

        # Game state
        self.player: Player | None = None
        self.map_controller = MapController(self.data_loader)
        self.event_controller = EventController(self.data_loader)

        # Screen instances (reusable)
        self._battle_screen = BattleScreen()
        self._map_screen = MapScreen()
        self._event_screen = EventScreen()
        self._loot_screen = LootScreen()
        self._game_over_screen = GameOverScreen()
        self._title_screen = TitleScreen()
        self._settings_screen = SettingsScreen()

        # Set game reference on all screens
        self._battle_screen.game = self
        self._map_screen.game = self
        self._event_screen.game = self
        self._loot_screen.game = self
        self._game_over_screen.game = self
        self._title_screen.game = self
        self._settings_screen.game = self

        # Clock
        self._clock = pygame.time.Clock()

    def run(self) -> None:
        """Start the main game loop."""
        self._running = True

        # Start at title screen
        self.state_machine.push(self._title_screen)

        while self._running:
            dt = self._clock.tick(self.FPS) / 1000.0

            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                    break
                # Track mouse state before passing to screens
                self.input_handler.process(event)
                self.state_machine.handle_event(event)

            # Update
            self.state_machine.update(dt)

            # Render
            self.state_machine.render(self._screen)
            pygame.display.flip()

            # Safety: clear any un-consumed click at end of frame
            self.input_handler.consume_click()

        pygame.quit()

    def quit(self) -> None:
        """Stop the game loop."""
        self._running = False

    # --- Game Flow Methods ---

    def start_new_run(self) -> None:
        """Start a new game run."""
        # Create new player
        self.player = Player(self.event_bus)
        self.player.setup_initial_deck(self.data_loader.create_card)

        # Generate first act map
        self.map_controller.current_act = 1
        self.map_controller.generate_act_map(1)

        # Go to map screen
        game_map = self.map_controller.get_current_map()
        self.state_machine.replace(self._map_screen, game_map=game_map)

    def start_battle(self, node: MapNode) -> None:
        """Start a battle from a map node."""
        if self.player is None:
            return

        enemy = self.data_loader.create_enemy(node.enemy_id)
        if enemy is None:
            return

        ctrl = BattleController(
            player=self.player,
            enemy=enemy,
            event_bus=self.event_bus,
            data_loader=self.data_loader,
        )

        self.state_machine.push(self._battle_screen, battle_controller=ctrl)

    def start_event(self, node: MapNode) -> None:
        """Start an event from a map node."""
        event_id = node.event_id
        if not event_id:
            return

        event_data = self.data_loader.get_event_data(event_id)
        if event_data is None:
            return

        self.state_machine.push(self._event_screen,
                                event_controller=self.event_controller,
                                event_data=event_data)

    def go_to_loot(self, battle_controller: BattleController) -> None:
        """Navigate to the loot screen after winning a battle."""
        souls = battle_controller.get_souls_reward()
        self.state_machine.replace(self._loot_screen, souls_reward=souls)

    def go_to_game_over(self) -> None:
        """Navigate to the game over screen."""
        victory = False
        if self.player and self.player.current_act > 3:
            victory = True
        self.state_machine.replace(self._game_over_screen, victory=victory)

    def go_to_title(self) -> None:
        """Return to the title screen."""
        self.state_machine.clear()
        self.state_machine.push(self._title_screen)

    def return_to_map(self) -> None:
        """Return to the map screen from an event/loot screen."""
        game_map = self.map_controller.get_current_map()

        # Check if current act is complete
        if game_map and game_map.is_complete():
            # Check if all acts are done
            next_act = self.map_controller.advance_to_next_act()
            if next_act is None:
                # Game complete! Victory!
                self.state_machine.replace(self._game_over_screen, victory=True)
                return
            else:
                if self.player:
                    self.player.current_act = next_act
                game_map = self.map_controller.generate_act_map(next_act)

        if game_map:
            self.state_machine.replace(self._map_screen, game_map=game_map)
        else:
            self.state_machine.replace(self._title_screen)

    def open_settings(self) -> None:
        """Open the settings overlay."""
        self.state_machine.push(self._settings_screen)

    def close_settings(self) -> None:
        """Close the settings overlay."""
        self.state_machine.pop()

    def toggle_fullscreen(self, fullscreen: bool) -> None:
        """Toggle between fullscreen and windowed mode."""
        self._fullscreen = fullscreen
        if fullscreen:
            self._screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self._screen = pygame.display.set_mode((1280, 720))
        # Update renderer's screen reference
        self.renderer = Renderer(self._screen, self._base_path)
        # Re-set game reference for current screen
        current = self.state_machine.current
        if current:
            current.game = self
