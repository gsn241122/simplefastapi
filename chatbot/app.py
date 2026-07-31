"""
Streamlit chatbot that talks to Gemini (through the OpenAI-compatible endpoint)
and can call tools exposed by the MCP server in server.py (health_check,
list_routes, call_api) to interact with the wrapped FastAPI app.
Run:
1. Start the MCP server:      python server.py
2. Start this chatbot:        streamlit run app.py
"""
from __future__ import annotations
import asyncio
import json
import os
import streamlit as st
from openai import OpenAI
from mcp_client import call_mcp_tool, fetch_mcp_tools

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

AVAILABLE_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]
DEFAULT_MODEL = "gemini-3.5-flash-lite"
MAX_TOOL_ROUNDS = 5

st.set_page_config(page_title="FastAPI MCP Chatbot (Gemini)", page_icon="🤖")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input(
        "Gemini API key",
        value=os.getenv("GEMINI_API_KEY", ""),
        type="password",
        help="Get one at https://aistudio.google.com/apikey",
    )

    model = st.selectbox(
        "Gemini model",
        options=AVAILABLE_MODELS,
        index=AVAILABLE_MODELS.index(DEFAULT_MODEL),
    )
    custom_model = st.text_input("...or use a custom model id", value="")
    if custom_model.strip():
        model = custom_model.strip()

    st.divider()

    mcp_url = st.text_input(
        "MCP server URL",
        value=os.getenv("MCP_URL", "http://localhost:8003/mcp"),
        help="URL of the running server.py MCP wrapper",
    )

    st.divider()

    # -----------------------------------------------------------------------
    # 🔐 LOGIN SECTION (via MCP call_api)
    # -----------------------------------------------------------------------
    st.subheader("🔐 Autentikasi API")

    if "api_bearer_token" not in st.session_state:
        st.session_state.api_bearer_token = os.getenv("API_BEARER_TOKEN", "")

    login_path = st.text_input(
        "Login Endpoint Path",
        value=os.getenv("LOGIN_PATH", "/auth/login"),
        help="Path endpoint login. Contoh: /auth/login, /token",
    )

    with st.form("login_form"):
        login_username = st.text_input("Username")
        login_password = st.text_input("Password", type="password")
        submit_login = st.form_submit_button("🔑 Login via MCP")

        if submit_login:
            if not login_username or not login_password:
                st.error("Username dan password wajib diisi!")
            else:
                try:
                    login_args = {
                        "method": "POST",
                        "path": login_path,
                        "data": {
                            "username": login_username,
                            "password": login_password,
                        },
                    }

                    with st.spinner("Melakukan login via MCP server..."):
                        result = asyncio.run(
                            call_mcp_tool(mcp_url, "call_api", login_args)
                        )

                    body = result.get("body")
                    if isinstance(body, str):
                        try:
                            body = json.loads(body)
                        except json.JSONDecodeError:
                            pass

                    if (
                        isinstance(body, dict)
                        and body.get("success")
                        and isinstance(body.get("data"), dict)
                    ):
                        token = body["data"].get("access_token")
                        if token:
                            st.session_state.api_bearer_token = token
                            st.success("✅ Login berhasil! Token telah disimpan.")
                        else:
                            st.error("❌ Login berhasil tetapi access_token tidak ditemukan.")
                    else:
                        error_msg = "Unknown error"
                        if isinstance(body, dict):
                            error_msg = (
                                body.get("message")
                                or body.get("detail")
                                or body.get("error")
                                or str(body)
                            )
                        elif isinstance(body, str):
                            error_msg = body[:300]

                        status_code = result.get("status_code") or result.get("status", "?")
                        st.error(f"❌ Login gagal (Status: {status_code}).")
                        st.caption(f"Detail: {error_msg}")

                except Exception as e:
                    st.error(f"❌ Error saat memanggil MCP tool: {e}")

    st.divider()

    # Bearer token (terikat ke session_state via key)
    api_bearer_token = st.text_input(
        "Bearer token untuk API target",
        key="api_bearer_token",
        type="password",
        help=(
            "Token ini otomatis ditambahkan sebagai header "
            "'Authorization: Bearer <token>' setiap kali tool `call_api` "
            "dipanggil. Terisi otomatis setelah Login berhasil."
        ),
    )

    st.divider()

    # -----------------------------------------------------------------------
    # 🛡️ SAFE MODE CONFIGURATION
    # -----------------------------------------------------------------------
    safe_mode = st.checkbox(
        "🛡️ Safe Mode (Konfirmasi aksi berbahaya)",
        value=True,
        help="Meminta konfirmasi eksplisit sebelum menjalankan method DELETE, PUT, PATCH, atau tool yang mengandung kata 'delete'.",
    )

    st.divider()

    if st.button("🔄 Refresh MCP tools"):
        st.session_state.pop("mcp_tools", None)

    if "mcp_tools" not in st.session_state:
        try:
            st.session_state.mcp_tools = asyncio.run(fetch_mcp_tools(mcp_url))
            st.session_state.mcp_error = None
        except Exception as exc:
            st.session_state.mcp_tools = []
            st.session_state.mcp_error = str(exc)

    if st.session_state.get("mcp_error"):
        st.error(f"Could not reach MCP server:\n{st.session_state.mcp_error}")
    else:
        st.success(f"Connected — {len(st.session_state.mcp_tools)} tool(s) available")
        for t in st.session_state.mcp_tools:
            st.caption(f"• {t['function']['name']}")

    st.divider()
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.session_state.pop("pending_tool_call", None)
        st.session_state.pop("pending_args", None)
        st.session_state.pop("resume_llm", None)
        st.rerun()

# ---------------------------------------------------------------------------
# Chat state initialization
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_tool_call" not in st.session_state:
    st.session_state.pending_tool_call = None

if "pending_args" not in st.session_state:
    st.session_state.pending_args = None

if "resume_llm" not in st.session_state:
    st.session_state.resume_llm = False

if not st.session_state.messages:
    st.session_state.messages.append(
        {
            "role": "system",
            "content": (
                "Kamu adalah asisten yang bisa memanggil API lewat tool `call_api`, "
                "`list_routes`, dan `health_check`. Autentikasi (Bearer token) untuk "
                "`call_api` sudah ditangani otomatis oleh sistem — jangan tanyakan "
                "token/kredensial ke user, langsung panggil `call_api` dengan method "
                "dan path yang sesuai. Jika endpoint tetap mengembalikan error 401/403, "
                "baru sampaikan ke user bahwa token yang dikonfigurasi tidak valid atau "
                "belum diisi di sidebar."
            ),
        }
    )

# ---------------------------------------------------------------------------
# ⬇️ HELPER FUNCTIONS — DIPINDAH KE ATAS SEBELUM DIPANGGIL
# ---------------------------------------------------------------------------
def get_thought_signature(tool_call) -> dict | None:
    """Pull the `extra_content.google.thought_signature` field Gemini attaches
    to function-call parts. Gemini 3.x models REQUIRE this to be echoed back
    on the next request or tool calling breaks with a 400 error."""
    extra = getattr(tool_call, "extra_content", None)
    if extra is None:
        model_extra = getattr(tool_call, "model_extra", None) or {}
        extra = model_extra.get("extra_content")
    return extra


def run_tool_call(tool_call) -> dict:
    """Execute one OpenAI-style tool_call against the MCP server."""
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments or "{}")
    except json.JSONDecodeError:
        args = {}

    # Auto-inject Bearer token
    if name == "call_api" and api_bearer_token:
        headers = dict(args.get("headers") or {})
        headers.setdefault("Authorization", f"Bearer {api_bearer_token}")
        args["headers"] = headers

    try:
        result = asyncio.run(call_mcp_tool(mcp_url, name, args))
    except Exception as exc:
        result = {"error": str(exc)}

    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": json.dumps(result, default=str),
    }


# ---------------------------------------------------------------------------
# Render chat history
# ---------------------------------------------------------------------------
st.title("🤖 FastAPI MCP Chatbot")
st.caption(f"Model: `{model}` · MCP: `{mcp_url}`")

for msg in st.session_state.messages:
    if msg["role"] in ("user", "assistant") and msg.get("content"):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# 🛡️ HANDLE PENDING DANGEROUS ACTION UI
# ---------------------------------------------------------------------------
if st.session_state.get("pending_tool_call"):
    st.warning("⚠️ **Aksi Berbahaya Terdeteksi (Safe Mode Aktif)**")
    tc = st.session_state.pending_tool_call
    args = st.session_state.pending_args

    st.markdown(
        f"**Tool:** `{tc.function.name}`  \n"
        f"**Method:** `{args.get('method', 'N/A')}`  \n"
        f"**Path:** `{args.get('path', 'N/A')}`"
    )

    with st.expander("🔍 Lihat Detail Payload"):
        st.json(args)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Ya, Eksekusi", type="primary", key="btn_confirm_exec"):
            # ✅ SEKARANG run_tool_call SUDAH TERDEFINISI
            result = run_tool_call(tc)
            st.session_state.messages.append(result)

            st.session_state.pending_tool_call = None
            st.session_state.pending_args = None
            st.session_state.resume_llm = True
            st.rerun()

    with col2:
        if st.button("❌ Batal", key="btn_confirm_cancel"):
            cancel_result = {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(
                    {"error": "Aksi dibatalkan oleh pengguna karena Safe Mode aktif."}
                ),
            }
            st.session_state.messages.append(cancel_result)

            st.session_state.pending_tool_call = None
            st.session_state.pending_args = None
            st.session_state.resume_llm = True
            st.rerun()

    st.stop()

# ---------------------------------------------------------------------------
# Chat input / LLM loop
# ---------------------------------------------------------------------------
user_input = st.chat_input("Ask something about the API (e.g. 'is the service healthy?')")

if user_input or st.session_state.resume_llm:

    if st.session_state.resume_llm:
        st.session_state.resume_llm = False
        messages_to_send = st.session_state.messages
    else:
        st.session_state.messages.append({"role": "user", "content": user_input})
        messages_to_send = st.session_state.messages
        with st.chat_message("user"):
            st.markdown(user_input)

    if not api_key:
        st.error("Please enter your Gemini API key in the sidebar.")
        st.stop()

    client = OpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)
    tools = st.session_state.get("mcp_tools") or None

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("_thinking..._")

        for _ in range(MAX_TOOL_ROUNDS):
            response = client.chat.completions.create(
                model=model,
                messages=messages_to_send,
                tools=tools,
                tool_choice="auto" if tools else None,
            )
            choice = response.choices[0].message

            assistant_msg = {"role": "assistant", "content": choice.content or ""}
            if choice.tool_calls:
                tool_call_dicts = []
                for tc in choice.tool_calls:
                    tc_dict = {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    thought_sig = get_thought_signature(tc)
                    if thought_sig:
                        tc_dict["extra_content"] = thought_sig
                    tool_call_dicts.append(tc_dict)
                assistant_msg["tool_calls"] = tool_call_dicts

            # -------------------------------------------------------------------
            # 🛡️ CEK AKSI BERBAHAYA SEBELUM EKSEKUSI
            # -------------------------------------------------------------------
            halted = False
            if choice.tool_calls:
                for tc in choice.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}

                    is_dangerous = safe_mode and (
                        (
                            tc.function.name == "call_api"
                            and args.get("method", "").upper() in ["DELETE", "PUT", "PATCH"]
                        )
                        or "delete" in tc.function.name.lower()
                    )

                    if is_dangerous:
                        st.session_state.pending_tool_call = tc
                        st.session_state.pending_args = args
                        st.session_state.messages.append(assistant_msg)
                        halted = True
                        break

                if halted:
                    st.rerun()

            st.session_state.messages.append(assistant_msg)

            if not choice.tool_calls:
                placeholder.markdown(choice.content or "")
                break

            placeholder.markdown(
                "_calling tool(s): "
                + ", ".join(tc.function.name for tc in choice.tool_calls)
                + "..._"
            )

            for tc in choice.tool_calls:
                st.session_state.messages.append(run_tool_call(tc))
        else:
            placeholder.markdown(
                "_Stopped after multiple tool calls without a final answer._"
            )