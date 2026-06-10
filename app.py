"""
斯金纳箱 · 表情版  —  模块化重构 + 风扇背景
按 空格 签到，按 E 切换表情浏览模式，按 H 查看历史
风扇在背景自主运行，恶搞音效作为环境音
"""
import pygame
import sys
import os

# ── 初始化 ────────────────────────────────────────────────────
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)

# ── 修复 pygame SysFont 在 Windows + Python 3.14 上枚举字体时收到非字符串类型的 bug ──
import pygame.sysfont as _sysfont

_orig_initsysfonts_win32 = _sysfont.initsysfonts_win32


def _safe_initsysfonts_win32():
    """包装原函数，捕获 TypeError 并回退到安全的手动字体枚举"""
    try:
        return _orig_initsysfonts_win32()
    except TypeError:
        pass

    # 回退：手动枚举 Windows Fonts 目录，过滤掉非字符串条目
    fonts = {}
    systemroot = os.environ.get("SystemRoot", "C:\\Windows")
    fontdir = os.path.join(systemroot, "Fonts")
    OpenType_extensions = _sysfont.OpenType_extensions
    try:
        for fname in os.listdir(fontdir):
            if not isinstance(fname, str):
                continue
            name, ext = os.path.splitext(fname)
            if ext.lower() in OpenType_extensions:
                fonts.setdefault(name, []).append(os.path.join(fontdir, fname))
    except OSError:
        pass
    return fonts


_sysfont.initsysfonts_win32 = _safe_initsysfonts_win32

WIDTH, HEIGHT = 1000, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("斯金纳箱 · 表情版")

BG_COLOR = (25, 25, 35)

# ── 项目路径 ──────────────────────────────────────────────────
SMILE_DIR = os.path.dirname(os.path.abspath(__file__))
QIANDAO_DIR = os.path.join(os.path.dirname(SMILE_DIR), "qiandao")
FAN_SOUNDS_DIR = os.path.join(SMILE_DIR, "fan_sounds")

# ── 导入模块 ──────────────────────────────────────────────────
sys.path.insert(0, SMILE_DIR)

from core.audio import AudioManager
from core.qiandao import QiandaoState
from core.face_engine import FaceEngine
from core.fan_engine import FanEngine
from core.expression_map import result_to_expression
from ui.sign_panel import SignPanel
from ui.browse_panel import BrowsePanel
from ui.history_panel import HistoryPanel


# ══════════════════════════════════════════════════════════════
#  风扇音效管理器 — 根据风扇速度切换恶搞音效
# ══════════════════════════════════════════════════════════════

class FanSoundController:
    """根据风扇 RPM 自动切换恶搞音效层级"""

    # RPM 阈值 -> (音效名, 基础音量)
    LAYERS = [
        (0,    "idle_purr",        0.08),   # 静止/极低速 → 猫打呼噜
        (120,  "low_buzz",         0.10),   # 低速 → 蜜蜂嗡嗡
        (250,  "medium_siren",     0.10),   # 中速 → 警笛
        (400,  "high_jetfart",     0.12),   # 高速 → 喷气放屁
    ]

    def __init__(self, audio_mgr, fan_sounds_dir):
        self.audio = audio_mgr
        self.current_layer = -1
        # 预加载所有风扇音效
        for _, name, _ in self.LAYERS:
            path = os.path.join(fan_sounds_dir, f"{name}.wav")
            self.audio.load_fan_sound(name, path)
        # 预加载启动/停止音效
        for sfx_name in ("startup_beep", "shutdown_trombone", "click"):
            path = os.path.join(fan_sounds_dir, f"{sfx_name}.wav")
            self.audio.load_fan_sound(sfx_name, path)
        # 预加载故障音效
        for sfx_name in ("wobble_ding", "scrape_squeak", "bearing_boom"):
            path = os.path.join(fan_sounds_dir, f"{sfx_name}.wav")
            self.audio.load_fan_sound(sfx_name, path)
        # 风声
        wind_path = os.path.join(fan_sounds_dir, "wind_howl.wav")
        self.audio.load_fan_sound("wind_howl", wind_path)

    def startup(self):
        """风扇启动时播放启动音效"""
        self.audio.play_fan_once("startup_beep", volume=0.2, channel_idx=2)
        self.audio.play_fan_once("click", volume=0.15, channel_idx=3)

    def update(self, rpm, speed_ratio):
        """根据 RPM 切换音效层级"""
        # 找到最大满足条件的层
        target_layer = 0
        for i, (threshold, _, _) in enumerate(self.LAYERS):
            if rpm >= threshold:
                target_layer = i

        if target_layer != self.current_layer:
            # 切换音效
            if self.current_layer >= 0:
                self.audio.stop_fan(channel_idx=0)
            self.current_layer = target_layer
            _, name, base_vol = self.LAYERS[target_layer]
            # 音量随速度比例微调
            vol = base_vol + speed_ratio * 0.05
            self.audio.play_fan_loop(name, volume=vol, channel_idx=0)

        # 风声音量也随速度变化
        wind_vol = speed_ratio * 0.06
        if speed_ratio > 0.1:
            # 只在有风时播放
            try:
                ch = self.audio._fan_channels[1]
                if not ch.get_busy():
                    self.audio.play_fan_loop("wind_howl", volume=wind_vol, channel_idx=1)
                else:
                    self.audio.set_fan_volume(wind_vol, channel_idx=1)
            except (IndexError, AttributeError):
                pass
        else:
            self.audio.stop_fan(channel_idx=1)


# ══════════════════════════════════════════════════════════════
#  主应用
# ══════════════════════════════════════════════════════════════

class SkinnerFaceApp:
    """斯金纳箱 · 表情版 — 签到驱动的表情模拟器 + 风扇背景"""

    def __init__(self):
        # 音频管理器（最先初始化，分配通道）
        self.audio = AudioManager(SMILE_DIR)
        self.audio.init()

        # 签到系统
        self.qd = QiandaoState(QIANDAO_DIR)

        # 表情系统
        self.face = FaceEngine("expressions.json", base_dir=SMILE_DIR, audio_manager=self.audio)

        # 风扇系统
        self.fan = FanEngine()
        self.fan_sound = FanSoundController(self.audio, FAN_SOUNDS_DIR)
        self.fan_sound.startup()

        # UI 面板
        self.sign_panel = SignPanel(self.qd, self.face, self.audio)
        self.browse_panel = BrowsePanel(self.face)
        self.history_panel = HistoryPanel(self.qd)

        # 状态
        self.mode = "sign"       # "sign" | "browse"
        self.show_history = False

        # 初始表情
        self._update_idle_expression()

    def _update_idle_expression(self):
        if self.qd.last_result:
            streak = self.qd.no_reward_streak
            if streak == 0:
                self.face.set_expression("default", play_sound=False)
            else:
                expr = result_to_expression(self.qd.last_result)
                self.face.set_expression(expr, play_sound=False)
        else:
            self.face.set_expression("default", play_sound=False)

    def _sign_btn_rect(self):
        """签到按钮位置（需要与 SignPanel 一致）"""
        panel_x = WIDTH // 2 + 10
        panel_w = WIDTH // 2 - 30
        cx = panel_x + panel_w // 2
        # cy 在 panel y=20 + pad=20 + 50 + 28 + 35 + 30 = ~183
        return pygame.Rect(cx - 100, 183, 200, 55)

    def run(self):
        clock = pygame.time.Clock()
        running = True

        while running:
            dt = clock.get_time() / 1000.0

            # ── 事件处理 ──
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_click(event.pos)
                elif event.type == pygame.MOUSEWHEEL:
                    if self.show_history:
                        self.history_panel.handle_scroll(event.y)

            # ── 更新 ──
            self.face.update(dt)
            rpm = self.fan.update()
            self.fan_sound.update(rpm, self.fan.speed_ratio)
            self.sign_panel.update(dt)

            # 签到结果淡出后回归待机表情
            if self.sign_panel.result_display_timer <= 0 and self.sign_panel.result_fade <= 0:
                if self.qd.last_result:
                    self._update_idle_expression()

            # ── 绘制 ──
            screen.fill(BG_COLOR)

            # 1) 风扇背景（左上角 + 右下角，半透明）
            self.fan.draw(screen, 130, 130, 110, alpha=120)
            self.fan.draw(screen, WIDTH - 100, HEIGHT - 100, 80, alpha=80)

            # 2) 前景内容
            if self.show_history:
                self.history_panel.draw(screen, WIDTH, HEIGHT)
            elif self.mode == "sign":
                # 左半边 - 表情
                face_cx = WIDTH // 4
                face_cy = HEIGHT // 2
                self.face.draw_face(screen, face_cx, face_cy, face_scale=0.85, dt=dt)
                # 右半边 - 签到面板
                panel_x = WIDTH // 2 + 10
                panel_w = WIDTH // 2 - 30
                self.sign_panel.draw(screen, panel_x, 20, panel_w, HEIGHT - 40)
            else:
                self.browse_panel.draw(screen, WIDTH, HEIGHT, dt)

            pygame.display.flip()
            clock.tick(60)

        pygame.quit()
        sys.exit()

    def _handle_key(self, key):
        if key == pygame.K_ESCAPE:
            if self.show_history:
                self.show_history = False
            elif self.mode == "browse":
                self.mode = "sign"
            else:
                pygame.event.post(pygame.event.Event(pygame.QUIT))

        elif key == pygame.K_SPACE:
            if self.mode == "sign" and not self.show_history:
                if self.qd.can_sign_today():
                    self.sign_panel.sign()

        elif key == pygame.K_e:
            self.mode = "browse" if self.mode == "sign" else "sign"

        elif key == pygame.K_h:
            self.show_history = not self.show_history

        if self.mode == "browse":
            self.browse_panel.handle_key(key)

    def _handle_click(self, pos):
        if self.mode == "sign" and not self.show_history:
            btn_rect = self._sign_btn_rect()
            self.sign_panel.handle_click(pos, btn_rect)


# ══════════════════════════════════════════════════════════════
#  启动
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = SkinnerFaceApp()
    app.run()
