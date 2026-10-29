#!/usr/bin/env python3
"""Text FPS - A text-based FPS game with pygame_ce GUI"""
import logging
import os
import sys

try:
    import pygame_ce as pygame
except ImportError:
    import pygame

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("text_fps")

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ['SDL_VIDEO_CENTERED'] = '1'

from core.game_state import GameState
from core.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS,
    PHASE_PLAYER_TURN, PHASE_ENEMY_TURN,
    PHASE_GAME_OVER, PHASE_VICTORY, DIR_DISPLAY,
)
from ui.renderer import Renderer
from data.levels import load_level, get_available_levels
from data.items import create_medkit
from models.item import WeaponModItem
from systems.combat import CombatSystem
from systems.movement import MovementSystem
from systems.inventory import InventorySystem
from systems.stealth import StealthSystem
from systems.level_generator import generate_campaign
from save.save_manager import SaveManager


class Game:
    """Main game class integrating all systems and the UI loop."""

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("文字FPS — 战术射击")
        self.clock = pygame.time.Clock()

        # Core — game_state is created in _start_new_game (F13: avoid building a
        # throwaway GameState in __init__ only to be replaced immediately).
        self.game_state = None  # type: ignore[assignment]

        # Systems
        self.combat = CombatSystem()
        self.movement = MovementSystem()
        self.inventory = InventorySystem()
        self.stealth = StealthSystem()
        self.save_manager = SaveManager()

        # UI
        self.renderer = Renderer(self.screen)

        # State
        self.running = True

        # Start first level
        self._start_new_game()

    def _start_new_game(self) -> None:
        """Initialize a new game from level 1."""
        self.game_state = GameState()
        level = load_level(1)
        self.game_state.load_level(level)
        # Give player starting items: 1 MedKit, 1 Armor Plate
        self.game_state.player.inventory.append(create_medkit(25))
        self.game_state.player.add_armor(25)
        self.game_state.phase = PHASE_PLAYER_TURN
        self.game_state.add_log("=== 文字FPS — 战术射击 ===")
        self.game_state.add_log("")
        self.game_state.add_log(f"你进入了{self.game_state.current_room.name}...")
        self.game_state.add_log(self.game_state.current_room.description)
        self.game_state.add_log("")
        self._describe_room()
        self.game_state.dirty = True

    def _describe_room(self) -> None:
        """Add room description to the game log."""
        room = self.game_state.current_room
        if room is None:
            return
        enemies = [e for e in room.enemies if e.is_alive]
        if enemies:
            self.game_state.add_log(f"！发现敌人：{', '.join(e.name for e in enemies)}")
        if room.items:
            self.game_state.add_log(f"地上的物品：{', '.join(i.name for i in room.items)}")
        exits = list(room.exits.keys())
        if exits:
            translated = [DIR_DISPLAY.get(d, d) for d in exits]
            self.game_state.add_log(f"出口：{', '.join(translated)}")
        if room.cover_objects:
            self.game_state.add_log(f"可用掩体：{', '.join(room.cover_objects)}")
        self.game_state.dirty = True

    def _get_living_enemies(self) -> list:
        """Get list of living enemies in the current room."""
        if not self.game_state.current_room:
            return []
        return [e for e in self.game_state.current_room.enemies if e.is_alive]

    def _start_random_campaign(self, seed: int = None) -> None:
        """Start a seeded procedural campaign (F4). Reproducible by seed."""
        import random as _r

        if seed is None:
            seed = _r.randint(1, 1_000_000)
        self.game_state = GameState()
        level = generate_campaign(seed)
        self.game_state.load_level(level)
        # Starting kit + one random extra weapon to showcase the expanded arsenal
        from data.weapons import create_weapon

        extra = _r.choice(["rifle", "smg", "shotgun", "ak", "dmr", "pdw", "lmg"])
        self.game_state.player.weapons.append(create_weapon(extra))
        self.game_state.player.inventory.append(create_medkit(25))
        self.game_state.player.add_armor(25)
        self.game_state.phase = PHASE_PLAYER_TURN
        self.game_state.add_log("=== 随机战役（种子 %d）===" % seed)
        self.game_state.add_log(f"你潜入了一座程序生成的设施：{level.name}。")
        self._describe_room()

    def _process_player_action(self, action: str, **kwargs) -> None:
        """Process a player action: execute action, apply noise, run enemy turn."""
        if self.game_state.phase != PHASE_PLAYER_TURN:
            return

        player = self.game_state.player
        room = self.game_state.current_room
        action_name = action  # For noise calculation

        if action == "fire":
            enemies = self._get_living_enemies()
            if enemies:
                target = enemies[self.game_state.selected_enemy_index % len(enemies)]
                result = self.combat.execute_fire(player, target, room)
                if result.get("success"):
                    self.game_state.add_log(result["message"])
                    if not result.get("enemy_alive", True):
                        # Drop loot
                        if target.loot:
                            for loot_item in target.loot:
                                room.add_item(loot_item)
                            self.game_state.add_log(
                                f"掉落物品：{', '.join(i.name for i in target.loot)}"
                            )
                        # Check if all enemies dead
                        if not self._get_living_enemies():
                            self.game_state.add_log("所有敌人已被消灭！")
                            self._check_level_complete()
                else:
                    self.game_state.add_log(result.get("message", "无法开火。"))
            else:
                self.game_state.add_log("没有可攻击的敌人。")

        elif action == "aim":
            result = self.combat.execute_aim(player)
            self.game_state.add_log(result["message"])

        elif action == "reload":
            result = self.combat.execute_reload(player)
            self.game_state.add_log(result["message"])

        elif action == "grenade":
            enemies = self._get_living_enemies()
            player.in_cover = False  # Grenade breaks cover
            result = self.combat.execute_grenade(player, enemies)
            self.game_state.add_log(result["message"])
            # Drop loot from killed enemies
            for e in result.get("killed", []):
                if e.loot:
                    for loot_item in e.loot:
                        room.add_item(loot_item)
                    self.game_state.add_log(
                        f"掉落物品：{', '.join(i.name for i in e.loot)}"
                    )
            if not self._get_living_enemies() and self.game_state.phase != PHASE_GAME_OVER:
                self.game_state.add_log("所有敌人已被消灭！")
                self._check_level_complete()

        elif action == "switch_weapon":
            result = self.inventory.switch_weapon(player)
            self.game_state.add_log(result["message"])

        elif action == "move":
            direction = kwargs.get("direction", "")
            result = self.movement.move(self.game_state, direction)
            if result.get("success"):
                self.game_state.add_log(result["message"])
                self._describe_room()
            else:
                self.game_state.add_log(result.get("message", "无法移动。"))

        elif action == "pickup":
            if room and room.items:
                result = self.inventory.pickup_all(player, room)
                self.game_state.add_log(result["message"])
            else:
                self.game_state.add_log("没有可拾取的物品。")

        elif action == "use_item":
            idx = kwargs.get("index", -1)
            if idx < 0:
                # Use first usable item
                idx = 0
            if 0 <= idx < len(player.inventory):
                result = self.inventory.use_item(
                    player, idx, self.combat, self._get_living_enemies()
                )
                self.game_state.add_log(result["message"])
                # Bug A: a grenade used via this path now drops loot just like the
                # dedicated grenade button (execute_grenade returns the killed list).
                for e in result.get("killed", []) or []:
                    if e.loot:
                        for loot_item in e.loot:
                            room.add_item(loot_item)
                        self.game_state.add_log(
                            f"掉落物品：{', '.join(i.name for i in e.loot)}"
                        )
                # If grenade was used, check level complete
                if not self._get_living_enemies() and self.game_state.phase != PHASE_GAME_OVER:
                    self.game_state.add_log("所有敌人已被消灭！")
                    self._check_level_complete()
            else:
                self.game_state.add_log("无效的物品选择。")

        elif action == "select_target":
            # F5: choose which living enemy to focus fire on. Does not consume a turn.
            idx = kwargs.get("index", 0)
            enemies = self._get_living_enemies()
            if 0 <= idx < len(enemies):
                self.game_state.selected_enemy_index = idx
            return

        elif action == "drop_item":
            idx = kwargs.get("index", -1)
            if 0 <= idx < len(player.inventory) and room:
                result = self.inventory.drop_item(player, idx, room)
                self.game_state.add_log(result["message"])
            else:
                self.game_state.add_log("无法丢弃此物品。")

        elif action == "toggle_cover":
            # F1: toggle into/out of cover (fixes the old "can't leave cover" bug)
            result = self.stealth.toggle_cover(player, room)
            self.game_state.add_log(result["message"])
            # Toggling cover is a free repositioning action -> no enemy turn.
            self.game_state.dirty = True
            return

        elif action == "modify_weapon":
            idx = kwargs.get("index", -1)
            if idx < 0:
                # Find first mod item
                for i, item in enumerate(player.inventory):
                    if isinstance(item, WeaponModItem):
                        idx = i
                        break
            if idx >= 0:
                result = self.inventory.modify_weapon(player, idx)
                self.game_state.add_log(result["message"])
            else:
                self.game_state.add_log("没有可用的武器改装件。")

        elif action == "save":
            slot = kwargs.get("slot", 1)
            self._handle_save(slot)
            return  # Don't trigger enemy turn for save

        elif action == "load":
            slot = kwargs.get("slot", 1)
            self._handle_load(slot)
            return  # Don't trigger enemy turn for load

        elif action == "new_game":
            self._start_new_game()
            return

        elif action == "random_campaign":
            # F4: seeded procedural campaign (different every run, reproducible by seed)
            self._start_random_campaign()
            return

        else:
            # F26: previously a silent no-op. Surface unknown actions for debugging.
            logger.warning("Unknown action received: %r (kwargs=%r)", action, kwargs)
            return  # Unknown action, no turn processing

        # Apply noise from action
        noise_result = self.stealth.apply_noise(player, action_name)
        if noise_result.get("alerted"):
            self.game_state.add_log("你的噪音引起了附近敌人的警觉！")
            alerted = self.stealth.check_alert(self.game_state)
            if alerted:
                self.game_state.add_log(
                    f"增援到达：{', '.join(e.name for e in alerted)}"
                )

        # Skip enemy turn if game is over or level transition happened
        if self.game_state.phase in (PHASE_GAME_OVER, PHASE_VICTORY):
            return

        # Process enemy turn
        self._enemy_turn()

    def _enemy_turn(self) -> None:
        """Execute enemy actions for all living enemies."""
        player = self.game_state.player
        room = self.game_state.current_room
        enemies = self._get_living_enemies()

        if not enemies:
            self.stealth.decay_noise(player)
            self.game_state.advance_turn()
            self.game_state.phase = PHASE_PLAYER_TURN
            self.game_state.dirty = True
            return

        self.game_state.phase = PHASE_ENEMY_TURN
        self.game_state.dirty = True

        # Execute enemy actions
        results = self.combat.execute_enemy_turn(enemies, player, room)
        for r in results:
            self.game_state.add_log(r.get("message", ""))

        # Check player death
        if not player.is_alive():
            self.game_state.phase = PHASE_GAME_OVER
            self.game_state.add_log("")
            self.game_state.add_log("=== 你倒下了 ===")
            self.game_state.add_log(
                f"最终统计: {player.kills}击杀, {player.shots_fired}次射击"
            )
            self.game_state.dirty = True
            return

        # End enemy turn
        self.stealth.decay_noise(player)
        # Tick transient player buffs (stim: accuracy/damage boost)
        if player.buffs.get("stim_turns", 0) > 0:
            player.buffs["stim_turns"] -= 1
            if player.buffs["stim_turns"] <= 0:
                player.buffs.pop("stim_turns", None)
                player.buffs.pop("stim_acc", None)
                player.buffs.pop("stim_dmg", None)
        # Cover persists unless player moves or takes an explicit action that breaks it
        # (moving, throwing grenade). It does NOT reset automatically each turn.
        self.game_state.advance_turn()
        self.game_state.phase = PHASE_PLAYER_TURN
        self.game_state.dirty = True

    def _check_level_complete(self) -> None:
        """Check if the current level is complete and advance."""
        level = self.game_state.levels[-1] if self.game_state.levels else None
        if level is None:
            return

        if not level.is_complete():
            return

        self.game_state.add_log(f"关卡'{level.name}'已完成！")

        # Try to load next level
        next_level_id = level.level_id + 1
        available = get_available_levels()

        if next_level_id in available:
            next_level = load_level(next_level_id)
            self.game_state.load_level(next_level)
            self.game_state.phase = PHASE_PLAYER_TURN
            self.game_state.add_log(f"正在进入{next_level.name}...")
            if next_level.get_room(next_level.start_room):
                self.game_state.add_log(
                    next_level.get_room(next_level.start_room).description
                )
            self._describe_room()
        else:
            # Victory!
            self.game_state.phase = PHASE_VICTORY
            self.game_state.add_log("")
            self.game_state.add_log("=== 胜利 ===")
            self.game_state.add_log("你已经清空了所有区域！")
            self.game_state.add_log(f"总击杀数: {self.game_state.player.kills}")
            self.game_state.dirty = True

    def _handle_save(self, slot: int) -> None:
        """Save the game to the specified slot."""
        if self.save_manager.save(self.game_state, slot):
            self.game_state.add_log(f"游戏已保存到槽位{slot}。")
        else:
            self.game_state.add_log("保存失败！")
        self.game_state.dirty = True

    def _handle_load(self, slot: int) -> None:
        """Load the game from the specified slot."""
        loaded = self.save_manager.load(slot)
        if loaded:
            self.game_state = loaded
            self.game_state.add_log(f"游戏已从槽位{slot}加载。")
            self._describe_room()
        else:
            self.game_state.add_log("加载失败！该槽位没有存档。")
        self.game_state.dirty = True

    def run(self) -> None:
        """Main game loop."""
        try:
            while self.running:
                try:
                    self._handle_events()
                    self.renderer.render(self.game_state)
                    pygame.display.flip()
                    self.game_state.dirty = False
                    self.clock.tick(FPS)
                except Exception as exc:  # #3: survive a single bad frame
                    logger.exception("Frame error (skipped): %s", exc)
        finally:
            pygame.quit()

    def _handle_events(self) -> None:
        """Process queued pygame events for one frame."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                action = self.renderer.handle_click(event.pos, self.game_state)
                if action:
                    self._process_player_action(**action)
            elif event.type == pygame.MOUSEWHEEL:  # F6: only MOUSEWHEEL (button 4/5 removed)
                self.renderer.handle_scroll(event.y)
            elif event.type == pygame.MOUSEMOTION:
                self.renderer.update_hover(event.pos, self.game_state)
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key)

    def _handle_key(self, key: int) -> None:
        """Handle keyboard shortcuts."""
        if self.game_state.phase != PHASE_PLAYER_TURN:
            if key == pygame.K_n and self.game_state.phase in (PHASE_GAME_OVER, PHASE_VICTORY):
                self._start_new_game()
            return

        # Keyboard shortcuts during player turn
        if key == pygame.K_f:
            self._process_player_action("fire")
        elif key == pygame.K_a:
            self._process_player_action("aim")
        elif key == pygame.K_r:
            self._process_player_action("reload")
        elif key == pygame.K_g:
            self._process_player_action("grenade")
        elif key == pygame.K_c:
            self._process_player_action("toggle_cover")
        elif key == pygame.K_w:
            self._process_player_action("move", direction="north")
        elif key == pygame.K_s:
            self._process_player_action("move", direction="south")
        elif key == pygame.K_d:
            self._process_player_action("move", direction="east")
        elif key == pygame.K_LEFT:
            self._process_player_action("move", direction="west")
        elif key == pygame.K_UP:
            self._process_player_action("move", direction="north")
        elif key == pygame.K_DOWN:
            self._process_player_action("move", direction="south")
        elif key == pygame.K_RIGHT:
            self._process_player_action("move", direction="east")
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
                     pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9):
            # F5: pick a living enemy as the focus target
            self._process_player_action("select_target", index=key - pygame.K_1)
        elif key == pygame.K_p:
            self._process_player_action("pickup")
        elif key == pygame.K_TAB:
            self._process_player_action("switch_weapon")


def main() -> None:
    """Entry point."""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
