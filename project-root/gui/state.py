"""gui/state.py — GUI 运行时状态中介。

原 LordOfMysteriesGUI 把 character / old_one_info / event_log / view_mode
直接散落在实例字段上；现集中到 GUIState，便于：
  - 面板只读 state.character；
  - 控制器只写 state；
  - 解除「面板持有根窗口、控制器吃根窗口字段」的环形依赖。
LordOfMysteriesGUI 通过属性把这四个字段代理到 state，外部访问方式不变。
"""

from inventory import Inventory
from achievements import AchievementSystem, CodexSystem


class GUIState:
    def __init__(self):
        self.character = None          # 当前角色（Sequence 实例）
        self.old_one_info = None       # 晋升旧日后的构成摘要（dict）
        self.event_log: list = []      # 事件日志
        self.view_mode = "character"   # "character" | "pathways" | "groups" | "factions" | "rivals" | "codex"
        self.fonts = None              # 字体字典（register_fonts 的返回值）
        self.pathway_items = {}        # 左侧途径列表布局：{pathway_key: (y, height)}
        self.inventory = Inventory()   # 魔药材料库存（E1）
        self.pending_event = None      # 待处理的随机事件（E3）：dict 或 None
        self.factions = {}             # 阵营声望（E7）：{faction_key: 声望值}
        # ── P2 新增 ──
        self.rival_system = None       # AI 对手系统（E8）：RivalSystem 或 None
        self.achievements = AchievementSystem()   # 成就（E9）
        self.codex = CodexSystem()                   # 图鉴（E9）
        self.seen_events = set()                     # 已遭遇事件标题（E9 图鉴）
        self.ambient = False                         # 沉浸模式（E10 可选环境音效）

    def __repr__(self):
        ch = self.character
        name = getattr(ch, "SEQUENCE_NAME", None) if ch else None
        return (f"<GUIState character={name!r} view_mode={self.view_mode!r} "
                f"log={len(self.event_log)} entries>")
