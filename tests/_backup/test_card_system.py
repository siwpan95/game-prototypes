"""CardSystem 测试 — 加载、收集、查询、面板渲染。"""
import json
from pathlib import Path

import pygame
import pytest
pygame.init()

from core.ecs import World, Entity
from core.event_bus import EventBus
from components.card_collectible import CardCollectible
from systems.card_system import CardSystem


ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / "data" / "cards"


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def card_sys(bus):
    screen = pygame.Surface((960, 640))
    return CardSystem(screen, bus)


@pytest.fixture
def world_with_card_entity():
    w = World()
    e = Entity(eid="test_card")
    e.add(CardCollectible(card_id="lavender_01", collected=False)
    w.add_entity(e)
    return w, e


# ── 卡牌定义加载 ──────────────────────────

class TestCardDefLoading:
    def test_all_json_loaded(self, card_sys):
        json_files = list(CARDS_DIR.glob("*.json"))
        assert len(json_files) > 0, "没有找到卡牌 JSON 文件"
        for f in json_files:
            cid = f.stem
            assert cid in card_sys.cards_def, f"{cid}.json 未加载"

    def test_total_cards_matches_files(self, card_sys):
        json_count = len(list(CARDS_DIR.glob("*.json")))
        assert card_sys.total_cards == json_count

    def test_sorted_ids_covers_all(self, card_sys):
        assert set(card_sys._sorted_ids) == set(card_sys.cards_def.keys())

    def test_get_card_def_valid(self, card_sys):
        cid = list(card_sys.cards_def.keys())[0]
        d = card_sys.get_card_def(cid)
        assert "name" in d
        assert "glyph" in d

    def test_get_card_def_invalid(self, card_sys):
        assert card_sys.get_card_def("nonexistent_id") is None


# ── 卡牌收集 ──────────────────────────

class TestCardCollect:
    def test_collect_emits_event(self, card_sys, bus):
        events = []
        bus.subscribe("CARD_COLLECTED", lambda d: events.append(d))
        bus.emit("CARD_COLLECTED", {"card_id": "lavender_01", "name": "薰衣草"})
        assert "lavender_01" in card_sys.collected

    def test_has_card_after_collect(self, card_sys, bus):
        bus.emit("CARD_COLLECTED", {"card_id": "key_01"})
        assert card_sys.has_card("key_01") is True

    def test_has_card_before_collect(self, card_sys):
        assert card_sys.has_card("key_01") is False

    def test_collected_count_increments(self, card_sys, bus):
        assert card_sys.collected_count == 0
        bus.emit("CARD_COLLECTED", {"card_id": "lavender_01"})
        assert card_sys.collected_count == 1
        bus.emit("CARD_COLLECTED", {"card_id": "key_01"})
        assert card_sys.collected_count == 2

    def test_duplicate_collect_idempotent(self, card_sys, bus):
        bus.emit("CARD_COLLECTED", {"card_id": "lavender_01"})
        bus.emit("CARD_COLLECTED", {"card_id": "lavender_01"})
        assert card_sys.collected_count == 1


# ── init_collection ──────────────────────────

class TestInitCollection:
    def test_precollected_marked(self, card_sys, bus):
        w = World()
        e = Entity(eid="pre_card")
        e.add(CardCollectible(card_id="carimara_01", collected=True)
        w.add_entity(e)
        card_sys.init_collection(w)
        assert card_sys.has_card("carimara_01")

    def test_uncollected_not_marked(self, card_sys, bus):
        w = World()
        e = Entity(eid="uncollected")
        e.add(CardCollectible(card_id="key_01", collected=False)
        w.add_entity(e)
        card_sys.init_collection(w)
        assert not card_sys.has_card("key_01")


# ── 卡牌定义必需字段 ──────────────────────────

class TestCardDefIntegrity:
    def test_all_have_required_fields(self, card_sys):
        for cid, d in card_sys.cards_def.items():
            for field in ("id", "name", "glyph", "desc"):
                assert field in d, f"{cid}.json 缺少字段: {field}"

    def test_id_matches_filename(self, card_sys):
        for cid, d in card_sys.cards_def.items():
            assert d["id"] == cid, f"{cid}.json: id 字段不匹配"

    def test_glyph_is_single_char(self, card_sys):
        for cid, d in card_sys.cards_def.items():
            assert len(d["glyph"]) == 1, f"{cid}: glyph 不是单个字符: {d['glyph']}"


# ── 渲染不崩溃 ──────────────────────────

class TestCardPanelRender:
    def test_update_no_crash(self, card_sys):
        screen = pygame.Surface((960, 640))
        card_sys.screen = screen
        card_sys.update(None, 0)

    def test_render_with_collected(self, card_sys, bus):
        bus.emit("CARD_COLLECTED", {"card_id": "lavender_01"})
        screen = pygame.Surface((960, 640))
        card_sys.screen = screen
        card_sys.update(None, 0)
