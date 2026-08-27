"""
Russian Roulette - ECS Edition
with pygame-ce GUI, 3D6 system, achievements, ASCII art, and i18n.
"""

import pygame
import random
import sys

# ── Local imports ─────────────────────────────────────────────────────
from ecs import World, Entity, SystemManager
from components import (
    ChamberComponent, HealthComponent, TurnComponent, DiceComponent,
    ShotComponent, AchievementComponent, AnimationComponent,
    BulletType, DiceResult, TurnPhase, ShotTarget
)
from systems import DiceSystem, ShootingSystem, TurnSystem, AnimationSystem, AchievementSystem
from dice import DiceManager
from achievements import AchievementManager, ALL_ACHIEVEMENTS
from ascii_art import (
    PLAYER_NORMAL, PLAYER_HIT, PLAYER_DEAD,
    OPPONENT_NORMAL, OPPONENT_HIT, OPPONENT_DEAD,
)
from lang import L, toggle_lang, get_lang, L_bullet, L_target, set_lang

# ── Constants ─────────────────────────────────────────────────────────

SCREEN_W, SCREEN_H = 1000, 700
FPS = 60

COLOR_BG        = (15, 15, 25)
COLOR_PANEL     = (25, 25, 40)
COLOR_BORDER    = (70, 70, 110)
COLOR_TEXT      = (220, 220, 230)
COLOR_ACCENT    = (255, 80, 80)
COLOR_SUCCESS   = (80, 200, 80)
COLOR_FAIL      = (255, 60, 60)
COLOR_GOLD      = (255, 200, 0)
COLOR_LIVE      = (255, 50, 50)
COLOR_BLANK     = (160, 160, 180)
COLOR_RUBBER    = (180, 100, 220)   # 紫色
COLOR_INCENDIARY = (255, 140, 50)   # 橙红色

# ── pygame init ──────────────────────────────────────────────────────

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
clock = pygame.time.Clock()

# ── Font setup (workaround for pygame-ce 2.5.7 SysFont bug on Python 3.14) ──

_font_path = None
import os as _os
_font_candidates = [
    _os.path.join(_os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyh.ttc"),
    _os.path.join(_os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simhei.ttf"),
    _os.path.join(_os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simsun.ttc"),
]
for _fp in _font_candidates:
    if _os.path.isfile(_fp):
        _font_path = _fp
        break

def _make_font(size, bold=False):
    global _font_path
    if _font_path:
        try:
            return pygame.font.Font(_font_path, size)
        except Exception:
            pass
    return pygame.font.Font(None, size)

font_s = _make_font(18)
font_m = _make_font(24)
font_l = _make_font(34)
font_xl = _make_font(80)

# ── ECS Setup ─────────────────────────────────────────────────────────

world = World()
sys_mgr = SystemManager()
sys_mgr.add_system(DiceSystem())
sys_mgr.add_system(ShootingSystem())
sys_mgr.add_system(TurnSystem())
sys_mgr.add_system(AnimationSystem())
sys_mgr.add_system(AchievementSystem())

player = Entity("player")
opponent = Entity("opponent")

for ent in (player, opponent):
    world.add_component(ent, ChamberComponent(max_slots=6))
    world.add_component(ent, HealthComponent(hp=1))
    world.add_component(ent, TurnComponent())
    world.add_component(ent, DiceComponent())
    world.add_component(ent, ShotComponent())
    world.add_component(ent, AchievementComponent())
    world.add_component(ent, AnimationComponent())

player_ach = AchievementManager()
opponent_ach = AchievementManager()

# ── State ────────────────────────────────────────────────────────────

game_phase = "START"
turn_number = 1
messages = []
bang_anim = {"active": False, "text": "", "timer": 0.0, "color": COLOR_ACCENT}
flash_anim = {"active": False, "timer": 0.0, "color": (255, 255, 255)}
ach_popup = {"active": False, "text": "", "timer": 0.0}
ach_panel_visible = False
center_msg = {"text": "", "timer": 0.0, "color": COLOR_GOLD}
buttons = {}

# 弹巢和骰子状态显示（在消息记录上方）
chamber_status = {"player": "", "opponent": ""}
dice_roll_info = {"roll1": "", "roll2": ""}
dice_mgr = DiceManager()
opp_dice_mgr = DiceManager()

# 状态效果变量
player_stunned = player_burning = False
opp_stunned = opp_burning = False


def add_msg(text, color=COLOR_TEXT):
    messages.append((text, color))
    if len(messages) > 12:
        messages.pop(0)


def _entity_name(ent):
    """Localized entity display name."""
    if ent == player:
        return L("char_player")
    return L("char_opponent")


def reset_game():
    global game_phase, turn_number, messages
    global dice_mgr, opp_dice_mgr, bang_anim, flash_anim
    global player_stunned, player_burning
    global opp_stunned, opp_burning, center_msg

    messages.clear()
    dice_mgr.reset()
    opp_dice_mgr.reset()
    bang_anim = {"active": False, "text": "", "timer": 0.0, "color": COLOR_ACCENT}
    flash_anim = {"active": False, "timer": 0.0, "color": (255, 255, 255)}
    player_ach.reset_per_game()
    opponent_ach.reset_per_game()
    
    # 重置状态效果
    player_stunned = player_burning = False
    opp_stunned = opp_burning = False
    
    # 显示中央消息
    center_msg = {"text": L("msg_new_game"), "timer": 2.0, "color": COLOR_GOLD}

    for ent in (player, opponent):
        ch = world.get_component(ent, ChamberComponent)
        hc = world.get_component(ent, HealthComponent)
        dc = world.get_component(ent, DiceComponent)
        sc = world.get_component(ent, ShotComponent)
        if ch:
            ch.bullets = []
            ch.fill_random()
        if hc:
            hc.hp = 3  # 3点生命值
        if dc:
            dc.roll_1_results = []
            dc.roll_2_results = []
            dc.last_crit_type = None
            dc.explosion_pending = False
        if sc:
            sc.was_shot = False
            sc.hit_live = False
            sc.stunned = False
            sc.burning = False

    turn_number = 1
    game_phase = "PLAYER_TURN"
    add_msg(L("msg_new_game"))
    add_msg(L("msg_turn1"))
    ch = world.get_component(player, ChamberComponent)
    add_msg(L("msg_chamber_info", live=ch.live_count, blank=ch.blank_count))


def do_shoot(shooter, target_name, precise=False):
    """
    shooter fires one bullet. target_name: "self" or "opponent".
    precise: if True, bullet is guaranteed live and not consumed from chamber.
    Returns (died: bool, bullet_type: int, effect: str or None)
    effect can be: "rubber", "incendiary", "blank", None
    """
    global bang_anim, flash_anim, player_stunned, player_burning
    global opp_stunned, opp_burning, chamber_status

    ch = world.get_component(shooter, ChamberComponent)
    sc = world.get_component(shooter, ShotComponent)
    if not ch or not ch.bullets:
        add_msg(L("msg_empty_chamber"))
        return False, None, None

    # 精准射击：必中实弹且不消耗
    if precise:
        if not ch.bullets:
            add_msg(L("msg_precise_no_bullet"))
            return False, None, None
        # 强制使用实弹
        original_bullet = ch.bullets[0]
        ch.bullets.pop(0)  # 移除子弹但不发射
        bullet = BulletType.LIVE
    else:
        bullet = ch.shoot()

    if sc:
        sc.bullet_type = bullet
        sc.was_shot = True

    # 根据target_name决定目标Entity
    if target_name == "self":
        target_ent = shooter
    else:
        target_ent = opponent if shooter is player else player

    bstr = L_bullet(bullet)
    shooter_name = _entity_name(shooter)
    target_name_display = _entity_name(target_ent)
    add_msg(L("msg_shoot", shooter=shooter_name, bullet=bstr, target=target_name_display))

    # Animation
    effect = None
    if bullet == BulletType.LIVE:
        bang_anim = {"active": True, "text": L("msg_bang"), "timer": 1.2, "color": COLOR_ACCENT}
        flash_anim = {"active": True, "timer": 0.3, "color": (255, 80, 80)}
    elif bullet == BulletType.BLANK:
        bang_anim = {"active": True, "text": L("msg_click"), "timer": 0.8, "color": COLOR_GOLD}
        flash_anim = {"active": True, "timer": 0.2, "color": (255, 255, 180)}
        effect = "blank"
    elif bullet == BulletType.RUBBER:
        bang_anim = {"active": True, "text": L("msg_click"), "timer": 0.8, "color": (200, 100, 255)}
        flash_anim = {"active": True, "timer": 0.2, "color": (200, 150, 255)}
        effect = "rubber"
    elif bullet == BulletType.INCENDIARY:
        bang_anim = {"active": True, "text": L("msg_bang"), "timer": 1.2, "color": (255, 150, 50)}
        flash_anim = {"active": True, "timer": 0.4, "color": (255, 100, 50)}
        effect = "incendiary"

    # Damage and effects
    died = False
    if bullet == BulletType.LIVE:
        hc = world.get_component(target_ent, HealthComponent)
        if hc:
            hc.hp -= 1
            if hc.hp <= 0:
                died = True
                add_msg(L("msg_killed", name=_entity_name(target_ent)))
        if sc:
            sc.hit_live = True
    else:
        if sc:
            sc.hit_live = False
        
    # 处理特殊子弹效果
    target_name_str = _entity_name(target_ent)
    if bullet == BulletType.BLANK:
        # 空包弹：只造成惊吓效果，无实际伤害
        add_msg(L("msg_blank_effect", name=target_name_str))
    elif bullet == BulletType.RUBBER:
        # 橡胶弹：眩晕（跳过下一回合）
        if target_ent == player:
            player_stunned = True
        else:
            opp_stunned = True
        add_msg(L("msg_rubber_hit", name=target_name_str))
    elif bullet == BulletType.INCENDIARY:
            # 燃烧弹：持续伤害标记
            if target_ent == player:
                player_burning = True
            else:
                opp_burning = True
            add_msg(L("msg_incendiary_hit", name=target_name_str))

    # Refill (精准射击不补充)
    if not precise:
        ch.refill_one()
    
    # 更新弹巢状态显示
    live_c = sum(1 for b in ch.bullets if b == BulletType.LIVE)
    blank_c = sum(1 for b in ch.bullets if b == BulletType.BLANK)
    shooter_key = "player" if shooter is player else "opponent"
    chamber_status[shooter_key] = f"{L('chamber_refill')}: {live_c}{L('bullet_live')} / {blank_c}{L('bullet_blank')}"
    
    return died, bullet, effect


def do_explosion(entity):
    global bang_anim, flash_anim
    hc = world.get_component(entity, HealthComponent)
    if hc:
        hc.hp = 0
    bang_anim = {"active": True, "text": "BOOM!", "timer": 2.0, "color": (255, 40, 40)}
    flash_anim = {"active": True, "timer": 1.0, "color": (255, 30, 30)}
    add_msg(L("msg_explosion_kill", name=_entity_name(entity)))
    # 重置精准射击状态
    dice_mgr.precise_shot = False


def opponent_turn():
    global opp_stunned, opp_burning
    
    # 检查状态效果
    if opp_stunned:
        opp_stunned = False
        add_msg(L("msg_stunned_skip", name=L("char_opponent")))
        return "stunned"
    if opp_burning:
        # 燃烧伤害
        opp_burning = False
        hc = world.get_component(opponent, HealthComponent)
        if hc:
            hc.hp -= 1
            if hc.hp <= 0:
                add_msg(L("msg_killed", name=L("char_opponent")))
                return "burn_death"
    
    dm = opp_dice_mgr
    dm.reset()
    add_msg(L("msg_opp_turn"))

    # Roll 1 - 决定行动
    r1_res, r1_label, r1_dice = dm.do_roll_1()
    add_msg(L("msg_opp_roll1", dice=r1_dice, total=sum(r1_dice), label=r1_label))
    opponent_ach.record_crit(r1_label)

    # 检查炸膛（大失败）
    if r1_label == "critical_fail":
        add_msg(L("msg_opp_explosion"))
        do_explosion(opponent)
        opponent_ach.record_explosion(survived=False)
        return "explosion"

    # 检查旋转（普通失败）
    if r1_label == "fail":
        ch = world.get_component(opponent, ChamberComponent)
        if ch:
            ch.spin()
        opponent_ach.record_spin()
        add_msg(L("msg_opp_spin"))
        return "spin_end"

    # 精准射击提示
    if r1_label == "critical_success":
        add_msg(L("msg_opp_precise"))

    # Roll 2 - 决定目标
    r2_res, r2_label, r2_dice, _ = dm.do_roll_2()
    target_label = L("msg_target_self") if dm.get_target_from_roll_2() == "self" else L("msg_target_opponent")
    add_msg(L("msg_opp_roll2", dice=r2_dice, total=sum(r2_dice), target_label=target_label))

    target = dm.get_target_from_roll_2()
    died, btype, effect = do_shoot(opponent, target, precise=(r1_label == "critical_success"))
    
    # 记录成就
    if btype == BulletType.LIVE:
        opponent_ach.record_shot("live", target, died)
    elif btype == BulletType.BLANK:
        opponent_ach.record_shot("blank", target, died)
    else:
        opponent_ach.record_shot("special", target, died)
    
    return "shot"


# ── Drawing ──────────────────────────────────────────────────────────

def draw_text(surf, text, x, y, font, color=COLOR_TEXT, center=False):
    for i, line in enumerate(text.split("\n")):
        img = font.render(line, True, color)
        r = img.get_rect()
        if center:
            r.center = (x, y + i * font.get_height())
        else:
            r.topleft = (x, y + i * font.get_height())
        surf.blit(img, r)


def draw_panel(surf, x, y, w, h, border=True):
    pygame.draw.rect(surf, COLOR_PANEL, (x, y, w, h), border_radius=8)
    if border:
        pygame.draw.rect(surf, COLOR_BORDER, (x, y, w, h), 2, border_radius=8)


def draw_chamber(surf, ch, x, y):
    if not ch:
        return
    sw = 44
    for i in range(ch.max_slots):
        sx = x + i * (sw + 5)
        pygame.draw.rect(surf, COLOR_PANEL, (sx, y, sw, 48), border_radius=6)
        pygame.draw.rect(surf, COLOR_BORDER, (sx, y, sw, 48), 2, border_radius=6)
        if i < len(ch.bullets):
            btype = ch.bullets[i]
            if btype == BulletType.LIVE:
                c = COLOR_LIVE
                lb = L("bullet_live")
            elif btype == BulletType.BLANK:
                c = COLOR_BLANK
                lb = L("bullet_blank")
            elif btype == BulletType.RUBBER:
                c = COLOR_RUBBER
                lb = L("bullet_rubber")
            else:  # INCENDIARY
                c = COLOR_INCENDIARY
                lb = L("bullet_incendiary")
            pygame.draw.circle(surf, c, (sx + sw // 2, y + 24), 10)
            draw_text(surf, lb, sx + sw // 2, y + 38, font_s, c, center=True)


def get_art(entity):
    hc = world.get_component(entity, HealthComponent)
    sc = world.get_component(entity, ShotComponent)
    if not hc or hc.hp <= 0:
        return PLAYER_DEAD if entity == player else OPPONENT_DEAD, (120, 120, 120)
    if sc and sc.was_shot and sc.hit_live:
        return PLAYER_HIT if entity == player else OPPONENT_HIT, COLOR_ACCENT
    return PLAYER_NORMAL if entity == player else OPPONENT_NORMAL, COLOR_TEXT


def draw_char(surf, entity, x, y):
    art, col = get_art(entity)
    for i, line in enumerate(art.strip().split("\n")):
        draw_text(surf, line, x, y + i * 18, font_s, col)
    name_col = COLOR_GOLD if entity == player else (80, 180, 255)
    draw_text(surf, _entity_name(entity), x + 20, y - 22, font_m, name_col)
    hc = world.get_component(entity, HealthComponent)
    hp_str = L("hp_alive", hp=hc.hp) if (hc and hc.hp > 0) else L("hp_dead")
    hp_col = COLOR_SUCCESS if (hc and hc.hp > 0) else (120, 120, 120)
    draw_text(surf, hp_str, x + 20, y + 82, font_s, hp_col)


def draw_dice(surf, dice_list, x, y, label="", decision=""):
    s = " + ".join(str(d) for d in dice_list) + f" = {sum(dice_list)}"
    draw_text(surf, f"[{s}]", x, y, font_m, COLOR_GOLD)
    if label:
        c = COLOR_SUCCESS if "success" in label else COLOR_FAIL
        draw_text(surf, f"{L('dice_result_prefix')}{label}", x, y + 26, font_s, c)
    if decision:
        draw_text(surf, decision, x, y + 50, font_s, (180, 180, 200))


def _msg_belongs_to_a(msg):
    """判断消息是否属于甲方(左侧显示)"""
    # 甲方相关关键词
    a_keywords = ["甲方", "你", "你的", "你的回合", "你先", "决定开枪", "精准射击", 
                  "旋转弹巢", "炸膛", "你赢了", "你输了", "大失败", "大成功",
                  "A:", "甲方先手"]
    # 乙方相关关键词（排除这些就是甲方的）
    b_keywords = ["乙方", "对手", "对手的", "对手回合", "对手先", "对手决定",
                  "对手旋转", "对手炸膛", "对手精准", "乙方先手"]
    
    for kw in b_keywords:
        if kw in msg:
            return False
    for kw in a_keywords:
        if kw in msg:
            return True
    # 默认：包含"回合"且包含"你的"或"第"的算甲方
    if "回合" in msg and ("你的" in msg or "第" in msg):
        return True
    return False

def draw_msgs(surf):
    # 消息记录面板 - 底部，左右分列
    draw_panel(surf, 20, 520, SCREEN_W - 40, 160)
    
    # 中间分隔线
    mid_x = SCREEN_W // 2
    pygame.draw.line(surf, COLOR_BORDER, (mid_x, 530), (mid_x, 670), 1)
    
    # 甲方消息标题
    draw_text(surf, L("char_player"), 30, 525, font_m, COLOR_GOLD)
    # 乙方消息标题
    draw_text(surf, L("char_opponent"), mid_x + 20, 525, font_m, (80, 180, 255))
    
    # 分开收集甲方和乙方消息
    msgs_a = []  # 甲方消息
    msgs_b = []  # 乙方消息
    
    for msg, col in messages:
        if _msg_belongs_to_a(msg):
            msgs_a.append((msg, col))
        else:
            msgs_b.append((msg, col))
    
    # 左侧显示甲方消息（最新的6条）
    y_start = 555
    for i, (msg, col) in enumerate(msgs_a[-6:]):
        draw_text(surf, msg, 30, y_start + i * 20, font_s, col)
    
    # 右侧显示乙方消息（最新的6条）
    for i, (msg, col) in enumerate(msgs_b[-6:]):
        draw_text(surf, msg, mid_x + 20, y_start + i * 20, font_s, col)


def draw_btns(surf):
    global buttons
    buttons = {}
    # 按钮放在中间下方
    bx = SCREEN_W // 2 - 75
    by = 470
    bw = 150
    bh = 42

    if game_phase == "START":
        _btn(surf, L("btn_start"), bx, by, bw, bh, "start")
    elif game_phase == "PLAYER_TURN":
        _btn(surf, L("btn_roll1"), bx, by, bw, bh, "roll1")
    elif game_phase == "ROLL1_DONE":
        _btn(surf, L("btn_roll2"), bx, by, bw, bh, "roll2")
    elif game_phase == "GAME_OVER":
        _btn(surf, L("btn_restart"), bx, by, bw, bh, "restart")

    # Language toggle — top right
    _btn(surf, L("btn_lang"), SCREEN_W - 70, 10, 55, 32, "toggle_lang")
    # Achievement button — top right
    _btn(surf, L("btn_achievement"), SCREEN_W - 135, 10, 60, 32, "achievement")


def draw_ach_panel(surf):
    """Draw the achievement panel overlay."""
    global ach_panel_visible
    
    # Panel background
    pw, ph = 400, 350
    px = (SCREEN_W - pw) // 2
    py = (SCREEN_H - ph) // 2 - 50
    
    pygame.draw.rect(surf, (25, 25, 45), (px, py, pw, ph), border_radius=12)
    pygame.draw.rect(surf, COLOR_GOLD, (px, py, pw, ph), 3, border_radius=12)
    
    # Title
    draw_text(surf, L("ach_title"), px + pw // 2, py + 15, font_l, COLOR_GOLD, center=True)
    
    # Get unlocked achievements
    unlocked = player_ach.get_unlocked_list()
    total = len(ALL_ACHIEVEMENTS)
    
    # Progress
    draw_text(surf, L("ach_progress", unlocked=len(unlocked), total=total), 
              px + pw // 2, py + 55, font_m, COLOR_TEXT, center=True)
    
    # List achievements
    y_offset = py + 85
    if unlocked:
        for i, ach in enumerate(unlocked[:10]):  # Show max 10
            icon = ach.get("icon", "•")
            name = ach.get("name", "?")
            desc = ach.get("desc", "")
            draw_text(surf, f"{icon} {name}", px + 20, y_offset, font_m, COLOR_GOLD)
            draw_text(surf, desc, px + 25, y_offset + 22, font_s, (180, 180, 180))
            y_offset += 50
    else:
        draw_text(surf, L("ach_none"), px + pw // 2, y_offset + 30, font_s, (150, 150, 150), center=True)
    
    # Close button
    close_rect = pygame.Rect(px + pw // 2 - 50, py + ph - 45, 100, 35)
    hover = close_rect.collidepoint(pygame.mouse.get_pos())
    c = (80, 80, 140) if hover else (45, 45, 80)
    pygame.draw.rect(surf, c, close_rect, border_radius=6)
    draw_text(surf, L("ach_close"), px + pw // 2, py + ph - 38, font_m, COLOR_TEXT, center=True)
    
    # Store close button rect for click handling
    buttons["ach_close"] = close_rect


def _btn(surf, text, x, y, w, h, key):
    global buttons
    rect = pygame.Rect(x, y, w, h)
    hover = rect.collidepoint(pygame.mouse.get_pos())
    c = (80, 80, 140) if hover else (45, 45, 80)
    bc = COLOR_GOLD if hover else COLOR_BORDER
    pygame.draw.rect(surf, c, rect, border_radius=8)
    pygame.draw.rect(surf, bc, rect, 2, border_radius=8)
    img = font_m.render(text, True, COLOR_TEXT)
    surf.blit(img, img.get_rect(center=rect.center))
    buttons[key] = rect


def handle_click(pos):
    for key, rect in buttons.items():
        if rect.collidepoint(pos):
            return key
    return None


def check_achievements(ach_mgr, turn_num):
    newly = ach_mgr.check_all(turn_num)
    if newly:
        ach = ALL_ACHIEVEMENTS.get(newly[-1])
        if ach:
            return L("ach_unlocked", name=ach["name"])
    return None


# ── Main Loop ─────────────────────────────────────────────────────────

def main():
    global game_phase, turn_number, bang_anim, flash_anim, ach_popup, ach_panel_visible, center_msg
    global player_stunned, player_burning

    # Update caption to current lang
    pygame.display.set_caption(L("caption"))

    reset_game()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # Events
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                action = handle_click(ev.pos)
                if action == "toggle_lang":
                    toggle_lang()
                    pygame.display.set_caption(L("caption"))
                    continue
                if action == "achievement":
                    ach_panel_visible = not ach_panel_visible
                    continue
                if action == "ach_close":
                    ach_panel_visible = False
                    continue

                if action == "start":
                    reset_game()
                elif action == "restart":
                    reset_game()
                elif action == "roll1" and game_phase == "PLAYER_TURN":
                    # 检查眩晕状态
                    if player_stunned:
                        player_stunned = False
                        add_msg(L("msg_stunned_skip", name=L("char_player")))
                        game_phase = "END_TURN"
                        continue
                    # 检查燃烧伤害
                    if player_burning:
                        player_burning = False
                        hc = world.get_component(player, HealthComponent)
                        if hc:
                            hc.hp -= 1
                            if hc.hp <= 0:
                                add_msg(L("msg_killed", name=L("char_player")))
                                player_ach.record_loss()
                                game_phase = "GAME_OVER"
                                add_msg(L("msg_you_lose", detail=L("detail_burning")))
                                continue
                    
                    r1, r1_label, r1_dice = dice_mgr.do_roll_1()
                    add_msg(L("msg_your_roll1", dice=r1_dice, total=sum(r1_dice), label=r1_label))
                    player_ach.record_crit(r1_label)

                    # 大失败 - 炸膛
                    if r1_label == "critical_fail":
                        add_msg(L("msg_explosion"))
                        do_explosion(player)
                        player_ach.record_explosion(survived=False)
                        game_phase = "GAME_OVER"
                        player_ach.record_loss()
                        add_msg(L("msg_you_lose", detail=L("detail_explosion")))
                        ach_msg = check_achievements(player_ach, turn_number)
                        if ach_msg:
                            ach_popup = {"active": True, "text": ach_msg, "timer": 3.0}
                        continue

                    # 普通失败 - 旋转弹巢
                    if r1_label == "fail":
                        ch = world.get_component(player, ChamberComponent)
                        if ch:
                            ch.spin()
                        player_ach.record_spin()
                        add_msg(L("msg_roll1_spin"))
                        game_phase = "END_TURN"
                        continue

                    # 成功/大成功 - 可以开枪
                    if r1_label == "critical_success":
                        add_msg(L("msg_roll1_precise"))
                    else:
                        add_msg(L("msg_roll1_shoot"))
                    game_phase = "ROLL1_DONE"
                    
                elif action == "roll2" and game_phase == "ROLL1_DONE":
                    r2_res, r2_label, r2_dice, _ = dice_mgr.do_roll_2()
                    target = dice_mgr.get_target_from_roll_2()
                    target_label = L("msg_target_self") if target == "self" else L("msg_target_opponent")
                    add_msg(L("msg_your_roll2", dice=r2_dice, total=sum(r2_dice), target_label=target_label))
                    player_ach.record_crit(r2_label)

                    # 精准射击
                    precise = dice_mgr.is_precise_shot()
                    if precise:
                        dice_mgr.precise_shot = False  # 重置精准射击状态

                    died, btype, effect = do_shoot(player, target, precise=precise)
                    
                    # 记录成就
                    if btype == BulletType.LIVE:
                        player_ach.record_shot("live", target, died)
                    elif btype == BulletType.BLANK:
                        player_ach.record_shot("blank", target, died)
                    else:
                        player_ach.record_shot("special", target, died)
                    
                    if died:
                        if target == "opponent":
                            add_msg(L("msg_you_win", detail=L("detail_killed_opp")))
                            player_ach.record_win(turn_number)
                        else:
                            add_msg(L("msg_you_lose", detail=L("detail_killed_self")))
                            player_ach.record_loss()
                        game_phase = "GAME_OVER"
                    else:
                        game_phase = "END_TURN"
                    ach_msg = check_achievements(player_ach, turn_number)
                    if ach_msg:
                        ach_popup = {"active": True, "text": ach_msg, "timer": 3.0}
                        
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN and game_phase == "START":
                    reset_game()
                elif ev.key == pygame.K_RETURN and game_phase == "GAME_OVER":
                    reset_game()
                elif ev.key == pygame.K_TAB:
                    toggle_lang()
                    pygame.display.set_caption(L("caption"))

        # Auto-advance: end turn / opponent turn
        if game_phase == "END_TURN":
            pygame.time.wait(1500)  # 增加等待时间让消息更清晰
            
            opp_result = opponent_turn()
            opp_hc = world.get_component(opponent, HealthComponent)
            player_hc = world.get_component(player, HealthComponent)
            
            if opp_result == "burn_death" or (opp_hc and opp_hc.hp <= 0):
                add_msg(L("msg_you_win", detail=L("detail_killed_opp")))
                player_ach.record_win(turn_number)
                game_phase = "GAME_OVER"
            elif opp_result == "explosion" and player_hc and player_hc.hp > 0:
                add_msg(L("msg_you_win", detail=L("detail_explosion")))
                player_ach.record_win(turn_number)
                game_phase = "GAME_OVER"
            elif player_hc and player_hc.hp <= 0:
                add_msg(L("msg_you_lose", detail=L("detail_killed_self")))
                player_ach.record_loss()
                game_phase = "GAME_OVER"
            else:
                turn_number += 1
                game_phase = "PLAYER_TURN"
                add_msg(L("msg_next_turn", n=turn_number))
                ach_msg = check_achievements(player_ach, turn_number)
                if ach_msg:
                    ach_popup = {"active": True, "text": ach_msg, "timer": 3.0}

        # Update animations
        for anim in (bang_anim, flash_anim):
            if anim.get("active"):
                anim["timer"] -= dt
                if anim["timer"] <= 0:
                    anim["active"] = False
        if ach_popup.get("active"):
            ach_popup["timer"] -= dt
            if ach_popup["timer"] <= 0:
                ach_popup["active"] = False
        if center_msg.get("timer", 0) > 0:
            center_msg["timer"] -= dt
            if center_msg["timer"] <= 0:
                center_msg["text"] = ""

        # ── Draw ────────────────────────────────────────────────────
        screen.fill(COLOR_BG)

        # ── Top: Title, Phase, Turn (centered) ─────────────────────
        draw_text(screen, L("title"), SCREEN_W // 2, 12, font_l, COLOR_ACCENT, center=True)
        phase_key = f"phase_{game_phase}"
        phase_text = L(phase_key)
        draw_text(screen, f"{L('phase_label')}{phase_text}", SCREEN_W // 2, 52, font_m, COLOR_GOLD, center=True)
        if game_phase not in ("START", "GAME_OVER"):
            draw_text(screen, f"{L('turn_label')}{turn_number}", SCREEN_W // 2, 80, font_s, COLOR_TEXT, center=True)

        # ── Characters and Chambers ─────────────────────────────────
        # Left: Player A
        draw_char(screen, player, 50, 110)
        pch = world.get_component(player, ChamberComponent)
        draw_chamber(screen, pch, 50, 330)
        draw_text(screen, L("char_player"), 50, 310, font_s, COLOR_GOLD)
        
        # Right: Player B
        draw_char(screen, opponent, SCREEN_W - 290, 110)
        och = world.get_component(opponent, ChamberComponent)
        draw_chamber(screen, och, SCREEN_W - 320, 330)
        draw_text(screen, L("char_opponent"), SCREEN_W - 290, 310, font_s, (80, 180, 255))

        # ── Center: Dice Results ────────────────────────────────────
        if game_phase not in ("START", "GAME_OVER"):
            # Player A's dice
            if dice_mgr.roll_1:
                draw_text(screen, L("char_player"), 350, 120, font_m, COLOR_GOLD)
                s1 = " + ".join(str(d) for d in dice_mgr.roll_1)
                draw_text(screen, f"[{s1}] = {sum(dice_mgr.roll_1)}", 350, 150, font_m, COLOR_GOLD)
                draw_text(screen, f"{L('dice_result_prefix')}{dice_mgr.roll_1_label}", 350, 180, font_s, 
                         COLOR_SUCCESS if "success" in dice_mgr.roll_1_label else COLOR_FAIL)
                draw_text(screen, L("dice_decision_roll1"), 350, 205, font_s, (180, 180, 180))
            if dice_mgr.roll_2:
                target = dice_mgr.get_target_from_roll_2()
                target_str = L("target_self") if target == "self" else L("target_opponent")
                s2 = " + ".join(str(d) for d in dice_mgr.roll_2)
                draw_text(screen, f"[{s2}] = {sum(dice_mgr.roll_2)}", 350, 235, font_m, COLOR_GOLD)
                draw_text(screen, f"{L('dice_decision_roll2')}{target_str}", 350, 265, font_s, COLOR_TEXT)
            
            # Player B's dice
            if opp_dice_mgr.roll_1:
                draw_text(screen, L("char_opponent"), 350, 300, font_m, (80, 180, 255))
                s1 = " + ".join(str(d) for d in opp_dice_mgr.roll_1)
                draw_text(screen, f"[{s1}] = {sum(opp_dice_mgr.roll_1)}", 350, 330, font_m, (80, 180, 255))
                draw_text(screen, f"{L('dice_result_prefix')}{opp_dice_mgr.roll_1_label}", 350, 360, font_s,
                         COLOR_SUCCESS if "success" in opp_dice_mgr.roll_1_label else COLOR_FAIL)
            if opp_dice_mgr.roll_2:
                target = opp_dice_mgr.get_target_from_roll_2()
                target_str = L("target_self") if target == "self" else L("target_opponent")
                s2 = " + ".join(str(d) for d in opp_dice_mgr.roll_2)
                draw_text(screen, f"[{s2}] = {sum(opp_dice_mgr.roll_2)}", 350, 390, font_m, (80, 180, 255))
                draw_text(screen, f"{L('dice_decision_roll2')}{target_str}", 350, 420, font_s, COLOR_TEXT)

        # ── Bottom: Messages (left/right split by player) ────────────
        draw_msgs(screen)

        # Buttons (includes language toggle)
        draw_btns(screen)

        # Fullscreen flash
        if flash_anim.get("active"):
            alpha = int(180 * max(0, flash_anim["timer"] / 0.3))
            s = pygame.Surface((SCREEN_W, SCREEN_H))
            s.fill(flash_anim["color"])
            s.set_alpha(min(alpha, 200))
            screen.blit(s, (0, 0))

        # Bang text
        if bang_anim.get("active"):
            txt = bang_anim["text"]
            img = font_xl.render(txt, True, bang_anim["color"])
            r = img.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 30))
            glow = font_xl.render(txt, True, (255, 255, 255))
            gr = glow.get_rect(center=(SCREEN_W // 2 + 4, SCREEN_H // 2 - 26))
            screen.blit(glow, gr)
            screen.blit(img, r)

        # Center message (e.g., "New Game")
        if center_msg.get("timer", 0) > 0 and center_msg.get("text"):
            draw_text(screen, center_msg["text"], SCREEN_W // 2, SCREEN_H // 2, font_l, center_msg["color"], center=True)

        # Achievement popup
        if ach_popup.get("active"):
            pygame.draw.rect(screen, (35, 35, 55),
                             (SCREEN_W // 2 - 220, 90, 440, 50), border_radius=10)
            pygame.draw.rect(screen, COLOR_GOLD,
                             (SCREEN_W // 2 - 220, 90, 440, 50), 2, border_radius=10)
            draw_text(screen, ach_popup["text"], SCREEN_W // 2, 105, font_m, COLOR_GOLD, center=True)

        # Achievement panel
        if ach_panel_visible:
            draw_ach_panel(screen)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
