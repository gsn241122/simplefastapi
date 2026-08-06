"""Per-chat ephemeral state (sliding window context).

Stored in-memory keyed by chat_id. Replace with a persistent store if you
need durability beyond a single bot process.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque


@dataclass
class ChatState:
    history: Deque[dict[str, str]] = field(default_factory=deque)
    last_seen_message_id: int | None = None


class StateStore:
    def __init__(self, max_turns: int) -> None:
        self._max_turns = max_turns
        self._states: dict[int, ChatState] = defaultdict(ChatState)

    def get(self, chat_id: int) -> ChatState:
        return self._states[chat_id]

    def append_turn(self, chat_id: int, user_msg: str, assistant_msg: str) -> None:
        state = self._states[chat_id]
        state.history.append({"role": "user", "content": user_msg})
        state.history.append({"role": "assistant", "content": assistant_msg})
        while len(state.history) > self._max_turns * 2:
            state.history.popleft()

    def reset(self, chat_id: int) -> None:
        self._states[chat_id] = ChatState()

    def is_duplicate(self, chat_id: int, message_id: int, ttl: int = 5) -> bool:
        """Return True if this message_id is a replay within the last `ttl` IDs."""
        state = self._states[chat_id]
        if state.last_seen_message_id == message_id:
            return True
        state.last_seen_message_id = message_id
        return False
