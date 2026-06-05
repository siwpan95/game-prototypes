"""
卡瑞玛拉: 枯肢之下 - 文字网格冒险
=====================================
基于 pygame-ce 的文字世界渲染。
支持 Mod/DLC 扩展 — 通过 mods/ 目录加载额外地图。

操控: WASD/方向键 移动, 空格 触碰相邻物件, Tab 设置面板
"""
import pygame
from core.paths import ROOT
from core.event_bus import EventBus
from core.map_data import MapData
from core.config import WINDOW_W, WINDOW_H
from core.text_world import create_text_world
from core.mod_loader import ModManager, MapManager

from systems.text_renderer import TextWorldRenderer
from systems.sanity_system import SanitySystem
from systems.player_controller import PlayerController
from systems.ui_system import UISystem
from systems.card_system import CardSystem
from systems.mechanism_system import MechanismSystem
from systems.audio_system import AudioSystem
from systems.settings_system import SettingsSystem

from components.sanity import Sanity

pygame.init()

screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
pygame.display.set_caption("卡瑞玛拉：枯肢之下 — CARIMARA: Beneath the Forlorn Limbs")
clock = pygame.time.Clock()

# ── Mod 管理（全局单例）──
mod_mgr = ModManager()


def setup_search_paths():
    """设置 PlayerController 的卡牌/记忆搜索路径。"""
    import systems.player_controller as pc
    pc.MEMORY_SEARCH_PATHS = mod_mgr.all_memory_paths()
    pc.CARD_SEARCH_PATHS = mod_mgr.all_card_dirs()


def build_game():
    """构建游戏世界和所有系统。"""
    setup_search_paths()

    bus = EventBus()
    map_data = MapData()
    world = create_text_world(bus, screen)

    ui_sys = UISystem(screen, bus)
    text_renderer = TextWorldRenderer(screen, map_data=map_data)
    sanity_sys = SanitySystem(event_bus=bus)
    card_sys = CardSystem(screen, bus)
    mech_sys = MechanismSystem(map_data, bus, ui_system=ui_sys)

    # MapManager — 管理地图加载/切换，需要在 PlayerController 之前创建
    map_mgr = MapManager(mod_mgr, world, map_data, bus,
                         card_sys=card_sys, mech_sys=mech_sys, ui_sys=ui_sys)

    player_ctrl = PlayerController(bus, map_data=map_data, map_manager=map_mgr)

    # 音频系统
    audio_sys = None
    audio_dir = ROOT / "assets" / "audio"
    if audio_dir.exists():
        try:
            audio_sys = AudioSystem(bus)
        except Exception:
            audio_sys = None

    card_sys.init_collection(world)

    # 设置系统
    settings_sys = SettingsSystem(screen, bus, card_sys=card_sys, audio_sys=audio_sys)

    world.add_system(text_renderer)
    world.add_system(sanity_sys)
    world.add_system(ui_sys)
    world.add_system(card_sys)
    world.add_system(mech_sys)
    world.add_system(settings_sys)

    # ── 加载初始地图（Base Mod 的 mansion）──
    map_mgr.load_initial_map(mod_id=None, map_id="mansion")

    # ── 事件监听 ──

    @bus.subscribe("MEMORY_TRIGGERED")
    def on_memory(data):
        player = world.entities["player"]
        s = player.get(Sanity)
        cost = data.get("sanity_cost", 0)
        if s and cost > 0:
            s.value -= cost

        answer_card = data.get("answer_card", "")
        if answer_card and card_sys.has_card(answer_card):
            cd = card_sys.get_card_def(answer_card)
            if cd:
                extra_data = {
                    "name": f"回答：{cd['name']}",
                    "sanity_cost": 0,
                    "text": f"你举起「{cd['name']}」的卡牌。{cd['desc']}\n\n记忆的碎片开始拼合……",
                }
                bus.emit("MEMORY_TRIGGERED", extra_data)

    @bus.subscribe("SANITY_RECOVER")
    def on_sanity_recover(data):
        player = world.entities.get("player")
        if not player:
            return
        s = player.get(Sanity)
        amount = data.get("amount", 0)
        if s and amount > 0:
            s.value = min(s.value + amount, s.max_value)

    @bus.subscribe("CARD_COLLECTED")
    def check_win(data):
        if card_sys.collected_count >= card_sys.total_cards:
            bus.emit("GAME_WIN", {})

    # ── 地图切换成功提示 ──
    @bus.subscribe("MAP_LOADED")
    def on_map_loaded(data):
        ui_sys.show_toast(f"进入：{data.get('map_name', '???')}")

    return world, {
        "bus": bus,
        "player_ctrl": player_ctrl,
        "ui_sys": ui_sys,
        "sanity_sys": sanity_sys,
        "card_sys": card_sys,
        "audio_sys": audio_sys,
        "settings_sys": settings_sys,
        "map_mgr": map_mgr,
    }


world, game = build_game()
running = True

while running:
    dt = clock.tick(60)

    events = pygame.event.get()
    consumed = []
    for event in events:
        if event.type == pygame.QUIT:
            running = False
            continue
        if (event.type == pygame.KEYDOWN and event.key == pygame.K_TAB
                and not game["ui_sys"].game_over and not game["ui_sys"].game_won):
            game["settings_sys"].toggle()
            continue
        consumed.append(event)

    if game["ui_sys"].game_over or game["ui_sys"].game_won:
        keys = pygame.key.get_pressed()
        if keys[pygame.K_r]:
            world, game = build_game()
            continue
        if keys[pygame.K_q]:
            running = False
            continue
        world.update(dt)
        if game["audio_sys"]:
            game["audio_sys"].update(world, dt)
        pygame.display.flip()
        continue

    if game["settings_sys"].open:
        for event in consumed:
            game["settings_sys"].handle_event(event)
        if game["settings_sys"].quit_requested:
            running = False
            continue
    else:
        game["player_ctrl"].handle_input(world, dt, consumed)

    world.update(dt)
    if game["audio_sys"]:
        game["audio_sys"].update(world, dt)
    pygame.display.flip()

pygame.quit()
