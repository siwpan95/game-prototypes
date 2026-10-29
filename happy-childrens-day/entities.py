"""
实体工厂 (Entities)
从 Excel 配置创建零食实体。
"""
from components import Transform, Render, Collider
from data_loader import SnackConfig

# 全局配置加载器（只加载一次）
CONFIG = SnackConfig()


def create_snack(world, x, y, snack_id=None):
    """在指定位置创建一个零食实体"""
    if snack_id is None:
        snack_id = CONFIG.get_random_snack_id()

    snack_data = CONFIG.get_snack_by_id(snack_id)
    if not snack_data:
        return None

    entity = world.create_entity()
    world.add_component(entity, Transform(x, y))
    # 使用 Excel 中的 shape（图形）+ label（标签）+ color（颜色）
    world.add_component(entity, Render(
        color=snack_data.color,
        shape=snack_data.shape,
        label=snack_data.label,
    ))
    world.add_component(entity, Collider(15))
    world.add_component(entity, snack_data)
    return entity
