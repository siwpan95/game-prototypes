"""ECS Core — Entity Component System framework for KARD."""

from __future__ import annotations


# ── Entity ──────────────────────────────────────────────────────────────────

class Entity:
    """Lightweight entity — just an integer ID."""
    _next_id: int = 0

    def __init__(self) -> None:
        self.id: int = Entity._next_id
        Entity._next_id += 1

    def __repr__(self) -> str:
        return f"Entity({self.id})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Entity) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


# ── Component ───────────────────────────────────────────────────────────────

class Component:
    """Base class for all components. Components hold DATA only — no logic."""
    pass


# ── System ──────────────────────────────────────────────────────────────────

class System:
    """Base class for all systems. Systems contain LOGIC and iterate over entities."""

    def update(self, world: "World", dt: float, events: list | None = None) -> None:
        """Override in subclasses. Called once per frame.

        Args:
            world:  The ECS World to query.
            dt:     Delta-time in seconds.
            events: Pygame event list for this frame (may be None).
        """
        pass


# ── World ───────────────────────────────────────────────────────────────────

class World:
    """Central ECS manager — owns entities, components, and systems."""

    def __init__(self) -> None:
        self.entities: set[Entity] = set()
        # {ComponentType: {Entity: component_instance}}
        self._components: dict[type, dict[Entity, Component]] = {}
        self.systems: list[System] = []

    # ── Entity management ───────────────────────────────────────────────

    def create_entity(self) -> Entity:
        e = Entity()
        self.entities.add(e)
        return e

    def destroy_entity(self, entity: Entity) -> None:
        for comp_map in self._components.values():
            comp_map.pop(entity, None)
        self.entities.discard(entity)

    # ── Component management ────────────────────────────────────────────

    def add_component(self, entity: Entity, component: Component) -> None:
        ct = type(component)
        if ct not in self._components:
            self._components[ct] = {}
        self._components[ct][entity] = component

    def get_component(self, entity: Entity, comp_type: type) -> Component | None:
        return self._components.get(comp_type, {}).get(entity)

    def has_component(self, entity: Entity, comp_type: type) -> bool:
        return entity in self._components.get(comp_type, {})

    def get_entities_with(self, *comp_types: type) -> set[Entity]:
        """Return the set of entities that have ALL specified component types."""
        if not comp_types:
            return set()
        result = set(self._components.get(comp_types[0], {}).keys())
        for ct in comp_types[1:]:
            result &= set(self._components.get(ct, {}).keys())
        return result

    def get_all_components(self, comp_type: type) -> dict[Entity, Component]:
        """Return the full {Entity: Component} mapping for a type."""
        return dict(self._components.get(comp_type, {}))

    def remove_component(self, entity: Entity, comp_type: type) -> None:
        self._components.get(comp_type, {}).pop(entity, None)

    # ── System management ───────────────────────────────────────────────

    def add_system(self, system: System) -> None:
        self.systems.append(system)

    # ── Update ──────────────────────────────────────────────────────────

    def update(self, dt: float, events: list | None = None) -> None:
        for system in self.systems:
            system.update(self, dt, events)

    # ── Convenience ─────────────────────────────────────────────────────

    def clear(self) -> None:
        """Remove all entities and components (keep systems)."""
        self.entities.clear()
        for cm in self._components.values():
            cm.clear()
