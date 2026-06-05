"""Game state machine for KARD."""

from __future__ import annotations
from enum import Enum, auto
from typing import Any
try:
    from audio.audio_constants import DEFAULT_VOLUMES
except ImportError:
    DEFAULT_VOLUMES: dict[str, float] = {"master": 1.0, "sfx": 0.8, "music": 0.6, "ui": 0.9, "ambience": 0.5}


class Phase(Enum):
    MENU = auto()
    SETTINGS = auto()          # 操作教学 / 设置界面
    PLAYER_TURN = auto()
    ENEMY_TURN = auto()
    ROOM_COMPLETE = auto()     # Room cleared (replaces WAVE_CLEAR)
    REWARD = auto()
    EVENT = auto()             # 随机事件房
    MERCHANT = auto()          # 商人房
    CAMPFIRE = auto()          # 篝火房
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
        self.room_clear_timer: float = 0.0  # renamed from wave_clear_timer
        self.game_over_timer: float = 0.0
        self.message: str = ""
        self.message_timer: float = 0.0
        self.turn_number: int = 0
        self.ascension_level: int = 0       # 进阶等级 0-5

        # ── Room System ────────────────────────────────────────────────
        self.room_number: int = 0          # Current room number
        self.is_battle_room: bool = False  # Is current room a BATTLE or ELITE?
        self.is_elite_room: bool = False   # Is current room an ELITE?
        self.gold: int = 50               # Starting gold

        # ── Event / Merchant / Campfire state ─────────────────────────
        self.current_event: dict | None = None  # Current event data
        self.event_resolved: bool = False
        self.merchant_cards: list = []     # Cards for sale (entity IDs)
        self.merchant_prices: dict = {}    # entity→price for merchant cards
        self.merchant_remove_cost: int = 50
        self.campfire_action: str = ""     # "upgrade" or "rest"
        self.campfire_done: bool = False

        # ── Room transition after reward ────────────────────────────
        self.pending_next_room_type: Any = None  # Room to transition to after reward pick

        # ── Volume Settings ───────────────────────────────────────────
        self.master_volume: float = DEFAULT_VOLUMES.get("master", 1.0)
        self.music_volume: float = DEFAULT_VOLUMES.get("music", 0.6)
        self.sfx_volume: float = DEFAULT_VOLUMES.get("sfx", 0.8)

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
    def is_event(self) -> bool:
        return self.phase == Phase.EVENT

    @property
    def is_merchant(self) -> bool:
        return self.phase == Phase.MERCHANT

    @property
    def is_campfire(self) -> bool:
        return self.phase == Phase.CAMPFIRE

    @property
    def is_settings(self) -> bool:
        return self.phase == Phase.SETTINGS

    @property
    def is_game_over(self) -> bool:
        return self.phase == Phase.GAME_OVER

    # ── Room helpers ────────────────────────────────────────────────────

    @property
    def room_label(self) -> str:
        """Return a display label for the current room."""
        if self.is_elite_room:
            return "精英"
        return "战斗"

    def add_gold(self, amount: int) -> None:
        self.gold += amount
        if self.gold < 0:
            self.gold = 0

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
