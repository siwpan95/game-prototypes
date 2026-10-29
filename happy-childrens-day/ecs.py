"""
ECS World - 实体组件系统核心
负责存储和管理所有实体（Entity）、组件（Component）和系统（System）。
"""
import uuid


class World:
    def __init__(self):
        # 存储格式: {entity_id: {ComponentType: component_instance}}
        self._entities = {}
        # 存储待删除的实体，避免在迭代中修改字典
        self._dead_entities = set()

    def create_entity(self):
        """创建一个新的实体（Entity），返回一个唯一的ID。"""
        entity_id = str(uuid.uuid4())[:8]
        self._entities[entity_id] = {}
        return entity_id

    def add_component(self, entity, component_instance):
        """给实体添加一个组件。"""
        comp_type = type(component_instance)
        if entity in self._entities:
            self._entities[entity][comp_type] = component_instance

    def remove_component(self, entity, component_type):
        """移除实体的某个组件。"""
        if entity in self._entities and component_type in self._entities[entity]:
            del self._entities[entity][component_type]

    def component_for_entity(self, entity, component_type):
        """获取实体特定的组件实例（用于单例访问，如Player）。"""
        if entity in self._entities:
            return self._entities[entity].get(component_type)
        return None

    def get_components(self, *component_types):
        """
        生成器：返回所有拥有指定组件组合的实体及其组件实例。
        用法: for ent, (trans, rend) in world.get_components(Transform, Render):
        """
        for entity, components in self._entities.items():
            if all(comp_type in components for comp_type in component_types):
                yield entity, [components[ct] for ct in component_types]

    def delete_entity(self, entity):
        """标记实体为待删除状态。"""
        if entity in self._entities:
            self._dead_entities.add(entity)

    def clear_dead_entities(self):
        """清理已死亡的实体（通常在帧末调用）。"""
        for entity in self._dead_entities:
            if entity in self._entities:
                del self._entities[entity]
        self._dead_entities.clear()

    def update(self, system_instance, *args, **kwargs):
        """
        执行一个系统（System）。
        系统通过调用 world.get_components() 来获取需要处理的数据。
        """
        system_instance.update(self, *args, **kwargs)
