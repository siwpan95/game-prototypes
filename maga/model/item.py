"""物品数据模型"""


class Item:
    """物品"""

    def __init__(self, item_data: "ItemData"):
        self.id = item_data.id
        self.name = item_data.name
        self.type = item_data.type  # heal / weapon / armor / fuel / buff
        self.effect_value = item_data.effect_value
        self.price = item_data.price
        self.description = item_data.description
        self.usable_in_battle = item_data.usable_in_battle
        self.data = item_data

    def to_dict(self) -> dict:
        """序列化为可 JSON 存档的最小字典（按 ID 重建）"""
        return {"id": self.id}

    @classmethod
    def from_dict(cls, d: dict, config) -> "Item":
        """从存档字典重建物品；config 为 ConfigLoader"""
        item_data = config.get_item_by_id(d["id"])
        if item_data is None:
            raise ValueError(f"存档引用了不存在的物品ID: {d['id']}")
        return cls(item_data)
