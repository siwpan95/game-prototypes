"""
文字世界工厂 — 创建玩家实体。
地图物件、卡牌、传送门等实体由 MapManager 管理。
"""
from core.ecs import World, Entity
from components.grid_position import GridPosition
from components.text_glyph import TextGlyph
from components.sanity import Sanity
from components.card_collectible import CardCollectible


def create_text_world(event_bus, screen):
    """创建世界并添加玩家实体。
    地图物件和卡牌实体由 MapManager.load_initial_map() 后续注入。"""
    world = World()

    # ── 玩家 (卡瑞玛拉) — 森林精灵，哑巴通灵者 ──
    player = Entity("player")
    player.add(Sanity(120, max_value=120))
    player.add(CardCollectible(card_id="carimara_01", collected=True))
    player.add(GridPosition(col=19, row=13))
    player.add(TextGlyph(char="我", fg=(200, 180, 140), highlight=True))
    world.add_entity(player)

    return world
