"""Game state machine for KARD."""

from __future__ import annotations
from enum import Enum, auto


class Phase(Enum):
    MENU = auto()
    PLAYER_TURN = auto()
    ENEMY_TURN = auto()
    WAVE_CLEAR = auto()
    REWARD = auto()
    GAME_OVER = auto()


class GameState:
    """Manages the current game phase and turn-level state."""

    def __init__(self) -> None:
        self.phase: Phase = Phase.MENU
        self.selected_card_entity = None   # Entity ID of card in hand being played
        self.selected_minion_entity = None # Entity ID of player minion selected to attack
        self.reward_cards: list = []       # Entity IDs of reward cards
        self.enemy_turn_timer: float = 0.0
        self.enemy_turn_index: int = 0
        self.wave_clear_timer: float = 0.0
        self.game_over_timer: float = 0.0
        self.message: str = ""
        self.message_timer: float = 0.0
        self.turn_number: int = 0

    # ── Phase checks ────────────────────────────────────────────────────

    @property
    def is_player_turn(self) -> bool:
        return self.phase == Phase.PLAYER_TURN

    @property
    def is_enemy_turn(self) -> bool:
        return self.phase == Phase.ENEMY_TURN

    @property
    def is_reward(self) -> bool:
        return self.phase == Phase.REWARD

    @property
    def is_game_over(self) -> bool:
        return self.phase == Phase.GAME_OVER

    # ── Selection helpers ───────────────────────────────────────────────

    def clear_selection(self) -> None:
        self.selected_card_entity = None
        self.selected_minion_entity = None

    @property
    def has_card_selected(self) -> bool:
        return self.selected_card_entity is not None

    @property
    def has_minion_selected(self) -> bool:
        return self.selected_minion_entity is not None

    # ── Message ─────────────────────────────────────────────────────────

    def show_message(self, text: str, duration: float = 2.0) -> None:
        self.message = text
        self.message_timer = duration
