"""
ECS Architecture Core
Entity-Component-System framework for Russian Roulette game.
"""

# ── Entity ──────────────────────────────────────────────────────────────

class Entity:
    """An entity is just a unique ID bag. Components are attached externally."""
    _next_id = 0

    def __init__(self, name: str = ""):
        self.id = Entity._next_id
        Entity._next_id += 1
        self.name = name or f"entity_{self.id}"

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, Entity) and self.id == other.id

    def __repr__(self):
        return f"<Entity #{self.id} '{self.name}'>"


# ── Component ──────────────────────────────────────────────────────────

class Component:
    """Base class for all components. Pure data, no logic."""
    pass


# ── World (Component Registry) ────────────────────────────────────────

class World:
    """
    Stores component instances keyed by (entity, ComponentClass).
    Systems query the world to find entities with specific component combos.
    """
    def __init__(self):
        # {ComponentClass: {entity: component_instance}}
        self._components: dict[type, dict[Entity, Component]] = {}

    def add_component(self, entity: Entity, component: Component):
        ctype = type(component)
        if ctype not in self._components:
            self._components[ctype] = {}
        self._components[ctype][entity] = component

    def remove_component(self, entity: Entity, component_type: type):
        if component_type in self._components:
            self._components[component_type].pop(entity, None)

    def get_component(self, entity: Entity, component_type: type) -> Component | None:
        return self._components.get(component_type, {}).get(entity)

    def has_component(self, entity: Entity, component_type: type) -> bool:
        return component_type in self._components and entity in self._components[component_type]

    def get_entities_with(self, *component_types: type) -> list[Entity]:
        """Return entities that have ALL the given component types."""
        if not component_types:
            return []
        first = set(self._components.get(component_types[0], {}).keys())
        result = first
        for ct in component_types[1:]:
            result = result & set(self._components.get(ct, {}).keys())
        return list(result)

    def get_component_map(self, component_type: type) -> dict[Entity, Component]:
        """Return {entity: component} for all entities with this component."""
        return self._components.get(component_type, {}).copy()


# ── System ─────────────────────────────────────────────────────────────

class System:
    """Base class for all systems. Override update(world, dt, **kwargs)."""
    def update(self, world: World, dt: float = 0.0, **kwargs):
        raise NotImplementedError


# ── System Manager ────────────────────────────────────────────────────

class SystemManager:
    """Owns the system list and runs them in order each frame."""
    def __init__(self):
        self.systems: list[System] = []

    def add_system(self, system: System):
        self.systems.append(system)

    def update_all(self, world: World, dt: float = 0.0, **kwargs):
        for system in self.systems:
            system.update(world, dt, **kwargs)
