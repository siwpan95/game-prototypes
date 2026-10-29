"""Card dataclass representing a game card."""


class Card:
    """Represents a single card in the game.

    Attributes:
        id: Unique card identifier (e.g., 'C001').
        name: Display name of the card.
        cost: Focus Point (FP) cost to play the card.
        type: Card type - 'Attack', 'Skill', or 'Power'.
        damage: Dice notation for damage (e.g., '2d6+STR') or '0'.
        block: Block value granted by this card.
        keywords: Dict of keyword effects and their values.
        description: Flavor / functional description.
        source: Origin of the card (e.g., 'Player', 'LothricKnight').
    """

    def __init__(
        self,
        id: str = "",
        name: str = "",
        cost: int = 0,
        type: str = "Attack",
        damage: str = "0",
        block: int = 0,
        keywords: dict | None = None,
        description: str = "",
        source: str = "Player",
    ) -> None:
        self.id = id
        self.name = name
        self.cost = cost
        self.type = type
        self.damage = damage
        self.block = block
        self.keywords = keywords if keywords is not None else {}
        self.description = description
        self.source = source

    def __repr__(self) -> str:
        return f"Card({self.id}: {self.name})"

    def is_attack(self) -> bool:
        """Return True if this card is an Attack type."""
        return self.type == "Attack"

    def is_skill(self) -> bool:
        """Return True if this card is a Skill type."""
        return self.type == "Skill"

    def has_keyword(self, keyword: str) -> bool:
        """Check if this card has a specific keyword."""
        return keyword in self.keywords
