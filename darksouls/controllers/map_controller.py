"""MapController - map generation and route selection."""

from __future__ import annotations

import random


class MapNode:
    """Represents a single node on the map.

    Attributes:
        node_type: Type of node ('battle', 'event', 'boss', 'bonfire', 'shop', 'blacksmith').
        act: Act number this node belongs to.
        row: Row position on the map.
        col: Column position on the map.
        visited: Whether this node has been visited.
        enemy_id: Enemy ID for battle nodes.
        event_id: Event ID for event nodes.
    """

    def __init__(
        self,
        node_type: str = "battle",
        act: int = 1,
        row: int = 0,
        col: int = 0,
        enemy_id: str = "",
        event_id: str = "",
    ) -> None:
        self.node_type = node_type
        self.act = act
        self.row = row
        self.col = col
        self.visited: bool = False
        self.enemy_id = enemy_id
        self.event_id = event_id
        self.cleared: bool = False

    def __repr__(self) -> str:
        return f"MapNode({self.node_type} row={self.row} col={self.col})"


class GameMap:
    """Represents the full map for a single act.

    The map is a grid of nodes arranged in rows. Each row contains
    a few nodes the player can choose from. The player progresses
    from top (row 0) to bottom (last row = boss).
    """

    def __init__(self, act: int = 1) -> None:
        self.act = act
        self.rows: list[list[MapNode]] = []
        self.current_row: int = 0
        self.selected_col: int = 0

    def generate(self, act_data: dict, data_loader=None) -> None:
        """Generate the map from act data.

        Args:
            act_data: Dict with act configuration from acts.json.
            data_loader: DataLoader for creating enemies/events.
        """
        self.rows.clear()
        self.current_row = 0
        self.selected_col = 0

        num_nodes = act_data.get("nodes", 5)
        enemy_ids = act_data.get("enemies", [])
        event_ids = act_data.get("events", [])
        boss_id = act_data.get("boss", "")

        # Generate rows of nodes
        for row_idx in range(num_nodes):
            row_nodes: list[MapNode] = []

            # Each row has 2-3 nodes to choose from
            num_cols = random.randint(2, 3)

            for col_idx in range(num_cols):
                # Determine node type
                roll = random.random()
                if row_idx == num_nodes - 1:
                    # Boss node at the end
                    node = MapNode(
                        node_type="boss",
                        act=self.act,
                        row=row_idx,
                        col=col_idx,
                        enemy_id=boss_id,
                    )
                elif roll < 0.55:
                    # Battle node
                    enemy_id = random.choice(enemy_ids) if enemy_ids else ""
                    node = MapNode(
                        node_type="battle",
                        act=self.act,
                        row=row_idx,
                        col=col_idx,
                        enemy_id=enemy_id,
                    )
                elif roll < 0.80:
                    # Event node
                    event_id = random.choice(event_ids) if event_ids else ""
                    node = MapNode(
                        node_type="event",
                        act=self.act,
                        row=row_idx,
                        col=col_idx,
                        event_id=event_id,
                    )
                else:
                    # Bonfire node
                    node = MapNode(
                        node_type="bonfire",
                        act=self.act,
                        row=row_idx,
                        col=col_idx,
                        event_id="EV_FIRE_01",
                    )

                row_nodes.append(node)

            self.rows.append(row_nodes)

        # Mark first row as accessible
        if self.rows:
            for node in self.rows[0]:
                node.visited = False

    def current_row_nodes(self) -> list[MapNode]:
        """Get the nodes in the current row."""
        if self.current_row < len(self.rows):
            return self.rows[self.current_row]
        return []

    def select_node(self) -> MapNode | None:
        """Select and return the current node, advance to next row."""
        nodes = self.current_row_nodes()
        if not nodes:
            return None

        if self.selected_col >= len(nodes):
            self.selected_col = len(nodes) - 1

        node = nodes[self.selected_col]
        node.visited = True
        return node

    def move_selection(self, direction: int) -> None:
        """Move selection left (-1) or right (+1)."""
        nodes = self.current_row_nodes()
        if not nodes:
            return
        self.selected_col = (self.selected_col + direction) % len(nodes)

    def advance_row(self) -> bool:
        """Move to the next row. Returns False if map is complete."""
        self.current_row += 1
        self.selected_col = 0
        return self.current_row < len(self.rows)

    def is_complete(self) -> bool:
        """Check if all rows have been visited."""
        return self.current_row >= len(self.rows)

    def current_node(self) -> MapNode | None:
        """Get the currently selected node."""
        nodes = self.current_row_nodes()
        if not nodes:
            return None
        if self.selected_col >= len(nodes):
            self.selected_col = len(nodes) - 1
        return nodes[self.selected_col]


class MapController:
    """Manages the map generation and navigation for all acts."""

    def __init__(self, data_loader=None) -> None:
        self.data_loader = data_loader
        self.maps: dict[int, GameMap] = {}
        self.current_act: int = 1

    def generate_act_map(self, act: int) -> GameMap:
        """Generate the map for a given act."""
        act_data = self.data_loader.get_act_data(act) if self.data_loader else None
        game_map = GameMap(act=act)

        if act_data:
            game_map.generate(act_data, self.data_loader)
        else:
            # Fallback: create a simple map
            default_data = {"nodes": 5, "enemies": ["E001", "E002"],
                          "boss": "B001", "events": ["EV_FIRE_01"]}
            game_map.generate(default_data, self.data_loader)

        self.maps[act] = game_map
        return game_map

    def get_current_map(self) -> GameMap | None:
        """Get the map for the current act."""
        return self.maps.get(self.current_act)

    def advance_to_next_act(self) -> int | None:
        """Advance to the next act. Returns the new act number, or None if game is complete."""
        self.current_act += 1
        if self.current_act > 3:
            return None
        return self.current_act
