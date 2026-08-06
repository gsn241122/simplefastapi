from enum import Enum
from bot.handlers.start import start_cmd, help_cmd, tools_cmd, status_cmd
from bot.handlers.auth import login2_cmd, logout_cmd, whoami_cmd
from bot.handlers.message import history_cmd, new_session_cmd, reset_cmd
from bot.handlers.model import model_cmd

class BotCommand(Enum):
    # Format: (command, description, handler_function)
    START = ("start", "Memulai bot dan menampilkan menu utama", start_cmd)
    HELP = ("help", "Menampilkan panduan bantuan", help_cmd)
    LOGIN = ("login", "Login ke sistem (input teks interaktif)", None) # Handled by ConvHandler
    LOGIN2 = ("login2", "Login via Telegram Mini App (WebApp)", login2_cmd)
    WHOAMI = ("whoami", "Cek status login & token pengguna", whoami_cmd)
    LOGOUT = ("logout", "Logout dari sistem", logout_cmd)
    MODEL = ("model", "Pilih model AI (Gemini/MiniMax/Ollama)", model_cmd)
    RESET = ("reset", "Reset riwayat percakapan AI", reset_cmd)
    HISTORY = ("history", "Lihat sesi & riwayat aktif", history_cmd)
    NEWSESSION = ("newsession", "Mulai sesi percakapan baru", new_session_cmd)
    CANCEL = ("cancel", "Membatalkan operasi yang sedang berjalan", None)
    TOOLS = ("tools", "Menampilkan daftar tools MCP yang aktif", tools_cmd)
    STATUS = ("status", "Cek status sistem dan resource", status_cmd)
