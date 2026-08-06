# MCP Local Tools — Skill Bridge

Dokumentasi integrasi `skills/` sebagai local MCP tools.

## 🎯 Konsep

Setiap folder di `skills/<skill_name>/` otomatis terdeteksi sebagai **local tool** yang bisa dipanggil oleh LLM, **tanpa** perlu menjalankan external MCP server process.

## 📁 Struktur

```
telegrambot/
├── mcp_agent/
│   ├── local_tools.py        # LocalSkillServer class
│   ├── extended_registry.py  # load_registry_with_local()
│   └── dispatcher.py         # UnifiedTools (single facade)
├── skills/
│   ├── checkresources/
│   │   ├── check_resources.py   # script yang di-bridge
│   │   └── skill.md             # description untuk LLM
│   └── myotherskill/
│       ├── myotherskill.py
│       └── skill.md
└── mcp_server.json           # tambah blok "local_skills"
```

## ⚙️ Konfigurasi `mcp_server.json`

```json
{
  "local_skills": {
    "path": "skills",
    "timeout_sec": 30
  },
  "mcpServers": { ... }
}
```

| Field | Default | Keterangan |
|-------|---------|------------|
| `path` | `skills` | Folder tempat skill disimpan |
| `timeout_sec` | `30` | Batas waktu eksekusi per call |
| `python` | `sys.executable()` | Path interpreter |

## 🔍 Aturan Auto-Discovery

1. Scan folder `skills/*/` (alfabetis).
2. Cari script entry point dengan urutan prioritas:
   1. `skills/<name>/<name>.py`
   2. `skills/<name>/main.py`
   3. `skills/<name>/run.py`
   4. `skills/<name>/*.py` (file pertama)
3. Baca deskripsi dari `skill.md` (paragraf pertama setelah judul).
4. Nama tool = slugify nama folder (lowercase, snake_case).

## 🛠️ Cara Pakai di Handler

Lihat implementasi lengkap di `bot/handlers/message.py` saat diintegrasikan. Contoh:

```python
from mcp_agent.dispatcher import UnifiedTools

# Di main.py / startup
registry, local_server = load_registry_with_local("mcp_server.json")
async with mcp_lifecycle(registry) as mcp_client:
    tools = UnifiedTools(mcp_client, local_server)

    # List semua tool (remote + local)
    all_tools = await tools.list_all()

    # Panggil tool — auto-route ke remote atau local
    result = await tools.call("checkresources", {})
```

## 📤 Output Format

Skill harus **print JSON valid** ke stdout. Contoh:

```python
import json, sys
print(json.dumps({"cpu": "85%", "ram": "60%"}))
```

Exit code `0` = sukses. Exit code lain = error (stderr akan diteruskan ke LLM).

## 🆕 Menambah Skill Baru

Cukup buat folder baru:

```bash
mkdir -p skills/myskill
cat > skills/myskill/myskill.py <<'EOF'
import json
print(json.dumps({"hello": "world"}))
EOF
```

Restart bot — skill otomatis terdeteksi! 🎉

## ⚠️ Limitasi

- Skill berjalan sebagai **subprocess** (overhead ~50-100ms per call).
- Tidak ada state antar-call (stateless).
- Output harus JSON-serializable.
- Tidak ada streaming (return final result).