import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
import math
import os
import sys
import random
from typing import Optional
from gui.theme import CLR, TAROT_ICONS, FONT_REGULAR, FONT_BOLD, register_fonts
from gui.drawing import (draw_rounded_rect, draw_gauge, pathway_sort_key,
                         group_key_of, _wrap_text)
from pathways_data import (PATHWAYS, PATHWAY_GROUPS, get_pathway, get_sequence_data,
                           get_compatible_pathways, needs_ritual, will_gender_change,
                           get_gender_change_message)
from sequences import Sequence, make_sequence
from anchor import Anchor
from pollution import PollutionLevel, PollutionSource, PollutionManager, InsanityError
from ascension import (ascend, switch_pathway, Potion, AscensionManager,
                       SequenceError, AnchorBreakError)
from uniqueness import Uniqueness, SequenceOneCharacteristic
from pathway_groups import OldOnePath, FOUR_PILLARS, promote_to_old_one, OldOneTier


class ControllersMixin:

    def _do_action(self, action_name: str, quality: str = "active"):
        """执行扮演行为（E5：支持主动/被动/背离质量维度）"""
        if not self.character:
            return
        ch = self.character
        qlabel = {"active": "主动", "passive": "被动", "divergent": "背离"}.get(quality, "主动")
        try:
            ch.perform_action(action_name, quality)
            self.add_log(f"▶ 执行扮演（{qlabel}）：{action_name}（消化 {ch.digestion_ratio:.0%}）")
            if ch.digested:
                self.add_log(f"✅ {ch.SEQUENCE_NAME} 扮演已完全消化！可晋升！")
            self.refresh_all()
        except Exception as e:
            self.add_log(f"❌ {e}")

    def _do_ascend(self):
        """晋升"""
        ch = self.character
        if ch.LEVEL <= 0:
            self.add_log("已是序列0，无法继续晋升")
            return
        if not ch.digested:
            self.add_log(f"⚠ 扮演消化未完成：{ch.digestion_ratio:.0%}，需100%")
            return

        next_lvl = ch.LEVEL - 1

        # 普通晋升（序列1~9）需要魔药材料（E1）
        formula = None
        if next_lvl >= 1:
            from pathways_data import get_potion_formula
            formula = get_potion_formula(ch.PATHWAY_KEY, next_lvl)
            if not self.state.inventory.has(formula):
                miss = "、".join(self.state.inventory.missing(formula))
                self.add_log(f"⚠ 魔药材料不足，无法晋升：缺 {miss}（点击『搜寻材料』获取）")
                return

        # 序列0 晋升：必须先完成「权柄收集」（本途径唯一性 + 3 份序列1特性）
        if next_lvl == 0:
            if not self._has_full_authority(ch.PATHWAY_KEY, ch):
                self.add_log("⚠ 晋升序列0需先在『权柄收集』面板集齐：本途径唯一性 + 3 份序列1特性")
                return
            # 先释放已收集的权柄，交由晋升流程重新聚合到新神躯
            self._release_pathway_authority(ch.PATHWAY_KEY, ch)
        try:
            ritual_check = None
            if needs_ritual(next_lvl):
                seq_data = get_sequence_data(ch.PATHWAY_KEY, next_lvl)
                ritual = seq_data.get("ritual", "")
                self.add_log(f"⚠ 序列{next_lvl}需要仪式：{ritual}")
                # 简化：假设仪式完成
                ritual_check = lambda: True

            old_char = ch
            self.character = ascend(ch, target_level=next_lvl, ritual_check=ritual_check)

            # 消耗魔药材料（E1）
            if formula is not None:
                self.state.inventory.consume(formula)

            self.add_log(f"⬆ 晋升成功！{old_char.SEQUENCE_NAME} → {self.character.SEQUENCE_NAME}")

            if will_gender_change(ch.PATHWAY_KEY, next_lvl):
                msg = get_gender_change_message(ch.PATHWAY_KEY, next_lvl)
                self.add_log(f"⚧ 性别转换：{msg}")

            self._draw_pathway_list()
            self.refresh_all()
        except (SequenceError, AnchorBreakError) as e:
            self.add_log(f"❌ 晋升失败：{e}")
        except Exception as e:
            self.add_log(f"❌ 晋升异常：{e}")

    def _do_gather_materials(self):
        """搜寻下一序列魔药所需材料（模拟世界探索 / 副本 / 交易）"""
        ch = self.character
        if not ch or ch.LEVEL <= 0:
            return
        from pathways_data import get_potion_formula
        target = ch.LEVEL - 1
        formula = get_potion_formula(ch.PATHWAY_KEY, target)
        inv = self.state.inventory
        gathered = []
        for m in [formula["main"]] + formula["supplementary"]:
            if inv.count(m) < 1:
                inv.add(m, 1)
                gathered.append(m)
        self.add_log(f"🜂 探索归来：搜集到 {len(gathered)} 份材料，可酿造序列{target}魔药")
        if self.state.inventory.has(formula):
            self.add_log("✔ 材料已齐备，可晋升！")
        self._draw_pathway_list()
        self.refresh_all()


    def _do_switch(self, to_pathway: str):
        """途径切换"""
        ch = self.character
        try:
            ch = switch_pathway(ch, to_pathway)
            self.character = ch
            tp = get_pathway(to_pathway)
            self.add_log(f"⇄ 途径切换成功！→ {tp['name']} 途径")
            self._draw_pathway_list()
            self.refresh_all()
        except Exception as e:
            self.add_log(f"❌ 切换失败：{e}")

    def _do_random_event(self):
        """触发随机事件：优先抽取数据驱动事件（E3），否则对 SAN 结算（E2）"""
        import random
        ch = self.character
        if not ch:
            return

        # ── E3：数据驱动事件 ──
        try:
            from events import pick_event
            ev = pick_event(ch, self.state)
            if ev is not None:
                self.state.pending_event = ev
                self.state.seen_events.add(ev["title"])   # E9 图鉴：记录已遭遇事件
                self.add_log(f"🎲 遭遇事件：《{ev['title']}》")
                self.refresh_all()
                return
        except Exception:
            pass

        # ── 兜底：直接对连续 SAN 结算（E2）──
        events = [
            ("封印物反应", "途径冲突", 0.2),
            ("听到隐秘存在的低语", "旧日耳语", 0.3),
            ("战斗中的精神冲击", "战斗创伤", 0.15),
            ("窥见禁忌知识", "禁忌知识", 0.25),
            ("封印物力量爆发", "封印物", 0.35),
        ]
        name, src_type, intensity = random.choice(events)
        ch.pollution.accumulate(PollutionSource(src_type, intensity))
        self.add_log(f"⚡ {name}！（{src_type}，强度{intensity:.1f}）理智 -{int(intensity*20)}")

        # 检查失控
        if ch.pollution.value >= 3:
            self.add_log("💀 污染已达失控等级！角色可能已失控！")

        self.refresh_all()

    def _do_event_choice(self, index: int):
        """处理随机事件中的玩家选择（E3）"""
        ev = self.state.pending_event
        if ev is None:
            return
        try:
            from events import resolve_choice
            logs = resolve_choice(self.state, ev, index)
            for line in logs:
                self.add_log(line)
        except Exception as e:
            self.add_log(f"❌ 事件结算异常：{e}")
        finally:
            self.state.pending_event = None
            self.refresh_all()

    # ═══════════════════════════════════════════════════════
    # 存档 / 读档（E4）
    # ═════════════════════════════════════════════════════

    def _do_save(self, slot: str = "quicksave"):
        """把当前会话序列化到指定槽位（默认 quicksave）"""
        from save_load import GameSession, slot_path
        try:
            sess = GameSession.from_state(self.state)
            path = sess.save(slot)
            self.add_log(f"💾 已存档至槽位「{slot}」：{os.path.basename(path)}")
        except Exception as e:
            self.add_log(f"❌ 存档失败：{e}")
        self.refresh_all()

    def _do_load(self, slot: str = "quicksave"):
        """从指定槽位读档并还原会话（默认 quicksave）"""
        from save_load import GameSession
        try:
            sess = GameSession.load(slot)
            sess.apply_to_state(self.state)
            self.add_log(f"📂 已读档槽位「{slot}」：{self.character.summary if self.character else '（空）'}")
            self._draw_pathway_list()
        except FileNotFoundError:
            self.add_log(f"⚠ 读档失败：槽位「{slot}」不存在")
        except Exception as e:
            self.add_log(f"❌ 读档失败：{e}")
        self.refresh_all()

    # ═══════════════════════════════════════════════════════
    # 权柄收集 / 旧日晋升（高级机制接入）
    # ═══════════════════════════════════════════════════════

    def _pathway_uniqueness(self, pk: str) -> "Uniqueness":
        """获取（或创建）某途径的唯一性（委托给 gui.helpers 共享实现）"""
        from gui.helpers import get_pathway_uniqueness
        return get_pathway_uniqueness(pk)

    def _has_full_authority(self, pk: str, char) -> bool:
        """是否已集齐该途径的唯一性 + 3 份序列1特性（且归属当前角色）"""
        u = self._pathway_uniqueness(pk)
        owned = SequenceOneCharacteristic.owned_count(pk, char)
        return (u.owner is char) and (owned >= 3)

    def _release_pathway_authority(self, pk: str, char):
        """释放当前角色持有的该途径权柄（交由晋升流程重新聚合）"""
        u = self._pathway_uniqueness(pk)
        if u.owner is char:
            u.unbind()
        for i in (1, 2, 3):
            c1 = SequenceOneCharacteristic.ensure(pk, i)
            if c1.owner is char:
                c1.unbind()

    def _do_collect_seq1(self):
        """争夺/容纳一份序列1非凡特性（权柄之争）"""
        ch = self.character
        if not ch or ch.LEVEL != 1:
            return
        pk = ch.PATHWAY_KEY
        for i in (1, 2, 3):
            c1 = SequenceOneCharacteristic.ensure(pk, i)
            if c1.owner is None:
                c1.bind(ch)
                self.add_log(f"⚔ 你容纳了 {ch.PATHWAY_NAME}途径 序列1特性#{i}")
                break
            if c1.owner is ch:
                continue  # 已持有，跳过
            # 他人持有 → 击败并夺取（单人模拟下的权柄之争）
            rival = getattr(c1.owner, "SEQUENCE_NAME", "未知")
            c1.unbind()
            c1.bind(ch)
            self.add_log(f"⚔ 你击败了 {rival}，夺取了序列1特性#{i}")
            break
        else:
            self.add_log("序列1特性已集齐（3/3）")
        self.refresh_all()

    def _do_collect_uniqueness(self):
        """容纳本途径唯一性（权柄之争）"""
        ch = self.character
        if not ch or ch.LEVEL != 1:
            return
        pk = ch.PATHWAY_KEY
        u = self._pathway_uniqueness(pk)
        if u.owner is None:
            u.bind(ch)
            self.add_log(f"🔒 你容纳了 {ch.PATHWAY_NAME}途径 唯一性")
        elif u.owner is ch:
            self.add_log("唯一性已为你持有")
        else:
            rival = getattr(u.owner, "SEQUENCE_NAME", "未知")
            u.unbind()
            u.bind(ch)
            self.add_log(f"🔒 你击败 {rival}，夺取了唯一性")
        self.refresh_all()

    # ═══════════════════════════════════════════════════════
    # 阵营 / 塔罗会社交（E7）
    # ═══════════════════════════════════════════════════════

    def _do_faction_action(self, faction_key: str, action_key: str):
        """执行阵营社交动作（消耗声望，换取材料/理智/锚）"""
        if not self.character:
            return
        from factions import FactionSystem
        try:
            fs = FactionSystem(self.state.factions)
            logs = fs.do_action(self.state, action_key)
            self.state.factions = fs.to_dict()
            for line in logs:
                self.add_log(line)
            # 阵营动作可能改变库存/理智，刷新相关面板
            self._draw_pathway_list()
        except Exception as e:
            self.add_log(f"❌ 阵营行动失败：{e}")
        self.refresh_all()

    def _do_promote_old_one(self):
        """晋升旧日：聚合途径组唯一性 + 源质"""
        ch = self.character
        if not ch or ch.LEVEL != 0:
            return
        gk = group_key_of(ch.PATHWAY_KEY)
        if not gk:
            self.add_log("⚠ 该途径不属于任何权柄体系，无法晋升旧日")
            return
        try:
            comp = promote_to_old_one(gk, ch)
            self.old_one_info = comp
            pillar = comp.get("pillar")
            tier = comp.get("tier") or "普通旧日"
            msg = f"🌟 晋升旧日成功！{comp['group']}"
            if pillar:
                msg += f"（支柱：{pillar}）"
            self.add_log(msg)
            self.add_log(f"   位阶：{tier}｜已聚合 {len(comp['pathways'])} 条途径的唯一性 + 序列1")
        except (SequenceError, RuntimeError) as e:
            self.add_log(f"❌ 旧日晋升失败（权柄争夺）：{e}")
        except Exception as e:
            self.add_log(f"❌ 旧日晋升异常：{e}")
        self.refresh_all()

    # ═══════════════════════════════════════════════════════
    # AI 对手非凡者（E8）
    # ═══════════════════════════════════════════════════════

    def _pick_other_pathway(self) -> str:
        """选一条与玩家不同的途径作为对手出生途径（优先同组，竞争更直接）。"""
        from pathways_data import PATHWAYS
        mine = self.character.PATHWAY_KEY if self.character else None
        opts = [pk for pk in PATHWAYS if pk != mine]
        return random.choice(opts)

    def _ensure_rival_system(self) -> "RivalSystem":
        from rivals import RivalSystem
        if self.state.rival_system is None:
            self.state.rival_system = RivalSystem(seed=12345)
        return self.state.rival_system

    def _do_rival_tick(self):
        """推进时间一个 tick：所有对手各推进一步，并在权柄上形成竞争。"""
        if not self.character:
            return
        rs = self._ensure_rival_system()
        if rs.count() == 0:
            # 首次推进时自动引入一名对手，便于直接体验竞争
            r = rs.add_rival(self._pick_other_pathway())
            self.add_log(f"⚔ 新对手登场：{r.name}（{r.character.PATHWAY_NAME}途径）")
        logs = rs.tick(1)
        for line in logs:
            self.add_log(line)
        # 竞争提示：若某对手已占住玩家本途径权柄，提醒需「击败并夺取」
        self._warn_rival_contention()
        self.refresh_all()

    def _do_add_rival(self, pathway_key: str = None):
        """添加一名 AI 对手（默认选与玩家不同的途径）。"""
        rs = self._ensure_rival_system()
        if pathway_key is None:
            pathway_key = self._pick_other_pathway()
        r = rs.add_rival(pathway_key)
        self.add_log(f"⚔ 新对手登场：{r.name}（{r.character.PATHWAY_NAME}途径）")
        self.refresh_all()

    def _warn_rival_contention(self):
        """若某对手已占住玩家所在途径的唯一性/序列1，提示玩家需争夺。"""
        ch = self.character
        if not ch or ch.LEVEL > 1:
            return
        from uniqueness import Uniqueness, SequenceOneCharacteristic
        from gui.helpers import get_pathway_uniqueness
        u = get_pathway_uniqueness(ch.PATHWAY_KEY)
        if u.owner is not None and u.owner is not ch:
            self.add_log(f"⚠ 你所在途径的唯一性已被对手占据，需「击败并夺取」")
        for i in (1, 2, 3):
            c = SequenceOneCharacteristic.ensure(ch.PATHWAY_KEY, i)
            if c.owner is not None and c.owner is not ch:
                self.add_log(f"⚠ 序列1特性 #{i} 已被对手占据，需「击败并夺取」")
                break

    # ═══════════════════════════════════════════════════════
    # 沉浸模式（E10）：可选环境音效开关
    # ═══════════════════════════════════════════════════════

    def _do_toggle_ambient(self):
        self.state.ambient = not getattr(self.state, "ambient", False)
        if self.state.ambient:
            self.add_log("🌫 沉浸模式开启：灰雾之上的低语在耳畔回响……")
            self._play_ambient()
        else:
            self.add_log("🌫 沉浸模式关闭。")
        self.refresh_all()

    def _play_ambient(self):
        """在 Windows 上播放一段极轻的低频音作为「灰雾低语」（无音频资源时为安全空操作）。"""
        try:
            import winsound
            winsound.Beep(180, 500)
        except Exception:
            pass

    # ─── 日志 ───
