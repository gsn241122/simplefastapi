---
name: weather_openmeteo
description: Mendapatkan prakiraan cuaca akurat menggunakan API Open-Meteo. Gunakan ini saat user bertanya tentang cuaca, suhu, atau hujan di kota mana pun. Tidak memerlukan API key.
---

# Skill Cuaca via Open-Meteo

## Prasyarat
Skill ini memerlukan tool HTTP GET (biasanya bernama `fetch`, `http_request`, atau `web_fetch`) yang tersedia di daftar MCP tools Anda.

## Alur Kerja (Step-by-Step)

### Langkah 1: Geocoding (Cari Koordinat Kota)
Open-Meteo membutuhkan Latitude dan Longitude. Jangan gunakan nama kota langsung di API cuaca.
Lakukan `GET` request ke Geocoding API:
**URL:** `https://geocoding-api.open-meteo.com/v1/search?name={NAMA_KOTA}&count=1&language=id`
*(Catatan: Pastikan `{NAMA_KOTA}` di-URL-encode, misal: `New York` menjadi `New%20York`)*

**Ekstrak dari JSON Response:**
- `latitude` (dari `results[0].latitude`)
- `longitude` (dari `results[0].longitude`)
- `name` & `country` (untuk konfirmasi ke user)
*Jika `results` kosong, beri tahu user bahwa kota tidak ditemukan.*

### Langkah 2: Ambil Data Cuaca
Gunakan koordinat dari Langkah 1 untuk memanggil Forecast API:
**URL:** `https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=temperature_2m,relative_humidity_2m,weather_code&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto`

### Langkah 3: Terjemahkan Kode Cuaca (WMO Code)
Open-Meteo mengembalikan angka (`weather_code`), bukan teks. Gunakan tabel ini untuk menerjemahkannya ke bahasa Indonesia:

| Code | Kondisi Cuaca |
|---|---|
| 0 | Cerah (Clear sky) |
| 1, 2, 3 | Cerah berawan / Berawan / Mendung |
| 45, 48 | Kabut / Berkabut |
| 51, 53, 55 | Gerimis (Ringan, Sedang, Tebal) |
| 56, 57 | Hujan beku (Freezing drizzle) |
| 61, 63, 65 | Hujan (Ringan, Sedang, Deras) |
| 66, 67 | Hujan beku (Freezing rain) |
| 71, 73, 75 | Salju (Ringan, Sedang, Tebal) |
| 77 | Butiran salju (Snow grains) |
| 80, 81, 82 | Hujan deras / Hujan lokal |
| 85, 86 | Hujan salju lebat |
| 95 | Badai petir |
| 96, 99 | Badai petir dengan hujan es |

### Langkah 4: Format Jawaban
Sajikan data dengan format yang mudah dibaca manusia:
1. **Kondisi Saat Ini:** Suhu, Kelembapan, dan Kondisi (dari kode WMO).
2. **Prakiraan 7 Hari:** Buat daftar singkat (Hari, Kondisi, Suhu Min-Max, Curah Hujan).
3. **Saran:** Berikan saran singkat (misal: "Bawa payung", "Gunakan tabir surya").

## Contoh Interaksi

**User:** "Cuaca di Bandung hari ini dan besok bagaimana?"
**Agen (Internal Thought):**
1. Fetch `https://geocoding-api.open-meteo.com/v1/search?name=Bandung&count=1` -> Dapat Lat: -6.91, Lon: 107.60
2. Fetch `https://api.open-meteo.com/v1/forecast?latitude=-6.91&longitude=107.60&current=...`
3. Parse JSON, terjemahkan WMO code, format output.

**Agen (Reply ke User):**
"Cuaca di Bandung, Indonesia:
☀️ **Saat ini:** 24°C, Cerah berawan, Kelembapan 75%.
📅 **Prakiraan:**
- Hari ini: Cerah berawan, 20°C - 29°C.
- Besok: Hujan ringan di sore hari, 19°C - 28°C (curah hujan ~5mm).
💡 **Saran:** Udara sejuk, namun siapkan payung jika Anda berencana keluar besok sore."