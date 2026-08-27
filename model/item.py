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
