"""核心游戏引擎 — Progress Quest 2"""

import time
import numpy as np
import os
from .types import (
    Race, Class, Stack, Monster, Quest, QueueItem,
    Equipment, QueueItemType, CurrentActionType, Color, GameState,
    LoadError, SaveError,
)
from .character import Character
from .newgame import NewGame
from .serializer import (
    save_to_file, load_from_file, _UnsupportedVersionError,
    _CorruptError, _InvalidDataError, _SaveTooLargeError,
)
from . import constants as C
from . import names as N
from .utils.plural import plural
from .utils.romannumerals import get_roman_numerals
from .utils.namegenerator import generate_random_name

# 数据导入
from .data.spells import get_spells
from .data.weapons import get_random_weapon
from .data.shields import get_random_shield
from .data.armors import get_random_armor
from .data.monsters import get_random_monster
from .data.titles import get_random_title, get_random_impressive_title
from .data.races import get_random_race
from .data.classes import get_random_class
from .data.boringitems import get_random_boring_item
from .data.itemattributes import get_random_item_attribute
from .data.specials import get_random_special
from .data.itemofs import get_random_item_of
from .data.offensiveattributes import get_random_good_offensive_attribute, get_random_bad_offensive_attribute
from .data.defensiveattributes import get_random_good_defensive_attribute, get_random_bad_defensive_attribute


VOWELS = "AEIOUÜaeiouü"


def _indefinite(name: str, count: int) -> str:
    """不定冠词"""
    if count == 1:
        if name and name[0] in VOWELS:
            return f"an {name}"
        return f"a {name}"
    return f"{count} {plural(name)}"


def _definite(name: str, count: int) -> str:
    """定冠词"""
    if count > 1:
        name = f"{count} {plural(name)}"
    return f"the {name}"


class Game:
    """Progress Quest 2 游戏引擎"""

    def __init__(self):
        self._rng = np.random.default_rng()
        self._filename = ""
        self._game_state = GameState.None_
        self.character = Character()
        # A4：自动存盘开关与失败回调（避免写失败被静默吞掉，postmortem Why3）
        self._auto_save_enabled = True
        self._save_error_handler = None
        # #10：自动存盘节流——记录上次成功写盘时刻，避免密集事件频繁写盘
        self._last_save_time = 0.0

    # ========== 存档 ==========

    def load_game(self, filepath: str) -> LoadError:
        """从 gzip JSON 加载存档"""
        try:
            load_from_file(filepath, self.character)
        except FileNotFoundError:
            return LoadError.FileNotFound
        except _UnsupportedVersionError:
            # A6：未知/未来版本头 -> 细分错误，而非 blanket NotValidSaveFile
            return LoadError.UnknownSaveVersion
        except _CorruptError:
            # ADR-001：信封/结构层损坏（解压失败/JSON 解析失败/mac 不匹配）
            return LoadError.Corrupt
        except _InvalidDataError:
            # #1：数据层 schema 校验失败（结构可解析但逻辑值非法）
            return LoadError.NotValidSaveFile
        except _SaveTooLargeError:
            # #3：gzip 炸弹防护——解压体积超限，按安全策略拒绝
            return LoadError.NotValidSaveFile
        except Exception:
            return LoadError.NotValidSaveFile
        self._filename = filepath
        self._game_state = GameState.Ready
        return LoadError.None_

    def load_game_with_recovery(self, filepath: str):
        """A7 启动自愈：加载存档；主档损坏时隔离为 .corrupt 并回退最近 .bak。

        返回 (LoadError, recovered: bool)：
          - 正常加载            -> (None_, False)
          - 主档损坏 + .bak 完好 -> 隔离主档为 <file>.corrupt（保留取证样本，不删除）、
                                    回填主档、-> (None_, True)
          - 主档损坏 + 无 .bak  -> (primary_err, False)，调用方应提示开新游戏
          - 主档与 .bak 均损坏  -> (bak_err, False)
          - 文件不存在          -> (FileNotFound, False)
        """
        primary = self.load_game(filepath)
        if primary == LoadError.None_:
            return LoadError.None_, False
        # 仅信封/数据损坏触发自愈；FileNotFound 等不自愈
        if primary not in (LoadError.Corrupt, LoadError.NotValidSaveFile,
                           LoadError.UnknownSaveVersion):
            return primary, False

        # 隔离损坏主档为 .corrupt（保留唯一取证样本，不删除）
        corrupt_path = filepath + ".corrupt"
        try:
            if os.path.exists(filepath):
                os.replace(filepath, corrupt_path)
        except OSError:
            pass

        # 回退最近 .bak
        bak = filepath + ".bak"
        if os.path.exists(bak):
            bak_err = self.load_game(bak)
            if bak_err == LoadError.None_:
                # 回填主档：先把路径记回主档（load_game(bak) 会把 _filename 记成 .bak），
                # 此时 filepath 已被隔离为 .corrupt，save_to_file 不会再覆盖 .bak
                self._filename = filepath
                self.save_game()
                return LoadError.None_, True
            return bak_err, False
        return primary, False

    def save_game(self, filepath: str = "") -> SaveError:
        if filepath:
            self._filename = filepath
        if not self._filename:
            # 新游戏首次存档：自动生成默认路径（与 main.py 同级）
            default_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self._filename = os.path.join(default_dir, "savefile.pq2")
        try:
            save_to_file(self.character, self._filename)
        except OSError as e:
            import errno
            if e.errno == errno.ENOSPC:
                return SaveError.OutOfSpace
            if e.errno in (errno.EACCES, errno.EPERM):
                return SaveError.InvalidPermissions
            return SaveError.InvalidPath
        except Exception:
            return SaveError.InvalidPath
        return SaveError.None_

    def set_auto_save(self, enabled: bool) -> None:
        """A4：允许外部（GUI）在写盘失败后暂停自动存盘"""
        self._auto_save_enabled = enabled

    def _auto_save(self) -> None:
        """A4：自动存盘点。消费 save_game 返回错误并上报 _save_error_handler，
        避免磁盘满/权限不足被静默忽略，导致内存状态与磁盘不一致、未来更易损坏。
        #10 节流：距上次成功写盘不足阈值时跳过，避免升级/完成任务密集时
        频繁写盘导致磁盘抖动与性能下降。
        """
        if not self._auto_save_enabled:
            return
        now = time.monotonic()
        if now - self._last_save_time < C.AUTO_SAVE_MIN_INTERVAL_S:
            return
        err = self.save_game()
        if err != SaveError.None_:
            if self._save_error_handler is not None:
                self._save_error_handler(err)
            return
        self._last_save_time = now

    def verify_save(self, filepath: str) -> LoadError:
        """A6 钩子：写后读回校验（信封/防御式解析已落地，细化错误类型）。
        用一次性角色试加载，返回 LoadError，供 A6 消费返回错误。
        """
        from .character import Character
        probe = Character()
        try:
            load_from_file(filepath, probe)
        except _CorruptError:
            return LoadError.Corrupt
        except _InvalidDataError:
            return LoadError.NotValidSaveFile
        except _UnsupportedVersionError:
            return LoadError.UnknownSaveVersion
        except Exception:
            return LoadError.NotValidSaveFile
        return LoadError.None_

    # ========== 新游戏 ==========

    def start_new_game(self) -> NewGame:
        return NewGame(self._rng, self._on_character_created)

    def _on_character_created(self, character: Character):
        self.character = character
        self.character.Level = 1
        self.character.Experience = 0
        self.character.MAX_HP = self._rng.integers(0, 9) + character.CON // 6
        self.character.MAX_MP = self._rng.integers(0, 9) + character.INT // 6
        # #5：把种族/职业的属性加成真正应用到角色数值，让养成机制生效
        # （之前 Race/Class.attributes 只参与序列化与哈希，被完全忽略）
        _STAT_ATTRS = ("STR", "CON", "DEX", "INT", "WIS", "CHA")
        for attr in list(character.CharacterRace.attributes) + list(character.CharacterClass.attributes):
            if attr in _STAT_ATTRS:
                setattr(character, attr, getattr(character, attr) + 1)
            elif attr == "HP Max":
                character.MAX_HP += 1
            elif attr == "MP Max":
                character.MAX_MP += 1
        self.character.Equipment[Equipment.Weapon] = "Sharp Rock"
        for i in range(Equipment.Shield, Equipment.Sollerets + 1):
            self.character.Equipment[i] = ""
        self.character.Gold = 0
        self.character.MaxQuestProgress = 0
        self.character.CurrentAction = CurrentActionType.Loading
        self.character.CurrentActionLabel = "Loading."
        self.character.CurrentProgress = 0
        self.character.MaxProgress = C.INITIAL_MAX_PROGRESS
        self.character.Queue.append(QueueItem(QueueItemType.Task, "Experiencing an enigmatic and foreboding night vision", 10))
        self.character.Queue.append(QueueItem(QueueItemType.Task, "Much is revealed about that wise old bastard you'd underestimated", 6))
        self.character.Queue.append(QueueItem(QueueItemType.Task, "A shocking series of events leaves you alone and bewildered, but resolute", 6))
        self.character.Queue.append(QueueItem(QueueItemType.Task, "Drawing upon an unrealized reserve of determination, you set out on a long and dangerous journey", 4))
        self.character.Queue.append(QueueItem(QueueItemType.Plot, "Loading", 2))
        self.character.Plot.append("Prologue")
        self._game_state = GameState.Ready

    # ========== 主循环 ==========

    def tick(self, ms: int):
        """推进游戏时钟"""
        if self._game_state != GameState.Ready:
            return
        while ms > 0:
            progress = min(ms, C.TICK_MS)
            gain = self.character.CurrentAction == CurrentActionType.Kill

            if self.character.CurrentProgress >= self.character.MaxProgress:
                if self.character.CurrentAction == CurrentActionType.Loading:
                    self.character.MaxProgress = 0

                # 获得经验 / 升级
                if gain and self.character.Experience >= self._get_level_up_max_value():
                    self._level_up()
                else:
                    self.character.Experience += self.character.MaxProgress // C.MS_PER_UNIT

                # 推进任务进度 (只有在战斗中 && 剧情已开始)
                if gain and len(self.character.Plot) > 1:
                    if self.character.CurrentQuestProgress >= self.character.MaxQuestProgress:
                        self._complete_quest()
                    elif self.character.Quests:
                        self.character.CurrentQuestProgress += self.character.MaxProgress // C.MS_PER_UNIT

                # 推进剧情进度 (战斗中 或 序幕阶段)
                should_progress_plot = gain or len(self.character.Plot) <= 1
                if should_progress_plot:
                    if self.character.CurrentPlotProgress >= self._get_plot_max_value():
                        self._interplot_cinematic()
                    else:
                        self.character.CurrentPlotProgress += self.character.MaxProgress // C.MS_PER_UNIT

                self._dequeue()
            else:
                self.character.CurrentProgress += progress

            ms -= progress

    def get_state(self) -> GameState:
        return self._game_state

    def close(self):
        self.save_game()
        self._game_state = GameState.Finished

    # ========== 能力值计算 ==========

    def _get_level_up_max_value(self) -> int:
        """升级所需经验 = (BASE + GROWTH^Level) * MULT 秒 (非线性增长)"""
        return int((C.LEVEL_EXP_BASE + C.LEVEL_EXP_GROWTH ** self.character.Level) * C.LEVEL_EXP_MULT)

    def get_encumbrance(self) -> int:
        """背包负重"""
        return sum(item.count for item in self.character.Inventory)

    def get_encumbrance_max_value(self) -> int:
        return C.ENCUMBRANCE_BASE + self.character.STR

    def _get_plot_max_value(self) -> int:
        if len(self.character.Plot) <= 1:
            return C.PLOT_PROLOGUE_MAX
        return C.PLOT_MAX_SECONDS * (1 + C.PLOT_MAX_PER_CHAPTER * len(self.character.Plot))

    # ========== 装备价格 ==========

    @staticmethod
    def _equip_price(level: int) -> int:
        return C.EQUIP_PRICE_A * level * level + C.EQUIP_PRICE_B * level + C.EQUIP_PRICE_C

    # ========== 升级 ==========

    def _level_up(self):
        c = self.character
        c.Level += 1
        c.MAX_HP += c.CON // C.HP_GROWTH_PER_CON + C.HP_GROWTH_BASE + self._rng.integers(0, C.GROWTH_DICE)
        c.MAX_MP += c.INT // C.MP_GROWTH_PER_INT + C.MP_GROWTH_BASE + self._rng.integers(0, C.GROWTH_DICE)
        self._win_stat()
        self._win_stat()
        self._win_spell()
        c.Experience = 0
        self._auto_save()

    def _win_stat(self):
        """属性点分配：50%随机，50%按平方加权"""
        odds = self._rng.integers(0, 2)
        stat_names = ["STR", "CON", "DEX", "INT", "WIS", "CHA", "MAX_HP", "MAX_MP"]

        if odds < 1:
            idx = self._rng.integers(0, 8)
        else:
            # 按属性值的平方加权采样
            values = [getattr(self.character, s) for s in stat_names[:6]]
            t = sum(v * v for v in values)
            t = abs(int(self._rng.integers(-128, 127))) % max(t, 1)
            idx = -1
            while t >= 0:
                idx += 1
                t -= values[idx] * values[idx]

        attr_name = stat_names[idx]
        setattr(self.character, attr_name, getattr(self.character, attr_name) + 1)

    def _win_spell(self):
        spells = get_spells()
        min_amount = min(self.character.WIS + self.character.Level, len(spells))
        random_number = min(
            self._rng.integers(0, min_amount),
            self._rng.integers(0, min_amount)
        )
        spell_name = spells[random_number]

        existing = False
        for curr_spell in self.character.Spells:
            if curr_spell.name == spell_name:
                curr_spell.count += 1
                existing = True
                break
        if not existing:
            self.character.Spells.append(Stack(spell_name, 1))

    def _win_item(self):
        # 库存超过 250 时，有概率复制已有物品
        if len(self.character.Inventory) > C.INVENTORY_COPY_THRESHOLD and self._rng.integers(0, 2) == 0:
            idx = self._rng.integers(0, len(self.character.Inventory))
            item = self.character.Inventory[idx]
            item.count += 1
            return
        item_name = f"{self._interesting_item()} of {get_random_item_of(self._rng)}"
        self._add_to_inventory(Stack(item_name, 1))

    def _interesting_item(self) -> str:
        return f"{get_random_item_attribute(self._rng)} {get_random_special(self._rng)}"

    def _win_equip(self):
        c = self.character
        equipment_type = self._rng.integers(0, Equipment.Sollerets + 1)

        if equipment_type == Equipment.Weapon:
            get_item = get_random_weapon
            get_better = get_random_good_offensive_attribute
            get_worse = get_random_bad_offensive_attribute
        else:
            get_better = get_random_good_defensive_attribute
            get_worse = get_random_bad_defensive_attribute
            if equipment_type == Equipment.Shield:
                get_item = get_random_shield
            else:
                get_item = get_random_armor

        # LPick: 5选1最接近等级的物品
        goal = c.Level
        item = get_item(self._rng)
        for _ in range(5):
            s = get_item(self._rng)
            if abs(goal - s.level) < abs(goal - item.level):
                item = s

        name = item.label
        quality = item.level
        plus = c.Level - quality

        if plus < 0:
            get_better = get_worse

        count = 0
        modifiers = []
        while count < 2 and plus != 0:
            attr = get_better(self._rng)
            modifier = attr.label
            if modifier in modifiers:
                break  # 不重复
            if abs(plus) < abs(attr.value):
                break
            modifiers.append(modifier)
            plus -= attr.value
            count += 1

        for mod in modifiers:
            name = f"{mod} {name}"
        # #15：plus<0（劣质装备）只保留修饰词，不应出现 "-N" 畸形前缀；
        # 仅当 plus>0 时加 "+N" 前缀。
        if plus > 0:
            name = f"+{plus} {name}"

        c.Equipment[equipment_type] = name

    # ========== 队列处理 ==========

    def _dequeue(self):
        c = self.character
        while c.CurrentProgress >= c.MaxProgress:
            # 处理上一个行动的结果
            if c.CurrentAction == CurrentActionType.Kill:
                if c.CurrentMonster.drop == "*":
                    self._win_item()
                elif c.CurrentMonster.drop:
                    item_name = f"{c.CurrentMonster.name} {c.CurrentMonster.drop}"
                    self._add_to_inventory(Stack(item_name, 1))
            elif c.CurrentAction == CurrentActionType.Buying:
                c.Gold -= self._equip_price(c.Level)
                self._win_equip()
            elif c.CurrentAction in (CurrentActionType.Market, CurrentActionType.Selling):
                if c.CurrentAction == CurrentActionType.Selling:
                    item = c.Inventory.pop(0)
                    amount = item.count * c.Level
                    if " of " in item.name:
                        amount *= (1 + min(self._rng.integers(0, 10), self._rng.integers(0, 10))) * \
                                  (1 + min(self._rng.integers(0, c.Level), self._rng.integers(0, c.Level)))
                    c.Gold += amount
                if c.Inventory:
                    item = c.Inventory[0]
                    c.CurrentActionLabel = f"Selling {_indefinite(item.name, item.count)}"
                    c.CurrentAction = CurrentActionType.Selling
                    c.CurrentProgress = 0
                    c.MaxProgress = C.SELLING_MAX_PROGRESS
                    break

            old_action = c.CurrentAction
            c.CurrentAction = CurrentActionType.None_

            if c.Queue:
                qi = c.Queue.pop(0)
                item_label = qi.label
                if qi.type in (QueueItemType.Task, QueueItemType.Plot):
                    if qi.type == QueueItemType.Plot:
                        self._complete_act()
                        item_label = f"Loading {c.Plot[-1]}"
                    c.CurrentActionLabel = item_label
                    c.CurrentProgress = 0
                    c.MaxProgress = qi.ms * C.MS_PER_UNIT
            elif self.get_encumbrance() >= self.get_encumbrance_max_value():
                c.CurrentActionLabel = "Heading to market to sell loot"
                c.CurrentAction = CurrentActionType.Market
                c.CurrentProgress = 0
                c.MaxProgress = 4000
            elif old_action not in (CurrentActionType.Kill, CurrentActionType.Heading):
                if c.Gold > self._equip_price(c.Level):
                    c.CurrentActionLabel = "Negotiating purchase of better equipment"
                    c.CurrentProgress = 0
                    c.MaxProgress = C.BUYING_MAX_PROGRESS
                    c.CurrentAction = CurrentActionType.Buying
                else:
                    c.CurrentActionLabel = "Heading to the killing fields"
                    c.CurrentProgress = 0
                    c.MaxProgress = C.MARKET_MAX_PROGRESS
                    c.CurrentAction = CurrentActionType.Heading
            else:
                self._monster_task()

    # ========== 怪物生成 ==========

    def _odds(self, chance: int, out_of: int) -> bool:
        return self._rng.integers(0, out_of) < chance

    def _monster_task(self):
        c = self.character
        level = int(c.Level)
        lev = 0
        monster = Monster("", 0)
        definite = False

        for i in range(level, 0, -1):
            if self._odds(*C.MONSTER_ODDS_PASS):
                level += self._rng.integers(0, 2) * 2 - 1
        level = max(level, 1)

        if self._odds(1, 25):
            # 使用 NPC
            name = get_random_race(self._rng).name
            if self._odds(1, 2):
                name = f"passing {name} {get_random_class(self._rng).name}"
            else:
                name = get_random_title(self._rng, True)
                definite = True
            lev = level
            monster = Monster(name, level, "*")
        elif c.Quests and c.Quests[-1].monster is not None and self._odds(1, 4):
            # 任务怪物
            monster = c.Quests[-1].monster
            lev = monster.level
        else:
            # 5选1最近原则
            monster = get_random_monster(self._rng)
            lev = monster.level
            for _ in range(5):
                m1 = get_random_monster(self._rng)
                if abs(level - m1.level) < abs(level - lev):
                    monster = m1
                    lev = monster.level

        name = monster.name
        qty = 1

        if level - lev > C.MONSTER_BIG_GAP:
            qty = int(level + self._rng.integers(0, level)) // max(lev, 1)
            # #15：防止 qty>level 导致 level//qty 退化为 0（产生等级为 0 的退化怪物）
            qty = max(1, min(qty, level))
            level = max(level // qty, 1)

        # 怪物修饰词
        if level - lev <= -10:
            name = "imaginary" + name
        elif level - lev < -5:
            i = 10 + (level - lev)
            i = 5 - self._rng.integers(0, i + 1)
            name = N.format_sick(i, N.format_young((lev - level) - i, name))
        elif level - lev < 0 and self._rng.integers(0, 2) == 1:
            name = N.format_sick(level - lev, name)
        elif level - lev < 0:
            name = N.format_young(level - lev, name)
        elif level - lev >= 10:
            name = "messianic " + name
        elif level - lev > 5:
            i = 10 - (level - lev)
            i = 5 - self._rng.integers(0, i + 1)
            name = N.format_big(i, N.format_special((level - lev) - i, name))
        elif level - lev > 0 and self._rng.integers(0, 2) == 1:
            name = N.format_big(level - lev, name)
        elif level - lev > 0:
            name = N.format_special(level - lev, name)

        lev = level
        level = lev * qty

        if not definite:
            name = _indefinite(name, qty)

        c.CurrentAction = CurrentActionType.Kill
        c.CurrentMonster = monster
        c.CurrentActionLabel = f"Executing {name}"
        c.CurrentProgress = 0
        c.MaxProgress = (5 * level * C.MS_PER_UNIT) // c.Level

    # 名称修饰词格式化已抽到 pq2.names（#13 拆分巨型类）

    # ========== 任务 ==========

    def _complete_quest(self):
        c = self.character
        c.CurrentQuestProgress = 0
        c.MaxQuestProgress = 50 + self._rng.integers(0, 100)

        if c.Quests:
            roll = self._rng.integers(0, 4)
            if roll == 0:
                self._win_spell()
            elif roll == 1:
                self._win_equip()
            elif roll == 2:
                self._win_stat()
            else:
                self._win_item()

        # 最多 100 个任务
        while len(c.Quests) > C.QUEST_KEEP_MAX:
            c.Quests.pop(0)

        quest_type = self._rng.integers(0, 5)
        quest = Quest("")

        if quest_type == 0:
            # Exterminate
            level = c.Level
            lev = 0
            for i in range(1, 5):
                m = get_random_monster(self._rng)
                if i == 1 or abs(m.level - level) < abs(lev - level):
                    lev = m.level
                    quest.monster = m
            quest.label = f"Exterminate {_definite(quest.monster.name, 2)}"
        elif quest_type == 1:
            quest.label = f"Seek {_definite(self._interesting_item(), 1)}"
        elif quest_type == 2:
            quest.label = f"Deliver this {get_random_boring_item(self._rng)}"
        elif quest_type == 3:
            quest.label = f"Fetch me {_indefinite(get_random_boring_item(self._rng), 1)}"
        else:
            # Placate
            level = c.Level
            lev = 0
            m = Monster("", 0)
            for i in range(1, 3):
                m = get_random_monster(self._rng)
                if i == 1 or abs(m.level - level) < abs(lev - level):
                    lev = m.level
            quest.label = f"Placate {_definite(m.name, 2)}"

        c.Quests.append(quest)
        self._auto_save()

    # ========== 剧情 ==========

    def _interplot_cinematic(self):
        c = self.character
        r = self._rng.integers(0, 3)

        if r == 0:
            c.Queue.append(QueueItem(QueueItemType.Task, "Exhausted, you arrive at a friendly oasis in a hostile land", 1))
            c.Queue.append(QueueItem(QueueItemType.Task, "You greet old friends and meet new allies", 2))
            c.Queue.append(QueueItem(QueueItemType.Task, "You are privy to a council of powerful do-gooders", 2))
            c.Queue.append(QueueItem(QueueItemType.Task, "There is much to be done. You are chosen!", 1))
        elif r == 1:
            c.Queue.append(QueueItem(QueueItemType.Task, "Your quarry is in sight, but a mighty enemy bars your path!", 1))
            # 生成宿敌名
            level = c.Level + 3
            lev = 0
            nemesis = ""
            for _ in range(5):
                m = get_random_monster(self._rng)
                if not nemesis or abs(level - m.level) < abs(level - lev):
                    nemesis = m.name
                    lev = m.level
            nemesis = f"{generate_random_name(self._rng)} the {nemesis}"
            c.Queue.append(QueueItem(QueueItemType.Task, f"A desperate struggle commences with {nemesis}", 4))
            r2 = self._rng.integers(0, 3)
            if r2 == 0:
                c.Queue.append(QueueItem(QueueItemType.Task, f"Locked in grim combat with {nemesis}", 2))
            elif r2 == 1:
                c.Queue.append(QueueItem(QueueItemType.Task, f"{nemesis} seems to have the upper hand!", 2))
            else:
                c.Queue.append(QueueItem(QueueItemType.Task, f"You seem to gain the advantage over {nemesis}", 2))
            c.Queue.append(QueueItem(QueueItemType.Task, f"Victory! {nemesis} is slain! Exhausted, you lose consciousness", 3))
            c.Queue.append(QueueItem(QueueItemType.Task, "You awake in a friendly place, but the road awaits", 2))
        else:
            nemesis = get_random_impressive_title(self._rng)
            if self._rng.integers(0, 2):
                nemesis += f" of the {get_random_race(self._rng).name}"
            else:
                nemesis += f" of {generate_random_name(self._rng)}"
            c.Queue.append(QueueItem(QueueItemType.Task, f"Oh sweet relief! You've reached the protection of the good {nemesis}", 2))
            c.Queue.append(QueueItem(QueueItemType.Task, f"There is rejoicing, and an unnerving encounter with {nemesis} in private", 3))
            c.Queue.append(QueueItem(QueueItemType.Task, f"You forget your {get_random_boring_item(self._rng)} and go back to get it", 2))
            c.Queue.append(QueueItem(QueueItemType.Task, "What''s this!? You overhear something shocking!", 2))
            c.Queue.append(QueueItem(QueueItemType.Task, f"Could {nemesis} be a dirty double-dealer?", 2))
            c.Queue.append(QueueItem(QueueItemType.Task, "Who can possibly be trusted with this news!? ... Oh yes, of course", 3))

        c.Queue.append(QueueItem(QueueItemType.Plot, "Loading", 1))

    def _complete_act(self):
        c = self.character
        c.CurrentPlotProgress = 0
        count = len(c.Plot) - 1
        roman = get_roman_numerals(count + 1)
        act_name = f"Act {roman}"
        c.Plot.append(act_name)
        if count > 1:
            self._win_item()
            self._win_equip()
            self._auto_save()

    # ========== 辅助方法 ==========

    def _add_to_inventory(self, item: Stack):
        c = self.character
        for existing in c.Inventory:
            if existing.name == item.name:
                existing.count += item.count
                return
        c.Inventory.append(item)
