from chatbot.sidebar import _build_saved_session_selection


def test_build_saved_session_selection_unique_labels() -> None:
    saved_sessions = [
        {
            "session_id": "session_1",
            "title": "Percakapan Seru",
            "created_at": "2026-07-31T14:13:16.123456",
        },
        {
            "session_id": "session_2",
            "title": "Percakapan Seru",
            "created_at": "2026-07-31T14:13:16.123456",
        },
    ]

    session_ids, session_labels = _build_saved_session_selection(saved_sessions)

    assert session_ids == ["session_1", "session_2"]
    assert session_labels["session_1"] != session_labels["session_2"]
    assert session_labels["session_2"].endswith("[session_2]")
