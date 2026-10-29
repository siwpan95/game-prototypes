"""
游戏配置 — 从 data/game_data.json 加载所有数据。
提供 dataclass 封装 + 向后兼容的模块级别名。
"""

import json
import os
from dataclasses import dataclass

from content_loader import load_content

# ======================================================================
#  JSON 加载（核心包 + 模组内容包合并，带重复 ID 校验）
# ======================================================================
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "game_data.json")
_ACHIEVEMENTS_PATH = os.path.join(os.path.dirname(__file__), "data", "achievements.json")
_MODULES_DIR = os.path.join(os.path.dirname(__file__), "data", "modules")

_data, _add_content, _content_issues = load_content(
    _CONFIG_PATH, _ACHIEVEMENTS_PATH, _MODULES_DIR
)
_achievements = _data["achievements"]

# ======================================================================
#  Dataclass 配置封装
# ======================================================================

# --- 颜色 ---
@dataclass(frozen=True)
class Colors:
    bg: str
    panel: str
    hero: str
    gold: str
    dps: str
    btn_bg: str
    btn_outline: str
    btn_text: str
    float: str
    golden_btn: str
    tooltip_bg: str
    tooltip_text: str
    era_bar_bg: str
    era_bar_fill: str
    era_text: str
    era_label: str
    tab_active: str
    tab_inactive: str
    tab_text: str
    skill_ready: str
    skill_cooldown: str
    skill_active: str
    prestige_btn: str
    locked: str
    locked_text: str


COLORS = Colors(**{
    k: v for k, v in _data["ui"]["colors"].items()
    if k in Colors.__dataclass_fields__
})


# --- 布局坐标 ---
@dataclass(frozen=True)
class Layout:
    window_width: int
    window_height: int
    canvas_top_h: int
    canvas_bottom_h: int
    panel_width: int

    # era_bar
    era_bar_x: int; era_bar_y: int; era_bar_w: int; era_bar_h: int

    # hero click area
    hero_cx: int; hero_cy: int; hero_r: int

    # hud
    hud_x: int; hud_y_gold: int; hud_y_dps: int

    # tabs
    tabs_x: int; tabs_y: int; tab_w: int; tab_h: int; tab_spacing: int

    # shop
    shop_x: int; shop_y0: int; shop_w: int; shop_h: int; shop_spacing: int

    # float
    float_base_x: int; float_base_y: int; float_offset_range: int
    float_lifetime: float; float_speed: float

    # skills
    skill_x: int; skill_y: int; skill_w: int; skill_h: int
    skill_cols: int; skill_rows: int; skill_gap_x: int; skill_gap_y: int

    # prestige button
    prestige_x: int; prestige_y: int; prestige_w: int; prestige_h: int

    # hero panel
    hero_panel_x: int; hero_panel_y: int; hero_panel_w: int; hero_panel_h: int
    hero_panel_spacing: int

    # equipment panel
    equip_panel_y: int; equip_item_w: int; equip_spacing: int; equip_max_show: int


_ui = _data["ui"]
LAYOUT = Layout(
    window_width=_ui["window"]["width"],
    window_height=_ui["window"]["height"],
    canvas_top_h=_ui["canvas_top"]["height"],
    canvas_bottom_h=_ui["canvas_bottom"]["height"],
    panel_width=_ui["panel_width"],
    era_bar_x=_ui["era_bar"]["x"], era_bar_y=_ui["era_bar"]["y"],
    era_bar_w=_ui["era_bar"]["width"], era_bar_h=_ui["era_bar"]["height"],
    hero_cx=_ui["hero"]["cx"], hero_cy=_ui["hero"]["cy"], hero_r=_ui["hero"]["r"],
    hud_x=_ui["hud"]["x"], hud_y_gold=_ui["hud"]["y_gold"], hud_y_dps=_ui["hud"]["y_dps"],
    tabs_x=_ui["tabs"]["x"], tabs_y=_ui["tabs"]["y"],
    tab_w=_ui["tabs"]["width"], tab_h=_ui["tabs"]["height"], tab_spacing=_ui["tabs"]["spacing"],
    shop_x=_ui["shop"]["x"], shop_y0=_ui["shop"]["y"],
    shop_w=_ui["shop"]["width"], shop_h=_ui["shop"]["height"], shop_spacing=_ui["shop"]["spacing"],
    float_base_x=_ui["float"]["base_x"], float_base_y=_ui["float"]["base_y"],
    float_offset_range=_ui["float"]["offset"], float_lifetime=_ui["float"]["lifetime"],
    float_speed=_ui["float"]["speed"],
    skill_x=_ui["skills"]["x"], skill_y=_ui["skills"]["y"],
    skill_w=_ui["skills"]["width"], skill_h=_ui["skills"]["height"],
    skill_cols=_ui["skills"]["cols"], skill_rows=_ui["skills"]["rows"],
    skill_gap_x=_ui["skills"]["gap_x"], skill_gap_y=_ui["skills"]["gap_y"],
    prestige_x=_ui["prestige_btn"]["x"], prestige_y=_ui["prestige_btn"]["y"],
    prestige_w=_ui["prestige_btn"]["width"], prestige_h=_ui["prestige_btn"]["height"],
    hero_panel_x=_ui["hero_panel"]["x"], hero_panel_y=_ui["hero_panel"]["y"],
    hero_panel_w=_ui["hero_panel"]["width"], hero_panel_h=_ui["hero_panel"]["height"],
    hero_panel_spacing=_ui["hero_panel"]["spacing"],
    equip_panel_y=_ui["equip_panel"]["y"], equip_item_w=_ui["equip_panel"]["item_width"],
    equip_spacing=_ui["equip_panel"]["spacing"], equip_max_show=_ui["equip_panel"]["max_show"],
)


# ======================================================================
#  向后兼容的模块级别名（现有代码无需修改）
# ======================================================================

# 存档 & 黄金 buff
SAVE_FILE = _data["save_file"]
GOLDEN_BUFF = _data["golden_buff"]

# 游戏常量（从 JSON 驱动，消除魔法数字）
_constants = _data["constants"]
BACKPACK_LIMIT = _constants["backpack_limit"]
TICK_DT_MAX = _constants["tick_dt_max"]
GAME_LOOP_MS = _constants["game_loop_ms"]
HERO_PANEL_SCROLL_H = _constants["hero_panel_scroll_h"]
SHOP_SCROLL_PADDING = _constants["shop_scroll_padding"]
OFFLINE_CAP_SECONDS = _constants["offline_cap_seconds"]
MILESTONE_STEPS = _constants["milestone_steps"]
DAILY_REWARD_SECONDS = _constants["daily_reward_seconds"]
AUTOSAVE_SECONDS = _constants["autosave_seconds"]

# 颜色（flat 别名）
COLOR_BG        = COLORS.bg
COLOR_PANEL     = COLORS.panel
COLOR_HERO      = COLORS.hero
COLOR_GOLD      = COLORS.gold
COLOR_DPS       = COLORS.dps
COLOR_BTN_BG    = COLORS.btn_bg
COLOR_BTN_OUT   = COLORS.btn_outline
COLOR_BTN_TEXT  = COLORS.btn_text
COLOR_FLOAT     = COLORS.float
COLOR_GOLDEN_BTN = COLORS.golden_btn
COLOR_TOOLTIP_BG  = COLORS.tooltip_bg
COLOR_TOOLTIP_TEXT = COLORS.tooltip_text
COLOR_ERA_BAR_BG   = COLORS.era_bar_bg
COLOR_ERA_BAR_FILL = COLORS.era_bar_fill
COLOR_ERA_TEXT     = COLORS.era_text
COLOR_ERA_LABEL    = COLORS.era_label
COLOR_TAB_ACTIVE   = COLORS.tab_active
COLOR_TAB_INACTIVE = COLORS.tab_inactive
COLOR_TAB_TEXT     = COLORS.tab_text
COLOR_SKILL_READY    = COLORS.skill_ready
COLOR_SKILL_COOLDOWN = COLORS.skill_cooldown
COLOR_SKILL_ACTIVE   = COLORS.skill_active
COLOR_PRESTIGE_BTN   = COLORS.prestige_btn
COLOR_LOCKED      = COLORS.locked
COLOR_LOCKED_TEXT = COLORS.locked_text

# 窗口
WINDOW_WIDTH  = LAYOUT.window_width
WINDOW_HEIGHT = LAYOUT.window_height
CANVAS_WIDTH  = WINDOW_WIDTH
CANVAS_HEIGHT = WINDOW_HEIGHT
CANVAS_TOP_H  = LAYOUT.canvas_top_h
CANVAS_BOTTOM_H = LAYOUT.canvas_bottom_h
PANEL_WIDTH   = LAYOUT.panel_width

# 纪元进度条
ERA_BAR_X, ERA_BAR_Y = LAYOUT.era_bar_x, LAYOUT.era_bar_y
ERA_BAR_W, ERA_BAR_H = LAYOUT.era_bar_w, LAYOUT.era_bar_h

# 英雄点击区域
HERO_CX, HERO_CY, HERO_R = LAYOUT.hero_cx, LAYOUT.hero_cy, LAYOUT.hero_r

# HUD
HUD_X, HUD_Y_GOLD, HUD_Y_DPS = LAYOUT.hud_x, LAYOUT.hud_y_gold, LAYOUT.hud_y_dps

# 商店
SHOP_X, SHOP_Y0 = LAYOUT.shop_x, LAYOUT.shop_y0
SHOP_W, SHOP_H = LAYOUT.shop_w, LAYOUT.shop_h
SHOP_SPACING = LAYOUT.shop_spacing
SHOP_CX = SHOP_X + SHOP_W // 2

# 分类标签
TABS_X, TABS_Y = LAYOUT.tabs_x, LAYOUT.tabs_y
TAB_W, TAB_H = LAYOUT.tab_w, LAYOUT.tab_h
TAB_SPACING = LAYOUT.tab_spacing

# 浮动飘字
FLOAT_BASE_X = LAYOUT.float_base_x
FLOAT_BASE_Y = LAYOUT.float_base_y
FLOAT_OFFSET_RANGE = LAYOUT.float_offset_range
FLOAT_LIFETIME = LAYOUT.float_lifetime
FLOAT_SPEED = LAYOUT.float_speed

# 技能按钮
SKILL_X, SKILL_Y = LAYOUT.skill_x, LAYOUT.skill_y
SKILL_W, SKILL_H = LAYOUT.skill_w, LAYOUT.skill_h
SKILL_COLS, SKILL_ROWS = LAYOUT.skill_cols, LAYOUT.skill_rows
SKILL_GAP_X, SKILL_GAP_Y = LAYOUT.skill_gap_x, LAYOUT.skill_gap_y

# 转生按钮
PRESTIGE_X, PRESTIGE_Y = LAYOUT.prestige_x, LAYOUT.prestige_y
PRESTIGE_W, PRESTIGE_H = LAYOUT.prestige_w, LAYOUT.prestige_h

# 英雄面板
HERO_PANEL_X, HERO_PANEL_Y = LAYOUT.hero_panel_x, LAYOUT.hero_panel_y
HERO_PANEL_W, HERO_PANEL_H = LAYOUT.hero_panel_w, LAYOUT.hero_panel_h
HERO_PANEL_SPACING = LAYOUT.hero_panel_spacing

# 装备面板
EQUIP_PANEL_Y = LAYOUT.equip_panel_y
EQUIP_ITEM_W = LAYOUT.equip_item_w
EQUIP_SPACING = LAYOUT.equip_spacing
EQUIP_MAX_SHOW = LAYOUT.equip_max_show

# ======================================================================
#  游戏数据（保持原样）
# ======================================================================
UPGRADE_DEFS = _data["upgrades"]
ERAS = _data["eras"]
CATEGORIES = _data["categories"]
SKILLS = _data["skills"]
CHALLENGES = _data["challenges"]
PRESTIGE_UPGRADES = _data["prestige_upgrades"]
HEROES = _data["heroes"]
EQUIP_TIERS = _data["equipment_tiers"]
EQUIP_NAMES = _data["equipment_names"]
ACHIEVEMENTS = _achievements

# ---- P1 模组内容（来自 data/modules 的 add 键）----
EQUIPMENT_SLOTS = _add_content.get("equipment_slots", [])
EQUIPMENT_AFFIXES = _add_content.get("equipment_affixes", [])
EQUIPMENT_SETS = _add_content.get("equipment_sets", [])
EQUIPMENT_AFFIX_RARITY_MULT = _add_content.get("equipment_affix_rarity_mult", {})
EQUIPMENT_AFFIX_COUNT = _add_content.get("equipment_affix_count", {})
EQUIPMENT_SET_CHANCE = _add_content.get("equipment_set_chance", 0.0)
GOLDEN_VARIANTS = _add_content.get("golden_variants", [])
EVENTS = _add_content.get("events", [])
DAILY_TASKS = _add_content.get("daily_tasks", [])
CONTENT_ISSUES = _content_issues


# ======================================================================
#  工具函数
# ======================================================================
def get_upgrade_by_key(key: str) -> dict | None:
    for u in UPGRADE_DEFS:
        if u["key"] == key:
            return u
    return None
