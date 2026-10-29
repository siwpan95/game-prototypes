"""Game world orchestration.

Assembles the map, player, renderer, audio and HUD. ``update(keys)`` mutates
state only; ``render(screen)`` draws only (architecture rule #9). Audio
position is synced inside ``update`` via ``update_position``.
"""
import math

try:
    import pygame_ce as pygame
except ImportError:  # pragma: no cover
    import pygame

from doom_game.config import (
    MOVE_SPEED, ROTATE_SPEED, DISABLE_AUDIO, HEADLESS_TEST,
    DEFAULT_MAP_WIDTH, DEFAULT_MAP_HEIGHT, WORLD_SEED, FRAME_DT,
    PLAYER_MAX_HP, ENEMY_HP, ENEMY_DAMAGE, ENEMY_SPEED,
    ENEMY_PERCEPTION_RANGE, ENEMY_CONTACT_DIST, ENEMY_CONTACT_COOLDOWN,
    HEALTH_PICKUP_AMOUNT, SCORE_PICKUP_AMOUNT, PICKUP_CONTACT_DIST,
    DEFAULT_MAP_PATH,
    PLAYER_ATTACK_DAMAGE, PLAYER_ATTACK_RANGE, PLAYER_ATTACK_COOLDOWN,
    PLAYER_ATTACK_HIT_DIST, LEVEL_CLEAR_DURATION, NEW_LEVEL_HP_FLOOR,
)
from doom_game.core.types import RenderMode, TextureType
from doom_game.core.player import Player
from doom_game.core.world_map import WorldMap
from doom_game.core.entities import Enemy, Pickup, PickupType, EnemyType
from doom_game.render.renderer import DOOMRenderer
from doom_game.audio.audio_system import DynamicAudioSystem
from doom_game.world.hud import HUD
from doom_game.world.level_io import load_map, build_enemies, build_pickups


class GameWorld:
    """Top-level facade wiring every subsystem together."""

    def __init__(self, map_width: int = DEFAULT_MAP_WIDTH,
                 map_height: int = DEFAULT_MAP_HEIGHT, seed: int = WORLD_SEED,
                 map_path: str = None, level_sequence: list = None):
        # Map + player.
        self.world_map = WorldMap()
        self.world_map.generate_maze(map_width, map_height, seed=seed)
        spawn = self.world_map.find_open_cell()
        self.player = Player(spawn[0] + 0.5, spawn[1] + 0.5, angle=0.0,
                             speed=MOVE_SPEED, rotate_speed=ROTATE_SPEED,
                             max_hp=PLAYER_MAX_HP, hp=PLAYER_MAX_HP, score=0)

        # Entities (enemies / pickups). Empty in maze mode; populated when a
        # level file is supplied via ``map_path`` (see load_level_data).
        self.enemies: list = []
        self.pickups: list = []
        self.map_path = map_path

        # Incremental V2: projectiles + level progression state machine.
        # ``map_path`` wins (single-level mode: clearing it == victory, Q4);
        # an explicit ``level_sequence`` enables the multi-level campaign;
        # neither -> legacy maze sandbox with no progression (progression is
        # inert because the sequence is empty and _check_level_complete is
        # only consulted when a sequence exists).
        self.projectiles: list = []
        if map_path:
            self.level_sequence: list = [map_path]
        elif level_sequence:
            self.level_sequence = list(level_sequence)
        else:
            self.level_sequence = []
        self.level_index = 0
        self.victory = False
        self.level_clear_timer = 0.0
        self._player_attack_cd = 0.0
        self._level_entry_score = 0

        # Rendering + HUD.
        self.renderer = DOOMRenderer()
        self.hud = HUD()
        self.render_mode = RenderMode.DOOM_STYLE

        # Audio (headless-safe; may be disabled).
        self.audio = DynamicAudioSystem()
        if DISABLE_AUDIO:
            self.audio.enabled = False

        # FPS bookkeeping.
        self.fps = 0
        self._frame_count = 0
        self._last_time = 0 if HEADLESS_TEST else pygame.time.get_ticks()

        # If a level file was requested, overlay it on top of the maze
        # fallback (a missing/invalid file keeps the generated maze).
        if map_path:
            self._load_map_file(map_path)
        elif self.level_sequence:
            # Campaign mode: enter the first level of the sequence.
            self.map_path = self.level_sequence[0]
            self._load_map_file(self.map_path)

    # ------------------------------------------------------------------ #
    # Level loading
    # ------------------------------------------------------------------ #
    def _load_map_file(self, path: str, keep_stats: bool = False) -> None:
        """Attempt to load a level file; fall back to the maze on failure."""
        try:
            level_data = load_map(path)
        except (OSError, ValueError) as exc:
            print(f"[WARN] could not load level '{path}': {exc}; "
                  f"falling back to generated maze")
            return
        self.load_level_data(level_data, keep_stats=keep_stats)

    def load_level_data(self, ld, keep_stats: bool = False) -> None:
        """Rebuild grid / player / entities in place from a ``LevelData``.

        The renderer, HUD and audio subsystems are intentionally left intact.
        ``keep_stats=False`` (default) keeps the historical behaviour: the
        player respawns with full health and zero score. ``keep_stats=True``
        carries the *current* hp / score over to the rebuilt player verbatim
        (``advance_level`` then applies the Q5 hp-floor formula on top).
        """
        prev_hp = self.player.hp
        prev_score = self.player.score
        int_to_tex = {0: None, 1: TextureType.BRICK, 2: TextureType.STONE,
                      3: TextureType.METAL, 4: TextureType.WOOD}
        # Rebuild the grid.
        self.world_map.width = int(ld.width)
        self.world_map.height = int(ld.height)
        self.world_map.cells = [
            [int_to_tex.get(int(v), None) for v in row] for row in ld.cells
        ]

        # Rebuild the player from the level start (full health, zero score).
        ps = ld.player_start
        px = float(ps.get("x", 1.5))
        py = float(ps.get("y", 1.5))
        pa = float(ps.get("angle", 0.0))
        # Validate: start must not sit on a wall; otherwise relocate.
        if self.world_map.is_wall(int(px), int(py)):
            sx, sy = self.world_map.find_open_cell()
            px, py = sx + 0.5, sy + 0.5
        self.player = Player(px, py, angle=pa, speed=MOVE_SPEED,
                             rotate_speed=ROTATE_SPEED,
                             max_hp=PLAYER_MAX_HP, hp=PLAYER_MAX_HP, score=0)
        if keep_stats:
            self.player.hp = prev_hp
            self.player.score = prev_score

        # Rebuild entities; in-flight projectiles never survive a rebuild.
        self.enemies = build_enemies(ld)
        self.pickups = build_pickups(ld)
        self.projectiles = []

    # ------------------------------------------------------------------ #
    # State update (no drawing)
    # ------------------------------------------------------------------ #
    def update(self, keys: dict) -> None:
        """Advance player position/rotation and sync audio position.

        Gate order (incremental V2): attack-cooldown tick -> victory / death
        freeze -> LEVEL CLEAR intermission countdown -> normal frame.
        Rendering is unaffected by the freeze (render() still draws).
        """
        # 1. Player attack cooldown always ticks (safety net for hitscan).
        if self._player_attack_cd > 0.0:
            self._player_attack_cd = max(0.0,
                                         self._player_attack_cd - FRAME_DT)

        # 2. Victory / death freeze: no entity, projectile or input updates.
        if self.victory or self.player.hp <= 0.0:
            return

        # 3. LEVEL CLEAR intermission: count down, then advance.
        if self.level_clear_timer > 0.0:
            self.level_clear_timer = max(0.0,
                                         self.level_clear_timer - FRAME_DT)
            if self.level_clear_timer <= 0.0:
                self.advance_level()
            return

        forward = 0.0
        strafe = 0.0
        if keys[pygame.K_w]:
            forward += 1.0
        if keys[pygame.K_s]:
            forward -= 1.0
        if keys[pygame.K_a]:
            strafe -= 1.0
        if keys[pygame.K_d]:
            strafe += 1.0
        if forward != 0.0 or strafe != 0.0:
            self._move_with_collision(forward, strafe)

        rotate = 0.0
        if keys[pygame.K_LEFT]:
            rotate -= 1.0
        if keys[pygame.K_RIGHT]:
            rotate += 1.0
        self.player.rotate(rotate)

        if self.audio.enabled:
            self.audio.update_position(
                self.player.pos.x, self.player.pos.y, self.player.angle)

        # Incremental: enemy AI + contact damage + pickup collection.
        # (Signature of ``update`` is unchanged; only the loop was added.)
        self._update_entities(FRAME_DT)

        # Incremental V2: projectile flight + level-complete detection.
        self._update_projectiles(FRAME_DT, self.player)
        if (self.level_sequence and not self.victory
                and self.level_clear_timer <= 0.0
                and self._check_level_complete()):
            if HEADLESS_TEST:
                self.advance_level()          # Q7: never block headless runs
            else:
                self.level_clear_timer = LEVEL_CLEAR_DURATION

    def _update_entities(self, dt: float) -> None:
        """Advance enemies/pickups and apply effects to the player."""
        player = self.player
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            damage = enemy.update(player, self.world_map, dt)
            if damage > 0:
                player.hp = max(0.0, player.hp - damage)
            # Ranged fire is part of the level-based combat loop; the legacy
            # maze sandbox (no level sequence) keeps its pre-V2 behaviour so
            # existing contact-damage contracts remain byte-identical.
            if self.level_sequence:
                projectile = enemy.try_fire(player, self.world_map)
                if projectile is not None:
                    self.projectiles.append(projectile)

        for pickup in self.pickups:
            if pickup.taken:
                continue
            if player.pos.distance_to(pickup.pos) < PICKUP_CONTACT_DIST:
                if pickup.kind == PickupType.HEALTH:
                    player.hp = min(player.max_hp, player.hp + pickup.amount)
                else:
                    player.score += pickup.amount
                pickup.taken = True

    def _update_projectiles(self, dt: float, player=None) -> None:
        """Advance all projectiles, apply hits, drop the dead ones.

        Damage is applied here (not inside ``Projectile``) so entities never
        mutate the player directly - same convention as enemy contact damage.
        The end-of-loop filter is the single leak-prevention point for all
        three death paths (hit / wall / max distance).
        """
        if not self.projectiles:
            return
        if player is None:
            player = self.player
        for projectile in self.projectiles:
            damage = projectile.update(self.world_map, player, dt)
            if damage > 0:
                player.hp = max(0.0, player.hp - damage)
        self.projectiles = [p for p in self.projectiles if p.alive]

    # ------------------------------------------------------------------ #
    # Player attack (SPACE hitscan) + level progression state machine
    # ------------------------------------------------------------------ #
    def player_attack(self) -> bool:
        """Instant hitscan along the view direction; True on an enemy hit.

        Called by ``main.py`` on KEYDOWN(SPACE) - event-driven, so holding
        the key never auto-fires. Refuses while dead / victorious / in the
        LEVEL CLEAR intermission / on cooldown. The ray steps at 0.05 grid
        units and stops at the first wall (attacks never pass through walls).
        """
        if self.victory or self.player.hp <= 0.0:
            return False
        if self.level_clear_timer > 0.0:
            return False
        if self._player_attack_cd > 0.0:
            return False
        self._player_attack_cd = PLAYER_ATTACK_COOLDOWN

        dir_x = math.cos(self.player.angle)
        dir_y = math.sin(self.player.angle)
        step = 0.05
        traveled = step
        while traveled <= PLAYER_ATTACK_RANGE:
            x = self.player.pos.x + dir_x * traveled
            y = self.player.pos.y + dir_y * traveled
            if self.world_map.is_wall(int(x), int(y)):
                return False              # wall blocks the shot
            for enemy in self.enemies:
                if not enemy.alive:
                    continue
                if math.hypot(enemy.pos.x - x,
                              enemy.pos.y - y) < PLAYER_ATTACK_HIT_DIST:
                    enemy.take_damage(PLAYER_ATTACK_DAMAGE)
                    return True
            traveled += step
        return False

    def _check_level_complete(self) -> bool:
        """True when the current level holds no living enemy (Q1)."""
        return (len(self.enemies) == 0
                or all(not e.alive for e in self.enemies))

    def advance_level(self) -> None:
        """Enter the next level of the sequence, or flag final victory.

        Q5 carry-over: score accumulates verbatim; hp carries but is floored
        at ``NEW_LEVEL_HP_FLOOR * max_hp`` and capped at ``max_hp``.
        """
        self.level_clear_timer = 0.0
        if self.level_index + 1 >= len(self.level_sequence):
            self.victory = True
            self.projectiles.clear()
            return
        hp0 = self.player.hp
        score0 = self.player.score
        self.level_index += 1
        path = self.level_sequence[self.level_index]
        # Keep map_path == level_sequence[level_index] so the in-game editor
        # (E key) and Ctrl+S always target the level being played (L9).
        self.map_path = path
        self._load_map_file(path, keep_stats=True)
        self.player.hp = min(max(hp0, NEW_LEVEL_HP_FLOOR
                                 * self.player.max_hp), self.player.max_hp)
        self.player.score = score0
        self._level_entry_score = score0
        self.projectiles.clear()

    def restart_level(self) -> None:
        """Reload the *current* level: full hp, score rolled back (L6/L8)."""
        self.victory = False
        self.level_clear_timer = 0.0
        self.projectiles.clear()
        if self.level_sequence:
            path = self.level_sequence[self.level_index]
            self.map_path = path
            self._load_map_file(path)     # keep_stats=False -> hp refilled
        else:
            # Legacy maze sandbox: regenerate the maze and reset the player.
            self.world_map.generate_maze(self.world_map.width,
                                         self.world_map.height,
                                         seed=WORLD_SEED)
            spawn = self.world_map.find_open_cell()
            self.player = Player(spawn[0] + 0.5, spawn[1] + 0.5, angle=0.0,
                                 speed=MOVE_SPEED, rotate_speed=ROTATE_SPEED,
                                 max_hp=PLAYER_MAX_HP, hp=PLAYER_MAX_HP,
                                 score=0)
            self.enemies = []
            self.pickups = []
        self.player.score = float(self._level_entry_score)

    def skip_level_clear(self) -> None:
        """Any-key skip of the LEVEL CLEAR intermission (Q7)."""
        if self.level_clear_timer > 0.0:
            self.level_clear_timer = 0.0
            self.advance_level()

    def _is_blocked(self, x: float, y: float, radius: float) -> bool:
        """True if any grid cell within ``radius`` of (x, y) is a wall."""
        for cx in (int(x - radius), int(x + radius)):
            for cy in (int(y - radius), int(y + radius)):
                if self.world_map.is_wall(cx, cy):
                    return True
        return False

    def _move_with_collision(self, forward: float, strafe: float) -> None:
        """Move the player with per-axis collision sliding."""
        old_x = self.player.pos.x
        old_y = self.player.pos.y
        # Use the player's own kinematics to compute intended displacement.
        self.player.move(forward, strafe)
        new_x = self.player.pos.x
        new_y = self.player.pos.y

        # Revert, then re-apply axis by axis for wall sliding.
        self.player.pos.x = old_x
        self.player.pos.y = old_y
        applied_dx = 0.0
        applied_dy = 0.0
        radius = 0.2
        if not self._is_blocked(new_x, old_y, radius):
            self.player.pos.x = new_x
            applied_dx = new_x - old_x
        if not self._is_blocked(self.player.pos.x, new_y, radius):
            self.player.pos.y = new_y
            applied_dy = new_y - old_y

        # Velocity reflects the *actual* displacement this frame (for audio).
        self.player.velocity_x = applied_dx
        self.player.velocity_y = applied_dy

    # ------------------------------------------------------------------ #
    # Rendering (no state change)
    # ------------------------------------------------------------------ #
    def render(self, screen) -> None:
        """Draw the scene and HUD onto ``screen``."""
        self.renderer.render(self.player, self.world_map, self.render_mode)
        # Incremental: billboard pass for enemies / pickups / projectiles.
        self.renderer.render_sprites(self.player, self.world_map,
                                     self.enemies, self.pickups,
                                     projectiles=self.projectiles)
        self.hud.render_minimap(screen, self, self.player)
        fps = self._compute_fps()
        self.hud.render_info(screen, self, self.player, fps)
        # Incremental HUD (R2.8): health bar, score and death overlay.
        self.hud.render_hp_bar(screen, self.player)
        self.hud.render_score(screen, self.player)
        self.hud.render_death(screen, self.player)
        # Incremental V2 HUD: banner -> LEVEL CLEAR card -> victory overlay.
        self.hud.render_level_banner(screen, self)
        self.hud.render_level_clear(screen, self)
        self.hud.render_victory(screen, self)
        if self.audio.enabled:
            self.hud.render_audio(screen, self.audio)

    def _compute_fps(self) -> int:
        now = pygame.time.get_ticks()
        self._frame_count += 1
        if now - self._last_time >= 1000:
            self.fps = self._frame_count
            self._frame_count = 0
            self._last_time = now
        return self.fps

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def generate(self) -> None:
        """(Re)generate the maze if needed; map is built in __init__."""
        pass

    def cleanup(self) -> None:
        """Tear down audio thread on exit."""
        if self.audio is not None:
            try:
                self.audio.stop()
            except Exception:
                pass
