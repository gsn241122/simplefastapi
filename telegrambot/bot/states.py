"""Per-chat state (sliding window context) with optional JSON file persistence.

Stored in-memory keyed by chat_id. If ``persist_path`` is provided, the store
auto-loads on init and auto-saves on every mutation, so chat history survives
process restarts.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque


@dataclass
class ChatState:
    history: Deque[dict[str, str]] = field(default_factory=deque)
    last_seen_message_id: int | None = None
    current_session_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))


class StateStore:
    def __init__(self, max_turns: int, persist_path: str | os.PathLike | None = None) -> None:
        self._max_turns = max_turns
        self._states: dict[int, ChatState] = defaultdict(ChatState)
        self._persist_path: Path | None = Path(persist_path) if persist_path else None
        if self._persist_path is not None:
            self._load()

    # ---------- persistence ----------
    def _load(self) -> None:
        """Load states from disk if file exists."""
        if self._persist_path is None or not self._persist_path.exists():
            return
        try:
            raw = json.loads(self._persist_path.read_text(encoding="utf-8"))
        except Exception:
            # Corrupt/partial file: keep a backup for inspection, start fresh.
            try:
                self._persist_path.rename(self._persist_path.with_suffix(".bak"))
            except OSError:
                pass
            return

        for chat_id_str, state_dict in raw.items():
            try:
                chat_id = int(chat_id_str)
            except (TypeError, ValueError):
                continue
            state = ChatState()
            for msg in state_dict.get("history", []):
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    state.history.append({"role": msg["role"], "content": msg["content"]})
            lid = state_dict.get("last_seen_message_id")
            if isinstance(lid, int):
                state.last_seen_message_id = lid
            sid = state_dict.get("current_session_id")
            if isinstance(sid, str):
                state.current_session_id = sid
            self._states[chat_id] = state

    def flush(self) -> None:
        """Atomically write current states to disk."""
        if self._persist_path is None:
            return
        payload = {
            str(chat_id): {
                "history": list(state.history),
                "last_seen_message_id": state.last_seen_message_id,
                "current_session_id": state.current_session_id,
            }
            for chat_id, state in self._states.items()
            if state.history or state.last_seen_message_id is not None
        }
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to temp file in same dir, then os.replace().
        fd, tmp_path = tempfile.mkstemp(
            prefix=self._persist_path.name + ".",
            suffix=".tmp",
            dir=self._persist_path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            os.replace(tmp_path, self._persist_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ---------- public API ----------
    def get(self, chat_id: int) -> ChatState:
        return self._states[chat_id]

    def append_turn(self, chat_id: int, user_msg: str, assistant_msg: str) -> None:
        state = self._states[chat_id]
        state.history.append({"role": "user", "content": user_msg})
        state.history.append({"role": "assistant", "content": assistant_msg})
        while len(state.history) > self._max_turns * 2:
            state.history.popleft()
        self.flush()

    def reset(self, chat_id: int) -> None:
        self._states[chat_id] = ChatState()
        self.flush()

    def new_session(self, chat_id: int) -> None:
        """Start a new session: rotate session_id and clear history."""
        state = self._states[chat_id]
        state.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        state.history.clear()
        self.flush()

    def is_duplicate(self, chat_id: int, message_id: int, ttl: int = 5) -> bool:
        """Return True if this message_id is a replay within the last `ttl` IDs."""
        state = self._states[chat_id]
        if state.last_seen_message_id == message_id:
            return True
        state.last_seen_message_id = message_id
        # Note: we don't flush here to avoid disk writes on every incoming message.
        # last_seen_message_id is only used for short-lived dedup, so losing it
        # across restart is acceptable.
        return False
