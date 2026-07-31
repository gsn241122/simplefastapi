# FastAPI MCP Chatbot

Streamlit chatbot backed by Gemini (via the OpenAI-compatible endpoint) that
can call tools exposed by multiple MCP servers.

## Run

```bash
streamlit run app.py
```

## Project layout

The original single-file `app.py` has been split into focused modules:

| File               | Responsibility                                                                 |
|--------------------|----------------------------------------------------------------------------------|
| `app.py`           | Entry point — wires everything together, no business logic of its own.        |
| `config.py`        | Constants: model list, Safe Mode rules, system prompt, etc.                    |
| `state.py`         | `session_state` initialization.                                               |
| `mcp_client.py`    | Low-level MCP connectivity (stdio + HTTP/SSE servers).                        |
| `tool_execution.py`| Parses tool-call arguments, decides what's "dangerous", runs tool calls.      |
| `sidebar.py`       | Sidebar UI: model settings, MCP server status, login form, Safe Mode toggle.  |
| `chat_ui.py`       | Chat history, the Safe Mode confirmation prompt, and the LLM/tool-call loop.  |

Behavior is unchanged from the original `app.py` — this is a structural
cleanup only (module split, English-only comments/UI text, consistent
docstrings and type hints).

## Configuration

- `mcp_servers.json` — MCP server definitions. Note that the `filesystem`
  and `git` entries currently point at an absolute local path
  (`/home/dell/Desktop/workspace/simplefastapi/`) — update this to your own
  machine's path, or better, load it from an environment variable if you
  plan to share this config across machines.
- `GEMINI_API_KEY`, `API_BEARER_TOKEN`, `LOGIN_PATH` — optional environment
  variables (e.g. via a `.env` file) that pre-fill the sidebar fields.