# -*- coding: utf-8 -*-
"""游戏主控：状态机 + 玩家位姿 + 每帧流水线。"""
import math
import random
import time
from typing import Optional

import pygame

from .audio.sfx import SFXPlayer
from .audio.synth import ZoneSynth
from .config import (
    BEAT,
    CHUNK_SIZE,
    EXPLORE_RADIUS,
    H,
    INTERACT_RANGE,
    MAX_DEPTH,
    MOVE_SPEED,
    MOUSE_SENS_X,
    MOUSE_SENS_Y,
    NUM_RAYS,
    PITCH_KEY_SPEED,
    PITCH_MAX_PIX,
    PORTAL_TELEPORT_CHANCE,
    RENDER_BACKEND,
    ROT_SPEED,
    SR,
    W,
)
from .highscore import load_highscore, save_highscore
from .preload import LoadingTask, PreloadManager
from .render.particles import Particle
from .render.raycast import Renderer
from .state import GameState
from .systems.ability import AbilitySystem
from .systems.energy import EnergySystem
from .systems.exploration import ExplorationTracker
from .systems.fragments import FragmentSystem
from .systems.interaction import InteractionSystem
from .ui.death import DeathScreen
from .ui.hud import draw_codex, draw_hud
from .ui.loading import LoadingScreen
from .ui.vignette import make_vignette
from .world.worldmap import WorldMap

# ─────────────────────── 主循环（状态机版本）─────────────────────────
class Game:
    """游戏主控制器，使用状态机管理不同阶段"""
    
    def __init__(self):
        pygame.init()
        pygame.mixer.pre_init(frequency=SR, size=-16, channels=2, buffer=2048)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(32)
        
        # ── 窗口 / 2D 画布 / GL 渲染器（Stage 4：window 与 offscreen 双模式）──
        self.use_gl = False
        self.gl_renderer = None
        if RENDER_BACKEND == "gl":
            try:
                import moderngl                       # noqa: F401  探测可用性
                pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
                pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
                pygame.display.set_mode((W, H), pygame.OPENGL | pygame.DOUBLEBUF)
                from .render.gl import GLRenderer
                # 真窗口模式：moderngl 接管 SDL 上下文，无像素读回
                self.gl_renderer = GLRenderer(None, None, mode="window")
                self.use_gl = True
            except Exception as e:
                print(f"[render] OPENGL 窗口不可用（{type(e).__name__}: {e}），改用 2D 窗口")
                pygame.display.quit()
                pygame.display.init()
                self.gl_renderer = None
        if not self.use_gl:
            self.screen = pygame.display.set_mode((W, H))
            if RENDER_BACKEND == "gl":
                try:
                    from .render.gl import GLRenderer
                    # 离屏模式：同一套 GL 管线，最后读回 blit（无头环境 / 回退）
                    self.gl_renderer = GLRenderer(self.screen, None, mode="offscreen")
                    self.use_gl = True
                except Exception as e:
                    print(f"[render] 离屏 GL 不可用，回退 2D 后端：{type(e).__name__}: {e}")
        # canvas = 所有 2D 内容的绘制目标。
        # GL 模式：离屏 SRCALPHA 层，present() 时作为纹理叠到 3D 之上；
        # 2D 模式：即主屏本身（行为与旧版完全一致）。
        if self.use_gl:
            self.canvas = pygame.Surface((W, H), pygame.SRCALPHA, 32)
        else:
            self.canvas = self.screen
        self.renderer = self.gl_renderer
        pygame.display.set_caption("KID-A WALKER  [INFINITE]")
        pygame.mouse.set_visible(False)

        # 初始化字体
        try:
            self.f_sm = pygame.font.SysFont("Courier New", 14, bold=True)
            self.f_bg = pygame.font.SysFont("Courier New", 32, bold=True)
        except Exception:
            self.f_sm = pygame.font.Font(None, 18)
            self.f_bg = pygame.font.Font(None, 40)

        # 状态机
        self.state = GameState.START_SCREEN
        self.clock = pygame.time.Clock()

        # 加载界面
        self.loading_screen = LoadingScreen(self.canvas)
        
        # 预加载管理器
        self.preload_manager: Optional[PreloadManager] = None
        
        # 游戏核心组件（延迟初始化）
        self.world: Optional[WorldMap] = None
        self.synth: Optional[ZoneSynth] = None
        self.renderer: Optional[Renderer] = None
        self.vignette: Optional[pygame.Surface] = None
        
        # 主菜单音乐（固定音乐）
        self.menu_synth: Optional[ZoneSynth] = None
        self.menu_active_sounds: list = []
        self.last_menu_sound_t = 0.0
        
        # 玩家状态
        self.px, self.py, self.pang = 10.5, 10.5, 0.0
        self.pitch = 0.0          # 俯仰：地平线相对屏幕中线的像素位移
        self.show_codex = False
        self.tick = 0
        self.survival_time = 0.0
        self.particles: list[Particle] = []
        self.part_timer = 0
        self.last_sound_t = 0.0
        self.last_chunk = (0, 0)
        self.active_sounds = []
        self.zbuf = [0.0] * NUM_RAYS
        self.dominant_zone = 2
        self._danger_near = False
        self._last_zone_chunk: tuple[int, int] = (0, 0)

        # ─── 增强系统 ───
        self.energy = EnergySystem()
        self.fragments = FragmentSystem()
        self.interaction = InteractionSystem(INTERACT_RANGE)
        self.abilities = AbilitySystem(self.fragments)
        self.exploration = ExplorationTracker(EXPLORE_RADIUS)
        self.sfx = SFXPlayer(enabled=True)
        self.markers: list[tuple] = []  # 橙色光源标记点
        
        # 加载完成动画计时
        self._complete_show_time = 0
        self._grab_released = True
        
        # 开始界面动画时间
        self._start_animate = 0.0
        
    def run(self):
        """主游戏循环"""
        # 初始化主菜单音乐（固定空灵神秘风格）
        self.menu_synth = ZoneSynth()
        self.menu_synth.set_zone(2)  # zone 2 = 空灵神秘
        
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            
            # 状态处理
            if self.state == GameState.START_SCREEN:
                self._handle_start_screen(dt)
            elif self.state == GameState.LOADING:
                self._handle_loading()
            elif self.state == GameState.PLAYING:
                self._handle_playing(dt)
            elif self.state == GameState.GAME_OVER:
                self._handle_game_over(dt)
            elif self.state == GameState.QUIT:
                running = False
            
            pygame.display.flip()
        
        # 清理
        if self.synth:
            self.synth.running = False
        pygame.quit()
    
    def _handle_start_screen(self, dt: float):
        """处理开始界面"""
        self._start_animate += dt
        
        # 播放主菜单固定音乐
        if self.menu_synth:
            now = time.monotonic()
            if now - self.last_menu_sound_t >= BEAT * 0.46:
                snd = self.menu_synth.pop_sound()
                if snd is not None:
                    snd.play()
                    self.last_menu_sound_t = now
                    self.menu_active_sounds.append(snd)
                    if len(self.menu_active_sounds) > 16:
                        self.menu_active_sounds = self.menu_active_sounds[-16:]
        
        # 事件处理
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.state = GameState.QUIT
                return
            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    pygame.mouse.set_visible(False)
                    self._start_loading()
                    return
                elif ev.key == pygame.K_ESCAPE:
                    self.state = GameState.QUIT
                    return
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                pygame.mouse.set_visible(False)
                self._start_loading()
                return
        
        # 绘制开始界面
        if self.use_gl:
            self.canvas.fill((0, 0, 0, 0))
        self.loading_screen._animate = self._start_animate
        self.loading_screen._draw_start_screen()
        self._present()
    
    def _start_loading(self):
        """开始后台加载"""
        # 停止主菜单音乐
        if self.menu_synth:
            self.menu_synth.running = False
            self.menu_synth = None
            self.menu_active_sounds = []
        
        self.state = GameState.LOADING
        self._complete_show_time = 0
        self._grab_released = False
        
        # 创建预加载管理器（带进度回调）
        def on_progress(task: LoadingTask):
            # 在主线程更新加载界面
            pass
        
        self.preload_manager = PreloadManager(on_progress)
        self.preload_manager.start()
    
    def _handle_loading(self):
        """处理加载状态"""
        # 事件处理（允许取消加载返回开始界面）
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.state = GameState.QUIT
                return
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    # 取消加载，返回开始界面
                    if self.preload_manager:
                        self.preload_manager.cancel()
                        self.preload_manager = None
                    self.state = GameState.START_SCREEN
                    self._start_animate = 0.0
                    pygame.mouse.set_visible(True)
                    return
        
        # 检查加载进度
        if self.preload_manager:
            progress, status = self.preload_manager.get_overall_progress()
            self.loading_screen._animate += 0.016  # 保持动画
            if self.use_gl:
                self.canvas.fill((0, 0, 0, 0))
            self.loading_screen.update_progress(progress, status)
            self._present()
            
            # 检查是否完成
            if self.preload_manager.is_complete():
                self._complete_show_time += 1
                if self._complete_show_time == 1:
                    self.loading_screen.draw_complete()
                elif self._complete_show_time > 50:  # 显示约0.8秒后进入游戏
                    self._initialize_game()
                    self.state = GameState.PLAYING
                    pygame.mouse.set_visible(False)
                    # 抓取鼠标：不抓的话光标一碰到窗口边缘，视角就转不动了
                    pygame.event.set_grab(True)
    
    def _initialize_game(self):
        """初始化游戏核心组件（在加载完成后调用）"""
        if not self.preload_manager:
            return
        
        # 获取预加载的数据
        world = self.preload_manager.get_world()
        if world is None:
            return
        self.world = world
        spawn = self.preload_manager.get_spawn()
        
        # 初始化音频
        self.synth = ZoneSynth()
        
        # 初始化渲染器
        self.renderer = self._make_renderer()
        self.renderer._ensure_bg_cache()  # 预渲染背景（增强版为空操作）

        self.vignette = make_vignette(W, H)

        # 设置玩家位置并确保周围区块已生成
        self.px, self.py = spawn
        self.pang = 0.0
        self.last_chunk = self.world.world_to_chunk(self.px, self.py)
        self._last_zone_chunk = self.last_chunk

        # 初始区域音效（随机选择）
        self.dominant_zone = random.randint(2, 12)
        self.synth.set_zone(self.dominant_zone)

        # 预生成玩家周围的区块（会清理远处区块增强随机性）
        self.world.ensure_neighbors(self.last_chunk[0], self.last_chunk[1])

    def _make_renderer(self):
        """按配置选择渲染后端。GL 渲染器随窗口创建，这里只绑定当前世界。"""
        if self.gl_renderer is not None:
            self.gl_renderer.set_world(self.world)
            return self.gl_renderer
        if RENDER_BACKEND in ("enhanced", "gl"):
            from .render.enhanced import EnhancedRenderer
            return EnhancedRenderer(self.canvas)
        return Renderer(self.canvas)

    def _present(self):
        """把 2D 画布合成到显示目标（GL 后端），2D 后端为空操作。"""
        if self.renderer is not None:
            self.renderer.present(self.canvas)
    
    def _handle_playing(self, dt: float):
        """处理游戏运行状态（集成增强系统）"""
        self.tick += 1
        self.survival_time += dt
        
        # 确保游戏组件已初始化
        if self.world is None or self.renderer is None:
            return
        
        # 事件处理
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.state = GameState.QUIT
                return
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    self.state = GameState.QUIT
                    return
                elif ev.key == pygame.K_TAB:
                    # Tab切换图鉴页
                    self.show_codex = not self.show_codex
                elif ev.key == pygame.K_e:
                    # E键交互
                    effects = self.interaction.interact(
                        self.px, self.py, self.world, self.fragments, self.energy)
                    if effects is not None:
                        deco_type = effects.get("type", 0)
                        # SFX
                        self.sfx.play_collect(deco_type)
                        if "shield" in effects:
                            self.sfx.play_shield()
                        if "marker" in effects:
                            self.markers.append(effects["marker"])
            elif ev.type == pygame.MOUSEMOTION:
                # ─── 鼠标视角：横向转向，纵向俯仰 ───
                if not self.show_codex:
                    self.pang += ev.rel[0] * MOUSE_SENS_X
                    self.pitch -= ev.rel[1] * MOUSE_SENS_Y

        # ─── 1. 移动计算（含速度倍率） ───
        keys = pygame.key.get_pressed()

        # ─── 1b. 俯仰（R/F 键盘，鼠标的备用方案） ───
        if keys[pygame.K_r]:
            self.pitch += PITCH_KEY_SPEED
        if keys[pygame.K_f]:
            self.pitch -= PITCH_KEY_SPEED
        self.pitch = max(-PITCH_MAX_PIX, min(PITCH_MAX_PIX, self.pitch))
        speed_mult = self.abilities.get_speed_multiplier()
        rot_spd = ROT_SPEED  # 旋转速度不随能力变化
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.pang -= rot_spd
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.pang += rot_spd
        
        is_moving = False
        mv = 0.0
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            mv = MOVE_SPEED * speed_mult
            is_moving = True
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            mv = -MOVE_SPEED * speed_mult
            is_moving = True
        
        # 移动和碰撞检测
        if mv:
            est_nx = self.px + math.cos(self.pang) * mv * 1.5
            est_ny = self.py + math.sin(self.pang) * mv * 1.5
            est_cx = int(math.floor(est_nx / CHUNK_SIZE))
            est_cy = int(math.floor(est_ny / CHUNK_SIZE))
            cur_cx = int(math.floor(self.px / CHUNK_SIZE))
            cur_cy = int(math.floor(self.py / CHUNK_SIZE))
            for dcx in range(min(cur_cx, est_cx) - 1, max(cur_cx, est_cx) + 2):
                for dcy in range(min(cur_cy, est_cy) - 1, max(cur_cy, est_cy) + 2):
                    self.world.ensure_neighbors(dcx, dcy)
        
        if mv:
            nx = self.px + math.cos(self.pang) * mv
            ny = self.py + math.sin(self.pang) * mv
            if self.world.cell(nx, self.py) == 0:
                self.px = nx
            if self.world.cell(self.px, ny) == 0:
                self.py = ny

        # ─── 传送门事件（P2-5） ───
        # 邻近触发：传送门格(C=12)本身不可踏入（移动只允许空地），
        # 改为扫描 3x3 邻域，靠近时每帧按概率传送
        near_portal = False
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if self.world.cell(self.px + dx, self.py + dy) == 12:
                    near_portal = True
                    break
            if near_portal:
                break
        if near_portal and random.random() < PORTAL_TELEPORT_CHANCE:
            # 随机传送到远处（5~15个区块距离）
            offset_cx = random.choice([-1, 1]) * random.randint(5, 15)
            offset_cy = random.choice([-1, 1]) * random.randint(5, 15)
            cur_c = self.world.world_to_chunk(self.px, self.py)
            target_cx = cur_c[0] + offset_cx
            target_cy = cur_c[1] + offset_cy
            # 确保目标区块已生成
            self.world.ensure_neighbors(target_cx, target_cy)
            # 寻找安全出生点
            spawn = self.world.find_safe_spawn(target_cx, target_cy)
            self.px, self.py = spawn
            self.last_chunk = (target_cx, target_cy)
            # 传送音效
            self.sfx.play_shield()
        
        # 区块边缘检测
        cur_chunk = self.world.world_to_chunk(self.px, self.py)
        if cur_chunk != self.last_chunk:
            self.last_chunk = cur_chunk
            self.world.ensure_neighbors(cur_chunk[0], cur_chunk[1])
        
        # ─── 2. 能量更新 ───
        # 单次 5x5 邻域扫描：发光柱(2)恢复 / 红色警示区(3)消耗 / 酸液池(5)消耗
        near_glow = near_red = near_acid = False
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                ct = self.world.cell(self.px + dx, self.py + dy)
                if ct == 2:
                    near_glow = True
                elif ct == 3:
                    near_red = True
                elif ct == 5:
                    near_acid = True
            if near_glow and near_red and near_acid:
                break

        drain_mult = self.abilities.get_drain_multiplier()
        shielded = self.abilities.is_danger_immune()
        self.energy.update(dt, is_moving, near_glow, near_red, near_acid, drain_mult, shielded)
        
        # 能量耗尽 → 死亡
        if self.energy.is_dead:
            self.state = GameState.GAME_OVER
            return
        
        # ─── 3. 探索追踪 ───
        self.exploration.check_and_mark(self.px, self.py, self.world)
        
        # ─── 4. 能力更新 ───
        self.abilities.update(dt)
        
        # ─── 5. 危险检测 ───
        self._danger_near = False
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                ct = self.world.cell(self.px + dx, self.py + dy)
                if ct == 3:  # 红色区
                    self._danger_near = True
                    break
            if self._danger_near:
                break
        
        # 危险预警蜂鸣
        if self._danger_near and not shielded:
            self.sfx.play_warning()
        
        # ─── 6. 区域/音频/粒子 ───
        self._update_zone()
        self._update_audio()
        self._update_particles()
        
        # ─── 7. 渲染 ───
        self._render()
    
    def _update_zone(self):
        """基于当前区块检测区域音效（切换区块时随机选择音乐）"""
        if self.world is None or self.synth is None:
            return
        cx, cy = self.world.world_to_chunk(self.px, self.py)
        if (cx, cy) != self._last_zone_chunk:
            self._last_zone_chunk = (cx, cy)
            # 随机选择音乐区域（2-12），每次进入新区块都随机
            zone = random.randint(2, 12)
            self.dominant_zone = zone
            self.synth.set_zone(zone)
    
    def _update_audio(self):
        """调度音频"""
        if self.synth is None:
            return
        now = time.monotonic()
        if now - self.last_sound_t >= BEAT * 0.46:
            snd = self.synth.pop_sound()
            if snd is not None:
                snd.play()
                self.last_sound_t = now
                self.active_sounds.append(snd)
                if len(self.active_sounds) > 16:
                    self.active_sounds = self.active_sounds[-16:]
    
    def _update_particles(self):
        """更新粒子"""
        if self.world is None:
            return
        self.part_timer += 1
        if self.part_timer % 8 == 0:
            scan_range = 5
            base_wx = int(self.px) - scan_range
            base_wy = int(self.py) - scan_range
            for dy_i in range(scan_range * 2 + 1):
                for dx_i in range(scan_range * 2 + 1):
                    wx_i = base_wx + dx_i
                    wy_i = base_wy + dy_i
                    ct = self.world.cell(wx_i + 0.5, wy_i + 0.5)
                    if ct >= 2:
                        ddx = wx_i + 0.5 - self.px
                        ddy = wy_i + 0.5 - self.py
                        dist2 = ddx * ddx + ddy * ddy
                        if dist2 < 20 and random.random() < 0.3:
                            rel_ang = math.atan2(ddy, ddx) - self.pang
                            dist = math.sqrt(dist2) + 0.01
                            sx = int(W / 2 + math.tan(rel_ang) * (W / 2))
                            sy = int(H / 2 + random.uniform(-60, 60) / dist)
                            if 0 <= sx < W and 0 <= sy < H:
                                self.particles.append(Particle(sx, sy, ct))
        
        # ─── 漂浮拾取物效果（P2-3） ───
        # 在可交互装饰物附近额外生成浮动粒子
        if self.part_timer % 16 == 0:
            nearest = self.interaction.find_nearest_deco(
                self.px, self.py, self.world, self.fragments)
            if nearest is not None:
                wx, wy, deco_type, _ = nearest
                ddx = wx + 0.5 - self.px
                ddy = wy + 0.5 - self.py
                rel_ang = math.atan2(ddy, ddx) - self.pang
                dist = math.sqrt(ddx * ddx + ddy * ddy) + 0.01
                sx = int(W / 2 + math.tan(rel_ang) * (W / 2))
                sy = int(H / 2 - 30 / dist)
                if 0 <= sx < W and 0 <= sy < H:
                    # 生成浮动上升粒子
                    for _ in range(2):
                        p = Particle(sx + random.randint(-8, 8),
                                     sy + random.randint(-5, 5), deco_type)
                        p.vy = -random.uniform(0.5, 1.5)  # 向上浮动
                        p.vx = random.uniform(-0.3, 0.3)
                        self.particles.append(p)
        
        self.particles = [p for p in self.particles if p.update()]
    
    def _render(self):
        """渲染画面（集成增强系统）"""
        if self.world is None or self.renderer is None:
            return

        # 计算有效视野深度
        depth_mult = self.abilities.get_depth_multiplier()
        cur_cx, cur_cy = self.world.world_to_chunk(self.px, self.py)
        is_dark = self.world.is_dark_room(cur_cx, cur_cy)
        dark_factor = 0.6 if is_dark else 1.0
        effective_max_depth = MAX_DEPTH * depth_mult * dark_factor

        # 渲染后端统一入口（GL → scene FBO；2D 后端 → 直接画到 canvas）
        self.renderer.draw_world(self.px, self.py, self.pang, self.pitch,
                                 self.zbuf, self.world, effective_max_depth)

        if self.use_gl:
            self.canvas.fill((0, 0, 0, 0))       # 2D 覆盖层清空为透明

        for p in self.particles:
            p.draw(self.canvas, self.renderer)

        self.renderer.render_scanlines()
        if self.vignette and not self.use_gl:    # GL 的暗角在后处理 shader 里
            self.canvas.blit(self.vignette, (0, 0))

        # 图鉴页（Tab切换）
        if self.show_codex:
            draw_codex(self.canvas, self.f_sm, self.fragments)

        # HUD（含能量/碎片/交互提示）
        cur_chunk = self.world.world_to_chunk(self.px, self.py)
        interaction_in_range = self.interaction.is_in_range(
            self.px, self.py, self.world, self.fragments)
        draw_hud(self.canvas, self.f_sm, self.f_bg, self.tick,
                 (self.px, self.py), cur_chunk, self.dominant_zone,
                 energy=self.energy, fragments=self.fragments,
                 interaction_in_range=interaction_in_range,
                 shielded=self.energy.is_shielded(),
                 danger_near=self._danger_near)

        self._present()

    def _handle_game_over(self, dt: float):
        """处理死亡结算状态"""
        if not self._grab_released:
            self._grab_released = True
            pygame.event.set_grab(False)
            pygame.mouse.set_visible(True)
        self.tick += 1

        # 事件处理
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.state = GameState.QUIT
                return
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_r:
                    self._restart()
                    return
                elif ev.key == pygame.K_ESCAPE:
                    self.state = GameState.QUIT
                    return

        # 渲染游戏场景（冻结）
        if self.world is not None and self.renderer is not None:
            self.renderer.draw_world(self.px, self.py, self.pang, self.pitch,
                                     self.zbuf, self.world, MAX_DEPTH)
            if self.use_gl:
                self.canvas.fill((0, 0, 0, 0))
            self.renderer.render_scanlines()
            if self.vignette and not self.use_gl:
                self.canvas.blit(self.vignette, (0, 0))

        # 计算并保存最高分
        score = DeathScreen.calculate_score(
            self.fragments, self.survival_time, self.exploration.get_explored_count())
        best = load_highscore()
        save_highscore(score)
        new_best = max(best, score)

        # 叠加结算画面（含最高分）
        DeathScreen.draw(self.canvas, self.f_sm, self.f_bg,
                         self.fragments, self.survival_time,
                         self.exploration.get_explored_count(), self.tick)
        # 最高分显示
        if new_best > 0:
            sw = self.canvas.get_width()
            hs_col = (255, 255, 100) if score >= best else (120, 120, 140)
            hs_text = self.f_sm.render(f"BEST: {new_best}", True, hs_col)
            self.canvas.blit(hs_text, (sw // 2 - hs_text.get_width() // 2, H * 3 // 4 - 30))
        self._present()

    def _restart(self):
        """重置所有系统，返回开始界面"""
        # 重置增强系统（图鉴不清除）
        self.energy.reset()
        self.fragments.reset()
        self.exploration.reset()
        self.abilities = AbilitySystem(self.fragments)
        self.markers.clear()

        # 重置玩家状态
        self.px, self.py, self.pang = 10.5, 10.5, 0.0
        self.pitch = 0.0
        self.survival_time = 0.0
        self.tick = 0
        self.particles.clear()
        self.dominant_zone = 2
        self._danger_near = False
        self._last_zone_chunk = (0, 0)
        self.show_codex = False

        # 重新生成世界
        self.world = None
        self.synth = None
        self.vignette = None
        self.preload_manager = None
        # GL 渲染器跨局复用（OPENGL 窗口不能没有它持续 present），只解绑世界
        self.renderer = self.gl_renderer
        if self.renderer is not None:
            self.renderer.set_world(None)

        # 返回开始界面
        self.state = GameState.START_SCREEN
        self._start_animate = 0.0
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
        self._grab_released = True
