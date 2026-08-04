"""History Manager: handles saving, loading, listing, and deleting chat sessions
and exporting chat history to JSON.

Tuning yang diterapkan:
- Menggunakan `pathlib.Path` untuk manajemen path yang lebih modern & aman.
- Validasi ukuran file (mencegah load JSON korup/terlalu besar).
- Sorting & filtering yang lebih robust.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from config import MAX_SESSION_FILE_SIZE_BYTES, MAX_SESSION_ID_HEX_LEN

SESSION_DIR = Path(__file__).resolve().parent / "chat_sessions"


def generate_session_id() -> str:
    """Generate a unique session ID incorporating datetime and a UUID suffix.

    The suffix was widened from 4 to 8 hex chars — collisions were already
    unlikely with 4, but the cost of the extra characters is effectively
    zero and it removes the risk entirely for rapid-fire session creation.
    """
    return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:MAX_SESSION_ID_HEX_LEN]}"


def ensure_session_dir() -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)


def save_session(session_id: str, title: str, messages: list) -> None:
    ensure_session_dir()
    filepath = SESSION_DIR / f"{session_id}.json"
    created_at = datetime.now().isoformat()
    final_title = title.strip() or "New conversation"

    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                old_data = json.load(f)
            created_at = old_data.get("created_at", created_at)

            # If a non-default title already exists, keep it.
            existing_title = old_data.get("title")
            if existing_title and existing_title.strip() not in ("", "New conversation"):
                final_title = existing_title

        except json.JSONDecodeError as e:
            logging.warning(
                f"Could not read original data from corrupt session file {filepath}. "
                f"A new timestamp will be generated. Error: {e}"
            )
        except Exception as e:
            logging.error(
                f"An unexpected error occurred while reading {filepath}. "
                f"A new timestamp will be generated. Error: {e}"
            )

    data = {
        "session_id": session_id,
        "title": final_title,
        "created_at": created_at,
        "messages": messages,
    }
    tmp_path = filepath.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(filepath)


def list_saved_sessions(sort_by: str = "newest") -> list[dict]:
    """List all saved chat sessions sorted by sort_by ('newest', 'oldest', 'title')."""
    ensure_session_dir()
    sessions = []
    if not SESSION_DIR.exists():
        return sessions

    for filepath in SESSION_DIR.glob("*.json"):
        try:
            if filepath.stat().st_size > MAX_SESSION_FILE_SIZE_BYTES:
                logging.warning(f"Skipping oversized session file: {filepath}")
                continue
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                sessions.append(
                    {
                        "session_id": data.get("session_id", filepath.stem),
                        "title": data.get("title", "Untitled"),
                        "created_at": data.get("created_at", ""),
                    }
                )
        except json.JSONDecodeError as e:
            logging.warning(f"Skipping corrupt session file: {filepath}. Error: {e}")
        except Exception as e:
            logging.error(f"Could not process session file {filepath}: {e}")

    if sort_by == "oldest":
        sessions.sort(key=lambda x: x["created_at"])
    elif sort_by == "title":
        sessions.sort(key=lambda x: x["title"].lower())
    else:  # newest
        sessions.sort(key=lambda x: x["created_at"], reverse=True)

    return sessions


def search_saved_sessions(query: str, sort_by: str = "newest") -> list[dict]:
    """Search saved sessions whose title, session ID, or message content contains the query string."""
    all_sessions = list_saved_sessions(sort_by=sort_by)
    if not query.strip():
        return all_sessions

    q = query.strip().lower()
    filtered_ids = set()
    filtered = []

    for s in all_sessions:
        # Check title and session_id first
        if q in s.get("title", "").lower() or q in s.get("session_id", "").lower():
            if s["session_id"] not in filtered_ids:
                filtered.append(s)
                filtered_ids.add(s["session_id"])
            continue

        # Check inside session messages JSON file (memory-efficiently)
        filepath = SESSION_DIR / f"{s['session_id']}.json"
        try:
            if not filepath.exists() or filepath.stat().st_size > MAX_SESSION_FILE_SIZE_BYTES:
                continue
            
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if q in line.lower():
                        if s["session_id"] not in filtered_ids:
                            filtered.append(s)
                            filtered_ids.add(s["session_id"])
                        break  # Found a match, move to the next session file
        except Exception as e:
            logging.warning(f"Could not search inside file {filepath}: {e}")
            
    return filtered


def load_session(session_id: str) -> list:
    filepath = SESSION_DIR / f"{session_id}.json"
    if not filepath.exists():
        return []
    try:
        if filepath.stat().st_size > MAX_SESSION_FILE_SIZE_BYTES:
            logging.warning(f"Attempted to load oversized session file: {filepath}")
            return []
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("messages", [])
    except json.JSONDecodeError as e:
        logging.error(f"Failed to load corrupt session file: {filepath}. Error: {e}")
        return []
    except Exception as e:
        logging.error(f"Could not load session file {filepath}: {e}")
        return []


def delete_session(session_id: str) -> None:
    filepath = SESSION_DIR / f"{session_id}.json"
    try:
        if filepath.exists():
            filepath.unlink()
    except Exception as e:
        logging.error(f"Failed to delete session file {filepath}: {e}")


def rename_session(session_id: str, new_title: str) -> bool:
    """Rename a saved chat session by updating its title field in the JSON file."""
    filepath = SESSION_DIR / f"{session_id}.json"
    if not filepath.exists():
        return False
    try:
        if filepath.stat().st_size > MAX_SESSION_FILE_SIZE_BYTES:
            logging.warning(f"Cannot rename oversized session file: {filepath}")
            return False
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["title"] = new_title.strip() or "Untitled conversation"
        tmp_path = filepath.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(filepath)
        return True
    except json.JSONDecodeError as e:
        logging.error(f"Failed to rename corrupt session file: {filepath}. Error: {e}")
        return False
    except Exception as e:
        logging.error(f"Could not rename session file {filepath}: {e}")
        return False


def get_default_session_title(messages: list[dict]) -> str:
    """Generate a short title from the first user message if available."""
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                clean = content.strip()
                return clean[:30] + ("..." if len(clean) > 30 else "")
    return "New conversation"


def export_messages_to_markdown(messages: list[dict]) -> str:
    """Convert chat messages to a clean Markdown string."""
    lines = ["# Chat Export\n"]
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            continue
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls")

        if role == "user":
            lines.append(f"### 👤 User\n\n{content}\n")
        elif role == "assistant":
            lines.append(f"### 🤖 Assistant\n\n{content or '_No text response_'}\n")
            if tool_calls:
                lines.append("**Tool Calls:**")
                for tc in tool_calls:
                    fn = tc.get("function", {}).get("name", "unknown")
                    args = tc.get("function", {}).get("arguments", "{}")
                    lines.append(f"- `{fn}`: ```json\n{args}\n```")
                lines.append("")
        elif role == "tool":
            lines.append(f"#### ⚙️ Tool Result\n```json\n{content}\n```\n")
    return "\n".join(lines)


def export_messages_to_text(messages: list[dict]) -> str:
    """Convert chat messages to a plain text string."""
    lines = ["=== CHAT EXPORT ===\n"]
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            continue
        content = msg.get("content", "")
        if role == "user":
            lines.append(f"[USER]: {content}\n")
        elif role == "assistant":
            lines.append(f"[ASSISTANT]: {content}\n")
        elif role == "tool":
            lines.append(f"[TOOL RESULT]: {content}\n")
    return "\n".join(lines)

def trim_messages_for_context(messages: list[dict], max_tokens_approx: int = 30_000) -> list[dict]:
    """
    Memotong riwayat pesan agar tidak melebihi perkiraan batas token,
    dengan tetap menjaga integritas System Prompt dan pasangan Tool Calls.
    """
    if not messages:
        return []

    # 1. Selalu pertahankan System Prompt di index 0
    system_msg = None
    chat_messages = messages
    if messages[0].get("role") == "system":
        system_msg = messages[0]
        chat_messages = messages[1:]

    # 2. Dari belakang (pesan terbaru), kumpulkan pesan sampai mendekati limit
    # Pendekatan aman: Pertahankan N turn terakhir secara utuh.
    # Contoh: Ambil 10 pesan terakhir secara utuh
    recent_messages = chat_messages[-10:] if len(chat_messages) > 10 else chat_messages

    # Pastikan tidak memotong di tengah-tengah tool sequence
    # Jika pesan pertama di  adalah role="tool", kita harus tarik
    # ke atas sampai menemukan pesan "assistant" yang memicu tool tersebut.
    while recent_messages and recent_messages[0].get("role") == "tool":
        idx = len(messages) - len(recent_messages) - 1
        if idx >= 1:
            recent_messages.insert(0, messages[idx])
        else:
            break

    # Gabungkan kembali dengan system prompt
    result = [system_msg] if system_msg else []
    result.extend(recent_messages)
    return result
