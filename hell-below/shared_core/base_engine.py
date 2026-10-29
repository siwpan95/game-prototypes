"""
Base Engine — 抽象游戏引擎基类（纯 Tkinter GUI，无 CLI 回退）。

所有游戏必须继承 BaseEngine 并实现抽象方法。
引擎负责：
  - 初始化 GameState + 子系统
  - 管理 Tkinter MainWindow 生命周期
  - 协调 Story / Puzzle / Combat 子系统
  - 处理用户输入回调（按钮点击、选项选择）
"""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

# 确保 shared_core 可被导入
_SHARED_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
if _SHARED_CORE_DIR not in sys.path:
    sys.path.insert(0, os.path.dirname(_SHARED_CORE_DIR))

from shared_core.game_state import GameState, PlayerState
from shared_core.save_load import SaveLoadManager
from shared_core.event_bus import EventBus


class BaseEngine(ABC):
    """
    抽象游戏引擎基类。

    纯 Tkinter GUI 驱动 — 不支持命令行模式。
    子类通过覆写 hook 方法来定制行为。
    """

    # ---- 游戏元信息（子类必须设置）----
    GAME_TITLE: str = "Hell Below Game"
    GAME_SUBTITLE: str = ""
    SAVE_VERSION: int = 1
    WINDOW_CONFIG: dict = {}  # 覆写默认窗口配置

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.data_dir = os.path.join(base_dir, "assets", "data")
        self.save_dir = os.path.join(base_dir, "assets", "saves")

        # 核心状态
        self.state: GameState = GameState()
        self.event_bus: EventBus = EventBus()

        # 存档管理
        self.saves: SaveLoadManager = SaveLoadManager(
            self.save_dir, self.SAVE_VERSION
        )

        # UI (延迟初始化 — 子类可在 _build_ui 中自定义)
        self.ui: Any = None

        # 内部状态
        self._pending_puzzle_id: Optional[str] = None
        self._awaiting_answer: bool = False
        self._initialized: bool = False
        self._first_content_shown: bool = False

    # ================================================================
    # 抽象方法 — 子类必须实现
    # ================================================================

    @abstractmethod
    def _build_ui(self) -> Any:
        """
        构建并返回 UI 实例（MainWindow 或子类）。

        返回的 UI 对象必须实现以下接口：
          - run()           -> 启动 mainloop
          - shutdown()      -> 销毁窗口
          - show_title_screen()   -> 显示标题画面
          - show_story(content)   -> 显示故事文本
          - show_choices(choices) -> 显示选项按钮
          - show_puzzle(data)     -> 显示谜题
          - show_feedback(type, msg) -> 显示反馈
          - update_status(state)  -> 更新状态面板
          - set_on_submit(cb)     -> 设置输入回调
          - set_on_choice(cb)     -> 设置选择回调
          - log(msg)              -> 记录日志消息
        """

    @abstractmethod
    def _load_story_data(self) -> None:
        """加载游戏的 JSON 剧情数据。"""

    @abstractmethod
    def _get_first_content(self) -> Optional[dict]:
        """获取第一个故事内容片段。返回 dict 或 None（结束）。"""

    @abstractmethod
    def _advance_content(self) -> Optional[dict]:
        """推进到下一个故事内容片段。返回 dict 或 None（结束）。"""

    @abstractmethod
    def _handle_game_over(self) -> None:
        """检查并处理游戏结束条件。"""

    # ================================================================
    # Hook 方法 — 子类可选覆写
    # ================================================================

    def _on_init(self) -> None:
        """初始化钩子 — 在 UI 创建前调用。用于预加载数据等。"""
        pass

    def _on_start(self) -> None:
        """开始游戏钩子 — 在标题画面后、第一个内容前调用。"""
        pass

    def _on_input(self, text: str) -> None:
        """文本输入处理钩子（谜题答案输入时触发）。"""
        if text.lower() in ("quit", "exit", "q"):
            self._shutdown()
            return

    def _on_choice(self, idx: int) -> None:
        """选项选择处理钩子。子类通常需要覆写此方法以实现分支逻辑。"""
        pass

    def _on_hint(self) -> None:
        """提示请求钩子。"""
        pass

    def _calculate_ending(self) -> tuple[str, str]:
        """计算结局。返回 (title, description)。"""
        return ("结局", "感谢游玩。")

    # ================================================================
    # 生命周期
    # ================================================================

    def initialize(self) -> None:
        """初始化：加载数据、构建世界、准备 UI。"""
        self._on_init()
        self._load_story_data()
        self.ui = self._build_ui()
        self.ui.set_on_submit(self._handle_input)
        self.ui.set_on_choice(self._handle_choice)
        self.ui.set_on_hint(self._on_hint)
        self._initialized = True
        self.ui.log("系统已初始化。准备就绪。")

    def start_game(self) -> None:
        """启动游戏（标题画面之后）。尝试加载自动存档。"""
        self._on_start()

        # 尝试加载自动存档
        loaded_state = self.saves.load_auto()
        if loaded_state is not None:
            self.state = loaded_state
            self.ui.update_status(self.state)
            # 存档恢复后，通知子类恢复内部索引
            self._on_state_loaded()
            # 从当前位置继续推进
            self._show_next_content()
            return

        # 无存档 → 正常开始
        self._first_content_shown = False
        self._show_next_content()

    def run(self) -> None:
        """启动 Tkinter 主循环。"""
        if not self._initialized:
            self.initialize()
        self.ui.show_title_screen()

    def save_game(self, slot: int = 0) -> bool:
        """保存游戏到指定槽位。"""
        return self.saves.save(self.state, slot)

    def load_game(self, slot: int = 0) -> bool:
        """从指定槽位加载存档。"""
        state = self.saves.load(slot)
        if state:
            self.state = state
            return True
        return False

    def _shutdown(self) -> None:
        """关闭清理。"""
        try:
            self.saves.auto_save(self.state)
        except Exception:
            pass
        self.ui.shutdown()

    # ================================================================
    # 内容推进
    # ================================================================

    def _on_content_shown(self, content: dict) -> bool:
        """子类可覆写此钩子以在内容显示后拦截后续流程。
        Returns True 表示已处理，跳过谜题/选项等。"""
        return False

    def _show_next_content(self) -> None:
        """获取并显示下一段内容。"""
        if not self._first_content_shown:
            content = self._get_first_content()
            self._first_content_shown = True
        else:
            content = self._advance_content()

        if content is None:
            self._show_ending()
            return

        self.state.record_event(
            "content_shown",
            (content.get("title") or content.get("text") or "")[:80],
        )

        self.ui.show_story(content)
        self.ui.update_status(self.state)

        # 钩子：子类可在此拦截（如触发战斗）
        if self._on_content_shown(content):
            return

        # 检查谜题
        if "puzzle" in content:
            puzzle_id = content["puzzle"]
            self._pending_puzzle_id = puzzle_id
            self._awaiting_answer = True
            self.ui.show_puzzle({"puzzle_id": puzzle_id, **content})
            self.state.set_var("current_puzzle", puzzle_id)
            return

        # 检查选项
        if "choices" in content and content["choices"]:
            self._awaiting_answer = False
            self.ui.show_choices(content["choices"])
            return

        # 无谜题无选项 → 显示继续按钮
        self._awaiting_answer = False
        self.state.advance()
        self.ui.show_next_button(self._show_next_content)

    def _show_ending(self) -> None:
        """显示结局。"""
        title, desc = self._calculate_ending()
        self.ui.show_ending((title, desc))

    # ================================================================
    # 回调处理器
    # ================================================================

    def _handle_input(self, text: str) -> None:
        """处理文本输入（谜题答案）。"""
        self._on_input(text)

    def _handle_choice(self, idx: int) -> None:
        """处理选项选择。"""
        self._on_choice(idx)
        self.state.advance()
        self._handle_game_over()
        self.ui.update_status(self.state)
        self._show_next_content()

    def _handle_next(self) -> None:
        """处理'下一页'按钮点击。"""
        if not self._awaiting_answer:
            self._show_next_content()

    def _handle_hint(self) -> None:
        """处理提示请求。"""
        self._on_hint()


# ================================================================
# Concrete Game Engine — 薄壳专用（无需子类化）
# ================================================================


class ConcreteGameEngine(BaseEngine):
    """具体游戏引擎 — 直接通过 config 模块运行，无需子类化。

    用法（薄壳 main.py）:
        import config
        from shared_core.base_engine import ConcreteGameEngine
        engine = ConcreteGameEngine(config)
        engine.run()
        engine.ui.root.mainloop()
    """

    def __init__(self, config_module):
        # 从 config 模块提取 base_dir
        base_dir = getattr(config_module, 'BASE_DIR',
                           os.path.dirname(os.path.abspath(config_module.__file__)))
        super().__init__(base_dir)

        self.config = config_module
        self.GAME_TITLE = getattr(config_module, 'GAME_NAME', 'Hell Below')
        self.GAME_SUBTITLE = getattr(config_module, 'GAME_SUBTITLE', '')
        self.SAVE_VERSION = getattr(config_module, 'SAVE_VERSION', 1)
        self._story_data: list | dict | None = None
        _story_file = getattr(config_module, 'STORY_FILE', None)
        self._story_filename = os.path.basename(_story_file) if _story_file else None
        self._content_index: int = -1
        self._flat_content: list[dict] = []

        # 读取游戏特性开关（由 config.py 定义）
        self.has_combat = getattr(config_module, 'HAS_COMBAT', False)
        self.has_cards = getattr(config_module, 'HAS_CARDS', False)
        self.has_map = getattr(config_module, 'HAS_MAP', False)
        self.has_event_bus = getattr(config_module, 'HAS_EVENT_BUS', True)

        # 卡牌/战斗子系统（延迟初始化）
        self.combat_engine: Any = None   # CombatEngine 实例
        self.card_deck: list = []        # 当前卡组
        self._cards_data: list = []      # 原始卡牌数据
        self._enemies_data: list = []    # 原始敌人数据
        self._events_data: list = []     # 原始事件数据
        self._current_combat: Any = None # 当前 CombatState
        self._in_combat: bool = False    # 是否处于战斗态

        # 遭遇/房间数据（用于战斗触发器）
        self._encounter_map: dict[str, dict] = {}  # encounter_id → data
        self._rooms_data: dict = {}                # room_id → room data
        self._encounter_pool: list[dict] = []      # 待注入的遭遇条目
        self._encounter_interval: int = 5           # 每隔N条故事注入一次遭遇

        # JSON 加载器
        from shared_core.json_loader import JSONLoader
        self.loader = JSONLoader(self.data_dir)

    # ── 抽象方法实现 ──

    def _build_ui(self) -> Any:
        """构建 MainWindow UI。"""
        from shared_core.main_win import MainWindow
        return MainWindow(self)

    def _load_story_data(self) -> None:
        """从 config 指定的路径加载故事数据。"""
        if self._story_filename and os.path.exists(
            os.path.join(self.data_dir, self._story_filename)
        ):
            data = self.loader.load(self._story_filename)
        else:
            # 自动探测主数据文件
            data = self._auto_detect_story()

        self._story_data = data
        self._flatten_content()

        # 加载游戏玩法数据（卡牌、敌人、事件）
        self._load_game_data()

        # 注入遭遇/战斗到故事流中
        if self.has_combat and self._encounter_pool:
            self._inject_encounters()

    def _load_game_data(self) -> None:
        """加载卡牌/敌人/事件数据（根据 HAS_* 开关）。"""
        if not (self.has_cards or self.has_combat):
            return

        # 卡牌
        cards_file = getattr(self.config, 'CARDS_FILE', None)
        if cards_file and os.path.exists(cards_file):
            cards_data = self.loader.load(os.path.basename(cards_file))
            if isinstance(cards_data, list):
                self._cards_data = cards_data
            elif isinstance(cards_data, dict):
                # 尝试已知的包装键
                for wrap_key in ('cards', 'data', 'list', 'entries'):
                    inner = cards_data.get(wrap_key)
                    if isinstance(inner, list):
                        self._cards_data = inner
                        break
                else:
                    self._cards_data = list(cards_data.values())

        # 敌人
        enemies_file = getattr(self.config, 'ENEMIES_FILE', None)
        if enemies_file and os.path.exists(enemies_file):
            enemies_data = self.loader.load(os.path.basename(enemies_file))
            if isinstance(enemies_data, list):
                self._enemies_data = enemies_data
            elif isinstance(enemies_data, dict):
                # 尝试已知的包装键
                for wrap_key in ('enemies', 'data', 'list', 'entries'):
                    inner = enemies_data.get(wrap_key)
                    if isinstance(inner, list):
                        self._enemies_data = inner
                        break
                else:
                    self._enemies_data = list(enemies_data.values())

        # 事件
        events_file = getattr(self.config, 'EVENTS_FILE', None)
        if events_file and os.path.exists(events_file):
            events_data = self.loader.load(os.path.basename(events_file))
            if isinstance(events_data, list):
                self._events_data = events_data

        # 遭遇数据 (encounters.json / rooms.json encounters)
        self._load_encounter_data()

        # 初始化卡牌战斗系统
        self._init_combat_system()

        # 构建遭遇池（在卡牌系统就绪后）
        self._build_encounter_pool()

    def _init_combat_system(self) -> None:
        """从已加载的数据构建卡牌对象和战斗引擎。"""
        from shared_core.card import Card
        from shared_core.combat_engine import CombatEngine
        from shared_core.enemy import Enemy

        # 构建卡牌对象
        self._card_objects: list[Card] = []
        for cdata in self._cards_data:
            try:
                card = Card.from_dict(cdata)
                self._card_objects.append(card)
            except Exception as e:
                print(f"[Engine] 卡牌加载失败 {cdata.get('id','?')}: {e}")

        # 构建敌人模板
        self._enemy_templates: dict[str, Enemy] = {}
        for edata in self._enemies_data:
            try:
                if not isinstance(edata, dict):
                    continue
                enemy = Enemy.from_dict(edata)
                self._enemy_templates[enemy.id] = enemy
            except Exception as e:
                eid = edata.get('id', '?') if isinstance(edata, dict) else str(edata)[:30]
                print(f"[Engine] 敌人加载失败 {eid}: {e}")

        self.combat_engine = CombatEngine()
        self.card_deck = self._card_objects[:]  # 初始卡组 = 全部卡牌
        if self._card_objects:
            print(f"[Engine] 卡牌系统就绪 ({len(self._card_objects)} 张牌, "
                  f"{len(self._enemy_templates)} 个敌人)")

    def _load_encounter_data(self) -> None:
        """加载遭遇和房间数据，构建 encounter_map 和 rooms_data。"""
        # 1) encounters.json (jx_liu 格式)
        enc_file = os.path.join(self.data_dir, 'encounters.json')
        if os.path.exists(enc_file):
            data = self.loader.load('encounters.json')
            encs = data.get('encounters', data) if isinstance(data, dict) else data
            if isinstance(encs, list):
                for e in encs:
                    if isinstance(e, dict) and 'id' in e:
                        self._encounter_map[e['id']] = e
            elif isinstance(encs, dict):
                self._encounter_map.update(encs)

        # 2) rooms.json (Rinyo / jx_liu 房间遭遇映射)
        rooms_file = getattr(self.config, 'ROOMS_FILE', None)
        if not rooms_file or not os.path.exists(rooms_file):
            rooms_file = os.path.join(self.data_dir, 'rooms.json')
        if os.path.exists(rooms_file):
            import json
            with open(rooms_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            rooms = data.get('rooms', data) if isinstance(data, dict) else {}
            if isinstance(rooms, dict):
                self._rooms_data = rooms

    def _build_encounter_pool(self) -> None:
        """从已加载的数据构建遭遇池（战斗条目列表）。

        优先级:
        1. encounters.json (jx_liu): 过滤 combat/elite/boss 类型
        2. rooms.json encounters (Rinyo): 从房间遭遇中解析敌人
        3. 自动生成 (Borjigin/Penicilin): 从 enemies_data 随机抽取
        """
        self._encounter_pool = []

        # 路径1: encounters.json
        if self._encounter_map:
            for enc_id, enc in self._encounter_map.items():
                etype = enc.get('encounter_type', '')
                if etype in ('combat', 'elite', 'boss'):
                    enemy_ids = enc.get('enemy_ids', [])
                    if enemy_ids:
                        valid = [eid for eid in enemy_ids
                                 if eid in self._enemy_templates]
                        if valid:
                            self._encounter_pool.append({
                                'enemy_id': valid[0],
                                'encounter_name': enc.get('name', enc_id),
                                'encounter_desc': enc.get('description', ''),
                                'all_enemies': valid,
                                '_source': 'encounters.json',
                            })
            if self._encounter_pool:
                print(f"[Engine] 遭遇池就绪 ({len(self._encounter_pool)} 场战斗)")
                return

        # 路径2: rooms.json encounters (Rinyo 格式)
        if self._rooms_data:
            for room_id, room in self._rooms_data.items():
                enc_ids = room.get('encounters', [])
                for enc_id in enc_ids:
                    # 尝试从 encounter_map 解析
                    if enc_id in self._encounter_map:
                        em = self._encounter_map[enc_id]
                        enemy_ids = em.get('enemy_ids', [])
                    # 尝试作为直接的敌人ID（去掉前缀）
                    elif enc_id.startswith('enemy_') and enc_id in self._enemy_templates:
                        enemy_ids = [enc_id]
                    elif enc_id in self._enemy_templates:
                        enemy_ids = [enc_id]
                    else:
                        # 模糊匹配：去掉 encounter_ 前缀
                        bare = enc_id.replace('encounter_', '')
                        if bare in self._enemy_templates:
                            enemy_ids = [bare]
                        else:
                            continue

                    valid = [eid for eid in enemy_ids
                             if eid in self._enemy_templates]
                    if valid:
                        self._encounter_pool.append({
                            'enemy_id': valid[0],
                            'encounter_name': enc_id,
                            'encounter_desc': room.get('description', ''),
                            'all_enemies': valid,
                            '_source': 'rooms.json',
                        })
            if self._encounter_pool:
                print(f"[Engine] 遭遇池就绪 ({len(self._encounter_pool)} 场战斗, 来自 rooms)")
                return

        # 路径3: 自动生成 (Borjigin / Penicilin)
        if self._enemy_templates:
            import random
            enemy_list = list(self._enemy_templates.keys())
            # 生成与敌人数量相当的遭遇
            count = min(len(enemy_list), 10)
            picked = random.sample(enemy_list, count) if len(enemy_list) > count else enemy_list
            for eid in picked:
                tmpl = self._enemy_templates[eid]
                self._encounter_pool.append({
                    'enemy_id': eid,
                    'encounter_name': tmpl.name,
                    'encounter_desc': getattr(tmpl, 'description', ''),
                    'all_enemies': [eid],
                    '_source': 'auto-generated',
                })
            print(f"[Engine] 遭遇池就绪 ({len(self._encounter_pool)} 场战斗, 自动生成)")

    def _inject_encounters(self) -> None:
        """将遭遇条目注入到 _flat_content 中，穿插在故事条目之间。"""
        pool = self._encounter_pool
        if not pool or not self._flat_content:
            return

        import random
        # 计算注入间隔：确保遭遇均匀分布
        n_story = len(self._flat_content)
        n_enc = len(pool)
        interval = max(2, n_story // (n_enc + 1))
        self._encounter_interval = interval

        # 随机打乱遭遇顺序
        shuffled = pool[:]
        random.shuffle(shuffled)

        new_flat = []
        enc_idx = 0
        for i, entry in enumerate(self._flat_content):
            new_flat.append(entry)
            # 每隔 interval 条故事注入一个遭遇
            if (i + 1) % interval == 0 and enc_idx < len(shuffled):
                enc = shuffled[enc_idx]
                combat_entry = {
                    'enemy_id': enc['enemy_id'],
                    'text': enc.get('encounter_desc', '') or f"你遭遇了敌人！",
                    'title': f"⚔ {enc.get('encounter_name', '战斗')}",
                }
                new_flat.append(combat_entry)
                enc_idx += 1

        # 剩余遭遇追加到末尾
        while enc_idx < len(shuffled):
            enc = shuffled[enc_idx]
            new_flat.append({
                'enemy_id': enc['enemy_id'],
                'text': enc.get('encounter_desc', '') or '你遭遇了敌人！',
                'title': f"⚔ {enc.get('encounter_name', '战斗')}",
            })
            enc_idx += 1

        self._flat_content = new_flat
        print(f"[Engine] 遭遇注入完成 ({len(pool)} 场战斗 → {len(new_flat)} 总条目)")

    def _auto_detect_story(self) -> Any:
        """自动探测主剧情文件（按优先级尝试常见文件名）。"""
        candidates = [
            'story.json', 'narratives.json', 'dialogs.json',
            'nodes.json', 'chapters.json', 'events.json',
            'world.json',
        ]
        for name in candidates:
            data = self.loader.load(name)
            if data is not None:
                self._story_filename = name
                return data
        return {}

    def _flatten_content(self) -> None:
        """将各种格式的剧情数据扁平化为内容列表。

        支持格式:
        - list[dict/str]: 直接列表
        - dict with list keys: chapters, scenes, nodes, entries, stories,
                               content, data, dialogs, narratives, events
        - dict with dict keys: dialog_trees, dialogs, events, rooms
        - rooms.json (无叙事文件时)
        """
        self._flat_content = []
        data = self._story_data

        if not data or data == {}:
            # 尝试从 rooms.json 生成内容
            self._load_from_rooms()
            return

        if isinstance(data, list):
            for item in data:
                if item is None:
                    continue
                if isinstance(item, dict) and ('nodes' in item or 'dialog_tree_id' in item):
                    # 列表项是对话树结构 → 扁平化其节点
                    tree_name = item.get('dialog_tree_id') or item.get('id', '')
                    nodes = item.get('nodes', {})
                    if isinstance(nodes, dict):
                        for node_id, node in nodes.items():
                            if node is None:
                                continue
                            if isinstance(node, dict):
                                entry = self._normalize_entry(node)
                                if entry.get('text') and entry['text'] != '（无文本）':
                                    entry['_tree'] = tree_name
                                    entry['_node'] = node_id
                                    self._flat_content.append(entry)
                    else:
                        self._flat_content.append(self._normalize_entry(item))
                else:
                    self._flat_content.append(self._normalize_entry(item))
        elif isinstance(data, dict):
            # 尝试所有已知的列表键
            list_keys = ('chapters', 'scenes', 'nodes', 'entries', 'stories',
                         'content', 'data', 'dialogs', 'narratives', 'events')
            found = False
            for key in list_keys:
                val = data.get(key)
                if isinstance(val, list):
                    self._flat_content = [self._normalize_entry(item) for item in val]
                    found = True
                    break
                elif isinstance(val, dict):
                    # dict of entries - flatten to list
                    entries = []
                    for k2, v2 in sorted(val.items()):
                        if v2 is None:
                            continue
                        if isinstance(v2, dict) and 'nodes' in v2:
                            # 值中包含对话树节点 → 扁平化
                            tree_name = v2.get('name') or v2.get('id', k2)
                            nodes = v2.get('nodes', {})
                            if isinstance(nodes, dict):
                                for node_id, node in nodes.items():
                                    if isinstance(node, dict):
                                        entry = self._normalize_entry(node)
                                        if entry.get('text') and entry['text'] != '（无文本）':
                                            entry['_tree'] = tree_name
                                            entry['_node'] = node_id
                                            entries.append(entry)
                            else:
                                v2 = dict(v2)
                                v2['_key'] = k2
                                entries.append(self._normalize_entry(v2))
                        else:
                            if isinstance(v2, dict):
                                v2 = dict(v2)
                                v2['_key'] = k2
                            entries.append(self._normalize_entry(v2))
                    self._flat_content = entries
                    found = True
                    break

            if not found:
                # 检查是否是 dialog_trees 或其他嵌套结构
                if 'dialog_trees' in data:
                    self._flatten_dialog_trees(data['dialog_trees'])
                else:
                    # 把顶层自身作为唯一内容
                    self._flat_content.append(self._normalize_entry(data))

        if not self._flat_content:
            self._flat_content = [{"text": "（暂无剧情数据）"}]

    def _normalize_entry(self, item) -> dict:
        """将各种格式的条目标准化为统一格式 {"text": ..., "title": ..., "choices": [...]}"""
        if isinstance(item, str):
            return {"text": item}
        if not isinstance(item, dict):
            return {"text": str(item)}

        result = {}

        # 文本字段（按优先级）
        if 'text' in item:
            result['text'] = item['text']
        elif 'content' in item and isinstance(item['content'], str):
            result['text'] = item['content']
        elif 'description' in item and isinstance(item['description'], str):
            result['text'] = item['description']
        elif 'lines' in item and isinstance(item['lines'], list):
            # 多行对话: {'speaker': 'x', 'lines': [{'text': '...'}, ...]}
            texts = []
            for line in item['lines']:
                if isinstance(line, dict) and 'text' in line:
                    texts.append(line['text'])
                elif isinstance(line, str):
                    texts.append(line)
            result['text'] = '\n'.join(texts)
        else:
            result['text'] = item.get('_key', '') or '（无文本）'

        # 标题
        if 'title' in item:
            result['title'] = item['title']
        elif 'name' in item:
            result['title'] = item['name']
        elif 'speaker' in item:
            result['title'] = item['speaker']
        elif 'id' in item:
            result['title'] = item['id']

        # 选项/选择
        choices = []
        if 'choices' in item and isinstance(item['choices'], list):
            for c in item['choices']:
                if isinstance(c, dict):
                    choices.append({"text": c.get('text', str(c))})
                elif isinstance(c, str):
                    choices.append({"text": c})
        elif 'responses' in item and isinstance(item['responses'], list):
            for r in item['responses']:
                if isinstance(r, dict):
                    choices.append({"text": r.get('text', str(r))})
                elif isinstance(r, str):
                    choices.append({"text": r})
        elif 'options' in item and isinstance(item['options'], list):
            for o in item['options']:
                if isinstance(o, dict):
                    choices.append({"text": o.get('text', o.get('label', str(o)))})
                elif isinstance(o, str):
                    choices.append({"text": o})

        if choices:
            result['choices'] = choices

        # 谜题
        if 'puzzle' in item:
            result['puzzle'] = item['puzzle']
        elif 'puzzle_id' in item:
            result['puzzle'] = item['puzzle_id']

        # 语调/风格
        if 'tone' in item:
            result['tone'] = item['tone']

        return result

    def _flatten_dialog_trees(self, dialog_trees: dict) -> None:
        """将对话树结构扁平化为内容列表。"""
        for tree_name, tree in sorted(dialog_trees.items()):
            if not isinstance(tree, dict):
                continue
            for node_id, node in tree.items():
                if node is None or not isinstance(node, dict):
                    continue
                entry = self._normalize_entry(node)
                if entry.get('text') and entry['text'] != '（无文本）':
                    entry['_tree'] = tree_name
                    entry['_node'] = node_id
                    self._flat_content.append(entry)

    def _load_from_rooms(self) -> None:
        """从 rooms.json 生成叙事内容（领域驱动模式）。"""
        rooms_file = getattr(self.config, 'ROOMS_FILE', None)
        if not rooms_file or not os.path.exists(rooms_file):
            self._flat_content = [{"text": "（暂无剧情数据）"}]
            return

        try:
            import json
            with open(rooms_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            rooms = data.get('rooms', data) if isinstance(data, dict) else {}
            if isinstance(rooms, dict):
                for room_id, room in sorted(rooms.items()):
                    if not isinstance(room, dict):
                        continue
                    text_parts = []
                    if room.get('first_visit_text'):
                        text_parts.append(room['first_visit_text'])
                    if room.get('description'):
                        text_parts.append(room['description'])

                    exits = room.get('exits', {})
                    if exits:
                        exit_text = '出口：' + '，'.join(f'{k}→{v}' for k, v in exits.items())
                        text_parts.append(exit_text)

                    entry = {
                        "text": '\n\n'.join(text_parts) if text_parts else room.get('name', room_id),
                        "title": room.get('name', room_id),
                    }
                    self._flat_content.append(entry)
        except Exception as e:
            print(f"[Engine] 加载房间数据失败: {e}")
            self._flat_content = [{"text": "（暂无剧情数据）"}]

    def _get_first_content(self) -> Optional[dict]:
        """获取第一个内容片段。"""
        self._content_index = 0
        if self._flat_content:
            return self._flat_content[0]
        return None

    def _advance_content(self) -> Optional[dict]:
        """推进到下一个内容片段。"""
        self._content_index += 1
        if self._content_index < len(self._flat_content):
            return self._flat_content[self._content_index]
        return None

    def _handle_game_over(self) -> None:
        """检查游戏结束条件（基于内容是否耗尽）。"""
        if self._content_index >= len(self._flat_content) - 1:
            pass  # 将在下次 _show_next_content 时触发结局

    # ================================================================
    # 内容钩子 — 战斗检测
    # ================================================================

    def _on_content_shown(self, content: dict) -> bool:
        """检测并触发战斗。"""
        if not self.has_combat or not content:
            return False
        enemy_id = content.get("enemy_id")
        if enemy_id and hasattr(self, '_enemy_templates') and \
           enemy_id in self._enemy_templates:
            self._start_combat(enemy_id)
            return True
        return False

    # ================================================================
    # 选择处理 — 覆写以支持战斗模式
    # ================================================================

    def _handle_choice(self, idx: int) -> None:
        """处理选项选择：战斗模式打出卡牌，剧情模式正常推进。"""
        if self._in_combat:
            self._handle_combat_card(idx)
            return
        # 正常剧情流
        self._on_choice(idx)
        self.state.advance()
        self._handle_game_over()
        self.ui.update_status(self.state)
        self._show_next_content()

    # ================================================================
    # 卡牌战斗系统
    # ================================================================

    def _start_combat(self, enemy_id: str) -> None:
        """启动一场战斗。"""
        from shared_core.enemy import EnemyInstance
        from shared_core.combat_engine import CombatState

        if enemy_id not in self._enemy_templates:
            self.ui.log(f"战斗数据缺失: {enemy_id}")
            return

        enemy_template = self._enemy_templates[enemy_id]
        enemy = EnemyInstance(enemy_template)

        self._current_combat = CombatState.new(
            max(1, self.state.player.hp),
            max(1, self.state.player.max_hp or 100),
            self.state.player.nerve,
            max(1, self.state.player.max_nerve or 50),
            enemy,
            self._card_objects[:],
            log_cb=self.ui.log,
        )
        self._in_combat = True
        self.ui.log(f"⚔ 战斗开始！遭遇 {enemy.name}。")
        self._show_combat_ui()

    def _show_combat_ui(self) -> None:
        """刷新战斗界面。"""
        cs = self._current_combat
        if not cs or cs.combat_over:
            return

        enemy = cs.enemy
        combat_text = (
            f"【{enemy.name}】 HP: {enemy.hp}/{enemy.max_hp}\n"
            f"你的 HP: {cs.player_hp}/{cs.player_max_hp}  AP: {cs.ap}  格挡: {cs.player_block}\n\n"
            f"手牌："
        )
        for i, card in enumerate(cs.hand, start=1):
            combat_text += f"\n{i}. [{card.ap_cost}AP] {card.name}：{card.description}"
        self.ui.show_story(
            {"text": combat_text, "title": f"⚔ 第 {cs.turn_number} 回合"}
        )

        choices = []
        for card in cs.hand:
            choices.append({
                "text": f"[{card.ap_cost}AP] {card.name}",
            })
        choices.append({"text": "▶ 结束回合"})
        self.ui.show_choices(choices)

    def _handle_combat_card(self, idx: int) -> None:
        """处理玩家出牌或结束回合。"""
        cs = self._current_combat
        if not cs or cs.combat_over:
            return

        if idx >= len(cs.hand):
            # 结束回合
            cs.end_player_turn()
            self.state.player.hp = cs.player_hp
            if cs.combat_over:
                self._end_combat()
                return
            self._show_combat_ui()
            return

        # 打出卡牌
        success = cs.play_card(idx)
        if not success:
            self.ui.show_feedback("failure", "无法打出此牌")
            self._show_combat_ui()
            return

        self.state.player.hp = cs.player_hp
        self.ui.update_status(self.state)

        if cs.combat_over:
            self._end_combat()
            return

        self._show_combat_ui()

    def _end_combat(self) -> None:
        """结束战斗，返回剧情。"""
        cs = self._current_combat
        if cs and cs.player_won:
            self.ui.show_feedback(
                "success", f"战斗胜利！击败了 {cs.enemy.name}。"
            )
        else:
            self.ui.show_game_over("你在战斗中倒下...")
            self._in_combat = False
            self._current_combat = None
            return

        self._in_combat = False
        self._current_combat = None
        self.state.advance()
        self._show_next_content()

    # ================================================================
    # 存档恢复钩子（子类覆写）
    # ================================================================

    def _on_state_loaded(self) -> None:
        """
        存档加载后的钩子。子类在此同步内部索引。

        ConcreteGameEngine 在此恢复 _content_index（索引偏移 -1，
        因为 _show_next_content 中 _advance_content 会 +1）。
        """
        saved_index = self.state.variables.get("_content_index", 0)
        self._content_index = max(-1, saved_index - 1)
        self._first_content_shown = True
