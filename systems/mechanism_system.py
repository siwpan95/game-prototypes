"""
机关系统 — 事件驱动的动态地图变化。
监听卡牌收集和记忆触发事件，修改地图墙壁、消除黑暗。
支持数据驱动机关（来自 Mod 清单）。
"""
from core.ecs import System


class MechanismSystem(System):
    """响应游戏事件，动态修改共享地图。
    机关可以从 Mod 清单动态加载，也保留内置机关作为回退。"""

    def __init__(self, map_data, event_bus, ui_system=None):
        self.map = map_data
        self.bus = event_bus
        self.ui = ui_system
        self._triggered = set()       # 已触发的机关 ID
        self.mechanisms = {}          # (event_type, trigger_id) → mechanism dict
        self._setup_listeners()
        self._define_builtin_mechanisms()

    def _setup_listeners(self):
        self.bus.subscribe("CARD_COLLECTED", self._on_event)
        self.bus.subscribe("MEMORY_TRIGGERED", self._on_event)

    def _define_builtin_mechanisms(self):
        """内置机关定义（回退用，当 base_mod.json 未加载时生效）。"""
        self.mechanisms.update({
            ("CARD_COLLECTED", "key_01"): {
                "id": "attic_unlock",
                "desc": "你举起铜钥匙。阁楼的墙壁发出一阵低沉的回声，一道隐藏的门缓缓显现。",
                "actions": [
                    {"type": "replace_at", "col": 18, "row": 3, "old": "门", "new": "░"},
                ],
            },
            ("CARD_COLLECTED", "suspicious_hole_01"): {
                "id": "basement_unlock",
                "desc": "墙壁上的洞突然开始扩大——碎石无声地剥落，露出通往地下的阶梯。",
                "actions": [
                    {"type": "replace_at", "col": 19, "row": 20, "old": "墙", "new": "░"},
                    {"type": "replace_at", "col": 20, "row": 20, "old": "墙", "new": "░"},
                    {"type": "replace_area", "col_start": 17, "col_end": 22,
                     "row_start": 21, "row_end": 29, "target": ["暗"], "replacement": "░"},
                ],
            },
            ("CARD_COLLECTED", "dead_vole_01"): {
                "id": "hallway_clear",
                "desc": "死去的田鼠从你手中化作一缕轻烟。走廊里的阴影开始退却……",
                "actions": [
                    {"type": "replace_area", "col_start": 0, "col_end": 39,
                     "row_start": 18, "row_end": 19, "target": ["暗"], "replacement": "░"},
                ],
            },
            ("MEMORY_TRIGGERED", "candle_01"): {
                "id": "basement_light",
                "desc": "祭烛的火焰虽然熄了，但余温仍在你掌心跳动。地下室深处的黑暗正在萎缩。",
                "actions": [
                    {"type": "replace_area", "col_start": 5, "col_end": 36,
                     "row_start": 22, "row_end": 29, "target": ["暗"], "replacement": "░"},
                ],
            },
            ("CARD_COLLECTED", "owl_01"): {
                "id": "basement_full_light",
                "desc": "猫头鹰张开翅膀，它的羽毛里涌出星尘般的光点，照亮了地下室最阴暗的角落。",
                "actions": [
                    {"type": "replace_area", "col_start": 0, "col_end": 39,
                     "row_start": 21, "row_end": 29, "target": ["暗"], "replacement": "░"},
                ],
            },
            ("CARD_COLLECTED", "wooden_statue_01"): {
                "id": "statue_hint",
                "desc": "无眼的猫头鹰雕像在你手中微微发烫……它的口中，你摸到了一片薰衣草花瓣。",
                "actions": [],
            },
        })

    def load_mechanisms(self, mod, map_def):
        """从 Mod/地图定义加载数据驱动机关（替换当前机关表）。
        mod: ModManifest, map_def: MapDef"""
        # 清除旧的机关定义
        self.mechanisms.clear()
        self._triggered.clear()
        # 加载内置回退
        self._define_builtin_mechanisms()
        # 叠加 Mod 机关（覆盖同 key 的内置机关）
        for mech in map_def.mechanisms:
            actions = []
            for a in mech.actions:
                actions.append({"type": a.type, **a.params})
            key = (mech.trigger_type, mech.trigger_id)
            self.mechanisms[key] = {
                "id": mech.mech_id,
                "desc": mech.desc,
                "actions": actions,
            }

    def _execute_action(self, action: dict):
        """执行单个数据驱动机关动作。"""
        atype = action["type"]
        if atype == "replace_at":
            self.map.replace_at(
                action["col"], action["row"],
                action["old"], action["new"],
            )
        elif atype == "replace_region":
            self.map.replace_region(
                action["col_start"], action["col_end"],
                action["row_start"], action["row_end"],
                action["old"], action["new"],
            )
        elif atype == "replace_area":
            target = set(action.get("target", []))
            self.map.replace_area(
                action["col_start"], action["col_end"],
                action["row_start"], action["row_end"],
                target, action["replacement"],
            )

    def _on_event(self, data):
        """统一的事件处理入口。"""
        if data is None:
            return

        if "card_id" in data:
            event_type = "CARD_COLLECTED"
            trigger_id = data["card_id"]
        elif "id" in data:
            event_type = "MEMORY_TRIGGERED"
            trigger_id = data["id"]
        else:
            return

        key = (event_type, trigger_id)
        mech = self.mechanisms.get(key)
        if mech is None:
            return

        mid = mech["id"]
        if mid in self._triggered:
            return

        self._triggered.add(mid)
        for action in mech["actions"]:
            self._execute_action(action)

        if self.ui:
            self.ui.show_mechanism_text(mech["desc"])

        self.bus.emit("MECHANISM_TRIGGERED", {"id": mid, "desc": mech["desc"]})

    def update(self, world, dt):
        pass
