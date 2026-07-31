"""History Manager: handles saving, loading, listing, and deleting chat sessions
and exporting chat history to JSON.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime

SESSION_DIR = os.path.join(os.path.dirname(__file__), "chat_sessions")


def generate_session_id() -> str:
    """Generate a unique session ID incorporating datetime and a short UUID suffix."""
    return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"


def ensure_session_dir() -> None:
    os.makedirs(SESSION_DIR, exist_ok=True)


def save_session(session_id: str, title: str, messages: list) -> None:
    ensure_session_dir()
    filepath = os.path.join(SESSION_DIR, f"{session_id}.json")
    created_at = datetime.now().isoformat()
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                created_at = old_data.get("created_at", created_at)
        except Exception:
            pass
    data = {
        "session_id": session_id,
        "title": title or "Percakapan Baru",
        "created_at": created_at,
        "messages": messages,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_saved_sessions() -> list[dict]:
    ensure_session_dir()
    sessions = []
    for filename in os.listdir(SESSION_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(SESSION_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append(
                        {
                            "session_id": data.get("session_id", filename[:-5]),
                            "title": data.get("title", "Tanpa Judul"),
                            "created_at": data.get("created_at", ""),
                        }
                    )
            except Exception:
                pass
    # Sort by creation time descending (newest first)
    sessions.sort(key=lambda x: x["created_at"], reverse=True)
    return sessions


def load_session(session_id: str) -> list:
    filepath = os.path.join(SESSION_DIR, f"{session_id}.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("messages", [])
        except Exception:
            pass
    return []


def delete_session(session_id: str) -> None:
    filepath = os.path.join(SESSION_DIR, f"{session_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)


def get_default_session_title(messages: list) -> str:
    """Generate a short title from the first user message if available."""
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()[:30] + ("..." if len(content.strip()) > 30 else "")
    return "Percakapan Baru"
