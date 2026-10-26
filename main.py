# -*- coding: utf-8 -*-
"""
Endless Highway 3D —— 游戏入口。

基于 3dworld 引擎（``pip install 3dworld``）重构：窗口、主循环、HUD、命令行
与截图全部走引擎的 ``world3d.platform.app.DemoApp``（与 3dworld-demos 同一套
范式），本文件只关心"这一帧游戏世界长什么样、怎么动"。

分层：

    main.py          本文件：应用装配（ECS 世界 + 3D 场景 + 音频 + 覆盖层）
    highway_scene.py 3D 表现：程序化几何、跟随相机、绘制
    ecs/             玩法逻辑（与渲染无关）
    audio/           电子配乐与音效（sounddevice 播放）

运行::

    python main.py                 正常游玩
    python main.py --smoke 3       冒烟 3 秒自动关闭
    python main.py --size 1280x720
"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
AUDIO_ASSETS = os.path.join(BASE_DIR, 'audio', 'assets')

# ⚠️ 必须在导入 world3d.platform.app **之前**设置：它在导入时就把
# PROJECT_ROOT（截图/文档落点）算死了，pip 安装后会落到 site-packages 下。
os.environ.setdefault('WORLD3D_PROJECT_ROOT', BASE_DIR)

import pyglet                                                     # noqa: E402
from pyglet.gl import (GL_BLEND, GL_DEPTH_TEST, GL_ONE_MINUS_SRC_ALPHA,  # noqa: E402
                       GL_SRC_ALPHA, glBlendFunc, glDisable, glEnable,
                       glClearColor)
from pyglet.math import Mat4                                      # noqa: E402

from world3d.platform.app import DemoApp, parse_args             # noqa: E402

from ecs import World                                             # noqa: E402
from ecs.components import (Drift, GameState, KeyState, Lateral,  # noqa: E402
                            Position, VehicleControl)
from ecs.systems import (CollisionSystem, DecorationScrollSystem,  # noqa: E402
                         DecorationSpawnSystem, DriftSystem, InputSystem,
                         MotionSystem, ScrollSystem)
from highway_scene import ChaseCamera, HighwayScene, make_key_state_reader  # noqa: E402
from audio.audio_manager import AudioManager                      # noqa: E402
from audio.ecs_system import AudioSystem, ensure_audio_assets, set_audio_manager  # noqa: E402
from recorder import FrameRecorder                                 # noqa: E402


def extract_app_args(argv):
    """取出本项目自有的开关（引擎的 parse_args 不认识），其余原样传回去。

    自有开关：
        --record=PATH        实机录像（rawvideo → ffmpeg 管道）
        --record-audio=PATH  录像同时把混音输出落成 WAV（供后续封装）
        --autopilot          自动驾驶（演示/录像用：把车稳在路中间）
        --demo               演示编排：自动驾驶 + 暂停展示 + 末尾撞毁
        --demo-crash-at=SEC  演示模式里第几秒开始冲向路肩（默认 160）
        --exit-after=SEC     运行 SEC 秒后自动退出
    """
    app_args = {
        'record': None, 'record_audio': None, 'autopilot': False,
        'demo': False, 'demo_crash_at': 160.0, 'exit_after': None,
    }
    rest = []
    for a in argv:
        if a.startswith('--record='):
            app_args['record'] = a.split('=', 1)[1]
        elif a.startswith('--record-audio='):
            app_args['record_audio'] = a.split('=', 1)[1]
        elif a.startswith('--demo-crash-at='):
            app_args['demo_crash_at'] = float(a.split('=', 1)[1])
        elif a.startswith('--exit-after='):
            app_args['exit_after'] = float(a.split('=', 1)[1])
        elif a == '--autopilot':
            app_args['autopilot'] = True
        elif a == '--demo':
            app_args['demo'] = True
            app_args['autopilot'] = True
        else:
            rest.append(a)
    return app_args, rest


def load_config(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_world(cfg: dict, key_state: KeyState) -> World:
    """创建 ECS 世界：装配实体与系统（顺序 = 执行顺序）。"""
    world = World()
    c3 = cfg.get('threed', {})
    r = cfg.get('road', {})
    p = cfg.get('player', {})
    d = cfg.get('drift', {})

    hw = float(c3.get('road_half_width', 6.0))
    car_hw = float(c3.get('car_half_width', 1.1))
    world_scroll = float(c3.get('world_scroll', 80.0))
    dash_period = float(c3.get('dash_count', 56)) * (
        float(c3.get('dash_length', 3.0)) + float(c3.get('dash_gap', 4.0)))

    # ── 玩家车（固定 z=0，靠 x 横向移动）────────────────────
    player = world.create_entity()
    world.add_component(player, Position(x=0.0, y=0.0, z=0.0))
    world.add_component(player, VehicleControl())
    world.add_component(player, Lateral(vx=0.0))
    world.add_component(player, Drift(
        chance=d.get('chance', 0.012),
        min_push=d.get('min_push', 0.5),
        max_push=d.get('max_push', 0.6),
    ))

    # ── 全局状态单例 ────────────────────────────────────────
    state_entity = world.create_entity()
    world.add_component(state_entity, GameState())

    # ── 系统 ────────────────────────────────────────────────
    world.add_system(InputSystem(key_state,
                                 steer_accel=float(c3.get('steer_accel', 22.0))))
    world.add_system(MotionSystem(drag=float(c3.get('lateral_drag', 3.2))))
    world.add_system(DriftSystem(
        scale_per_km=d.get('scale_per_km', 0.012),
        world_scale=float(c3.get('drift_world_scale', 12.0))))
    world.add_system(CollisionSystem(road_half_width=hw, car_half_width=car_hw))
    world.add_system(ScrollSystem(
        scroll_speed=r.get('scroll_speed', 5),
        distance_factor=r.get('distance_factor', 0.01),
        world_scroll=world_scroll,
        dash_period=dash_period))
    world.add_system(DecorationSpawnSystem(
        cfg.get('decorations', {}), road_half_width=hw,
        far_z=float(c3.get('deco_spawn_z', -150.0))))
    world.add_system(DecorationScrollSystem(
        world_scroll=world_scroll, near_z=float(c3.get('road_near_z', 14.0))))
    return world


class HighwayApp(DemoApp):
    """Endless Highway 的 3D 应用。"""

    TITLE = 'Endless Highway 3D'
    HELP = '← →  转向      SPACE  暂停/继续      ESC  退出'
    FOV = 62.0
    Z_NEAR, Z_FAR = 0.5, 900.0
    # --shot 抓帧时刻（相对启动秒数）→ 落点（相对仓库根）
    SHOTS = ((2.0, 'docs/highway_3d.png'),)

    def __init__(self, width=1280, height=720, args=None, app_args=None):
        # 窗口标题在 DemoApp.__init__ 里由 TITLE 类属性决定（pyglet 的
        # window.caption 是只读的），所以先把配置里的标题写进类属性。
        self.cfg = load_config(CONFIG_PATH)
        self.c3 = self.cfg.get('threed', {})
        self.app_args = app_args or {}
        type(self).TITLE = self.cfg.get('window', {}).get('title', self.TITLE)
        # 调试开关：--flag crash —— 首帧直接撞毁，用于验证结束界面
        self.crash_flag = 'crash' in getattr(args, 'flags', set())
        if self.crash_flag:
            type(self).SHOTS = ((2.0, 'docs/highway_crash.png'),)
        super().__init__(width, height, args=args)

    def setup(self):
        """创建 GL 资源（窗口上下文已就绪）。"""
        cfg, self.c3 = self.cfg, self.cfg.get('threed', {})

        # 天空色（window.clear() 只清缓冲，不会重设清除色）
        sky = self.c3.get('sky_color', (0.72, 0.82, 0.92))
        glClearColor(float(sky[0]), float(sky[1]), float(sky[2]), 1.0)
        glEnable(GL_DEPTH_TEST)

        # 键盘（ECS 侧只见 KeyState，不依赖 pyglet）
        self.read_keys = make_key_state_reader(self.window)
        self.key_state = KeyState()

        # 3D 场景 + 跟随相机
        self.scene = HighwayScene(self.c3).build()
        self.camera = ChaseCamera(
            height=float(self.c3.get('camera_height', 4.5)),
            back=float(self.c3.get('camera_back', 11.0)),
            look_ahead=float(self.c3.get('camera_look_ahead', 30.0)))

        # ECS 世界
        self.world = build_world(cfg, self.key_state)
        self.world.add_system(AudioSystem())

        # 音频（合成电子配乐 + 引擎音 + 音效）
        self.audio_mgr = None
        try:
            paths = ensure_audio_assets(AUDIO_ASSETS)
            am = AudioManager()
            if am.initialize(paths):
                set_audio_manager(am)
                # 录像配音：把混音输出落盘（与视频分开，最后再封装）
                if self.app_args.get('record_audio'):
                    from audio import sd_mixer
                    sd_mixer.enable_recording(self.app_args['record_audio'])
                    print(f"[main] audio recording -> {self.app_args['record_audio']}")
                am.start_music()
                self.audio_mgr = am
        except Exception as e:                 # 无音频设备时静默继续
            print(f"[main] audio unavailable: {e}")

        # 实机录像：帧回读 → ffmpeg rawvideo 管道
        self.recorder = None
        if self.app_args.get('record'):
            self.recorder = FrameRecorder(self.app_args['record'], fps=30)
            self.recorder.start(self.window.width, self.window.height)
            print(f"[main] recording -> {self.recorder.out_path}")

        self._crash_handled = False
        self._demo_t = 0.0
        self._demo_pause_done = False
        self._demo_pause_end = 0.0
        self._build_overlays()
        self._layout_overlays(self.window.width, self.window.height)

        # 调试：首帧就把车推出路肩，触发"撞毁"分支
        if self.crash_flag:
            limit = float(self.c3.get('road_half_width', 6.0)) - \
                float(self.c3.get('car_half_width', 1.1))
            for entity in self.world.get_entities_with(Position, VehicleControl):
                self.world.get_component(entity, Position).x = limit + 0.5
                break

    # ── 覆盖层（暂停 / 结束）─────────────────────────────────
    def _build_overlays(self):
        from pyglet import shapes, text
        from world3d.engine.fonts import resolve_cjk_font

        font_kw = {}
        cjk = resolve_cjk_font()
        if cjk:
            font_kw['font_name'] = cjk

        self.overlay_over = pyglet.graphics.Batch()
        self.ov_dim = shapes.Rectangle(0, 0, 10, 10, color=(12, 8, 6, 175),
                                       batch=self.overlay_over)
        self.ov_title = text.Label('GAME OVER', font_size=56, weight='bold',
                                   color=(255, 92, 72, 255), x=0, y=0,
                                   anchor_x='center', anchor_y='center',
                                   batch=self.overlay_over, **font_kw)
        self.ov_stats = text.Label('', font_size=20, color=(240, 238, 232, 255),
                                    x=0, y=0, anchor_x='center', anchor_y='center',
                                    batch=self.overlay_over, **font_kw)
        self.ov_hint = text.Label('按 ESC 退出', font_size=16,
                                  color=(190, 186, 178, 255), x=0, y=0,
                                  anchor_x='center', anchor_y='center',
                                  batch=self.overlay_over, **font_kw)

        self.overlay_pause = pyglet.graphics.Batch()
        self.pv_dim = shapes.Rectangle(0, 0, 10, 10, color=(10, 10, 14, 120),
                                       batch=self.overlay_pause)
        self.pv_text = text.Label('PAUSED', font_size=42, weight='bold',
                                  color=(255, 224, 96, 255), x=0, y=0,
                                  anchor_x='center', anchor_y='center',
                                  batch=self.overlay_pause, **font_kw)

    def _layout_overlays(self, width, height):
        for rect in (self.ov_dim, self.pv_dim):
            rect.position = (0, 0)
            rect.width, rect.height = width, height
        cx, cy = width // 2, height // 2
        self.ov_title.position = (cx, cy + 46, 0)
        self.ov_stats.position = (cx, cy - 18, 0)
        self.ov_hint.position = (cx, cy - 66, 0)
        self.pv_text.position = (cx, cy, 0)

    def _draw_overlay(self, batch):
        """在屏幕空间绘制覆盖层（切正交投影 → 画 → 还原 3D 状态）。"""
        w, h = self.window.width, self.window.height
        proj, view = self.window.projection, self.window.view
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_DEPTH_TEST)
        self.window.projection = Mat4.orthogonal_projection(0, w, 0, h, -255, 255)
        self.window.view = Mat4()
        batch.draw()
        self.window.projection = proj
        self.window.view = view
        glEnable(GL_DEPTH_TEST)

    # ── 主循环钩子 ────────────────────────────────────────────
    def update(self, dt):
        """推进玩法与相机。注意：基类在暂停时**仍会**调用本方法。"""
        self.read_keys()

        # 演示/录像用的独立时钟：基类在暂停时不累加 self.time，
        # 而演示编排要在暂停期间继续推进，所以自己记一份。
        self._demo_t += dt
        if self.app_args.get('demo'):
            self._demo_beats()
        if self.app_args.get('autopilot') and not self.paused:
            self._autopilot_steer()

        state = self.world.get_singleton(GameState)
        if state is None or self.paused:
            return
        if not state.alive:
            return

        self.world.update(dt)

        # 相机跟随
        for entity in self.world.get_entities_with(Position, VehicleControl):
            pos = self.world.get_component(entity, Position)
            self.camera.update(dt, pos.x)
            break

        # 撞击后处理
        if not state.alive and not self._crash_handled:
            if self.app_args.get('demo') and \
                    self._demo_t < float(self.app_args.get('demo_crash_at', 160.0)):
                # 演示模式：还没到计划的撞毁时刻就撞了 → 原地复活，
                # 保证录像能覆盖完整内容（漂移是随机的，不设保险会中途黑屏）。
                self._revive(state)
                return
            self._crash_handled = True
            if self.audio_mgr is not None:
                self.audio_mgr.stop_music(fade_ms=1500)
            self.ov_stats.text = (f'里程 {state.distance_km:.2f} km     '
                                  f'漂移 {state.drift_count} 次')

    # ── 自动驾驶 / 演示编排（演示与录像用）────────────────────
    def _player_entity(self):
        for entity in self.world.get_entities_with(Position, VehicleControl):
            return entity
        return None

    def _demo_target_x(self):
        """演示模式下车的目标横向位置：平时居中，末段冲向路肩制造撞毁。"""
        crash_at = float(self.app_args.get('demo_crash_at', 160.0))
        if self._demo_t >= crash_at:
            return 20.0
        return 0.0

    def _autopilot_steer(self):
        """比例-微分控制：把车稳在目标横向位置（替玩家操作左右键）。"""
        entity = self._player_entity()
        if entity is None:
            return
        pos = self.world.get_component(entity, Position)
        lat = self.world.get_component(entity, Lateral)
        if pos is None or lat is None:
            return
        err = self._demo_target_x() - pos.x
        desired_vx = max(-6.0, min(6.0, err * 1.8))
        dv = desired_vx - lat.vx
        self.key_state.left = dv < -0.15
        self.key_state.right = dv > 0.15

    def _revive(self, state):
        """演示模式保险丝：把车放回路中间复活，并恢复引擎音。"""
        entity = self._player_entity()
        if entity is not None:
            self.world.get_component(entity, Position).x = 0.0
            self.world.get_component(entity, Lateral).vx = 0.0
        state.alive = True
        if self.audio_mgr is not None:
            try:
                self.audio_mgr.start_engine_sfx()
            except Exception:
                pass

    def _demo_beats(self):
        """演示编排：开头暂停展示 PAUSED 覆盖层，末段撞毁展示 GAME OVER。"""
        if not self._demo_pause_done and self._demo_t >= 6.0:
            self.paused = True
            self._demo_pause_done = True
            self._demo_pause_end = self._demo_t + 3.5
            if self.audio_mgr is not None:
                self.audio_mgr.trigger_sfx('event:/SFX/UI_Pause')
        elif self._demo_pause_done and self.paused and self._demo_t >= self._demo_pause_end:
            self.paused = False
            if self.audio_mgr is not None:
                self.audio_mgr.trigger_sfx('event:/SFX/UI_Resume')

    def render(self):
        """绘制 3D 画面（清屏由基类完成）。"""
        self.scene.render(self.window, self.camera.view(), self.world,
                          self.camera.eye)

        state = self.world.get_singleton(GameState)
        if state is not None and not state.alive:
            self._draw_overlay(self.overlay_over)
        elif self.paused:
            self._draw_overlay(self.overlay_pause)

    def status_text(self):
        state = self.world.get_singleton(GameState)
        km = state.distance_km if state else 0.0
        drifts = state.drift_count if state else 0
        flag = '  [PAUSED]' if self.paused else ''
        return f'{km:8.2f} km   drifts {drifts:3d}   {self.fps:5.1f} fps{flag}'

    def on_key(self, symbol, modifiers):
        """额外按键（ESC / SPACE 由基类处理）。"""
        pass

    def _on_key_press(self, symbol, modifiers):
        """拦截 SPACE：暂停/继续时补一对 UI 音效。"""
        was_paused = self.paused
        super()._on_key_press(symbol, modifiers)
        if symbol == pyglet.window.key.SPACE and self.paused != was_paused:
            if self.audio_mgr is not None:
                self.audio_mgr.trigger_sfx(
                    'event:/SFX/UI_Pause' if self.paused else 'event:/SFX/UI_Resume')

    def _on_resize(self, width, height):
        super()._on_resize(width, height)
        self._layout_overlays(width, height)

    def _on_draw(self):
        """基类画完 3D + HUD 之后再抓帧（此时帧缓冲内容是最终画面）。"""
        super()._on_draw()
        if self.recorder is not None:
            self.recorder.grab(self.window)

    # ── 收尾 ──────────────────────────────────────────────────
    def shutdown(self):
        if self.recorder is not None:
            try:
                path = self.recorder.close()
                print(f'[main] recorded {self.recorder.frames} frames -> {path}')
            except Exception as e:
                print(f'[main] recorder close failed: {e}')
            self.recorder = None
        if self.audio_mgr is not None:
            try:
                self.audio_mgr.shutdown()
            except Exception:
                pass
            self.audio_mgr = None
        try:
            from audio import sd_mixer
            sd_mixer.disable_recording()
        except Exception:
            pass
        try:
            self.scene.dispose()
        except Exception:
            pass


def main():
    cfg = load_config(CONFIG_PATH)
    app_args, argv = extract_app_args(list(sys.argv[1:]))
    if not any(a.startswith('--size') for a in argv):
        w = cfg.get('window', {}).get('width', 1280)
        h = cfg.get('window', {}).get('height', 720)
        argv += ['--size', f'{w}x{h}']

    args = parse_args(argv)
    app = HighwayApp(args.width, args.height, args=args, app_args=app_args)

    if args.smoke is not None:
        pyglet.clock.schedule_once(lambda dt: app.close(), args.smoke)
        print(f'[smoke] auto-close in {args.smoke}s')
    elif args.shot:
        print(f'[shot] planned {len(HighwayApp.SHOTS)} frames, close when done')
    if app_args.get('exit_after'):
        secs = float(app_args['exit_after'])
        pyglet.clock.schedule_once(lambda dt: app.close(), secs)
        print(f'[main] auto-close in {secs}s')
    pyglet.app.run(interval=1 / 60)

    app.shutdown()
    print('EXIT_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
