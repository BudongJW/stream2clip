"""Linear undo/redo history of immutable states."""

from __future__ import annotations

from typing import Generic, TypeVar

__all__ = ["History"]

T = TypeVar("T")


class History(Generic[T]):
    def __init__(self, initial: T, *, limit: int = 200) -> None:
        self._states: list[T] = [initial]
        self._index = 0
        self._limit = max(2, limit)

    @property
    def current(self) -> T:
        return self._states[self._index]

    @property
    def can_undo(self) -> bool:
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        return self._index < len(self._states) - 1

    def push(self, state: T) -> T:
        if state is self.current or state == self.current:
            return self.current
        del self._states[self._index + 1 :]
        self._states.append(state)
        if len(self._states) > self._limit:
            del self._states[0]
        self._index = len(self._states) - 1
        return state

    def undo(self) -> T:
        if self.can_undo:
            self._index -= 1
        return self.current

    def redo(self) -> T:
        if self.can_redo:
            self._index += 1
        return self.current

    def __len__(self) -> int:
        return len(self._states)
