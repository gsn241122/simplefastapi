#!/usr/bin/env python3
"""
Skill: weather_openmeteo
Ambil prakiraan cuaca real-time via Open-Meteo API (tanpa API key).
Menerima argumen: --city=<nama_kota>
Output: JSON terstruktur siap konsumsi bot Telegram.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_GEO = "https://geocoding-api.open-meteo.com/v1/search"
API_WEATHER = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 10

# Hardcoded map kota-kota besar Indonesia (paling reliable, bypass geocoding API
# yang tidak konsisten untuk nama kota generik seperti "Bandung", "Jakarta", dll).
KNOWN_CITIES = {
    "jakarta":           {"name": "Jakarta",             "admin1": "DKI Jakarta",      "lat": -6.2088,  "lon": 106.8456},
    "kota jakarta":      {"name": "Jakarta",             "admin1": "DKI Jakarta",      "lat": -6.2088,  "lon": 106.8456},
    "bandung":           {"name": "Kota Bandung",        "admin1": "Jawa Barat",       "lat": -6.9222,  "lon": 107.6069},
    "kota bandung":      {"name": "Kota Bandung",        "admin1": "Jawa Barat",       "lat": -6.9222,  "lon": 107.6069},
    "kab bandung":       {"name": "Kabupaten Bandung",   "admin1": "Jawa Barat",       "lat": -7.1342,  "lon": 107.4917},
    "kabupaten bandung": {"name": "Kabupaten Bandung",   "admin1": "Jawa Barat",       "lat": -7.1342,  "lon": 107.4917},
    "surabaya":          {"name": "Surabaya",            "admin1": "Jawa Timur",       "lat": -7.2575,  "lon": 112.7521},
    "semarang":          {"name": "Semarang",            "admin1": "Jawa Tengah",      "lat": -6.9667,  "lon": 110.4167},
    "yogyakarta":        {"name": "Yogyakarta",          "admin1": "DI Yogyakarta",    "lat": -7.7956,  "lon": 110.3695},
    "jogja":             {"name": "Yogyakarta",          "admin1": "DI Yogyakarta",    "lat": -7.7956,  "lon": 110.3695},
    "medan":             {"name": "Medan",               "admin1": "Sumatera Utara",   "lat":  3.5952,  "lon":  98.6722},
    "makassar":          {"name": "Makassar",            "admin1": "Sulawesi Selatan", "lat": -5.1477,  "lon": 119.4327},
    "denpasar":          {"name": "Denpasar",            "admin1": "Bali",             "lat": -8.6500,  "lon": 115.2167},
    "balikpapan":        {"name": "Balikpapan",          "admin1": "Kalimantan Timur", "lat": -1.2379,  "lon": 116.8528},
    "manado":            {"name": "Manado",              "admin1": "Sulawesi Utara",   "lat":  1.4748,  "lon": 124.8421},
    "jayapura":          {"name": "Jayapura",            "admin1": "Papua",            "lat": -2.5337,  "lon": 140.7181},
    "ambon":             {"name": "Ambon",               "admin1": "Maluku",           "lat": -3.6954,  "lon": 128.1814},
    "bogor":             {"name": "Kota Bogor",          "admin1": "Jawa Barat",       "lat": -6.5950,  "lon": 106.8166},
    "bekasi":            {"name": "Kota Bekasi",         "admin1": "Jawa Barat",       "lat": -6.2383,  "lon": 106.9756},
    "depok":             {"name": "Kota Depok",          "admin1": "Jawa Barat",       "lat": -6.4025,  "lon": 106.7942},
    "tangerang":         {"name": "Kota Tangerang",      "admin1": "Banten",           "lat": -6.1783,  "lon": 106.6319},
    "cilegon":           {"name": "Cilegon",             "admin1": "Banten",           "lat": -6.0023,  "lon": 106.0537},
    "serang":            {"name": "Serang",              "admin1": "Banten",           "lat": -6.1104,  "lon": 106.1639},
    "tasikmalaya":       {"name": "Kota Tasikmalaya",    "admin1": "Jawa Barat",       "lat": -7.3274,  "lon": 108.2207},
    "cirebon":           {"name": "Kota Cirebon",        "admin1": "Jawa Barat",       "lat": -6.7320,  "lon": 108.5523},
    "sukabumi":          {"name": "Kota Sukabumi",       "admin1": "Jawa Barat",       "lat": -6.9277,  "lon": 106.9289},
}

# Prefiks administratif yang umum di nama kota Indonesia
_ADMIN_PREFIXES = (
    "kota ", "kabupaten ", "kab. ", "kab ",
    "kota administrasi ", "kabupaten administrasi ",
    "kecamatan ", "kec. ", "kec ",
    "desa ", "kelurahan ", "kel. ", "kel ",
    "nagari ",
)


def _strip_admin_prefix(name: str) -> str:
    """Hapus prefiks administratif ('Kota ', 'Kabupaten ', dll) dari nama kota."""
    n = name.strip().lower()
    for p in _ADMIN_PREFIXES:
        if n.startswith(p):
            return n[len(p):]
    return n


def _starts_with_admin_prefix(name: str, query: str) -> bool:
    """True kalau `query` cocok dengan nama setelah prefiks administratif dihapus."""
    stripped = _strip_admin_prefix(name)
    return stripped == query or stripped.startswith(query + " ")


def fetch_json(url: str) -> dict:
    """GET JSON dari URL, raise RuntimeError kalau gagal."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "weather_openmeteo-skill/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} dari Open-Meteo: {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Gagal terhubung ke Open-Meteo: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Response bukan JSON valid: {e}") from e


def _score_match(city_query: str, item: dict) -> int:
    """Skor kecocokan hasil geocoding vs query user (lebih tinggi = lebih cocok)."""
    name = (item.get("name") or "").lower()
    admin1 = (item.get("admin1") or "").lower()
    country = (item.get("country") or "").lower()
    feature = (item.get("feature_code") or "").lower()
    population = item.get("population") or 0
    q = city_query.lower().strip()

    score = 0
    # Exact name match = bonus terbesar
    if name == q:
        score += 1_000_000
    # Prefix langsung (mis. "bandung" cocok dengan "bandung" lowercased)
    elif name.startswith(q) or q.startswith(name):
        score += 100_000
    # Query cocok dengan nama setelah membuang prefiks administratif
    # (mis. query "bandung" cocok dengan "kota bandung" / "kabupaten bandung")
    elif _starts_with_admin_prefix(name, q) or _starts_with_admin_prefix(q, name):
        score += 100_000
    # Substring match (query ada di tengah nama)
    elif q in name or name in q:
        score += 10_000

    # Prioritaskan Indonesia kalau query tidak menyebut negara lain
    if country in ("indonesia", ""):
        score += 50_000
    # Pulau prioritas
    if "jawa barat" in admin1:
        score += 5_000
    if "jawa" in admin1:
        score += 1_000
    # Tipe fitur: kota besar lebih diutamakan dari pada desa kecil
    if feature == "pplc":  # capital of country / state
        score += 8_000
    elif feature == "ppla":  # seat of admin division
        score += 4_000
    elif feature == "ppla2":
        score += 2_000
    # Populasi sebagai tie-breaker
    score += min(population, 500_000) // 10_000
    return score


def geocode(city: str) -> dict:
    """Cari koordinat kota via Open-Meteo Geocoding.

    Layer 1: cek KNOWN_CITIES dict (paling reliable).
    Layer 2: fallback ke API geocoding dengan smart-scoring (population null-safe,
             exact-match prioritized, admin1 bonus untuk query spesifik).
    """
    if not city or not city.strip():
        raise RuntimeError("Nama kota kosong")

    city_q = city.strip().lower()

    # Layer 1: hardcoded map (prioritas: exact match > prefix > substring)
    # Exact match duluan (termasuk exact key dari dict)
    if city_q in KNOWN_CITIES:
        coords = KNOWN_CITIES[city_q]
        return {
            "name": coords["name"],
            "country": "Indonesia",
            "admin1": coords["admin1"],
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "timezone": "Asia/Jakarta",
            "population": 999_999_999,
            "alternatives": [],
            "_source": "known_cities",
        }

    # Substring match: pilih key terpanjang (paling spesifik) untuk cegah
    # 'Kabupaten Bandung' match key 'bandung' yg lebih pendek.
    substring_matches = [
        (key, KNOWN_CITIES[key])
        for key in KNOWN_CITIES
        if city_q in key or key in city_q
    ]
    if substring_matches:
        # Pilih key dengan panjang terbesar (paling spesifik)
        best_key, best_coords = max(substring_matches, key=lambda kv: len(kv[0]))
        return {
            "name": best_coords["name"],
            "country": "Indonesia",
            "admin1": best_coords["admin1"],
            "latitude": best_coords["lat"],
            "longitude": best_coords["lon"],
            "timezone": "Asia/Jakarta",
            "population": 999_999_999,
            "alternatives": [],
            "_source": "known_cities",
        }

    # Layer 2: API geocoding
    params = urllib.parse.urlencode({
        "name": city.strip(),
        "count": 10,
        "language": "id",
        "format": "json",
    })
    data = fetch_json(f"{API_GEO}?{params}")
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"Kota '{city}' tidak ditemukan di geocoding Open-Meteo")

    id_results = [r for r in results if (r.get("country") or "").lower() == "indonesia"]
    candidates = id_results if id_results else results

    candidates.sort(key=lambda r: _score_match(city, r), reverse=True)
    top = candidates[0]

    alternatives = [
        {
            "name": r.get("name"),
            "admin1": r.get("admin1"),
            "country": r.get("country"),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "population": r.get("population"),
        }
        for r in candidates[1:4]
    ]

    return {
        "name": top.get("name", city),
        "country": top.get("country", ""),
        "admin1": top.get("admin1", ""),
        "latitude": top["latitude"],
        "longitude": top["longitude"],
        "timezone": top.get("timezone", "auto"),
        "population": top.get("population"),
        "alternatives": alternatives,
        "_source": "open_meteo_api",
    }


def _safe_get(arr, i, default=None):
    """Index list dengan default aman (anti IndexError)."""
    if not arr:
        return default
    if i < 0 or i >= len(arr):
        return default
    return arr[i]


def fetch_weather(lat: float, lon: float, tz: str) -> dict:
    """Ambil cuaca saat ini + prakiraan 3 hari ke depan."""
    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                    "is_day,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_sum,precipitation_probability_max,"
                 "sunrise,sunset,uv_index_max",
        "timezone": tz or "auto",
        "forecast_days": 3,
    })
    return fetch_json(f"{API_WEATHER}?{params}")


# Kode cuaca WMO → deskripsi singkat (id)
WMO_CODE = {
    0: "Cerah",
    1: "Sebagian besar cerah",
    2: "Berawan sebagian",
    3: "Mendung penuh",
    45: "Kabut",
    48: "Kabut beku",
    51: "Gerimis ringan",
    53: "Gerimis sedang",
    55: "Gerimis lebat",
    56: "Gerimis beku ringan",
    57: "Gerimis beku lebat",
    61: "Hujan ringan",
    63: "Hujan sedang",
    65: "Hujan lebat",
    66: "Hujan beku ringan",
    67: "Hujan beku lebat",
    71: "Salju ringan",
    73: "Salju sedang",
    75: "Salju lebat",
    77: "Butiran salju",
    80: "Hujan shower ringan",
    81: "Hujan shower sedang",
    82: "Hujan shower lebat",
    85: "Snow shower ringan",
    86: "Snow shower lebat",
    95: "Badai petir",
    96: "Badai petir + hujan es ringan",
    99: "Badai petir + hujan es lebat",
}


def describe_code(code: int | None) -> str:
    if code is None:
        return "-"
    return WMO_CODE.get(code, f"Kode tidak dikenal ({code})")


def parse_args(argv: list[str]) -> dict:
    """Parser argumen sederhana: --key=value."""
    args = {}
    for a in argv[1:]:
        if "=" not in a:
            continue
        k, v = a.lstrip("-").split("=", 1)
        args[k.strip()] = v.strip()
    return args


def main() -> int:
    args = parse_args(sys.argv)
    city = args.get("city") or args.get("q") or "Jakarta"

    try:
        loc = geocode(city)
        wx = fetch_weather(loc["latitude"], loc["longitude"], loc["timezone"])

        current = wx.get("current", {}) or {}
        daily = wx.get("daily", {}) or {}

        result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "location": {
                "name": loc["name"],
                "country": loc["country"],
                "admin1": loc["admin1"],
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "timezone": wx.get("timezone", loc["timezone"]),
            },
            "current": {
                "temperature_c": current.get("temperature_2m"),
                "apparent_c": current.get("apparent_temperature"),
                "humidity_pct": current.get("relative_humidity_2m"),
                "is_day": current.get("is_day"),
                "precipitation_mm": current.get("precipitation"),
                "weather_code": current.get("weather_code"),
                "weather_desc": describe_code(current.get("weather_code")),
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "wind_direction_deg": current.get("wind_direction_10m"),
                "time": current.get("time"),
            },
            "daily_forecast": [],
        }

        # daily fields → list aligned (anti IndexError via _safe_get)
        dates = daily.get("time", []) or []
        wc = daily.get("weather_code") or []
        tmax = daily.get("temperature_2m_max") or []
        tmin = daily.get("temperature_2m_min") or []
        psum = daily.get("precipitation_sum") or []
        pprob = daily.get("precipitation_probability_max") or []
        sunrise = daily.get("sunrise") or []
        sunset = daily.get("sunset") or []
        uvmax = daily.get("uv_index_max") or []

        for i, d in enumerate(dates):
            code_i = _safe_get(wc, i)
            result["daily_forecast"].append({
                "date": d,
                "weather_code": code_i,
                "weather_desc": describe_code(code_i),
                "temp_max_c": _safe_get(tmax, i),
                "temp_min_c": _safe_get(tmin, i),
                "precip_mm": _safe_get(psum, i),
                "precip_prob_pct": _safe_get(pprob, i),
                "sunrise": _safe_get(sunrise, i),
                "sunset": _safe_get(sunset, i),
                "uv_index_max": _safe_get(uvmax, i),
            })

        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    except RuntimeError as e:
        # Error yang bisa ditampilkan ke user
        print(json.dumps({"error": str(e), "city_requested": city}, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
