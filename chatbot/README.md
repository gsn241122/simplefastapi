# FastAPI MCP Chatbot

Streamlit chatbot backed by Gemini (via the OpenAI-compatible endpoint) that
can call tools exposed by multiple MCP servers.

## Run

```bash
streamlit run app.py
```

## Project layout

| File               | Responsibility                                                                    |
|---------------------|------------------------------------------------------------------------------------|
| `app.py`            | Entry point — wires everything together, no business logic of its own.           |
| `config.py`         | Constants: model list, tunable defaults, Safe Mode rules, system prompt.         |
| `state.py`          | `session_state` initialization.                                                  |
| `mcp_pool.py`        | Persistent connection pool: opens each MCP server once, reused across calls.     |
| `mcp_client.py`      | Public MCP API — config loading, tool-schema/result normalization, uses the pool.|
| `tool_execution.py`  | Parses tool-call arguments, decides what's "dangerous", runs tool calls.         |
| `sidebar.py`         | Sidebar UI: model settings, advanced tuning, MCP status, login, Safe Mode.       |
| `chat_ui.py`         | Chat history, the Safe Mode confirmation prompt, and the LLM/tool-call loop.     |

## Performance: the connection pool

`mcp_pool.py` runs one background thread with its own event loop and keeps a
single, persistent session open per MCP server (stdio subprocess or HTTP
client), for the lifetime of the app process:

- **Parallel connect** — on startup / refresh, all configured servers are
  connected to concurrently (`asyncio.gather`) instead of one at a time.
- **Connection reuse** — every tool call reuses the already-open session
  instead of spawning a fresh subprocess / opening a fresh HTTP client each
  time.
- **Timeouts** — both connecting and calling a tool are bounded, so one
  slow/hung server can't freeze the whole app. Configurable from the
  sidebar.
- **Auto-recovery** — if a call fails, that server's connection is dropped
  so the next attempt reconnects cleanly instead of repeatedly hitting a
  dead session.

## Advanced tuning (sidebar)

The "🎛️ Advanced tuning" panel exposes:

- **Temperature** — passed to `chat.completions.create`.
- **Max output tokens** — optional cap on generated tokens.
- **Max tool-call rounds** — how many tool-call round-trips the assistant
  may make in a single turn before giving up.
- **MCP connect / tool-call timeouts** — see above.
- **Safe Mode keywords** — comma-separated list of substrings; any tool
  name containing one requires explicit confirmation when Safe Mode is on
  (in addition to `call_api` DELETE/PUT/PATCH, which is always gated).

## Configuration

- `mcp_servers.json` — MCP server definitions. Note that the `filesystem`
  and `git` entries currently point at an absolute local path
  (`/home/dell/Desktop/workspace/simplefastapi/`) — update this to your own
  machine's path, or load it from an environment variable if you plan to
  share this config across machines.
- `GEMINI_API_KEY`, `API_BEARER_TOKEN`, `LOGIN_PATH` — optional environment
  variables (e.g. via a `.env` file) that pre-fill the sidebar fields.