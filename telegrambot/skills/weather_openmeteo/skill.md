---
name: weather_openmeteo
description: Mendapatkan prakiraan cuaca real-time via Open-Meteo API (tanpa API key). Menerima argumen --city untuk nama kota, output JSON terstruktur (cuaca saat ini + prakiraan 3 hari ke depan).
---

# 🌤️ Skill: weather_openmeteo

## Deskripsi
Skill ini digunakan untuk mendapatkan **prakiraan cuaca real-time** dari API publik Open-Meteo (gratis, tanpa API key). Output berupa JSON terstruktur yang siap dikonsumsi bot Telegram.

Informasi yang dikembalikan:
- 📍 **Lokasi**: nama kota, negara, koordinat (lat/lon), timezone
- 🌡️ **Cuaca saat ini**: suhu, terasa seperti, kelembapan, presipitasi, kecepatan & arah angin
- 📅 **Prakiraan 3 hari**: suhu min/max, curah hujan, probabilitas hujan, sunrise/sunset, UV index max

## Prasyarat
- Python 3.8+
- **Tidak butuh API key** (Open-Meteo adalah API publik gratis)
- Hanya butuh library standar Python (`urllib`, `json`, `datetime`)
- Koneksi internet untuk akses `api.open-meteo.com` & `geocoding-api.open-meteo.com`

## Cara Pakai

### 1. Jalankan Script
```bash
# Dari direktori skill
cd skills/weather_openmeteo
python weather_openmeteo.py --city=Jakarta

# Dari mana saja (absolute path)
python skills/weather_openmeteo/weather_openmeteo.py --city=Bandung

# Default kota = Jakarta jika --city tidak diberikan
python weather_openmeteo.py
```

### 2. Argumen yang Didukung
| Argumen | Alias | Default | Keterangan |
|---------|-------|---------|------------|
| `--city=<nama>` | `--q=<nama>` | `Jakarta` | Nama kota (auto di-URL-encode) |

### 3. Output
Script print JSON terstruktur ke **stdout**. Jika ada error (misal: kota tidak ditemukan), error ditulis ke **stderr** dalam format JSON dan exit code = 1.

## Struktur Output JSON

```json
{
  "generated_at": "2026-05-14T10:30:00+00:00",
  "location": {
    "name": "Jakarta",
    "country": "Indonesia",
    "admin1": "Jakarta",
    "latitude": -6.1751,
    "longitude": 106.865,
    "timezone": "Asia/Jakarta"
  },
  "current": {
    "temperature_c": 30.5,
    "apparent_c": 34.2,
    "humidity_pct": 75,
    "is_day": 1,
    "precipitation_mm": 0.0,
    "weather_code": 2,
    "weather_desc": "Berawan sebagian",
    "wind_speed_kmh": 12.5,
    "wind_direction_deg": 180,
    "time": "2026-05-14T10:00"
  },
  "daily_forecast": [
    {
      "date": "2026-05-14",
      "weather_code": 2,
      "weather_desc": "Berawan sebagian",
      "temp_max_c": 32.5,
      "temp_min_c": 25.0,
      "precip_mm": 2.5,
      "precip_prob_pct": 60,
      "sunrise": "2026-05-14T05:55",
      "sunset": "2026-05-14T17:45",
      "uv_index_max": 8.5
    }
  ]
}
```

## 🌦️ Kode Cuaca WMO (Referensi)

| Code | Kondisi |
|------|---------|
| 0 | Cerah |
| 1 | Sebagian besar cerah |
| 2 | Berawan sebagian |
| 3 | Mendung penuh |
| 45, 48 | Kabut / Kabut beku |
| 51, 53, 55 | Gerimis (ringan/sedang/lebat) |
| 61, 63, 65 | Hujan (ringan/sedang/lebat) |
| 71, 73, 75 | Salju (ringan/sedang/lebat) |
| 80, 81, 82 | Hujan shower |
| 95 | Badai petir |
| 96, 99 | Badai petir + hujan es |

## 🛡️ Penanganan Error

| Skenario | Behavior |
|----------|----------|
| Kota tidak ditemukan di geocoding | JSON `{"error": "...", "city_requested": "..."}` ke stderr, exit 1 |
| HTTP 4xx/5xx dari Open-Meteo | RuntimeError + exit 1 |
| Timeout (>10s) | URLError + exit 1 |
| Response bukan JSON | JSONDecodeError + exit 1 |

## 🐛 Troubleshooting

**Q: Output kosong / tidak muncul apa-apa?**
Pastikan pakai `python weather_openmeteo.py --city=Jakarta` (cek stdout, bukan stderr).

**Q: `ModuleNotFoundError: No module named 'urllib'`?**
`urllib` adalah modul **bawaan Python** — seharusnya selalu ada. Cek instalasi Python Anda.

**Q: Internet terbatas / API down?**
Script akan error dengan pesan `Gagal terhubung ke Open-Meteo`. Coba lagi nanti atau gunakan cache jika ada.

## 📝 Versi & Changelog
- **v1.0** — Initial release: geocoding + current weather + 3-day forecast

## ⚠️ Catatan
- ✅ Script ini **read-only** — tidak ada efek samping
- 🌐 Butuh akses internet ke `*.open-meteo.com`
- ⏱️ Timeout default: 10 detik
- 🔄 Setiap request = 2 HTTP call (geocoding + forecast)
