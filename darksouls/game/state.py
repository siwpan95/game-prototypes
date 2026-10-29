"""State base class and GameStateMachine for managing game screens."""


class State:
    """Abstract base class for game states (screens)."""

    def __init__(self) -> None:
        self.game = None

    def on_enter(self, **kwargs) -> None:
        """Called when this state becomes the active state."""
        pass

    def on_exit(self) -> None:
        """Called when this state is replaced by another state."""
        pass

    def handle_event(self, event) -> None:
        """Handle a pygame event."""
        pass

    def update(self, dt: float) -> None:
        """Update logic for this state. dt is in seconds."""
        pass

    def render(self, surface) -> None:
        """Render this state to the given surface."""
        pass


class GameStateMachine:
    """Manages a stack of game states with push/pop/replace operations."""

    def __init__(self) -> None:
        self._states: list[State] = []

    @property
    def current(self) -> State | None:
        """Return the current (top) state, or None if empty."""
        if self._states:
            return self._states[-1]
        return None

    def push(self, state: State, **kwargs) -> None:
        """Push a new state on top of the stack."""
        if self._states:
            self._states[-1].on_exit()
        self._states.append(state)
        state.on_enter(**kwargs)

    def pop(self) -> State | None:
        """Pop the current state off the stack."""
        if not self._states:
            return None
        state = self._states.pop()
        state.on_exit()
        if self._states:
            self._states[-1].on_enter()
        return state

    def replace(self, state: State, **kwargs) -> None:
        """Replace the current state with a new one."""
        if self._states:
            self._states[-1].on_exit()
            self._states.pop()
        self._states.append(state)
        state.on_enter(**kwargs)

    def clear(self) -> None:
        """Remove all states."""
        while self._states:
            self._states.pop().on_exit()

    def handle_event(self, event) -> None:
        """Forward event to current state."""
        if self._states:
            self._states[-1].handle_event(event)

    def update(self, dt: float) -> None:
        """Update current state."""
        if self._states:
            self._states[-1].update(dt)

    def render(self, surface) -> None:
        """Render current state."""
        if self._states:
            self._states[-1].render(surface)
