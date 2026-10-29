"""
签到面板 v2 — 融合抽卡式开奖体验
增强点（基于行为设计与 game juice 研究）：
- 三段式开奖悬念动画：光球脉冲 → 稀有度色预兆闪光 → 揭晓（借鉴抽卡游戏"金光"节奏）
- 保底进度可视化：让"连续无奖励"从挫败感变成"离保底更近了"的期待感
- 连胜冻结卡显示（Duolingo 式）
- 里程碑成就弹窗
- 结果卡片用 ease_out_back 弹出，彩带 + 屏幕震动按稀有度分级
"""
import math
import pygame
from .common import draw_rounded_rect, draw_progress_bar, RARITY_COLORS, load_font
from core.expression_map import result_to_expression
from core.juice import RevealSequence, ease_out_back, ease_out_cubic

# 稀有度 → 屏幕震动强度（trauma）
RARITY_SHAKE = {
    "普通": 0.28, "稀有": 0.38, "史诗": 0.5, "传说": 0.65, "神话": 0.8,
}
# 稀有度 → 彩带数量倍率
RARITY_CONFETTI = {
    "普通": 45, "稀有": 65, "史诗": 90, "传说": 130, "神话": 180,
}


class SignPanel:
    """签到模式面板：右侧显示签到信息和操作"""

    def __init__(self, qd, face, audio, shake=None, confetti=None):
        self.qd = qd
        self.face = face
        self.audio = audio
        self.shake = shake          # ScreenShake（可选注入）
        self.confetti = confetti    # ConfettiSystem（可选注入）
        self.reveal = RevealSequence()
        self.result_display_timer = 0.0
        self.result_fade = 0.0
        self.result_pop = 0.0       # 结果卡片弹出动画进度
        self.sign_animation = 0.0
        self.milestone_queue = []   # 待展示的里程碑
        self.milestone_timer = 0.0
        self.font_lg = load_font(36)
        self.font_md = load_font(24)
        self.font_sm = load_font(18)
        self.font_xs = load_font(14)
        self.btn_rect = pygame.Rect(0, 0, 200, 55)
        self._panel_center = (750, 350)   # 上次绘制时的面板中心（彩带落点）
        self._orb_center = (750, 300)

    # ── 签到入口：先算结果，再演出 ────────────────────────────
    def sign(self):
        if self.reveal.active:
            return
        result = self.qd.sign()
        self.sign_animation = 1.0
        # 悬念阶段表情：思考中
        self.face.set_expression("thinking", play_sound=False)
        self.reveal.start(result, on_reveal=self._on_reveal)

    def _on_reveal(self, result):
        """悬念结束，正式揭晓"""
        expr = result_to_expression(result)
        self.face.set_expression(expr, play_sound=True)
        self.result_display_timer = 5.0
        self.result_fade = 0.0
        self.result_pop = 0.0

        if result["reinforced"]:
            rarity = result["reward"].get("rarity", "普通")
            if self.shake:
                self.shake.add(RARITY_SHAKE.get(rarity, 0.3))
            if self.confetti:
                cx, cy = self._panel_center
                tiers = list(RARITY_SHAKE)
                tier_idx = tiers.index(rarity) if rarity in tiers else 0
                self.confetti.burst(cx, cy - 60,
                                    count=RARITY_CONFETTI.get(rarity, 45),
                                    power=1.0 + 0.15 * tier_idx)
        else:
            if self.shake:
                self.shake.add(0.12)   # 落空也有轻微反馈（确认已处理）

        # 里程碑入队展示
        for ms in result.get("milestones", []):
            self.milestone_queue.append(ms)
        if self.milestone_queue and self.milestone_timer <= 0:
            self.milestone_timer = 3.5

    def update(self, dt):
        self.reveal.update(dt)

        if self.result_display_timer > 0:
            self.result_display_timer -= dt
            self.result_fade = min(1.0, self.result_fade + dt * 4)
            self.result_pop = min(1.0, self.result_pop + dt * 2.4)
        else:
            self.result_fade = max(0.0, self.result_fade - dt * 2)

        if self.sign_animation > 0:
            self.sign_animation = max(0, self.sign_animation - dt * 3)

        # 里程碑轮播
        if self.milestone_timer > 0:
            self.milestone_timer -= dt
            if self.milestone_timer <= 0 and self.milestone_queue:
                self.milestone_queue.pop(0)
                if self.milestone_queue:
                    self.milestone_timer = 3.5

    # ── 绘制 ──────────────────────────────────────────────────
    def draw(self, screen, x, y, w, h):
        PANEL_BG = (35, 35, 50)
        draw_rounded_rect(screen, PANEL_BG, (x, y, w, h), 15)
        draw_rounded_rect(screen, (60, 60, 80), (x, y, w, h), 15, 2)

        pad = 20
        cx = x + w // 2
        cy = y + pad
        self._panel_center = (cx, y + h // 2)

        # 标题
        title = self.font_lg.render("斯金纳箱", True, (255, 255, 255))
        screen.blit(title, (cx - title.get_width() // 2, cy))
        cy += 50

        # 状态栏：总数 / 连续 / 最长 / 冻结卡
        streak_text = f"总签到 {self.qd.n}  |  连续 {self.qd.c}天  |  最长 {max(self.qd.best_c, self.qd.c)}天"
        st = self.font_sm.render(streak_text, True, (200, 200, 200))
        screen.blit(st, (cx - st.get_width() // 2, cy))
        cy += 26

        # 冻结卡（Duolingo 式连胜保护）
        freeze_text = "连胜保护: " + ("❄" * self.qd.freezes if self.qd.freezes else "无")
        ft = self.font_xs.render(freeze_text, True, (120, 190, 255))
        screen.blit(ft, (cx - ft.get_width() // 2, cy))
        cy += 24

        # 概率（含保底加成后的真实概率）
        p_now = self.qd.current_prob()
        prob_text = f"强化概率: {p_now:.1%}"
        fails, hard, in_soft = self.qd.pity_info
        prob_color = (255, 210, 90) if in_soft else (200, 200, 200)
        pt = self.font_sm.render(prob_text, True, prob_color)
        screen.blit(pt, (cx - pt.get_width() // 2, cy))
        cy += 28

        # 概率进度条
        bar_w = w - pad * 2
        draw_progress_bar(screen, x + pad, cy, bar_w, 12,
                          ease_out_cubic(min(1.0, p_now)),
                          (80, 200, 120) if p_now < 0.15 else
                          (255, 200, 60) if p_now < 0.4 else (255, 100, 80))
        cy += 22

        # 保底进度条（软/硬保底可视化 — 把挫败转化为期待）
        pity_label = self.font_xs.render(
            f"保底进度 {fails}/{hard - 1}" + ("  即将必出!" if in_soft else ""),
            True, (255, 190, 90) if in_soft else (130, 130, 150))
        screen.blit(pity_label, (x + pad, cy))
        cy += 20
        draw_progress_bar(screen, x + pad, cy, bar_w, 8,
                          min(1.0, fails / max(1, hard - 1)),
                          (255, 170, 60), bg_color=(45, 45, 58))
        cy += 22

        # 签到按钮
        can_sign = self.qd.can_sign_today() and not self.reveal.active
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
        if self.reveal.active:
            btn_text = "抽取中..."
        elif self.qd.can_sign_today():
            btn_text = "签 到"
        else:
            btn_text = "今日已签到"
        bt = self.font_md.render(btn_text, True,
                                 (255, 255, 255) if can_sign else (150, 150, 160))
        screen.blit(bt, (self.btn_rect.centerx - bt.get_width() // 2,
                         self.btn_rect.centery - bt.get_height() // 2))
        cy += 75

        self._orb_center = (cx, cy + 60)

        # 开奖悬念 / 签到结果 / 提示
        if self.reveal.active:
            self._draw_reveal_orb(screen, cx, cy + 60)
        elif self.qd.last_result and self.result_fade > 0:
            self._draw_result(screen, self.qd.last_result, cx, cy, w)
        else:
            hint = "按 空格 签到" if self.qd.can_sign_today() else "明天再来签到吧"
            hint_surf = self.font_sm.render(hint, True, (140, 140, 160))
            screen.blit(hint_surf, (cx - hint_surf.get_width() // 2, cy))

        # 里程碑弹窗
        if self.milestone_queue and self.milestone_timer > 0:
            self._draw_milestone(screen, self.milestone_queue[0], cx, y + h - 130, w - pad * 2)

        # 底部快捷键提示
        bottom_y = y + h - 30
        keys_text = "空格:签到  E:表情  H:历史  S:统计  ESC:退出"
        keys_surf = self.font_xs.render(keys_text, True, (80, 80, 100))
        screen.blit(keys_surf, (cx - keys_surf.get_width() // 2, bottom_y))

    # ── 开奖光球（anticipation → 稀有度预兆闪光）──────────────
    def _draw_reveal_orb(self, screen, cx, cy):
        t = self.reveal.timer
        phase = self.reveal.phase

        # 基础脉冲
        pulse = 1.0 + 0.18 * math.sin(t * 9.0)
        base_r = int(38 * pulse)

        if phase == "flash" and self.reveal.result:
            # 预兆：颜色渐变为稀有度色（无奖励 → 灰蓝）
            prog = self.reveal.flash_progress
            if self.reveal.result["reinforced"]:
                rarity = self.reveal.result["reward"].get("rarity", "普通")
                target = RARITY_COLORS.get(rarity, (255, 255, 255))
            else:
                target = (110, 115, 140)
            start = (200, 200, 220)
            color = tuple(int(s + (e - s) * ease_out_cubic(prog))
                          for s, e in zip(start, target))
            base_r = int(base_r * (1.0 + prog * 0.6))   # 揭晓前膨胀
        else:
            color = (200, 200, 220)

        # 光晕（多层同心圆模拟辉光）
        for i, (mult, alpha) in enumerate([(2.2, 30), (1.6, 60), (1.15, 110)]):
            r = int(base_r * mult)
            glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*color, alpha), (r, r), r)
            screen.blit(glow, (cx - r, cy - r))
        pygame.draw.circle(screen, color, (cx, cy), base_r)
        pygame.draw.circle(screen, (255, 255, 255), (cx, cy), base_r, 2)

        # 环绕星点
        for i in range(6):
            a = t * 3.2 + i * math.pi / 3
            orbit = base_r + 26 + 6 * math.sin(t * 5 + i)
            sx = cx + orbit * math.cos(a)
            sy = cy + orbit * math.sin(a) * 0.55
            pygame.draw.circle(screen, (255, 255, 210),
                               (int(sx), int(sy)), 3 if i % 2 else 2)

        label = self.font_sm.render("命运抽取中...", True, (190, 190, 210))
        screen.blit(label, (cx - label.get_width() // 2, cy + base_r + 34))

    # ── 结果卡片（ease_out_back 弹出）─────────────────────────
    def _draw_result(self, screen, result, cx, cy, panel_w):
        alpha = int(255 * min(1.0, self.result_fade))
        pop = ease_out_back(self.result_pop) if self.result_pop < 1.0 else 1.0
        pop = max(0.35, pop)

        def blit_scaled(surf, center_x, top_y):
            if pop != 1.0:
                sw = max(1, int(surf.get_width() * pop))
                sh = max(1, int(surf.get_height() * pop))
                surf = pygame.transform.smoothscale(surf, (sw, sh))
            surf.set_alpha(alpha)
            screen.blit(surf, (center_x - surf.get_width() // 2, top_y))
            return surf.get_height()

        if result["reinforced"]:
            rw = result["reward"]
            rarity = rw.get("rarity", "普通")
            rcolor = RARITY_COLORS.get(rarity, (255, 255, 255))

            if result.get("pity_triggered"):
                pity_surf = self.font_xs.render("★ 保底触发 ★", True, (255, 190, 90))
                cy += blit_scaled(pity_surf, cx, cy) + 4

            rarity_surf = self.font_md.render(f"[{rarity}]", True, rcolor)
            cy += blit_scaled(rarity_surf, cx, cy) + 6

            reward_surf = self.font_lg.render(rw["name"], True, (255, 255, 255))
            cy += blit_scaled(reward_surf, cx, cy) + 8

            desc = rw.get("description", "")
            if desc:
                desc_surf = self.font_sm.render(desc, True, (180, 180, 180))
                cy += blit_scaled(desc_surf, cx, cy) + 4

            cat = rw.get("category", "")
            if cat:
                cat_surf = self.font_xs.render(f"分类: {cat}", True, (140, 140, 140))
                cy += blit_scaled(cat_surf, cx, cy) + 4
        else:
            streak = result["no_reward_streak"]
            no_text = f"连续 {streak} 次无奖励" if streak > 1 else "本次无奖励"
            no_surf = self.font_md.render(no_text, True, (150, 150, 160))
            cy += blit_scaled(no_surf, cx, cy) + 6

            fails, hard, in_soft = self.qd.pity_info
            remain = max(0, hard - 1 - fails)
            if remain == 0:
                encourage = "下次必出奖励！保底已就位"
                enc_color = (255, 190, 90)
            elif in_soft:
                encourage = f"软保底生效中，最多再 {remain} 次必出！"
                enc_color = (255, 190, 90)
            else:
                encourage = self._get_encourage_text(streak)
                enc_color = (120, 120, 140)
            enc_surf = self.font_sm.render(encourage, True, enc_color)
            cy += blit_scaled(enc_surf, cx, cy) + 4

        # 冻结卡事件提示
        if result.get("freeze_used"):
            fz = self.font_xs.render("❄ 冻结卡已自动使用，连胜保住了！", True, (120, 190, 255))
            cy += blit_scaled(fz, cx, cy) + 2
        if result.get("freeze_earned"):
            fz = self.font_xs.render("❄ 连续7天达成，获得 1 张冻结卡！", True, (120, 220, 255))
            cy += blit_scaled(fz, cx, cy) + 2

        info = f"第{result['n']}次签到  概率{result['prob']:.1%}"
        info_surf = self.font_xs.render(info, True, (100, 100, 120))
        info_surf.set_alpha(alpha)
        screen.blit(info_surf, (cx - info_surf.get_width() // 2, cy + 4))

    # ── 里程碑弹窗 ────────────────────────────────────────────
    def _draw_milestone(self, screen, ms, cx, y, w):
        # 进入动画：前 0.4 秒滑入
        elapsed = 3.5 - self.milestone_timer
        slide = ease_out_back(min(1.0, elapsed / 0.4))
        offset_y = int((1.0 - slide) * 40)

        box_w, box_h = min(w, 340), 74
        bx = cx - box_w // 2
        by = y + offset_y
        draw_rounded_rect(screen, (55, 48, 25), (bx, by, box_w, box_h), 12)
        draw_rounded_rect(screen, (255, 200, 80), (bx, by, box_w, box_h), 12, 2)

        trophy = self.font_md.render("🏆", True, (255, 210, 90))
        screen.blit(trophy, (bx + 14, by + box_h // 2 - trophy.get_height() // 2))

        title = self.font_sm.render(f"里程碑达成: {ms['title']}", True, (255, 220, 120))
        screen.blit(title, (bx + 52, by + 12))
        desc = self.font_xs.render(ms["desc"], True, (210, 195, 150))
        screen.blit(desc, (bx + 52, by + 40))

    @staticmethod
    def _get_encourage_text(streak):
        if streak <= 1:
            return "再接再厉！"
        elif streak <= 3:
            return "坚持签到，概率会提升哦"
        else:
            return "别灰心，保底进度在积累中..."

    def handle_click(self, pos, btn_rect=None):
        rect = btn_rect or self.btn_rect
        if rect.collidepoint(pos):
            if self.qd.can_sign_today() and not self.reveal.active:
                self.sign()
                return True
        return False
