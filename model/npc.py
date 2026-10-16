"""NPC 数据模型"""


class NPC:
    """非玩家角色"""

    def __init__(self, npc_data: "NPCData"):
        self.id = npc_data.id
        self.name = npc_data.name
        self.role = npc_data.role
        self.dialog = npc_data.dialog
        self.dialogs = npc_data.dialogs or [(None, npc_data.dialog)]
        self.location_x = npc_data.location_x
        self.location_y = npc_data.location_y
        self.map_id = npc_data.map_id
        self.data = npc_data
