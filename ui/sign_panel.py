"""
签到面板
"""
import pygame
from .common import draw_rounded_rect, draw_progress_bar, RARITY_COLORS, load_font
from core.qiandao import reinforcement_prob
from core.expression_map import result_to_expression


class SignPanel:
    """签到模式面板：右侧显示签到信息和操作"""

    def __init__(self, qd, face, audio):
        self.qd = qd
        self.face = face
        self.audio = audio
        self.result_display_timer = 0.0
        self.result_fade = 0.0
        self.sign_animation = 0.0
        self.font_lg = load_font(36)
        self.font_md = load_font(24)
        self.font_sm = load_font(18)
        self.font_xs = load_font(14)
        self.btn_rect = pygame.Rect(0, 0, 200, 55)  # 动态存储实际按钮区域

    def sign(self):
        result = self.qd.sign()
        expr = result_to_expression(result)
        self.face.set_expression(expr, play_sound=True)
        self.result_display_timer = 5.0
        self.result_fade = 0.0
        self.sign_animation = 1.0

    def update(self, dt):
        if self.result_display_timer > 0:
            self.result_display_timer -= dt
            self.result_fade = min(1.0, self.result_fade + dt * 4)
        else:
            self.result_fade = max(0.0, self.result_fade - dt * 2)

        if self.sign_animation > 0:
            self.sign_animation = max(0, self.sign_animation - dt * 3)

    def draw(self, screen, x, y, w, h):
        PANEL_BG = (35, 35, 50)
        draw_rounded_rect(screen, PANEL_BG, (x, y, w, h), 15)
        draw_rounded_rect(screen, (60, 60, 80), (x, y, w, h), 15, 2)

        pad = 20
        cx = x + w // 2
        cy = y + pad

        # 标题
        title = self.font_lg.render("斯金纳箱", True, (255, 255, 255))
        screen.blit(title, (cx - title.get_width() // 2, cy))
        cy += 50

        # 状态栏
        p_now = reinforcement_prob(self.qd.n, self.qd.c, self.qd.g)
        streak_text = f"总签到: {self.qd.n}  |  连续: {self.qd.c}天"
        st = self.font_sm.render(streak_text, True, (200, 200, 200))
        screen.blit(st, (cx - st.get_width() // 2, cy))
        cy += 28

        prob_text = f"强化概率: {p_now:.1%}"
        pt = self.font_sm.render(prob_text, True, (200, 200, 200))
        screen.blit(pt, (cx - pt.get_width() // 2, cy))
        cy += 35

        # 概率进度条
        bar_w = w - pad * 2
        draw_progress_bar(screen, x + pad, cy, bar_w, 14, p_now / 0.35,
                          (80, 200, 120) if p_now < 0.15 else
                          (255, 200, 60) if p_now < 0.25 else (255, 100, 80))
        cy += 30

        # 签到按钮
        can_sign = self.qd.can_sign_today()
        self.btn_rect = pygame.Rect(cx - 100, cy, 200, 55)

        btn_color = (60, 180, 100) if can_sign else (80, 80, 90)
        if self.sign_animation > 0:
            scale = 1.0 + self.sign_animation * 0.1
            bw = int(200 * scale)
            bh = int(55 * scale)
            self.btn_rect = pygame.Rect(cx - bw // 2, cy - int((bh - 55) // 2), bw, bh)
            if can_sign:
                btn_color = (
                    min(255, int(60 + 195 * self.sign_animation)),
                    min(255, int(180 + 75 * self.sign_animation)),
                    min(255, int(100 + 155 * self.sign_animation)),
                )

        draw_rounded_rect(screen, btn_color, self.btn_rect, 12)
        btn_text = "签 到" if can_sign else "今日已签到"
        bt = self.font_md.render(btn_text, True, (255, 255, 255) if can_sign else (120, 120, 120))
        screen.blit(bt, (self.btn_rect.centerx - bt.get_width() // 2,
                         self.btn_rect.centery - bt.get_height() // 2))
        cy += 75

        # 签到结果
        if self.qd.last_result and self.result_fade > 0:
            self._draw_result(screen, self.qd.last_result, cx, cy, w)
        else:
            hint = "按 空格 签到" if self.qd.can_sign_today() else "明天再来签到吧"
            hint_surf = self.font_sm.render(hint, True, (140, 140, 160))
            screen.blit(hint_surf, (cx - hint_surf.get_width() // 2, cy))

        # 底部快捷键提示
        bottom_y = y + h - 30
        keys_text = "空格:签到  E:浏览表情  H:历史  ESC:退出"
        keys_surf = self.font_xs.render(keys_text, True, (80, 80, 100))
        screen.blit(keys_surf, (cx - keys_surf.get_width() // 2, bottom_y))

    def _draw_result(self, screen, result, cx, cy, panel_w):
        alpha = int(255 * min(1.0, self.result_fade))

        if result["reinforced"]:
            rw = result["reward"]
            rarity = rw.get("rarity", "普通")
            rcolor = RARITY_COLORS.get(rarity, (255, 255, 255))

            rarity_surf = self.font_md.render(f"[{rarity}]", True, rcolor)
            rarity_surf.set_alpha(alpha)
            screen.blit(rarity_surf, (cx - rarity_surf.get_width() // 2, cy))
            cy += 32

            reward_surf = self.font_lg.render(rw["name"], True, (255, 255, 255))
            reward_surf.set_alpha(alpha)
            screen.blit(reward_surf, (cx - reward_surf.get_width() // 2, cy))
            cy += 45

            desc = rw.get("description", "")
            if desc:
                desc_surf = self.font_sm.render(desc, True, (180, 180, 180))
                desc_surf.set_alpha(alpha)
                screen.blit(desc_surf, (cx - desc_surf.get_width() // 2, cy))
                cy += 24

            cat = rw.get("category", "")
            if cat:
                cat_surf = self.font_xs.render(f"分类: {cat}", True, (140, 140, 140))
                cat_surf.set_alpha(alpha)
                screen.blit(cat_surf, (cx - cat_surf.get_width() // 2, cy))
                cy += 22
        else:
            streak = result["no_reward_streak"]
            no_text = f"连续 {streak} 次无奖励" if streak > 1 else "本次无奖励"
            no_surf = self.font_md.render(no_text, True, (150, 150, 160))
            no_surf.set_alpha(alpha)
            screen.blit(no_surf, (cx - no_surf.get_width() // 2, cy))
            cy += 32

            encourage = self._get_encourage_text(streak)
            enc_surf = self.font_sm.render(encourage, True, (120, 120, 140))
            enc_surf.set_alpha(alpha)
            screen.blit(enc_surf, (cx - enc_surf.get_width() // 2, cy))
            cy += 24

        info = f"第{result['n']}次签到  概率{result['prob']:.1%}"
        info_surf = self.font_xs.render(info, True, (100, 100, 120))
        info_surf.set_alpha(alpha)
        screen.blit(info_surf, (cx - info_surf.get_width() // 2, cy))

    @staticmethod
    def _get_encourage_text(streak):
        if streak <= 1:
            return "再接再厉！"
        elif streak <= 3:
            return "坚持签到，概率会提升哦"
        elif streak <= 6:
            return "别灰心，强化概率在上升中..."
        elif streak <= 10:
            return "快了快了，概率越来越高！"
        else:
            return "大器晚成，好运即将降临！"

    def handle_click(self, pos, btn_rect=None):
        rect = btn_rect or self.btn_rect
        if rect.collidepoint(pos):
            if self.qd.can_sign_today():
                self.sign()
                return True
        return False
