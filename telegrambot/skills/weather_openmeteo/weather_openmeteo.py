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


def geocode(city: str) -> dict:
    """Cari koordinat kota via Open-Meteo Geocoding."""
    params = urllib.parse.urlencode({
        "name": city,
        "count": 1,
        "language": "id",
        "format": "json",
    })
    data = fetch_json(f"{API_GEO}?{params}")
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"Kota '{city}' tidak ditemukan di geocoding Open-Meteo")
    top = results[0]
    return {
        "name": top.get("name", city),
        "country": top.get("country", ""),
        "admin1": top.get("admin1", ""),
        "latitude": top["latitude"],
        "longitude": top["longitude"],
        "timezone": top.get("timezone", "auto"),
        "population": top.get("population"),
    }


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

        # daily fields → list aligned
        dates = daily.get("time", []) or []
        for i, d in enumerate(dates):
            result["daily_forecast"].append({
                "date": d,
                "weather_code": (daily.get("weather_code") or [None] * (i + 1))[i],
                "weather_desc": describe_code(
                    (daily.get("weather_code") or [None] * (i + 1))[i]
                ),
                "temp_max_c": (daily.get("temperature_2m_max") or [None] * (i + 1))[i],
                "temp_min_c": (daily.get("temperature_2m_min") or [None] * (i + 1))[i],
                "precip_mm": (daily.get("precipitation_sum") or [None] * (i + 1))[i],
                "precip_prob_pct": (daily.get("precipitation_probability_max") or [None] * (i + 1))[i],
                "sunrise": (daily.get("sunrise") or [None] * (i + 1))[i],
                "sunset": (daily.get("sunset") or [None] * (i + 1))[i],
                "uv_index_max": (daily.get("uv_index_max") or [None] * (i + 1))[i],
            })

        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    except RuntimeError as e:
        # Error yang bisa ditampilkan ke user
        print(json.dumps({"error": str(e), "city_requested": city}, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
