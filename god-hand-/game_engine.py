import json
import random
import os
from typing import Any, Dict, List, Optional, Tuple


class GameEngine:
    # 试炼池名中英文映射
    POOL_CN = {
        'physical': '肉体',
        'mental': '心智',
        'divine': '神性',
        'hidden': '隐藏',
        'lore': '传承',
        'unknown': '未知',
    }

    def __init__(self, character_id: str, unlock_mgr, labour_combo: str = "random",
                 data_root: str = 'data'):
        # 数据根目录（兼容 PyInstaller 打包路径）
        self.data_root = data_root
        # 解锁管理器
        self.unlock_mgr = unlock_mgr

        # 角色数据
        char_data = self._load_json('data/characters.json')[character_id]
        self.stats = dict(char_data['base_stats'])
        self.character_name = char_data['name']
        self.character_id = character_id
        # 初始最大生命 = 初始生命值
        self.stats['_max_life'] = self.stats.get('生命', 10)

        # 遗物系统
        self.relics: List[Dict] = []
        self.relics_data = self._load_json('data/relics.json')
        self.add_relic(char_data['start_relic'])

        # 世界状态
        self.world_state = {
            "flags": {},
            "counters": {"labors_completed": 0, "times_refused_help": 0},
            "path_history": [],
            "active_mechanic": None
        }

        # 试炼池与选择
        self.labour_pool = self._load_json('data/labours.json')
        available_pools = ['physical', 'mental', 'divine']
        if self.unlock_mgr.is_unlocked('hidden_labours'):
            available_pools.append('hidden')

        # 角色专属试炼模式：beowulf/kratos 使用专属池
        char_exclusive_pool = character_id if character_id in self.labour_pool else None

        if labour_combo == "lore" and char_exclusive_pool:
            # 传承模式：使用角色专属剧情试炼
            self.selected_labours = list(self.labour_pool[char_exclusive_pool])
        elif labour_combo == "random":
            # 真正随机：从所有基础池中随机抽取3个不重复试炼
            all_labours = []
            for pool in available_pools:
                all_labours.extend(self.labour_pool[pool])
            self.selected_labours = random.sample(all_labours, min(3, len(all_labours)))
        elif labour_combo == "balanced":
            self.selected_labours = self._pick_three_random(available_pools)
        elif labour_combo == "all_physical":
            self.selected_labours = [random.choice(self.labour_pool['physical']) for _ in range(3)]
        elif labour_combo == "all_mental":
            self.selected_labours = [random.choice(self.labour_pool['mental']) for _ in range(3)]
        elif labour_combo == "all_divine":
            self.selected_labours = [random.choice(self.labour_pool['divine']) for _ in range(3)]
        elif labour_combo == "chaos":
            # 混沌：从所有池（包括hidden）随机抽取
            chaos_pools = list(available_pools)
            if 'hidden' not in chaos_pools:
                chaos_pools.append('hidden')
            all_ids = []
            for pool in chaos_pools:
                if pool in self.labour_pool:
                    all_ids.extend(self.labour_pool[pool])
            self.selected_labours = random.sample(all_ids, min(3, len(all_ids)))
        else:
            self.selected_labours = self._pick_three_random(available_pools)

        # 试炼进度
        self.path_sequence: List[str] = []    # 记录已通过的试炼主题
        self.current_labour_index = 0          # 当前试炼索引 (0~2)
        self.total_labours = 3
        self.state = "PLAYING"

        # 章节事件队列
        self.chapter_event_queue: List[Dict] = []
        self.current_event_index = 0
        self.turn = 0

        # 上一次检定结果（供UI展示）
        self.last_roll_result: Optional[str] = None
        self.last_roll_value: int = 0

        # 加载其他数据
        self.random_events = self._load_json('data/random_events.json')
        self.endings = self._load_json('data/endings.json')

        # 加载第一个试炼
        self._load_chapter(self.selected_labours[0])

    # ---------- 辅助方法 ----------
    def _resolve_path(self, rel: str) -> str:
        """将相对路径解析为绝对路径（兼容 PyInstaller _MEIPASS）"""
        if os.path.isabs(rel):
            return rel
        # data_root 是绝对路径（由 main.py 的 _data_path 传入）
        # rel 形如 "data/characters.json"，需去掉 "data/" 前缀再拼接
        if rel.startswith('data/') or rel.startswith('data\\'):
            rel_stripped = rel[5:]  # 去掉 "data/"
            return os.path.join(self.data_root, rel_stripped)
        return os.path.join(self.data_root, rel)

    def _load_json(self, path: str) -> Any:
        resolved = self._resolve_path(path)
        with open(resolved, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _pick_three_random(self, pools: List[str]) -> List[str]:
        chosen = []
        if 'physical' in pools:
            chosen.append(random.choice(self.labour_pool['physical']))
        if 'mental' in pools:
            chosen.append(random.choice(self.labour_pool['mental']))
        if 'divine' in pools:
            chosen.append(random.choice(self.labour_pool['divine']))
        # 如果有多余池（如hidden），随机替换一个
        extra_pools = [p for p in pools if p not in ['physical', 'mental', 'divine']]
        if extra_pools:
            extra_id = random.choice(self.labour_pool[random.choice(extra_pools)])
            chosen[random.randint(0, 2)] = extra_id
        random.shuffle(chosen)
        return chosen

    # ---------- 章节加载 ----------
    def _load_chapter(self, chapter_id: str):
        resolved = os.path.join(self.data_root, 'chapters', f'{chapter_id}.json')
        if os.path.exists(resolved):
            with open(resolved, 'r', encoding='utf-8') as f:
                self.chapter_event_queue = json.load(f)
            self.current_event_index = 0
            self.world_state['active_mechanic'] = None
            # 根据章节ID设置特殊机制
            self._setup_chapter_mechanic(chapter_id)
        else:
            self.chapter_event_queue = []

    def _setup_chapter_mechanic(self, chapter_id: str):
        """设置章节特殊机制"""
        chapter_mechanics = {
            'chapter_02': 'hydra_regen',   # 九头蛇：砍头再生
            'chapter_05': 'filth',          # 牛棚：污秽侵蚀
            'chapter_11': 'time_curse',     # 金苹果：时间诅咒
        }
        mechanic = chapter_mechanics.get(chapter_id)
        if mechanic:
            self.world_state['active_mechanic'] = mechanic

    # ---------- 章节特殊机制 ----------
    def apply_chapter_mechanic(self, mechanic_type: str):
        """应用章节特殊机制的回合效果"""
        if mechanic_type == 'filth':
            # 污秽：每回合神恩-1
            self.stats['神恩'] = self.stats.get('神恩', 0) - 1
        elif mechanic_type == 'time_curse':
            # 时间诅咒：每次行动疯狂+1（已在 process_option 中处理）
            pass

    def apply_hydra_regen_damage(self, base_damage: int) -> Tuple[int, str]:
        """九头蛇再生：失败时将生命伤害转为最大生命伤害"""
        current_max = self.stats.get('_max_life', 20)
        new_max = max(1, current_max - base_damage)
        self.stats['_max_life'] = new_max
        # 如果当前生命超过新上限，调整生命
        if self.stats.get('生命', 0) > new_max:
            self.stats['生命'] = new_max
        return (0, f"九头蛇再生！最大生命上限降低 {base_damage} → 上限现为 {new_max}")

    # ---------- 遗物系统 ----------
    def add_relic(self, relic_id: str):
        if relic_id in [r['id'] for r in self.relics]:
            return
        data = self.relics_data.get(relic_id)
        if not data:
            return
        self.relics.append({'id': relic_id, **data})
        for stat, value in data.get('on_acquire', {}).items():
            if stat.startswith('_'):
                continue  # 跳过内部属性
            if isinstance(value, str) and value.startswith('set_'):
                self.stats[stat] = int(value.split('_')[1])
            else:
                self.stats[stat] = self.stats.get(stat, 0) + value

    def trigger_hooks(self, hook_type: str, context: Dict) -> Dict:
        # 如果被遗弃（神恩≤0），遗物失效
        abandoned = self.stats.get('神恩', 0) <= 0
        for relic in self.relics:
            # ON_DEATH 和 ON_TAKE_DAMAGE 即使被遗弃也保留基础保护
            if abandoned and hook_type not in ('ON_DEATH',):
                continue
            hooks = relic.get('hooks', {})
            if hook_type in hooks:
                hook = hooks[hook_type]
                if hook_type == 'ON_STAT_CHECK':
                    if context.get('stat') == hook.get('stat'):
                        context['bonus'] = context.get('bonus', 0) + hook.get('bonus', 0)
                elif hook_type == 'ON_TAKE_DAMAGE':
                    if 'reduce_percent' in hook:
                        context['damage'] = int(context.get('damage', 0) * (1 - hook['reduce_percent']))
                elif hook_type == 'ON_DEATH':
                    context['prevented'] = True
                    context['revive_stat'] = hook.get('stat')
                    context['revive_value'] = hook.get('value', 0)
        return context

    # ---------- 属性与检定 ----------
    def get_effective_stat(self, stat_name: str) -> float:
        base = self.stats.get(stat_name, 0)
        if base <= 10:
            return base
        return 10 + (base - 10) * 0.5

    def roll_check(self, stat_name: str, difficulty: int) -> str:
        effective = self.get_effective_stat(stat_name)
        roll = random.randint(1, 20)
        context = {'stat': stat_name, 'bonus': 0}
        context = self.trigger_hooks('ON_STAT_CHECK', context)
        total = roll + int(effective) + context['bonus']
        self.last_roll_value = roll
        if roll == 20:
            self.last_roll_result = "CRIT_SUCCESS"
            return "CRIT_SUCCESS"
        if roll == 1:
            self.last_roll_result = "CRIT_FAILURE"
            return "CRIT_FAILURE"
        if total >= difficulty:
            self.last_roll_result = "SUCCESS"
            return "SUCCESS"
        self.last_roll_result = "FAILURE"
        return "FAILURE"

    # ---------- 事件流 ----------
    def get_current_event(self) -> Optional[Dict]:
        if self.state != "PLAYING":
            return None

        # 当前章节还有事件
        if self.current_event_index < len(self.chapter_event_queue):
            return self.chapter_event_queue[self.current_event_index]

        # 章节完成，记录主题
        current_chapter_id = self.selected_labours[self.current_labour_index]
        theme = 'unknown'
        for t, ids in self.labour_pool.items():
            if current_chapter_id in ids:
                theme = t
                break
        self.path_sequence.append(theme)
        self.world_state['counters']['labors_completed'] += 1

        # 推进到下一试炼
        self.current_labour_index += 1
        if self.current_labour_index >= self.total_labours:
            self.state = "GAME_OVER"
            return None

        # 加载下一试炼
        next_chapter = self.selected_labours[self.current_labour_index]
        self._load_chapter(next_chapter)

        # 70% 概率在章节前插入随机乱入事件
        if random.random() < 0.7 and self.random_events:
            # 筛选满足条件的事件
            valid_events = [e for e in self.random_events if self._check_event_conditions(e)]
            if valid_events:
                interlude = random.choice(valid_events)
                self.chapter_event_queue.insert(0, interlude)

        return self.chapter_event_queue[0] if self.chapter_event_queue else None

    # ---------- 选项处理 ----------
    def process_option(self, event: Dict, option_index: int) -> Tuple[bool, str, Dict]:
        option = event['options'][option_index]
        required = option.get('required_stat', {})

        # 属性需求检查（硬门槛，直接失败无检定）
        for stat, val in required.items():
            if self.stats.get(stat, 0) < val:
                fail_text = option.get('fail_text', '你未能做到。')
                fail_effects = self._apply_fail_multiplier(
                    option.get('fail_effects', {}).copy()
                )
                # 九头蛇再生机制：失败伤害转为最大生命损失
                if self.world_state.get('active_mechanic') == 'hydra_regen':
                    life_dmg = abs(fail_effects.get('生命', 0))
                    if life_dmg > 0:
                        _, regen_msg = self.apply_hydra_regen_damage(life_dmg)
                        fail_effects['生命'] = 0
                        fail_text += f"\n{regen_msg}"
                self._apply_effects(fail_effects)
                self.turn += 1
                self.apply_turn_end_effects()
                return (False, fail_text, fail_effects)

        # 检定
        difficulty = option.get('difficulty', None)
        if difficulty:
            stat_to_check = option.get('check_stat', '力量')
            result = self.roll_check(stat_to_check, difficulty)

            if result == "CRIT_FAILURE":
                # 大失败：固定惩罚（受倍率影响）
                fail_effects = self._apply_fail_multiplier({'生命': -3, '疯狂': 2})
                self._apply_effects(fail_effects)
                self.turn += 1
                self.apply_turn_end_effects()
                crit_text = f"命运对你露出了狰狞的獠牙。【大失败！骰点：1】"
                return (False, crit_text, fail_effects)

            if result == "FAILURE":
                fail_effects = self._apply_fail_multiplier(
                    option.get('fail_effects', {}).copy()
                )
                # 九头蛇再生机制
                if self.world_state.get('active_mechanic') == 'hydra_regen':
                    life_dmg = abs(fail_effects.get('生命', 0))
                    if life_dmg > 0:
                        _, regen_msg = self.apply_hydra_regen_damage(life_dmg)
                        fail_effects['生命'] = 0
                        fail_text = option.get('fail_text', '尝试失败。') + f"\n{regen_msg}"
                    else:
                        fail_text = option.get('fail_text', '尝试失败。')
                else:
                    fail_text = option.get('fail_text', '尝试失败。')
                self._apply_effects(fail_effects)
                self.turn += 1
                self.apply_turn_end_effects()
                return (False, fail_text, fail_effects)

            # 大成功：额外奖励
            if result == "CRIT_SUCCESS":
                effects = option.get('effects', {}).copy()
                # 大成功额外：荣耀+1，负面效果减半
                effects['荣耀'] = effects.get('荣耀', 0) + 1
                for stat in ['生命', '疯狂', '神恩']:
                    if effects.get(stat, 0) < 0:
                        effects[stat] = max(-1, effects[stat] // 2)
                self._apply_effects(effects)
                # 世界状态标记
                for flag, val in option.get('set_world_state', {}).items():
                    self.world_state['flags'][flag] = val
                branch = option.get('branch', '')
                self.world_state['path_history'].append({
                    'chapter_id': self.selected_labours[self.current_labour_index],
                    'branch': branch,
                    'event_id': event['event_id']
                })
                if 'grant_relic' in option:
                    self.add_relic(option['grant_relic'])
                # 时间诅咒：大成功也触发
                if self.world_state.get('active_mechanic') == 'time_curse':
                    self.stats['疯狂'] = self.stats.get('疯狂', 0) + 1
                self.current_event_index += 1
                self.turn += 1
                self.apply_turn_end_effects()
                crit_text = f"【大成功！骰点：20】{option['text']}"
                return (True, crit_text, effects)

        # 普通成功效果
        effects = option.get('effects', {}).copy()
        self._apply_effects(effects)

        # 世界状态标记（只写 flags）
        for flag, val in option.get('set_world_state', {}).items():
            self.world_state['flags'][flag] = val

        # 路径记录
        branch = option.get('branch', '')
        self.world_state['path_history'].append({
            'chapter_id': self.selected_labours[self.current_labour_index],
            'branch': branch,
            'event_id': event['event_id']
        })

        # 授予遗物
        if 'grant_relic' in option:
            self.add_relic(option['grant_relic'])

        # 章节特殊机制（时间诅咒）
        if self.world_state.get('active_mechanic') == 'time_curse':
            self.stats['疯狂'] = self.stats.get('疯狂', 0) + 1

        self.current_event_index += 1
        self.turn += 1
        self.apply_turn_end_effects()
        return (True, option['text'], effects)

    def _apply_fail_multiplier(self, effects: Dict) -> Dict:
        """根据当前试炼难度调整失败惩罚"""
        mult = [1.0, 1.5, 2.5][self.current_labour_index] if self.current_labour_index < 3 else 2.5
        result = {}
        for stat, val in effects.items():
            if stat in ['生命', '疯狂', '荣耀', '神恩'] and isinstance(val, (int, float)):
                result[stat] = int(val * mult) if val < 0 else val
            else:
                result[stat] = val
        return result

    def _check_event_conditions(self, event: Dict) -> bool:
        """检查随机事件的触发条件"""
        conditions = event.get('conditions')
        if not conditions:
            return True
        return self._eval_condition(conditions)

    # ---------- 最大生命追踪 ----------
    def _apply_effects(self, effects: Dict):
        for stat, value in effects.items():
            if stat == 'max_life':
                # 扣最大生命上限（九头蛇）
                current_max = self.stats.get('_max_life', 20)
                self.stats['_max_life'] = max(1, current_max + value)
                if self.stats.get('生命', 0) > self.stats['_max_life']:
                    self.stats['生命'] = self.stats['_max_life']
            elif stat.startswith('_'):
                self.stats[stat] = self.stats.get(stat, 0) + value
            else:
                self.stats[stat] = self.stats.get(stat, 0) + value

    def apply_turn_end_effects(self):
        # 污秽等全局机制
        mechanic = self.world_state.get('active_mechanic')
        if mechanic and mechanic != 'time_curse':
            self.apply_chapter_mechanic(mechanic)

        # 遗物钩子：每回合结束效果（如被遗弃则跳过）
        abandoned = self.stats.get('神恩', 0) <= 0
        for relic in self.relics:
            if abandoned:
                continue
            hooks = relic.get('hooks', {})
            if 'ON_TURN_END' in hooks:
                hook = hooks['ON_TURN_END']
                if 'stat' in hook and 'change' in hook:
                    self.stats[hook['stat']] = self.stats.get(hook['stat'], 0) + hook['change']

    # ---------- 属性临界阈值效果 ----------
    def get_stat_threshold_effects(self) -> Dict[str, bool]:
        """获取当前属性达到临界阈值的效果"""
        effects = {}
        if self.stats.get('力量', 0) >= 15:
            effects['战神'] = True
        if self.stats.get('智慧', 0) >= 15:
            effects['先知'] = True
        if self.stats.get('疯狂', 0) >= 10:
            effects['幻觉'] = True
        if self.stats.get('疯狂', 0) >= 20:
            effects['湮灭'] = True
        if self.stats.get('神恩', 0) >= 15:
            effects['半神容器'] = True
        if self.stats.get('神恩', 0) <= 0:
            effects['被遗弃'] = True
        return effects

    def has_threshold_bonus(self, threshold_name: str) -> bool:
        return threshold_name in self.get_stat_threshold_effects()

    def get_path_sequence_cn(self) -> str:
        """返回翻译后的中文路径序列"""
        if not self.path_sequence:
            return '未知'
        return ' → '.join(self.POOL_CN.get(t, t) for t in self.path_sequence)

    # ---------- 终局评分报告 ----------
    def generate_post_game_report(self) -> str:
        report_lines = []
        report_lines.append("=" * 50)
        report_lines.append("【试 炼 报 告】")
        report_lines.append("=" * 50)
        report_lines.append(f"英雄：{self.character_name}")
        report_lines.append(f"试炼次数：{self.turn}")
        report_lines.append(f"路径序列：{self.get_path_sequence_cn()}")
        report_lines.append("")
        report_lines.append("属性概览：")
        report_lines.append("-" * 50)
        for stat in ['荣耀', '力量', '智慧', '神恩', '疯狂', '生命']:
            value = self.stats.get(stat, 0)
            bar_len = 20
            filled = max(0, min(value, 20))
            bar = '█' * filled + '░' * (bar_len - filled)
            report_lines.append(f"  {stat:<4}：{bar} {value:+}")
        thresholds = self.get_stat_threshold_effects()
        if thresholds:
            report_lines.append("")
            report_lines.append("临界状态：")
            for name in thresholds:
                report_lines.append(f"  ◆ {name}")
        if self.relics:
            report_lines.append("")
            report_lines.append("获得遗物：")
            for relic in self.relics:
                report_lines.append(f"  ◆ {relic.get('name', '未知遗物')}")
        if self.world_state.get('path_history'):
            report_lines.append("")
            report_lines.append("关键抉择：")
            for entry in self.world_state['path_history'][-5:]:
                branch = entry.get('branch', '?')
                report_lines.append(f"  ◆ {entry.get('chapter_id', '?')} → {branch}")
        report_lines.append("=" * 50)
        return '\n'.join(report_lines)

    # ---------- 隐藏第十三试炼检测 ----------
    def check_hidden_labor_trigger(self) -> bool:
        flags = self.world_state.get('flags', {})
        return not flags.get('dragon_slain', False) and not flags.get('cerberus_forced', False)

    # ---------- 结局判定 ----------
    def check_endings(self) -> List[Dict]:
        triggered = []
        for ending in self.endings:
            if self._eval_condition(ending['condition']):
                triggered.append(ending)
        return triggered

    def _eval_condition(self, cond: Dict) -> bool:
        logic = cond.get('logic', 'AND')
        results = []
        for rule in cond.get('rules', []):
            if rule['type'] == 'stat':
                val = self.stats.get(rule['name'], 0)
                results.append(self._compare(val, rule['op'], rule['value']))
            elif rule['type'] == 'flag':
                flag_val = self.world_state['flags'].get(rule['name'])
                results.append(flag_val == rule['value'])
            elif rule['type'] == 'counter':
                count = self.world_state['counters'].get(rule['name'], 0)
                results.append(self._compare(count, rule['op'], rule['value']))
            elif rule['type'] == 'path_sequence':
                results.append(self.path_sequence == rule['value'])
            elif rule['type'] == 'path_contains':
                results.append(rule['value'] in self.path_sequence)
        if logic == 'AND':
            return all(results)
        elif logic == 'OR':
            return any(results)
        return False

    def _compare(self, a, op, b) -> bool:
        if op == '>=': return a >= b
        if op == '<=': return a <= b
        if op == '==': return a == b
        if op == '>': return a > b
        if op == '<': return a < b
        return False

    # ---------- 生死状态 ----------
    def is_alive(self) -> bool:
        life = self.stats.get('生命', 0)
        madness = self.stats.get('疯狂', 0)
        if life <= 0:
            context = self.trigger_hooks('ON_DEATH', {'prevented': False})
            if context.get('prevented'):
                self.stats['生命'] = 1
                rev_stat = context.get('revive_stat')
                rev_val = context.get('revive_value', 0)
                if rev_stat and rev_val:
                    self.stats[rev_stat] = self.stats.get(rev_stat, 0) + rev_val
                return True
            return False
        if madness >= 20:
            return False
        return True

    def get_death_reason(self) -> str:
        if self.stats.get('生命', 0) <= 0:
            return "你的生命之火已经熄灭。"
        if self.stats.get('疯狂', 0) >= 20:
            return "疯狂彻底吞噬了你的心智。"
        return ""

    # ---------- 角色专属被动（每回合检查）----------
    def apply_character_passive(self) -> Optional[str]:
        """角色专属被动效果，返回提示文本（可为None）"""
        cid = self.character_id
        msg = None
        if cid == 'beowulf':
            # 贝奥武夫：荣耀超过10时，每回合荣耀+1（荣耀上升为力量）
            if self.stats.get('荣耀', 0) >= 10:
                self.stats['荣耀'] = self.stats.get('荣耀', 0) + 1
                msg = "【贝奥武夫之志】荣耀驱动你前进，荣耀 +1"
        elif cid == 'kratos':
            # 奎托斯：每次疯狂增加时，力量也同步增加（疯狂即力量）
            # 此被动通过 threshold 触发，每当疯狂≥5时力量+1（上限一次）
            madness = self.stats.get('疯狂', 0)
            if madness >= 5 and not self.world_state['flags'].get('_kratos_rage_5', False):
                self.stats['力量'] = self.stats.get('力量', 0) + 1
                self.world_state['flags']['_kratos_rage_5'] = True
                msg = "【斯巴达之怒】怒意涌现，力量 +1"
            if madness >= 10 and not self.world_state['flags'].get('_kratos_rage_10', False):
                self.stats['力量'] = self.stats.get('力量', 0) + 2
                self.world_state['flags']['_kratos_rage_10'] = True
                msg = "【斯巴达之怒·极限】怒火彻底爆发，力量 +2"
        return msg
