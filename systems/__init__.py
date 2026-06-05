# Systems package — ECS game systems
from systems.combat_system import CombatSystem
from systems.keyword_system import KeywordSystem
from systems.render_system import RenderSystem
from systems.input_system import InputSystem
from systems.status_system import StatusSystem
from systems.difficulty_system import (
    DifficultyManager, get_difficulty, set_difficulty,
    DEFAULT_ASCENSION, MAX_ASCENSION,
)
