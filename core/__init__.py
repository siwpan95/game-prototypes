# -*- coding: utf-8 -*-
"""
core/__init__.py — 包入口与 Services 门面

设计约束（铁律，会被 grep 检查）：
- core/ 内禁止 import tkinter / print() / input() / time.sleep()
- 表现层只 from core import get_services；禁止直接 import core 子模块

Services 是领域层对外的唯一聚合点。B1 阶段它聚合：
  content (ContentLoader) / profile (Profile) / saves (SaveManager)
B2-B5 会在各自批次里把 anti_repeat / talents / deck / events / careers /
relations / endings / achievements / report 等系统挂到 Services 上，
本文件预留好挂载点，保证 get_services() 在任意批次都可用。
"""

from __future__ import annotations

from typing import Optional

from core.constants import SCHEMA_VERSION
from core.paths import ROOT, CONTENT_DIR, SAVES_DIR, PROFILE_PATH
from core.models import Talent, Career, Ending, Achievement, EventItem, CardItem


class Services:
    """领域层服务聚合门面。表现层只通过它访问 core。"""

    def __init__(self) -> None:
        # ── B1 已落地的系统 ──
        from core.content_loader import ContentLoader
        from core.profile import Profile
        from core.savegame import SaveManager

        self.content: ContentLoader = ContentLoader()
        self.profile: Profile = Profile(PROFILE_PATH)
        self.saves: SaveManager = SaveManager()

        # 内容与档案先就绪，B2a 的抽样中间层依赖它们
        self.content.load()
        self.profile.load()

        # ── B2a 抽样中间层（已落地）──
        from core.antirepeat import AntiRepeatEngine
        from core.deck import DeckBinder
        from core.events_picker import EventPicker

        self.anti_repeat: AntiRepeatEngine = AntiRepeatEngine(self.profile)
        self.deck: DeckBinder = DeckBinder(self.content, self.anti_repeat, self.profile)
        self.events: EventPicker = EventPicker(self.content, self.anti_repeat, self.profile)

        # ── B2b-B5 挂载点（当前为 None，后续批次注入）──
        self.talents = None          # B2b: TalentSystem
        self.careers = None          # B4: CareerSystem
        self.relations = None        # B4: RelationshipSystem
        self.endings = None          # B4: EndingResolver
        self.achievements = None     # B4: AchievementSystem
        self.report = None           # B4: LifeReport

        # 便捷常量
        self.SCHEMA_VERSION = SCHEMA_VERSION
        self.ROOT = ROOT
        self.CONTENT_DIR = CONTENT_DIR
        self.SAVES_DIR = SAVES_DIR
        self.PROFILE_PATH = PROFILE_PATH

    # 数据模型类透传，方便表现层 from core import get_services 后直接取用
    Talent = Talent
    Career = Career
    Ending = Ending
    Achievement = Achievement
    EventItem = EventItem
    CardItem = CardItem


_services_instance: Optional[Services] = None


def get_services() -> Services:
    """获取 Services 单例（懒加载，进程内共享）。"""
    global _services_instance
    if _services_instance is None:
        _services_instance = Services()
    return _services_instance


__all__ = ["Services", "get_services"]
