# 使用 pygame_ce（社区版）替代 pygame
try:
    import pygame_ce as pygame
    import pygame_ce.freetype as pygame_freetype
except ImportError:
    import pygame
    import pygame.freetype as pygame_freetype
from ui_base import BaseUI
from game_engine import GameEngine
import textwrap

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
FPS = 60

COLOR_BG = (30, 28, 24)
COLOR_PARCHMENT = (240, 230, 210)
COLOR_GOLD = (212, 175, 55)
COLOR_RED = (160, 40, 40)
COLOR_GREEN = (60, 140, 60)
COLOR_PURPLE = (120, 60, 120)
COLOR_TEXT = (220, 220, 220)
COLOR_DIM = (140, 130, 120)

PANEL_PADDING = 20
BAR_WIDTH = 200
BAR_HEIGHT = 16
OPTION_HEIGHT = 50

class PygameUI(BaseUI):
    def __init__(self):
        pygame.init()
        pygame_freetype.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("十二试炼 · 神话重构")
        # 使用系统默认字体避免缺失文件
        default_font = pygame_freetype.get_default_font()
        self.font_title = pygame_freetype.Font(default_font, 36)
        self.font_header = pygame_freetype.Font(default_font, 24)
        self.font_text = pygame_freetype.Font(default_font, 20)
        self.font_small = pygame_freetype.Font(default_font, 16)
        self.clock = pygame.time.Clock()
        self.running = False
        self.engine = None
        self.option_rects = []
        self.typing_index = 0
        self.typing_text = ""
        self.typing_speed = 2
        self.typing_timer = 0
        self._cached_event = None  # 缓存当前事件，避免渲染时触发状态推进

    def run(self, engine: GameEngine):
        self.engine = engine
        self.running = True
        self._cached_event = engine.get_current_event()
        if self._cached_event:
            self.start_typing(self._cached_event.get('text', ''))
        while self.running:
            dt = self.clock.tick(FPS)
            self.handle_events()
            self.update(dt)
            self.draw()
        # 游戏结束后显示终局报告（须在 pygame.quit 之前，否则 screen 已销毁）
        endings = engine.check_endings()
        self.show_post_game_report(engine, endings)
        pygame.quit()
        return endings

    def _wait_for_key(self):
        """等待任意按键或点击继续（替代固定延时）"""
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type in (pygame.QUIT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    waiting = False
            self.clock.tick(30)

    def show_post_game_report(self, engine: GameEngine, endings: list):
        """显示终局报告"""
        self.screen.fill((15, 15, 15))
        y = 50

        # 标题
        self.font_title.render_to(self.screen, (SCREEN_WIDTH//2-150, y), "【试 炼 报 告】", COLOR_GOLD)
        y += 60

        # 基本信息
        self.font_header.render_to(self.screen, (50, y), f"英雄：{engine.character_name}", COLOR_TEXT)
        y += 35
        self.font_text.render_to(self.screen, (50, y), f"试炼次数：{engine.turn}", COLOR_TEXT)
        y += 30
        path_str = engine.get_path_sequence_cn()
        self.font_text.render_to(self.screen, (50, y), f"路径：{path_str}", COLOR_DIM)
        y += 50

        # 属性显示
        self.font_header.render_to(self.screen, (50, y), "属性概览", COLOR_GOLD)
        y += 35
        s = engine.stats
        for stat in ['荣耀', '力量', '智慧', '神恩', '疯狂', '生命']:
            value = s.get(stat, 0)
            bar = '█' * min(value, 20) + '░' * max(0, 20 - value)
            self.font_text.render_to(self.screen, (50, y), f"{stat:<4}", COLOR_TEXT)
            self.font_text.render_to(self.screen, (120, y), f"[{bar}]", COLOR_DIM)
            self.font_text.render_to(self.screen, (600, y), f"{'+' if value > 10 else ''}{value}", COLOR_TEXT)
            y += 28

        # 隐藏第十三试炼检测
        if engine.check_hidden_labor_trigger():
            y += 20
            self.font_header.render_to(self.screen, (50, y), "【隐藏触发】", COLOR_PURPLE)
            y += 35
            hidden_text = "在通关的光芒中，你似乎听到了第十三个心跳。"
            self.font_text.render_to(self.screen, (50, y), hidden_text, COLOR_DIM)

        self.font_small.render_to(self.screen, (50, SCREEN_HEIGHT-40), "按任意键继续...", COLOR_DIM)
        pygame.display.flip()
        self._wait_for_key()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key in (pygame.K_1, pygame.K_KP1):
                    self.select_option(0)
                elif event.key in (pygame.K_2, pygame.K_KP2):
                    self.select_option(1)
                elif event.key in (pygame.K_3, pygame.K_KP3):
                    self.select_option(2)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    for i, rect in enumerate(self.option_rects):
                        if rect.collidepoint(event.pos):
                            self.select_option(i)

    def update(self, dt):
        if self.typing_index < len(self.typing_text):
            self.typing_timer += dt
            if self.typing_timer >= 1000 / self.typing_speed:
                self.typing_index += 1
                self.typing_timer = 0

    def draw(self):
        self.screen.fill(COLOR_BG)
        self.draw_status_panel()
        self.draw_event_panel()
        self.draw_options_panel()
        self.draw_turn_info()
        pygame.display.flip()

    def draw_status_panel(self):
        s = self.engine.stats
        panel_rect = pygame.Rect(PANEL_PADDING, PANEL_PADDING, SCREEN_WIDTH - PANEL_PADDING*2, 140)
        pygame.draw.rect(self.screen, (20, 20, 20), panel_rect, border_radius=8)
        pygame.draw.rect(self.screen, COLOR_GOLD, panel_rect, 2, border_radius=8)
        x, y = panel_rect.x + 20, panel_rect.y + 20
        self.font_header.render_to(self.screen, (x, y), f"⚔️ {self.engine.character_name}", COLOR_GOLD)

        # 章节进度
        chapter_num = self.engine.current_labour_index + 1
        total = self.engine.total_labours
        self.font_small.render_to(self.screen, (x+300, y),
                                  f"第 {chapter_num}/{total} 试炼 | 回合 {self.engine.turn}", COLOR_DIM)

        bar_y = y + 40
        self.draw_stat_bar(x, bar_y, "荣耀", s.get('荣耀',0), 20, COLOR_GOLD)
        self.draw_stat_bar(x+220, bar_y, "力量", s.get('力量',0), 20, COLOR_RED)
        self.draw_stat_bar(x+440, bar_y, "智慧", s.get('智慧',0), 20, COLOR_GREEN)
        self.draw_stat_bar(x+660, bar_y, "神恩", s.get('神恩',0), 20, COLOR_PURPLE)
        bar_y += 30
        self.draw_stat_bar(x, bar_y, "疯狂", s.get('疯狂',0), 20, COLOR_PURPLE)
        self.draw_stat_bar(x+220, bar_y, "生命", s.get('生命',0), 20, COLOR_RED)

        # 遗物显示
        relics = self.engine.relics
        if relics:
            relic_text = "📿 " + "、".join([r['name'] for r in relics])
            self.font_small.render_to(self.screen, (x, bar_y+35), relic_text, COLOR_DIM)

        # 章节特殊机制状态
        mechanic = self.engine.world_state.get('active_mechanic')
        if mechanic:
            mechanic_names = {
                'hydra_regen': '⚠ 九头蛇再生',
                'filth': '⚠ 污秽侵蚀',
                'time_curse': '⚠ 时间诅咒'
            }
            mech_text = mechanic_names.get(mechanic, f'⚠ {mechanic}')
            self.font_small.render_to(self.screen, (x+400, bar_y+35), mech_text, COLOR_RED)

    def draw_stat_bar(self, x, y, name, value, max_val, color):
        self.font_small.render_to(self.screen, (x, y-5), name, COLOR_TEXT)
        pygame.draw.rect(self.screen, (60,60,60), (x, y, BAR_WIDTH, BAR_HEIGHT))
        fill_width = int((value/max_val)*BAR_WIDTH)
        if fill_width>0:
            pygame.draw.rect(self.screen, color, (x, y, fill_width, BAR_HEIGHT))
        pygame.draw.rect(self.screen, COLOR_GOLD, (x, y, BAR_WIDTH, BAR_HEIGHT), 1)
        self.font_small.render_to(self.screen, (x+BAR_WIDTH+10, y-2), f"{value}/{max_val}", COLOR_TEXT)

    def draw_event_panel(self):
        event = self._cached_event
        if not event: return
        panel_rect = pygame.Rect(PANEL_PADDING, 160, SCREEN_WIDTH - PANEL_PADDING*2, 280)
        pygame.draw.rect(self.screen, (20,20,20), panel_rect, border_radius=8)
        pygame.draw.rect(self.screen, COLOR_GOLD, panel_rect, 2, border_radius=8)
        x, y = panel_rect.x+20, panel_rect.y+20
        self.font_header.render_to(self.screen, (x, y), event.get('title','未知事件'), COLOR_GOLD)
        pygame.draw.line(self.screen, COLOR_GOLD, (x, y+40), (panel_rect.right-20, y+40), 2)
        text_x, text_y = x, y+60
        display_text = self.typing_text[:self.typing_index]
        wrapped = textwrap.wrap(display_text, width=70)
        for i, line in enumerate(wrapped):
            self.font_text.render_to(self.screen, (text_x, text_y+i*28), line, COLOR_TEXT)

    def draw_options_panel(self):
        event = self._cached_event
        if not event: return
        options = event.get('options', [])
        self.option_rects = []
        start_y = 460
        for i, opt in enumerate(options):
            rect = pygame.Rect(PANEL_PADDING, start_y+i*(OPTION_HEIGHT+10), SCREEN_WIDTH-PANEL_PADDING*2, OPTION_HEIGHT)
            self.option_rects.append(rect)
            pygame.draw.rect(self.screen, (50,45,40), rect, border_radius=6)
            pygame.draw.rect(self.screen, COLOR_GOLD, rect, 2, border_radius=6)
            self.font_text.render_to(self.screen, (rect.x+20, rect.y+15), f"[{i+1}] {opt['text']}", COLOR_TEXT)
            req = opt.get('required_stat', {})
            if req:
                req_text = "需求: " + ", ".join([f"{k}≥{v}" for k,v in req.items()])
                self.font_small.render_to(self.screen, (rect.x+400, rect.y+17), req_text, COLOR_DIM)

    def draw_turn_info(self):
        info = "ESC: 退出 | 1-3: 选择 | 鼠标点击"
        self.font_small.render_to(self.screen, (PANEL_PADDING, SCREEN_HEIGHT-30), info, COLOR_DIM)

    def start_typing(self, text):
        self.typing_text = text
        self.typing_index = 0
        self.typing_timer = 0

    def select_option(self, index):
        event = self._cached_event
        if not event or index >= len(event.get('options', [])):
            return
        success, text, _ = self.engine.process_option(event, index)
        self.start_typing(text)
        # 注：apply_turn_end_effects() 已在 process_option() 内部调用，此处无需重复
        if not self.engine.is_alive():
            self.show_death_screen()
            self.running = False
            return
        endings = self.engine.check_endings()
        if endings:
            self.show_ending_screen(endings[0])
            self.running = False
            return
        # 只在状态变更时刷新缓存事件（避免渲染时触发 get_current_event 副作用）
        self._cached_event = self.engine.get_current_event()
        if self._cached_event:
            self.start_typing(self._cached_event.get('text', ''))

    def show_death_screen(self):
        self.screen.fill((20,0,0))
        self.font_title.render_to(self.screen, (SCREEN_WIDTH//2-150, SCREEN_HEIGHT//2-50), "英雄陨落", COLOR_RED)
        self.font_header.render_to(self.screen, (SCREEN_WIDTH//2-200, SCREEN_HEIGHT//2+20), self.engine.get_death_reason(), COLOR_TEXT)
        self.font_small.render_to(self.screen, (SCREEN_WIDTH//2-60, SCREEN_HEIGHT//2+80), "按任意键继续...", COLOR_DIM)
        pygame.display.flip()
        self._wait_for_key()

    def show_ending_screen(self, ending):
        self.screen.fill((10,10,20))
        self.font_title.render_to(self.screen, (SCREEN_WIDTH//2-150, SCREEN_HEIGHT//2-100), ending['name'], COLOR_GOLD)
        wrapped = textwrap.wrap(ending['text'], width=50)
        for i, line in enumerate(wrapped):
            self.font_text.render_to(self.screen, (SCREEN_WIDTH//2-250, SCREEN_HEIGHT//2+i*30), line, COLOR_TEXT)
        self.font_small.render_to(self.screen, (SCREEN_WIDTH//2-60, SCREEN_HEIGHT//2+120), "按任意键继续...", COLOR_DIM)
        pygame.display.flip()
        self._wait_for_key()