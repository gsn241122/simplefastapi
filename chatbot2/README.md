# MCP Chatbot — rewrite notes

This is a restructured version of the app we reviewed. Drop the contents of
`chatbot/` in place of your existing files (same filenames, so it's a
straight swap), keep your own `mcp_servers.json` one level up, same as
before. Nothing about `mcp_servers.json`'s format or the MCP server
protocol has changed.

## New file: `security.py`

Everything security-related that used to be scattered as inline `if`
statements now lives in one auditable module:

- `redact_secrets(value)` — recursively masks dict values whose key looks
  sensitive (`authorization`, `password`, `token`, `api_key`, `secret`,
  `cookie`, ...). Used everywhere a tool's arguments/result get logged,
  displayed, saved to disk, or exported.
- `classify_tool_risk(name, args, keywords)` — the "does this need
  confirmation" logic, now whole-word matched instead of raw substring
  matched (`get_execution_report` no longer trips on `exec`).
- `is_retryable_exception(exc)` — used by `mcp_client.py` so retries only
  happen for transient failures (timeouts, connection resets), not for
  permanent ones (bad arguments, tool not found) where retrying just wastes
  time.

## Fixed: secrets leaking into logs / history / exports

This was the most important finding. Previously:

- The Safe Mode audit log stored raw tool arguments and results, including
  the injected `Authorization: Bearer <token>` header — and had an
  **Export JSON** button.
- The sidebar's chat history **Export** (Markdown/JSON/Text) dumped
  `st.session_state.messages` verbatim, which could include a real
  `access_token` if a login ever happened through the `call_api` tool
  mid-conversation instead of the dedicated login form.

Now: `tool_execution.run_tool_call` redacts secrets **once, at the source**
(`security.redact_secrets`), and that redacted copy is what flows into the
audit log, the message sent back to the LLM, the chat UI, the saved session
file on disk, and any export. See the docstring in `tool_execution.py` for
the one known limitation this doesn't cover (a user typing a raw password
directly into the chat box instead of the login form) — the sidebar login
form now has a caption calling this out explicitly.

Also fixed: the `Authorization` header injection used to be
`headers.setdefault(...)`, meaning a model-supplied `Authorization` header
would silently win over the app's real token. It's now always overwritten.

## Fixed: XSS surface in `chat_ui.py`

`st.markdown(..., unsafe_allow_html=True)` was used to render user input,
streamed LLM output, and (indirectly) tool-call arguments. `unsafe_allow_html`
was not needed for any of these — Streamlit's default markdown already
handles bold/italics/code/links — and it opened the door to raw
`<script>`/`<img onerror=...>` content coming back from an LLM or a tool
result being rendered as live HTML. Removed everywhere content isn't
Claude's/your own trusted static string.

## Fixed: single source of truth for defaults

`DEFAULT_TEMPERATURE` used to be independently declared in both
`config.py` and `state.py`. `state.py` now only imports from `config.py`.

## Changed: retry policy (`mcp_client.py`)

Retries are now gated by `security.is_retryable_exception` — timeouts and
connection errors get retried with backoff, everything else (bad args,
tool-not-found, auth failures) fails fast instead of retrying an identical
failure two more times.

## Changed: tool-result size sent to the LLM (`tool_execution.py`)

Previously the UI truncated long tool results for *display* but always sent
the full, untruncated result back to the model — a large file read or API
response could silently balloon token usage on every subsequent turn. Now
controlled by `config.TOOL_RESULT_LLM_TRUNCATE_CHARS` (default 20,000
chars; set to `None` to restore the old "always full" behavior). Display
truncation is unchanged and still separate.

## Changed: Safe Mode defaults (`config.py`)

- `DANGEROUS_HTTP_METHODS` now includes `POST` in addition to
  `DELETE`/`PUT`/`PATCH`. This is a genuine behavior change (more
  confirmation prompts) — POST is how most create/submit/pay actions
  happen, and the old default let all of those through unconfirmed.
  If this is too aggressive for your use case, remove `"POST"` from the
  set in `config.py`, one line.
- `DANGEROUS_NAME_KEYWORDS` expanded from 3 words to a broader list
  (`remove`, `drop`, `write`, `run`, `update`, `patch`, `send`, `pay`,
  `purge`, `truncate`), now matched as whole words via `security.py`
  instead of substrings.

## Changed: system prompt (`config.py`)

Removed the line telling the model to "proceed directly with the action"
without confirmation — Safe Mode confirmation is enforced by the app, not
the model, so that instruction only encouraged the model to move fast
without adding any actual safety. Kept the "don't ask the user for
credentials" instruction, since that one's still correct (credentials are
injected automatically).

## Cleanup

- `app.py`: removed the commented-out "Right Panel" block that ran
  `subprocess.run(["git", "status"], cwd="/home/dell/Desktop/...")` — a
  hardcoded path from someone's machine, and dead code either way.
  Removed the now-unused `subprocess` import.
- `history_manager.py`: session-file size limit and the random ID suffix
  length are now both `config.py` constants (10 MB and 8 hex chars,
  up from a hardcoded 50 MB and 4 hex chars) instead of being hardcoded
  inline.
- Mixed Indonesian/English UI strings unified to English for consistency.
  Happy to flip the whole UI to Indonesian instead if you'd prefer that —
  just say the word.

## Not changed

- `mcp_pool.py` — the persistent connection-pool design (background thread
  + its own event loop, one session per server reused across reruns) was
  already correct and is untouched.
- `mcp_servers.json` format / MCP protocol handling.
- Overall UI layout and flow (chat + sidebar), streaming logic, thinking
  tool router — these all worked and weren't part of what we identified as
  broken.

## Known limitations / things worth a follow-up pass

- Redaction is key-based (`is_sensitive_key`), not content-based — it won't
  catch a secret value sitting under an innocuously-named key. Good enough
  for the identified leak paths, not a guarantee against every leak.
- No allowlist yet for what hosts/paths `call_api` can hit — it's still
  bounded by whatever the MCP server's own base URL is configured to be,
  which is probably fine for a single trusted backend, but worth adding if
  you ever point this at a more general-purpose HTTP-calling MCP server.
- Assistant-generated tool-call *arguments* (as opposed to tool *results*)
  are redacted only for on-screen display, not before being sent to the
  LLM API itself — they have to reach the model as-is for tool execution to
  work; the risk here is specifically a user typing secrets into chat.

## Theming

The sidebar has an **Appearance** section with a theme selector. Four themes ship
out of the box:

- ☀️ **Light** — default clean/bright theme
- 🌙 **Dark** — easy on the eyes in low-light environments
- 🌊 **Ocean** — calming sea-blue palette
- ⚡ **Neon** — bold cyberpunk-inspired colors

The selected theme is persisted in `st.session_state.current_theme` for the
duration of the browser session. All color values are injected as CSS custom
properties (`:root { --primary: ...; --background: ...; }`), so a theme switch
takes effect on the very next Streamlit rerun without reloading the page.

### Adding a new theme

1. Create `chatbot2/themes/<name>.py` exporting a `THEME` dict with the same
   keys as `light.py` (plus optional `name`, `icon`, `description` for the
   selector).
2. Register it in `chatbot2/themes/theme_manager.py` by adding an import and an
   entry in the `THEMES` dict.

That's it — the selector picks it up automatically.
