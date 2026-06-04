"""
ECS Core - A lightweight Entity-Component-System framework.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Type
import uuid


class Component:
    """Base class for all components (pure data)."""
    pass


class System:
    """Base class for all systems (pure logic)."""
    def update(self, world: "World", dt: float) -> None:
        raise NotImplementedError


class Entity:
    """An entity is just a unique identifier."""
    def __init__(self, entity_id: Optional[str] = None):
        self.id = entity_id or uuid.uuid4().hex[:8]

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, Entity) and self.id == other.id


class World:
    """The World manages all entities, components, and systems."""

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.components: Dict[Type[Component], Dict[str, Component]] = {}
        self.systems: List[System] = []
        self._entity_counter = 0

    # ── Entity management ──────────────────────────────────────────

    def create_entity(self) -> Entity:
        """Create and return a new entity."""
        entity = Entity()
        self.entities[entity.id] = entity
        return entity

    def remove_entity(self, entity: Entity) -> None:
        """Remove an entity and all its components."""
        eid = entity.id
        self.entities.pop(eid, None)
        for comp_dict in self.components.values():
            comp_dict.pop(eid, None)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get an entity by ID."""
        return self.entities.get(entity_id)

    # ── Component management ───────────────────────────────────────

    def add_component(self, entity: Entity, component: Component) -> None:
        """Attach a component to an entity."""
        comp_type = type(component)
        if comp_type not in self.components:
            self.components[comp_type] = {}
        self.components[comp_type][entity.id] = component

    def remove_component(self, entity: Entity, comp_type: Type[Component]) -> None:
        """Remove a component type from an entity."""
        if comp_type in self.components:
            self.components[comp_type].pop(entity.id, None)

    def get_component(self, entity: Entity, comp_type: Type[Component]) -> Optional[Component]:
        """Get a specific component from an entity."""
        return self.components.get(comp_type, {}).get(entity.id)

    def has_component(self, entity: Entity, comp_type: Type[Component]) -> bool:
        """Check if an entity has a specific component."""
        return entity.id in self.components.get(comp_type, {})

    # ── Querying ───────────────────────────────────────────────────

    def get_entities_with(self, *comp_types: Type[Component]) -> List[Entity]:
        """Return all entities that have ALL specified component types."""
        if not comp_types:
            return []
        # Start with entities that have the first component type
        result: Set[str] = set(self.components.get(comp_types[0], {}).keys())
        # Intersect with each subsequent component type
        for ct in comp_types[1:]:
            result &= set(self.components.get(ct, {}).keys())
        return [self.entities[eid] for eid in result]

    def get_singleton(self, comp_type: Type[Component]) -> Optional[Component]:
        """Get the component of a given type from the first entity that has it."""
        entities = self.get_entities_with(comp_type)
        if entities:
            return self.get_component(entities[0], comp_type)
        return None

    # ── System management ──────────────────────────────────────────

    def add_system(self, system: System) -> None:
        """Register a system. Systems are updated in registration order."""
        self.systems.append(system)

    def update(self, dt: float) -> None:
        """Run all systems once."""
        for system in self.systems:
            system.update(self, dt)
