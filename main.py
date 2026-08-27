#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人生重开模拟器 + SBTI风格出身选择 + 王权决策树
采用模块化设计：本体 + JSON内容库 + 决策树模块
"""

import random
import sys
import json
import os
from typing import Dict, Any, List, Tuple

from core import constants

# 获取脚本所在目录，用于定位同目录的JSON文件
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- 工具函数 ----------
def safe_input(prompt: str, valid_options: List[str]) -> str:
    """安全获取玩家输入，必须为 valid_options 中的一个（不区分大小写）"""
    while True:
        try:
            choice = input(prompt).strip().upper()
            if choice in valid_options:
                return choice
            print(f"请输入有效选项：{'/'.join(valid_options)}")
        except (EOFError, KeyboardInterrupt):
            print("\n游戏结束。")
            sys.exit(0)

def load_json(filename: str) -> Dict:
    """加载JSON文件（自动定位到脚本所在目录）"""
    filepath = os.path.join(SCRIPT_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到文件 {filepath}")
        print(f"请确保 {filename} 和 main.py 在同一目录下")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"错误：{filename} 格式不正确")
        sys.exit(1)

def save_json(filepath: str, data: Dict):
    """保存JSON文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- 玩家数据类 ----------
class Player:
    def __init__(self):
        self.name = ""
        self.gender = ""
        self.title = "平民"

        # 基础属性
        self.strength = 5
        self.intelligence = 5
        self.agility = 5
        self.charisma = 5
        self.luck = 5
        self.wealth = 3
        self.happiness = 5
        self.health = 80

        # MBTI维度 (正/负决定倾向)
        self.EI = 0   # >0 外向E, <=0 内向I
        self.SN = 0   # >0 实感S, <=0 直觉N
        self.TF = 0   # >0 思考T, <=0 情感F
        self.JP = 0   # >0 判断J, <=0 知觉P

        # 特质列表
        self.traits = []

        # 年龄
        self.age = 0

        # 加载SBTI类型映射
        self.sbti_types = self._load_sbti_types()

        # 王权决策树
        self.decision_tree = None

        # ── B1 新增字段（§3.11，全部在 __init__ 赋默认值，R1）──
        # 存档元信息
        self.schema_version = 2          # int  R3：无此字段的旧存档视为 v1
        self.game_mode = ""              # str  BUG-2 修复：收敛进 to_dict

        # 出身扩展（对应 3.7 的 sets）
        self.birth_era = ""              # str
        self.region = ""                 # str
        self.siblings = ""               # str
        self.aptitude = ""              # str
        self.life_goal = ""              # str

        # 天赋（P0-2/P0-3）
        self.talents = []                # list[str]  本局持有的天赋 id
        self.talent_offered = []         # list[str]  本局 10 连抽的候选

        # 篇章（Q1）
        self.era = "dynasty"             # str  dynasty | modern，决定卡池

        # 职业（P1-3）
        self.education = "none"          # str  EDUCATION_CHAIN
        self.career_id = None            # str|None
        self.career_tier = 0             # int
        self.career_years = 0            # int

        # 关系（P1-5）
        self.relationships = {"parent": 60, "partner": 0, "friend": 40}  # dict[str,int] 0..100

        # 防重复（单局已见，随存档走）
        self.seen_content = {"cards": [], "events": []}   # dict[str, list[str]]

        # 结算与成就素材
        self.run_flags = []              # list[str]
        self.run_log = []                # list[dict]
        self.achievements_run = []       # list[str]
        self.score = 0                   # int

    def _load_sbti_types(self) -> Dict:
        """加载SBTI类型描述"""
        return {
            'INTJ': {'name': '卷王之王（INTJ）', 'desc': '你是那种"嘴上说着躺平，私下卷死所有人"的类型。表面佛系，实则早已规划到十年后。'},
            'INTP': {'name': '躺平学家（INTP）', 'desc': '人间清醒，看透一切，但懒。典型的"道理我都懂，但我就是不想动"。'},
            'ENTJ': {'name': '霸道总裁（ENTJ）', 'desc': '天生的领导，坚信"不听我的就滚蛋"。效率至上，但人际关系经常爆炸。'},
            'ENTP': {'name': '互联网杠精（ENTP）', 'desc': '行走的ETC，自动抬杠。看到观点就想辩驳，哪怕对方是你妈。'},
            'INFJ': {'name': '流泪圣母（INFJ）', 'desc': '表面温柔，内心戏精。一边治愈别人，一边自己深夜emo。'},
            'INFP': {'name': '流泪猫猫头（INFP）', 'desc': '高敏感人群，泪点极低。看到流浪猫能哭半小时，看到感人视频能哭一小时。'},
            'ENFJ': {'name': '人生导师（ENFJ）', 'desc': '人均心理医生，朋友的情绪垃圾桶。热心到让人怀疑是不是有社交NB症。'},
            'ENFP': {'name': '快乐修勾（ENFP）', 'desc': '快乐小狗，人形向日葵。有你的地方就有笑声，但专注力约等于金鱼。'},
            'ISTJ': {'name': '人形Excel（ISTJ）', 'desc': '人形规章，行走的SOP。讨厌变化，热爱清单，是老板最爱的打工人。'},
            'ISFJ': {'name': '老好人（ISFJ）', 'desc': '老好人，不会拒绝。帮同事带咖啡，帮朋友搬家，帮陌生人指路。'},
            'ESTJ': {'name': '职场卷王（ESTJ）', 'desc': '卷王本王，坚信"不加班的人生不完整"。口头禅是"你这个需求不合理"。'},
            'ESFJ': {'name': '社交悍匪（ESFJ）', 'desc': '社交悍匪，没有你暖不起来的场。但有时热情过度，让人想逃。'},
            'ISTP': {'name': '手艺人（ISTP）', 'desc': '手艺人，信奉"能动手就不哔哔"。工具控，动手能力强，但社交能力弱。'},
            'ISFP': {'name': '佛系艺术家（ISFP）', 'desc': '佛系艺术家，活在当下。口头禅是"都行，可以，没关系"，但审美极高。'},
            'ESTP': {'name': '社会人（ESTP）', 'desc': '社会人，人脉王。擅长见人说人话，见鬼说鬼话，但缺乏深度。'},
            'ESFP': {'name': '派对动物（ESFP）', 'desc': '派对动物，气氛组担当。有你在就不会冷场，但经常被说"不够稳重"。'}
        }

    @property
    def mbti_code(self) -> str:
        """获取MBTI四字母代码"""
        e_or_i = 'E' if self.EI > 0 else 'I'
        s_or_n = 'S' if self.SN > 0 else 'N'
        t_or_f = 'T' if self.TF > 0 else 'F'
        j_or_p = 'J' if self.JP > 0 else 'P'
        return e_or_i + s_or_n + t_or_f + j_or_p

    @property
    def sbti(self) -> str:
        """获取SBTI类型名称"""
        mbti_code = self.mbti_code
        return self.sbti_types.get(mbti_code, {}).get('name', mbti_code)

    def get_sbti_description(self) -> str:
        """获取SBTI类型描述"""
        mbti_code = self.mbti_code
        return self.sbti_types.get(mbti_code, {}).get('desc', '你的性格很特别，难以用简单的标签定义。')

    def adjust(self, **kwargs):
        """批量调整属性"""
        for attr, delta in kwargs.items():
            if attr == 'traits':
                if isinstance(delta, list):
                    self.traits.extend(delta)
                elif isinstance(delta, str):
                    self.traits.append(delta)
            elif hasattr(self, attr):
                current = getattr(self, attr)
                if isinstance(current, (int, float)):
                    setattr(self, attr, current + delta)
                else:
                    setattr(self, attr, delta)
            else:
                if attr in ['EI', 'SN', 'TF', 'JP']:
                    setattr(self, attr, getattr(self, attr) + delta)

        # 属性下限0，上限20（健康0-100）
        for attr in ['strength', 'intelligence', 'agility', 'charisma', 'luck', 'wealth', 'happiness']:
            val = getattr(self, attr)
            if val < 0:
                setattr(self, attr, 0)
            elif val > 20:
                setattr(self, attr, 20)

        if self.health < 0:
            self.health = 0
        elif self.health > 100:
            self.health = 100

    def show_stats(self):
        """显示玩家状态"""
        print("\n" + "=" * 50)
        print(f"  {self.name} ({self.title}) | {self.gender} | {self.age}岁")
        print(f"  SBTI类型：{self.sbti}")
        print("-" * 50)

        attributes = [
            ("  力量", self.strength, 20),
            ("  智力", self.intelligence, 20),
            ("  敏捷", self.agility, 20),
            ("  魅力", self.charisma, 20),
            ("  运气", self.luck, 20),
            ("  财富", self.wealth, 20),
            ("  幸福", self.happiness, 20),
            ("  健康", self.health, 100)
        ]

        for name, value, max_val in attributes:
            bar_length = 10
            filled = int(value * bar_length / max_val)
            bar = "█" * filled + "░" * (bar_length - filled)
            print(f"{name}: {bar} {value:3d}/{max_val}")

        print(f"  EI:{self.EI:+.1f}  SN:{self.SN:+.1f}  TF:{self.TF:+.1f}  JP:{self.JP:+.1f}")

        if self.traits:
            print(f"  特质：{', '.join(self.traits)}")

        print("=" * 50)

    def init_decision_tree(self):
        """初始化决策树"""
        from decision_tree import DecisionTree, Dimension
        self.decision_tree = DecisionTree(self)

        # 根据出身调整初始维度
        if "高贵血统" in self.traits:
            self.decision_tree.adjust_dimension(Dimension.NOBLES, 20)
            self.decision_tree.adjust_dimension(Dimension.CHARISMA, 10)
        if "富二代" in self.traits:
            self.decision_tree.adjust_dimension(Dimension.WEALTH, 25)
        if "草根" in self.traits:
            self.decision_tree.adjust_dimension(Dimension.COMMONERS, 20)
            self.decision_tree.adjust_dimension(Dimension.NOBLES, -10)
        if "骑士训练" in self.traits:
            self.decision_tree.adjust_dimension(Dimension.STRENGTH, 20)
        if "学术熏陶" in self.traits:
            self.decision_tree.adjust_dimension(Dimension.INTELLIGENCE, 20)
        if "街头智慧" in self.traits:
            self.decision_tree.adjust_dimension(Dimension.INTELLIGENCE, 10)
            self.decision_tree.adjust_dimension(Dimension.STABILITY, -5)
        if "冒险精神" in self.traits:
            self.decision_tree.adjust_dimension(Dimension.STRENGTH, 10)
            self.decision_tree.adjust_dimension(Dimension.STABILITY, -5)
        if "商业头脑" in self.traits:
            self.decision_tree.adjust_dimension(Dimension.WEALTH, 15)
        if "神秘知识" in self.traits:
            self.decision_tree.adjust_dimension(Dimension.INTELLIGENCE, 15)
            self.decision_tree.adjust_dimension(Dimension.CHURCH, -10)

        # 根据MBTI调整
        mbti_code = self.mbti_code
        if mbti_code[0] == 'E':
            self.decision_tree.adjust_dimension(Dimension.CHARISMA, 10)
        else:
            self.decision_tree.adjust_dimension(Dimension.INTELLIGENCE, 10)

        if mbti_code[3] == 'J':
            self.decision_tree.adjust_dimension(Dimension.STABILITY, 10)

    def to_dict(self) -> Dict:
        """序列化玩家数据"""
        return {
            'name': self.name,
            'gender': self.gender,
            'title': self.title,
            'strength': self.strength,
            'intelligence': self.intelligence,
            'agility': self.agility,
            'charisma': self.charisma,
            'luck': self.luck,
            'wealth': self.wealth,
            'happiness': self.happiness,
            'health': self.health,
            'EI': self.EI,
            'SN': self.SN,
            'TF': self.TF,
            'JP': self.JP,
            'traits': self.traits,
            'age': self.age,
            # B1 新增字段（§3.11，收进 to_dict；不输出 sbti_types / decision_tree）
            'schema_version': self.schema_version,
            'game_mode': self.game_mode,
            'birth_era': self.birth_era,
            'region': self.region,
            'siblings': self.siblings,
            'aptitude': self.aptitude,
            'life_goal': self.life_goal,
            'talents': self.talents,
            'talent_offered': self.talent_offered,
            'era': self.era,
            'education': self.education,
            'career_id': self.career_id,
            'career_tier': self.career_tier,
            'career_years': self.career_years,
            'relationships': self.relationships,
            'seen_content': self.seen_content,
            'run_flags': self.run_flags,
            'run_log': self.run_log,
            'achievements_run': self.achievements_run,
            'score': self.score
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Player':
        """从字典反序列化"""
        player = cls()
        for key, value in data.items():
            if hasattr(player, key):
                setattr(player, key, value)
        return player

# ---------- 出身选择 ----------
def background_choice(player: Player, backgrounds: Dict):
    """出身选择阶段"""
    print("\n" + "═" * 50)
    print(f"         {backgrounds.get('title', '人生重开模拟器')}")
    print(f"         {backgrounds.get('description', '')}")
    print("═" * 50)

    steps = backgrounds.get('steps', {})

    # 1. 姓名
    name_step = steps.get('name', {})
    prompt = name_step.get('prompt', '请输入你的名字：')
    player.name = input(prompt).strip()
    if not player.name:
        player.name = random.choice(name_step.get('random_names', ['无名氏']))
        print(f"懒得取名？那就叫{player.name}吧。")

    # 后续步骤
    step_keys = ['gender', 'father_job', 'childhood', 'teenage', 'adulthood']
    for step_key in step_keys:
        if step_key in steps:
            run_background_step(player, steps[step_key])

    player.age = 20
    print("\n" + "═" * 50)
    print("         【出身选择完成】")
    print("══════════════════════════════════════════════════")
    print(f"姓名：{player.name}")
    print(f"性别：{player.gender}")
    print(f"年龄：{player.age}岁（法定成年，但心理年龄待定）")
    print(f"SBTI人格：{player.sbti}")
    print(f"人格描述：{player.get_sbti_description()}")
    print("═" * 50)
    player.show_stats()

def run_background_step(player: Player, step_data: Dict):
    """运行单个出身选择步骤"""
    print(f"\n{step_data.get('title', '')}")

    for option in step_data.get('options', []):
        print(f"  {option.get('key', '')}. {option.get('text', '')}")

    valid_keys = [opt['key'] for opt in step_data.get('options', [])]
    if not valid_keys:
        return

    choice = safe_input(f"{step_data.get('description', '请选择：')} ", valid_keys)

    for option in step_data.get('options', []):
        if option.get('key') == choice:
            effects = option.get('effects', {})

            if 'gender' in effects:
                player.gender = effects['gender']

            if 'stats' in effects:
                for stat, value in effects['stats'].items():
                    if hasattr(player, stat):
                        setattr(player, stat, getattr(player, stat) + value)

            if 'mbti' in effects:
                for dim, value in effects['mbti'].items():
                    if hasattr(player, dim):
                        setattr(player, dim, getattr(player, dim) + value)

            if 'traits' in effects:
                player.traits.extend(effects['traits'])

            feedback = option.get('feedback', '')
            if feedback:
                print(feedback)

            break

# ---------- 人生道路选择 ----------
def choose_life_path(player: Player) -> str:
    """选择人生道路"""
    print("\n" + "═" * 50)
    print("         【人生道路选择】")
    print("══════════════════════════════════════════════════")
    print("你已成年，请选择未来的人生道路：")
    print("")
    print("  A.  权力之路 - 进入王权决策系统，统治国家")
    print("     管理国家，平衡各方势力，做出重大决策")
    print("")
    print("  B.  冒险之路 - 传统人生事件系统")
    print("     经历随机事件，体验多样人生")
    print("")
    print("  C.  修行之路 - 专注个人成长")
    print("     提升自我，探索内心世界")
    print("")

    choice = safe_input("请选择人生道路 (A/B/C): ", ['A', 'B', 'C'])

    if choice == 'A':
        return "reigns"
    elif choice == 'B':
        return "traditional"
    else:
        return "cultivation"

# ---------- 王权决策游戏 ----------
def play_reigns_mode(player: Player):
    """王权决策模式"""
    from decision_tree import Dimension

    print("\n" + "═" * 50)
    print("         王权决策系统")
    print("══════════════════════════════════════════════════")
    print("欢迎来到王权系统！在这里你将统治一个国家。")
    print("通过左右选择来平衡各方势力，做出明智的决策。")
    print("每个决策都会影响多个维度，小心不要让任何一方崩溃！")
    print("")
    input("按回车开始你的统治...")

    player.init_decision_tree()

    while True:
        player.decision_tree.display_status()

        game_over, message = player.decision_tree.is_game_over()
        if game_over:
            print(f"\n{message}")
            break

        available_cards = player.decision_tree.get_available_cards()
        if not available_cards:
            print("\n暂时没有决策需要处理。")
            player.decision_tree.advance_time()
            input("\n按回车继续...")
            continue

        card = available_cards[0]
        print(f"\n >> {card['title']}")
        print(f"    {card['description']}")
        print("")
        print(f"  <-- 左：{card['left_choice']['text']}")
        print(f"  --> 右：{card['right_choice']['text']}")
        print("")

        choice = safe_input("你的选择 (L=左 / R=右): ", ['L', 'R'])

        choice_key = "left_choice" if choice == 'L' else "right_choice"
        result = player.decision_tree.apply_decision(card, choice_key)

        print(f"\n >> {result['speech']}")

        if result['effects']:
            print("\n决策影响：")
            for dim, delta in result['effects'].items():
                try:
                    dim_obj = Dimension[dim]
                    direction = "+" if delta > 0 else ""
                    print(f"   {dim_obj.value}: {direction}{delta}")
                except KeyError:
                    pass

        if result['chain_reactions']:
            print("\n连锁反应：")
            for reaction in result['chain_reactions']:
                print(f"   {reaction['title']}: {reaction['description']}")

        player.age += 1

        if player.age >= 100:
            print("\n你已年迈，决定退位让贤。")
            break

        input("\n按回车继续统治...")

    reigns_ending(player)

def reigns_ending(player: Player):
    """王权模式结局"""
    from decision_tree import Dimension

    if not player.decision_tree:
        return

    print("\n" + "═" * 50)
    print("         统治总结")
    print("══════════════════════════════════════════════════")

    years_ruled = player.decision_tree.year
    print(f"统治时间：{years_ruled}年")
    print(f"重大决策：{len(player.decision_tree.history)}次")

    print("\n【最终国家状态】")
    player.decision_tree.display_status()

    print("\n【历史评价】")
    ending_text = player.decision_tree.get_ending_based_on_history()
    print(ending_text)

    dims = player.decision_tree.dimensions
    titles = []

    if dims[Dimension.STRENGTH] >= 80:
        titles.append("征服者")
    if dims[Dimension.INTELLIGENCE] >= 80:
        titles.append("智者")
    if dims[Dimension.CHARISMA] >= 80:
        titles.append("仁君")
    if dims[Dimension.WEALTH] >= 80:
        titles.append("富王")
    if dims[Dimension.STABILITY] >= 80:
        titles.append("明君")
    if dims[Dimension.COMMONERS] >= 80 and dims[Dimension.NOBLES] >= 80:
        titles.append("平衡大师")

    if titles:
        print(f"\n历史称号：{'、'.join(titles)}")
    else:
        print(f"\n历史评价：普通统治者")

    # 最终结局（数据驱动，含 7 个王权专属结局）
    print_resolved_ending(player, "reigns")

    print("\n" + "═" * 50)
    print("      王权游戏结束，感谢你的统治！")
    print("═" * 50)

# ---------- 传统人生事件 ----------
def _career_category(career_id, events_data):
    """从 events_data 顶层的 careers 列表反查职业类别（R10 容错：查不到返回 None）。

    用于把 by_career.<category> 事件接入人生事件选取。events_data 由 ContentLoader
    深合并得到，顶层含 'careers'（每条带 id / category）。任何异常一律安全降级。
    """
    try:
        for c in events_data.get("careers", []) or []:
            if isinstance(c, dict) and c.get("id") == career_id:
                return c.get("category")
    except Exception:
        pass
    return None


def life_event(player: Player, events_data: Dict, stage: int) -> bool:
    """触发人生事件"""
    print(f"\n--- 你 {player.age} 岁了 ---")

    possible_events = []

    # 通用事件
    possible_events.extend(events_data.get('event_templates', {}).get('generic', []))

    # 按财富水平
    if player.wealth >= 7:
        possible_events.extend(events_data.get('event_templates', {}).get('by_wealth', {}).get('rich', []))
    elif player.wealth <= 2:
        possible_events.extend(events_data.get('event_templates', {}).get('by_wealth', {}).get('poor', []))

    # 按性格
    if player.EI > 0:
        possible_events.extend(events_data.get('event_templates', {}).get('by_personality', {}).get('extrovert', []))
    else:
        possible_events.extend(events_data.get('event_templates', {}).get('by_personality', {}).get('introvert', []))

    # 按MBTI大类
    mbti_code = player.mbti_code
    if mbti_code in ['INTJ', 'INTP', 'ENTJ', 'ENTP']:
        possible_events.extend(events_data.get('event_templates', {}).get('by_personality', {}).get('nt_rational', []))
    if mbti_code in ['INFP', 'INFJ', 'ENFP', 'ENFJ']:
        possible_events.extend(events_data.get('event_templates', {}).get('by_personality', {}).get('nf_idealist', []))

    # 按属性
    if player.strength >= 8:
        possible_events.extend(events_data.get('event_templates', {}).get('by_personality', {}).get('strong_warrior', []))
    if player.intelligence >= 8:
        possible_events.extend(events_data.get('event_templates', {}).get('by_personality', {}).get('smart_scholar', []))
    if "冒险精神" in player.traits:
        possible_events.extend(events_data.get('event_templates', {}).get('by_personality', {}).get('adventurer', []))

    # 按年龄段
    age_group = get_age_group(player.age)
    age_events = events_data.get('event_templates', {}).get('by_age', {}).get(age_group, [])
    possible_events.extend(age_events)

    # 按职业类别（需已选定职业；通过 career_id 反查 category）
    career_id = getattr(player, 'career_id', None)
    if career_id:
        career_cat = _career_category(career_id, events_data)
        if career_cat:
            possible_events.extend(
                events_data.get('event_templates', {}).get('by_career', {}).get(career_cat, [])
            )

    # 按特质（玩家拥有的每个特质若有对应池则接入）
    by_trait = events_data.get('event_templates', {}).get('by_trait', {})
    for t in (getattr(player, 'traits', None) or []):
        if t in by_trait:
            possible_events.extend(by_trait[t])

    if not possible_events:
        possible_events.append({
            "desc": "平淡的一天，什么都没发生。",
            "options": {
                "A": {
                    "text": "继续生活",
                    "effects": {},
                    "feedback": ["又是平凡的一天。", "岁月静好。"]
                }
            }
        })

    event = random.choice(possible_events)
    print(event.get('desc', '发生了一些事...'))

    options = event.get('options', {})
    for key, option_data in options.items():
        print(f"  {key}. {option_data.get('text', '')}")

    valid_keys = list(options.keys())
    choice = safe_input("你的选择：", valid_keys)

    if choice in options:
        option_data = options[choice]
        effects = option_data.get('effects', {})
        player.adjust(**effects)

        feedbacks = option_data.get('feedback', ["这很符合你的人设。"])
        print(f"  -> {random.choice(feedbacks)}")

    player.age += 10
    if player.age >= 100:
        return False

    return True

def get_age_group(age: int) -> str:
    """获取年龄段"""
    if age < 30:
        return "20s"
    elif age < 40:
        return "30s"
    elif age < 50:
        return "40s"
    elif age < 60:
        return "50s"
    else:
        return "60+"

# ---------- 结局解析（数据驱动，共用于三种模式） ----------
RARITY_LABEL = {
    "common": "普通", "uncommon": "少见", "rare": "稀有",
    "epic": "史诗", "legendary": "传说", "mythic": "神话",
}
CATEGORY_LABEL = {
    "normal": "普通结局", "career": "事业结局", "emotion": "情感结局",
    "hidden": "隐藏结局", "death": "死亡结局", "legendary": "传说结局",
}


def print_resolved_ending(player: Player, mode: str = "traditional"):
    """解析并打印本局最终结局 + 挑战判定 + 传承结果。

    内部调用 core.runtime.finish_run：结局匹配、档案写入、挑战校验、
    传家宝传承掷骰一次性完成。任何子系统失败都静默降级，不影响结算展示。
    """
    try:
        from core import runtime
        res = runtime.finish_run(player, mode)
    except Exception:
        return

    if res.get("ending_name"):
        cat = CATEGORY_LABEL.get(res.get("ending_category", ""), "结局")
        rar = RARITY_LABEL.get(res.get("ending_rarity", ""), "")
        new_mark = "  ★NEW★" if res.get("is_new_ending") else ""
        print(f"\n【{cat}】{res['ending_name']}（{rar}）{new_mark}")
        if res.get("ending_text"):
            for line in _wrap_cn(res["ending_text"], 44):
                print("  " + line)

    # 副结局提示
    others = res.get("also_matched") or []
    if others:
        names = "、".join(getattr(o, "name", "?") for o in others)
        print(f"\n  （你同时也接近这些结局：{names}）")

    # 结局图鉴进度
    coll = res.get("collection") or {}
    if coll.get("total"):
        print(f"\n  结局图鉴：{coll.get('seen', 0)}/{coll['total']}")

    # 挑战结算
    cr = res.get("challenge_result")
    if cr:
        c = cr.get("challenge") or {}
        if cr.get("won"):
            print(f"\n  🏆 挑战达成：{c.get('name','?')}")
            reward = cr.get("reward") or {}
            if reward.get("unlock_talent"):
                print(f"     解锁天赋：{reward['unlock_talent']}")
            if reward.get("unlock_mode"):
                print(f"     解锁模式：{reward['unlock_mode']}")
        else:
            print(f"\n  ✗ 挑战未达成：{c.get('name','?')}")
            for r in (cr.get("reasons_unmet") or [])[:3]:
                print(f"     未满足：{r}")

    # 传承结果
    inh = res.get("inheritance")
    if inh:
        if inh.get("kept"):
            print(f"\n  传承：{len(inh['kept'])} 件传家宝传给了下一代。")
        if inh.get("lost_names"):
            print(f"  失落：{'、'.join(inh['lost_names'])}")


def _wrap_cn(text: str, width: int = 44) -> List[str]:
    """按字符宽度粗略折行（中文按 1 字计），保证终端不炸行。"""
    lines: List[str] = []
    for para in str(text).split("\n"):
        cur = ""
        for ch in para:
            cur += ch
            if len(cur) >= width:
                lines.append(cur)
                cur = ""
        if cur:
            lines.append(cur)
    return lines or [""]


# ---------- 传统人生结局 ----------
def traditional_ending(player: Player):
    """传统模式结局"""
    print("\n" + "=" * 50)
    print("         【人生总结报告】")
    print("══════════════════════════════════════════════════")

    print(f"姓名：{player.name}")
    print(f"性别：{player.gender}")
    print(f"终年：{player.age}岁")
    print(f"SBTI类型：{player.sbti}")
    print(f"性格描述：{player.get_sbti_description()}")

    # 属性评价
    print("\n【属性总结】")
    print(f"  财富：{'$' * min(player.wealth, 10)} {'(财务自由)' if player.wealth >= 8 else '(刚好够用)' if player.wealth >= 4 else '(有点拮据)'}")
    print(f"  幸福：{'*' * min(player.happiness, 10)} {'(非常幸福)' if player.happiness >= 8 else '(一般幸福)' if player.happiness >= 4 else '(不太幸福)'}")
    print(f"  魅力：{'@' * min(player.charisma, 10)} {'(人见人爱)' if player.charisma >= 8 else '(普普通通)' if player.charisma >= 4 else '(存在感低)'}")
    print(f"  智力：{'#' * min(player.intelligence, 10)} {'(天才)' if player.intelligence >= 8 else '(普通人)' if player.intelligence >= 4 else '(有待提高)'}")
    print(f"  力量：{'!' * min(player.strength, 10)} {'(猛人)' if player.strength >= 8 else '(正常)' if player.strength >= 4 else '(战五渣)'}")
    print(f"  运气：{'%' * min(player.luck, 10)} {'(天选之子)' if player.luck >= 8 else '(一般)' if player.luck >= 4 else '(非酋)'}")

    # 特质评价
    if player.traits:
        print(f"\n【人生特质】")
        print("  " + ", ".join(player.traits))

    # 综合结局
    print("\n【最终评价】")
    mbti_code = player.mbti_code
    final_words = {
        'INTJ': "你一生都在计划和执行，但可能忘了为什么出发。",
        'INTP': "你想明白了很多事，但该做的事一件没做。",
        'ENTJ': "你带领团队完成了KPI，但没交到什么朋友。",
        'ENTP': "你赢了所有辩论，但输了所有人际关系。",
        'INFJ': "你治愈了很多人，但深夜自己偷偷emo。",
        'INFP': "你为世界流了太多泪，但世界依然如此。",
        'ENFJ': "你成为了很多人的太阳，但自己也会累。",
        'ENFP': "你给世界带来快乐，但没给自己找到答案。",
        'ISTJ': "你遵守了所有规则，但可能错过了意外之喜。",
        'ISFJ': "你帮助了所有人，但忘了帮助自己。",
        'ESTJ': "你卷赢了所有人，但不知道为了什么。",
        'ESFJ': "你温暖了所有人，但边界感有点模糊。",
        'ISTP': "你动手解决了很多问题，但没解决自己的孤独。",
        'ISFP': "你活得很美，但可能有点不接地气。",
        'ESTP': "你玩得很开心，但深度思考可能不够。",
        'ESFP': "你是派对的中心，但一个人的时候会空虚。"
    }

    print("  " + final_words.get(mbti_code, "你度过了独特的一生。"))

    # 最终结局（数据驱动，60 结局库按 priority 匹配）
    print_resolved_ending(player, "traditional")

    # 年龄评价
    if player.age >= 90:
        print("  >> 寿命成就：活得太久，见证了太多历史")
    elif player.age >= 80:
        print("  >> 寿命成就：正常退休，开始养生")
    elif player.age >= 70:
        print("  >> 寿命成就：开始被年轻人叫爷爷/奶奶")
    elif player.age >= 60:
        print("  >> 寿命成就：刚退休，还没想好干什么")
    else:
        print("  >> 寿命评价：英年早逝，但可能避免了中年危机")

    print("\n" + "=" * 50)
    print("      游戏结束，但你的人生还在继续")
    print("      （本测试仅供娱乐，别太当真）")
    print("=" * 50)

# ---------- 修行模式 ----------
def play_cultivation_mode(player: Player, events_data: Dict):
    """修行模式 - 专注个人成长"""
    print("\n" + "═" * 50)
    print("         修行之路")
    print("══════════════════════════════════════════════════")
    print("你选择了修行的道路，远离尘世喧嚣。")
    print("在山林之间，你将寻找内心的平静与力量。")
    print("")
    input("按回车开始你的修行...")

    # 修行事件
    cultivation_events = [
        {
            "desc": "你在山中遇到一位老者，他问你是否愿意听他讲道。",
            "options": {
                "A": {"text": "虚心求教 (智力+2, 幸福+1)", "effects": {"intelligence": 2, "happiness": 1}, "feedback": ["悟性+1。", "大道至简。"]},
                "B": {"text": "婉言谢绝，自行参悟 (智力+1, JP+1)", "effects": {"intelligence": 1, "JP": 1}, "feedback": ["独自修行。", "佛在心中。"]},
                "C": {"text": "和他切磋辩论 (智力+1, 魅力+1, EI+1)", "effects": {"intelligence": 1, "charisma": 1, "EI": 1}, "feedback": ["棋逢对手。", "以辩会友。"]}
            }
        },
        {
            "desc": "你在溪边冥想，忽然顿悟了什么。",
            "options": {
                "A": {"text": "顺着感觉走 (运气+2, 幸福+2)", "effects": {"luck": 2, "happiness": 2}, "feedback": ["天人合一。", "道法自然。"]},
                "B": {"text": "记录下来反复研究 (智力+3, JP+1)", "effects": {"intelligence": 3, "JP": 1}, "feedback": ["好记性不如烂笔头。", "格物致知。"]},
                "C": {"text": "与路过的旅人分享 (魅力+2, 幸福+1)", "effects": {"charisma": 2, "happiness": 1}, "feedback": ["渡人渡己。", "法布施。"]}
            }
        },
        {
            "desc": "山中风雨大作，你的小屋被吹塌了。",
            "options": {
                "A": {"text": "重建小屋 (力量+2, 敏捷+1)", "effects": {"strength": 2, "agility": 1}, "feedback": ["自力更生。", "锻炼身体。"]},
                "B": {"text": "在雨中冥想 (幸福+2, 健康-10)", "effects": {"happiness": 2, "health": -10}, "feedback": ["苦行僧。", "身体是革命的本钱啊。"]},
                "C": {"text": "下山暂避 (财富-1, 魅力+1)", "effects": {"wealth": -1, "charisma": 1}, "feedback": ["入世修行。", "红尘炼心。"]}
            }
        },
        {
            "desc": "你遇到了一群山贼拦路。",
            "options": {
                "A": {"text": "以武力击退 (力量+2, 魅力-1)", "effects": {"strength": 2, "charisma": -1}, "feedback": ["以暴制暴。", "武功再高也怕菜刀。"]},
                "B": {"text": "以德服人 (魅力+3, 运气+1)", "effects": {"charisma": 3, "luck": 1}, "feedback": ["感化了。", "浪子回头。"]},
                "C": {"text": "绕路而行 (敏捷+2)", "effects": {"agility": 2}, "feedback": ["三十六计走为上。", "避其锋芒。"]}
            }
        }
    ]

    for stage in range(8):
        print(f"\n--- 修行第{stage+1}年 ---")

        # 50%概率遇到修行事件，50%遇到普通事件
        if random.random() < 0.5 and cultivation_events:
            event = random.choice(cultivation_events)
        else:
            # 复用普通事件
            generic_events = events_data.get('event_templates', {}).get('generic', [])
            if generic_events:
                event = random.choice(generic_events)
            else:
                event = random.choice(cultivation_events)

        print(event.get('desc', '发生了一些事...'))

        options = event.get('options', {})
        for key, option_data in options.items():
            print(f"  {key}. {option_data.get('text', '')}")

        valid_keys = list(options.keys())
        choice = safe_input("你的选择：", valid_keys)

        if choice in options:
            option_data = options[choice]
            effects = option_data.get('effects', {})
            player.adjust(**effects)
            feedbacks = option_data.get('feedback', ["道可道，非常道。"])
            print(f"  -> {random.choice(feedbacks)}")

        player.age += 10
        player.show_stats()

        if player.age >= 100:
            break

        input("\n按回车继续修行...")

    # 修行结局
    print("\n" + "=" * 50)
    print("         【修行总结】")
    print("══════════════════════════════════════════════════")
    print(f"姓名：{player.name}")
    print(f"终年：{player.age}岁")
    print(f"SBTI类型：{player.sbti}")

    if player.intelligence >= 15:
        print("\n  >> 你悟道成仙，化为山间一缕清风。")
    elif player.happiness >= 15:
        print("\n  >> 你修成正果，内心无比宁静。")
    elif player.strength >= 15:
        print("\n  >> 你武道通神，成为一代宗师。")
    else:
        print("\n  >> 你虽未成大道，但心有所得，不虚此行。")

    # 最终结局（数据驱动，含 3 个修行专属结局）
    print_resolved_ending(player, "cultivation")

    player.show_stats()
    print("=" * 50)

# ---------- 保存/加载 ----------
def save_game(player: Player, game_mode: str = "traditional"):
    """保存游戏"""
    saves_dir = os.path.join(SCRIPT_DIR, "saves")
    os.makedirs(saves_dir, exist_ok=True)

    save_name = input("请输入存档名称（留空使用默认）: ").strip()
    if not save_name:
        save_name = f"save_{player.name}_{player.age}"

    save_file = os.path.join(saves_dir, f"{save_name}.json")
    data = player.to_dict()
    data['game_mode'] = game_mode

    save_json(save_file, data)
    print(f"游戏已保存到：{save_file}")

def load_game_menu() -> tuple:
    """加载游戏菜单"""
    saves_dir = os.path.join(SCRIPT_DIR, "saves")
    if not os.path.exists(saves_dir):
        print("\n没有找到保存文件。")
        return None, None

    save_files = [f for f in os.listdir(saves_dir) if f.endswith('.json')]
    if not save_files:
        print("\n没有找到保存文件。")
        return None, None

    print("\n" + "=" * 50)
    print("         加载游戏")
    print("=" * 50)

    for i, save_file in enumerate(save_files, 1):
        print(f"  {i}. {save_file[:-5]}")

    print("  0. 返回主菜单")
    print("=" * 50)

    try:
        choice = int(input("请选择存档: "))
        if choice == 0:
            return None, None
        if 1 <= choice <= len(save_files):
            save_path = os.path.join(saves_dir, save_files[choice-1])
            with open(save_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            player = Player.from_dict(data)
            game_mode = constants.normalize_mode(data.get('game_mode', 'traditional'))
            print(f"\n已加载存档：{save_files[choice-1][:-5]}")
            return player, game_mode
    except (ValueError, IndexError, json.JSONDecodeError):
        print("无效选择。")

    return None, None

# ---------- 连胜 / 挑战 / 传承 / 图鉴（CLI 面板） ----------
DIFFICULTY_LABEL = {
    "easy": "简单", "normal": "普通", "hard": "困难",
    "very_hard": "地狱", "extreme": "噩梦",
}


def print_streak_banner():
    """启动时打印连胜横幅。失败静默跳过。"""
    try:
        from core import runtime
        res = runtime.session_start()
    except Exception:
        return
    if not res.get("ok"):
        return
    streak = res.get("streak", 0)
    best = res.get("best", 0)
    flame = "🔥" * min(streak, 7)
    print("\n" + "─" * 50)
    print(f"  {flame}  连胜 {streak} 天   （历史最佳 {best} 天）")
    if res.get("message"):
        print(f"  {res['message']}")
    ms = res.get("milestone")
    if ms:
        buff = (ms.get("reward") or {}).get("next_run_buff") or {}
        if buff:
            parts = "、".join(f"{k}+{v}" for k, v in buff.items())
            print(f"  🎁 里程碑奖励：下一局 {parts}")
    nxt = res.get("next_milestone")
    if nxt and nxt > streak:
        print(f"  再连 {nxt - streak} 天可解锁下一个里程碑。")
    print("─" * 50)


def show_challenge_menu():
    """挑战模式选择面板。"""
    try:
        from core import challenges, runtime
    except Exception:
        print("\n挑战系统不可用。")
        input("按回车返回...")
        return

    prof = runtime.get_profile()
    items = challenges.all_challenges()
    if not items:
        print("\n暂无可用挑战。")
        input("按回车返回...")
        return

    summ = challenges.challenge_summary(prof.data)
    completed = set(summ.get("completed_ids") or [])
    active_id = summ.get("active_id")

    print("\n" + "═" * 60)
    print("    🎯 挑战模式")
    print("═" * 60)
    print(f"  进度：{summ.get('completed', 0)}/{summ.get('total', 0)} 已完成")
    if active_id:
        cur = challenges.get_challenge(active_id)
        print(f"  当前激活：{cur.get('name', active_id) if cur else active_id}")
    print("─" * 60)

    for i, c in enumerate(items, 1):
        cid = c.get("id", "")
        mark = "✔" if cid in completed else ("▶" if cid == active_id else " ")
        diff = DIFFICULTY_LABEL.get(c.get("difficulty", ""), c.get("difficulty", ""))
        print(f"  {mark} {i}. {c.get('name','?')}  [{diff}]")
        print(f"       {c.get('description','')}")
        win = c.get("win_conditions") or {}
        if win:
            print(f"       胜利条件：{_fmt_conditions(win)}")
        reward = c.get("reward") or {}
        rparts = []
        if reward.get("unlock_talent"):
            rparts.append(f"天赋 {reward['unlock_talent']}")
        if reward.get("unlock_mode"):
            rparts.append(f"模式 {reward['unlock_mode']}")
        if reward.get("unlock_achievement"):
            rparts.append(f"成就 {reward['unlock_achievement']}")
        if rparts:
            print(f"       奖励：{'、'.join(rparts)}")
        if c.get("flavor"):
            print(f"       「{c['flavor']}」")
        print()

    print("  A. 取消当前挑战       0. 返回")
    print("═" * 60)
    choice = input("选择要激活的挑战编号: ").strip().upper()

    if choice == "0" or not choice:
        return
    if choice == "A":
        if challenges.abandon_challenge(prof.data):
            runtime.save_profile()
            print("\n已取消当前挑战。")
        else:
            print("\n当前没有激活的挑战。")
        input("按回车返回...")
        return

    try:
        idx = int(choice)
        if not (1 <= idx <= len(items)):
            raise ValueError
    except ValueError:
        print("\n无效选择。")
        input("按回车返回...")
        return

    target = items[idx - 1]
    res = challenges.start_challenge(prof.data, target.get("id", ""))
    if res.get("ok"):
        runtime.save_profile()
        print(f"\n✅ 已激活挑战「{target.get('name','?')}」")
        ov = res.get("start_override") or {}
        if ov:
            print(f"   开局将被强制调整：{_fmt_override(ov)}")
        print("   下一局新游戏时生效。")
    else:
        print(f"\n激活失败：{res.get('message','未知原因')}")
    input("按回车返回...")


def _fmt_conditions(conds: Dict) -> str:
    """把 win_conditions 翻成人话。"""
    name_map = {
        "wealth_gte": "财富≥", "wealth_lte": "财富≤",
        "age_gte": "年龄≥", "age_lte": "年龄≤",
        "happiness_gte": "幸福≥", "intelligence_gte": "智力≥",
        "career_tier_gte": "职业阶梯≥", "health_gte": "健康≥",
        "education_max": "学历不超过", "mode": "模式为",
    }
    parts = []
    for k, v in conds.items():
        label = name_map.get(k, k)
        if isinstance(v, bool):
            parts.append(label if v else f"非{label}")
        elif isinstance(v, list):
            parts.append(f"{label}{v}")
        else:
            parts.append(f"{label}{v}")
    return "，".join(parts)


def _fmt_override(ov: Dict) -> str:
    """把 start_override 翻成人话。"""
    parts = []
    for k, v in ov.items():
        if k.endswith("_blacklist"):
            parts.append(f"禁用 {len(v) if isinstance(v, list) else 0} 项")
        elif isinstance(v, (int, float, str)):
            parts.append(f"{k}={v}")
    return "，".join(parts) or "无"


def show_lineage_panel():
    """家族传承图鉴：已持有 / 未持有的传家宝。"""
    try:
        from core import heirlooms, runtime
    except Exception:
        print("\n传承系统不可用。")
        input("按回车返回...")
        return

    prof = runtime.get_profile()
    summary = heirlooms.lineage_summary(prof.data)
    held_ids = set(heirlooms.held_heirloom_ids(prof.data))
    all_items = heirlooms.all_heirlooms()

    print("\n" + "═" * 60)
    print("    🏺 家族传承")
    print("═" * 60)
    print(f"  传承代数：第 {summary.get('generations', 0)} 代")
    print(f"  持有传家宝：{summary.get('heirloom_count', 0)}/{len(all_items)}")
    print("─" * 60)

    rarity_label = {"common": "普通", "uncommon": "少见", "rare": "稀有",
                    "epic": "史诗", "legendary": "传说"}

    for h in all_items:
        hid = h.get("id", "")
        if hid in held_ids:
            rar = rarity_label.get(h.get("rarity", ""), h.get("rarity", ""))
            chance = h.get("inherit_chance", 0.5)
            print(f"  ● {h.get('name','?')}  [{rar}]  传承率 {int(float(chance) * 100)}%")
            print(f"      {h.get('description','')}")
            eff = h.get("effects") or {}
            if eff:
                parts = [f"{k}{'+' if isinstance(v,(int,float)) and v >= 0 else ''}{v}"
                         for k, v in eff.items()]
                print(f"      效果：{'、'.join(parts)}")
        else:
            hint = h.get("unlock_hint") or "尚未解锁"
            print(f"  ○ ???  —— {hint}")
        print()

    print("═" * 60)
    input("按回车返回...")


def show_ending_codex():
    """结局图鉴：已见过的结局按分类展示。"""
    try:
        from core import endings as E, runtime
    except Exception:
        print("\n结局系统不可用。")
        input("按回车返回...")
        return

    prof = runtime.get_profile()
    coll = E.collection_summary(prof.data)
    seen = set(prof.data.get("seen_endings") or [])

    print("\n" + "═" * 60)
    print("    📜 结局图鉴")
    print("═" * 60)
    print(f"  总进度：{coll.get('seen', 0)}/{coll.get('total', 0)}")
    for cat, prog in (coll.get("by_category") or {}).items():
        label = CATEGORY_LABEL.get(cat, cat)
        bar_len = 20
        ratio = prog["seen"] / prog["total"] if prog["total"] else 0
        bar = "█" * int(bar_len * ratio) + "░" * (bar_len - int(bar_len * ratio))
        print(f"    {label:8s} {bar} {prog['seen']}/{prog['total']}")
    print("─" * 60)

    cur_cat = None
    for e in sorted(E.all_endings(), key=lambda x: (x.category, -x.priority)):
        if e.category != cur_cat:
            cur_cat = e.category
            print(f"\n  【{CATEGORY_LABEL.get(cur_cat, cur_cat)}】")
        if e.id in seen:
            rar = RARITY_LABEL.get(e.rarity, e.rarity)
            print(f"    ● {e.name}  [{rar}]")
        else:
            print(f"    ○ ??????")
    print("\n" + "═" * 60)
    input("按回车返回...")


# ---------- 主菜单 ----------
def show_main_menu():
    """显示主菜单"""
    print("\n" + "═" * 50)
    print("    人生重开模拟器 - SBTI毒舌版")
    print("    含：SBTI出身选择 + 王权决策树")
    print("══════════════════════════════════════════════════")
    print("  温馨提示：本游戏可能引起不适，玻璃心请退出")
    print("═" * 50)
    print("  1. 新游戏")
    print("  2. 加载游戏")
    print("  3. 🎯 挑战模式")
    print("  4. 🏺 家族传承")
    print("  5. 📜 结局图鉴")
    print("  6. 关于")
    print("  0. 退出")
    print("═" * 50)

# ---------- 主程序 ----------
def main():
    """主程序"""
    # 检查必要文件
    required_files = ["backgrounds.json", "events.json"]
    for filename in required_files:
        filepath = os.path.join(SCRIPT_DIR, filename)
        if not os.path.exists(filepath):
            print(f"错误：找不到 {filename} 文件")
            print(f"请确保 {filename} 和 main.py 在同一目录下")
            return

    # 连胜打卡（每进程一次）
    print_streak_banner()

    while True:
        show_main_menu()
        choice = input("请选择: ").strip()

        if choice == '1':
            # 新游戏
            backgrounds = load_json("backgrounds.json")
            events_data = load_json("events.json")

            player = Player()

            # 开局接线：挑战覆写 + 传家宝加成 + 连胜 buff
            try:
                from core import runtime
                boot = runtime.begin_run(player)
                if boot.get("notes"):
                    print("\n" + "─" * 50)
                    for note in boot["notes"]:
                        print(f"  ⚑ {note}")
                    print("─" * 50)
            except Exception:
                pass

            background_choice(player, backgrounds)

            # 选择人生道路
            life_path = choose_life_path(player)

            input("\n按回车开始你的人生...")

            game_mode = "traditional"
            if life_path == "power":
                game_mode = "reigns"
                play_reigns_mode(player)
            elif life_path == "adventure":
                game_mode = "traditional"
                for stage in range(8):
                    continue_game = life_event(player, events_data, stage)
                    if not continue_game:
                        break
                    player.show_stats()
                    if stage < 7:
                        input("\n按回车继续你的人生...")
                traditional_ending(player)
            else:
                game_mode = "cultivation"
                play_cultivation_mode(player, events_data)

            # 询问是否保存
            save_choice = input("\n是否保存游戏？(Y/N): ").strip().upper()
            if save_choice == 'Y':
                save_game(player, game_mode)

        elif choice == '2':
            # 加载游戏
            player, game_mode = load_game_menu()
            if player is None:
                continue

            events_data = load_json("events.json")

            if game_mode == "reigns":
                play_reigns_mode(player)
            elif game_mode == "cultivation":
                play_cultivation_mode(player, events_data)
            else:
                # 归一化后剩余的统一视为 traditional（含 power/adventure 历史别名）
                game_mode = "traditional"
                for stage in range(8):
                    continue_game = life_event(player, events_data, stage)
                    if not continue_game:
                        break
                    player.show_stats()
                    if stage < 7:
                        input("\n按回车继续你的人生...")
                traditional_ending(player)

        elif choice == '3':
            show_challenge_menu()

        elif choice == '4':
            show_lineage_panel()

        elif choice == '5':
            show_ending_codex()

        elif choice == '6':
            # 关于
            print("\n" + "=" * 50)
            print("  人生重开模拟器 - SBTI毒舌版")
            print("  版本：2.1.0")
            print("  特点：")
            print("  * SBTI风格毒舌出身选择")
            print("  * 王权决策树系统")
            print("  * 传统人生事件模式")
            print("  * 修行之路模式")
            print("  * 60 结局库（数据驱动匹配）")
            print("  * 挑战模式 / 家族传承 / 连胜系统")
            print("  * 存档/读档功能")
            print("=" * 50)
            input("\n按回车返回...")

        elif choice == '0':
            print("\n再见！记得现实生活也要努力哦！")
            print("（虽然努力了也不一定有用）")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n游戏被用户中断。")
    except Exception as e:
        print(f"\n游戏运行时发生错误: {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车退出...")
