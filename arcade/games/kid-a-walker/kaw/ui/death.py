# -*- coding: utf-8 -*-
"""死亡结算画面与评分。"""
import math

import pygame

# ─────────────────────── 结算画面 ─────────────────────────
class DeathScreen:
    """游戏结算画面"""

    @staticmethod
    def calculate_score(fragments, survival_time, explored_count) -> int:
        """计算最终评分：碎片×100 + 区块数×50 + 存活秒×2 + 全类型×500"""
        score = 0
        score += fragments.get_total() * 100
        score += explored_count * 50
        score += int(survival_time) * 2
        if fragments.is_all_types_collected():
            score += 500
        return score

    @staticmethod
    def draw(screen, f_sm, f_bg, fragments, survival_time, explored_count, tick):
        """绘制结算画面"""
        score = DeathScreen.calculate_score(fragments, survival_time, explored_count)
        sw, sh = screen.get_size()

        # 半透明遮罩
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))

        # 标题
        title = f_bg.render("SYSTEM OFFLINE", True, (220, 60, 60))
        screen.blit(title, (sw // 2 - title.get_width() // 2, sh // 4))

        # 统计信息
        y = sh // 4 + 80
        stats = [
            f"DATA FRAGMENTS: {fragments.get_total()} ({fragments.get_unique_types()}/10 TYPES)",
            f"SURVIVAL TIME: {int(survival_time) // 60:02d}:{int(survival_time) % 60:02d}",
            f"SECTORS EXPLORED: {explored_count}",
            f"FINAL SCORE: {score}",
        ]
        for s in stats:
            lbl = f_sm.render(s, True, (200, 220, 255))
            screen.blit(lbl, (sw // 2 - lbl.get_width() // 2, y))
            y += 30

        # 碎片类型详情
        y += 10
        type_names = {
            2: "GLOW", 3: "RED", 4: "GOLD", 5: "VERD", 6: "NRG",
            7: "FIRE", 8: "DEBR", 9: "TECH", 10: "CRYS", 11: "MYST",
        }
        type_colors = {
            2: (0, 255, 200), 3: (220, 60, 60), 4: (220, 180, 60),
            5: (60, 200, 100), 6: (180, 80, 240), 7: (255, 150, 60),
            8: (140, 140, 150), 9: (80, 220, 255), 10: (100, 180, 255),
            11: (160, 80, 220),
        }
        frag_detail_x = sw // 2 - 200
        for dt_idx, dt_type in enumerate(range(2, 12)):
            fx = frag_detail_x + (dt_idx % 5) * 85
            fy = y + (dt_idx // 5) * 22
            count = fragments.get_count(dt_type)
            name = type_names.get(dt_type, "????")
            col = type_colors.get(dt_type, (200, 200, 200))
            has = count > 0
            lbl = f_sm.render(f"{name}:{count}", True, col if has else (60, 60, 80))
            screen.blit(lbl, (fx, fy))

        # 重启提示
        pulse = abs(math.sin(tick * 0.05))
        col = (int(150 + 105 * pulse), 255, int(200 + 55 * pulse))
        hint = f_sm.render("[R] RESTART  |  [ESC] QUIT", True, col)
        screen.blit(hint, (sw // 2 - hint.get_width() // 2, sh * 3 // 4))
