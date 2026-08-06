# 🖥️ Skill: checkresources

## Deskripsi
Skill ini digunakan untuk menampilkan **informasi sumber daya komputer** (resource monitoring) secara real-time, meliputi:
- 🖥️ Informasi sistem (OS, kernel, hostname, uptime, load average)
- 🧠 CPU (model, core/thread, frequency, usage, temperature)
- 💾 Memory / RAM (total, used, available, swap)
- 💿 Disk (filesystem, total, used, free, device, fstype)
- 🎮 GPU (jenis kartu grafis via `lspci`)
- 🌐 Network interfaces (IP, speed, MTU, traffic)
- 🔋 Baterai laptop (jika ada)
- 🔥 Top processes (by CPU & RAM)
- ⚠️ Health warnings (auto-detect jika ada masalah)

## Tujuan
- Monitoring kesehatan sistem komputer
- Deteksi dini jika resource hampir habis (disk full, RAM tinggi, dll)
- Digunakan oleh AI Assistant untuk menjawab perintah user seperti "tampilkan resource komputer"

## Cara Pakai

### 1. Instalasi Dependency
Pastikan dependency `psutil` sudah terinstall:
```bash
pip install psutil
```

### 2. Jalankan Script
```bash
# Dari direktori skill
cd skills/checkresources
python checkresources.py

# Dari mana saja (absolute path)
python skills/checkresources/checkresources.py

# Simpan output ke file
python checkresources.py > resources.json
```

### 3. Output
Script akan print JSON terstruktur ke stdout. AI Assistant akan memformat ulang menjadi pesan yang mudah dibaca user.

## Dependency
- Python 3.8+
- `psutil` untuk monitoring CPU, RAM, Disk, Network, dan proses
- `platform`, `socket`, `time`, `subprocess` (built-in Python)

## Struktur Output JSON

```json
{
  "generated_at": "2026-05-14T10:30:00+00:00",
  "system": {
    "os": "Linux 6.17.0-41-generic",
    "kernel": "...",
    "hostname": "dell",
    "architecture": "x86_64",
    "python": "3.12.3",
    "boot_time_utc": "...",
    "uptime_seconds": 3000,
    "users": {
      "count": 1,
      "names": ["root"],
      "method": "gui_session"
    },
    "load_average": [1.17, 1.57, 1.53]
  },
  "cpu": {
    "model": "Intel® Core™ i5-3320M @ 2.60GHz",
    "physical_cores": 2,
    "logical_cores": 4,
    "current_mhz": 2378.0,
    "min_mhz": 1200.0,
    "max_mhz": 3300.0,
    "usage_percent": 12.5,
    "load_avg": [1.17, 1.57, 1.53],
    "temperature": {
      "label": "Core 0",
      "chip": "coretemp",
      "temp_c": 52.0,
      "high_c": 80.0,
      "critical_c": 100.0
    }
  },
  "memory": {
    "ram": {
      "total_gb": 15.52,
      "used_gb": 5.92,
      "free_gb": 9.61,
      "percent": 38.1
    },
    "swap": {
      "total_gb": 8.76,
      "used_gb": 0.0,
      "free_gb": 8.76,
      "percent": 0.0
    }
  },
  "disk": {
    "path": "/",
    "device": "/dev/sda1",
    "fstype": "ext4",
    "total_gb": 111.79,
    "used_gb": 106.77,
    "free_gb": 2.35,
    "percent": 95.0
  },
  "gpu": ["Intel Corporation 3rd Gen Core processor Graphics Controller"],
  "network": [
    {
      "name": "wlp3s0",
      "is_up": true,
      "speed_mbps": 300,
      "mtu": 1500,
      "ips": ["192.168.1.100"],
      "bytes_sent": 1234567,
      "bytes_recv": 9876543,
      "packets_sent": 10000,
      "packets_recv": 15000
    }
  ],
  "battery": null,
  "top_processes": {
    "by_cpu": [
      {"pid": 7118, "name": "antigravity", "cpu_percent": 18.0, "mem_percent": 2.7, "status": "running"}
    ],
    "by_mem": [
      {"pid": 14380, "name": "firefox", "cpu_percent": 6.6, "mem_percent": 3.6, "status": "running"}
    ]
  }
}
```

## 👤 Logika Deteksi User (Penting!)

Field `users` mengembalikan **object** (bukan angka) dengan 3 fallback:

```json
"users": {
  "count": 1,
  "names": ["root"],
  "method": "psutil" | "who" | "gui_session" | "none"
}
```

### Prioritas Method:
1. **`psutil`** → Standar (baca `/var/run/utmp`). Tidak mencatat sesi GUI Wayland/X11.
2. **`who`** → Fallback jika `psutil` = 0. Lebih lengkap tapi tetap tidak catat GUI.
3. **`gui_session`** → Deteksi via env vars (`$XDG_SESSION_ID`, `$USER`, `$LOGNAME`) atau `logname`. Solusi untuk sesi desktop.
4. **`none`** → Semua method gagal.

### Kenapa Penting?
`psutil.users()` & `who` **tidak mencatat sesi desktop** (Wayland/X11) di Linux. Tanpa fallback, `users` akan selalu `0` padahal Anda sedang aktif menggunakan komputer. Field `method` membuat logika ini transparan untuk debugging.

## 🛡️ Penanganan Data Tidak Tersedia

Script ini didesain **fault-tolerant** — jika ada komponen yang tidak tersedia, tidak akan crash:

| Komponen | Jika Tidak Tersedia | Behavior |
|----------|---------------------|----------|
| 🌡️ **CPU Temperature** | `lm-sensors` belum terinstall | Field `temperature` = `null` |
| 🔋 **Battery** | Bukan laptop / tanpa baterai | Field `battery` = `null` |
| 💿 **Disk device/fstype** | `findmnt` tidak tersedia | Fallback ke `"unknown"` |
| 🌐 **Network IP** | Interface tanpa IP | Field `ips` = `[]` (array kosong) |
| 🎮 **GPU** | `lspci` tidak ada / tidak ada VGA device | Field `gpu` = `[]` |
| ⚡ **CPU usage** | Permission denied untuk baca proses | Lewati proses tersebut, tidak crash |
| 🧠 **CPU model** | `platform.processor()` return Unknown | Fallback ke `/proc/cpuinfo` → "model name" / "Hardware" / "Processor" |
| 👤 **Users** | `psutil.users()` + `who` = 0 (sesi GUI) | Fallback ke env vars (`$USER`/`$LOGNAME`) atau `logname` |

### Instalasi Optional (untuk data lebih lengkap)
```bash
# Untuk CPU temperature
sudo apt install lm-sensors
sudo sensors-detect
sensors

# Untuk GPU detail
sudo apt install lspci

# Untuk info disk detail
sudo apt install util-linux  # findmnt (biasanya sudah default)
```

## ⚠️ Catatan Penting

- ✅ Script ini **read-only** — tidak mengubah sistem apapun
- 🔒 Beberapa info mungkin butuh permission (misal: baca proses user lain)
- 📊 Data bersifat **snapshot** saat script dijalankan (bukan real-time streaming)
- 🐧 Script dioptimasi untuk **Linux**. Di Windows/macOS beberapa field mungkin `null`
- ⚡ Untuk CPU usage akurat, ada `time.sleep(0.1)` internal — jadi script butuh ~0.5 detik total

## 🚀 Integrasi dengan Bot/API

### Contoh dari Python:
```python
import subprocess, json

result = subprocess.run(
    ["python", "skills/checkresources/checkresources.py"],
    capture_output=True, text=True
)
data = json.loads(result.stdout)
print(f"Disk usage: {data['disk']['percent']}%")
```

### Contoh Endpoint FastAPI:
```python
from fastapi import APIRouter
import subprocess, json

router = APIRouter()

@router.get("/system/resources")
def get_resources():
    result = subprocess.run(
        ["python", "skills/checkresources/checkresources.py"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)
```

## 📝 Versi & Changelog
- **v1.0** — Initial release (CPU, RAM, Disk, GPU, Top processes)
- **v1.1** — Tambah: CPU model fix (/proc/cpuinfo), Network interfaces, Battery, Temperature
- **v1.2** — Bug fix: cpu_percent akurat (sampling interval), handling None untuk semua sensor
- **v1.3** — Fix `users: 0` bug: tambah multi-fallback (psutil → who → GUI session detection)
