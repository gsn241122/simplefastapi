#!/usr/bin/env python3
"""
Skill: check-resources
Mengumpulkan data resource komputer (CPU, RAM, Disk, GPU, Network, Battery, Temp).
Output: JSON terstruktur siap konsumsi bot Telegram / API lain.
"""

import json
import os
import platform
import subprocess
import time
from datetime import datetime, timezone

try:
    import psutil
except ImportError:
    raise SystemExit("psutil belum terinstall. Jalankan: pip install psutil")


# ---------- Helpers ----------

def read_cpuinfo():
    """Fallback untuk ambil model CPU dari /proc/cpuinfo (Linux)."""
    info = {}
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if ":" in line:
                    key, val = line.split(":", 1)
                    info[key.strip()] = val.strip()
    except Exception:
        pass
    return info


def get_cpu_model():
    """Ambil model CPU, coba beberapa sumber agar tidak Unknown."""
    try:
        model = platform.processor()
        if model and model.strip() and model.strip().lower() != "unknown":
            return model.strip()
    except Exception:
        pass
    cpuinfo = read_cpuinfo()
    for key in ("model name", "Hardware", "Processor"):
        if cpuinfo.get(key):
            return cpuinfo[key]
    return "Unknown"


def run_cmd(cmd):
    """Jalankan shell command, return stdout string atau None."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def get_gpu_info():
    """Ambil info GPU via lspci (fallback sederhana)."""
    out = run_cmd("lspci | grep -i 'vga\\|3d\\|2d'")
    if not out:
        return []
    gpus = []
    for line in out.splitlines():
        # contoh: "00:02.0 VGA compatible controller: Intel Corporation ..."
        parts = line.split(":", 2)
        if len(parts) >= 3:
            gpus.append(parts[2].strip())
    return gpus


def get_cpu_temp():
    """Coba ambil suhu CPU. Return None kalau tidak tersedia."""
    # 1) psutil sensors (Linux)
    try:
        temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        for name, entries in temps.items():
            for e in entries:
                if e.current and e.current > 0:
                    return {
                        "label": e.label or name,
                        "chip": name,
                        "temp_c": round(e.current, 1),
                        "high_c": e.high,
                        "critical_c": e.critical,
                    }
    except Exception:
        pass

    # 2) Fallback ke sensors (lm-sensors)
    out = run_cmd("sensors 2>/dev/null | grep -i 'core 0\\|package id 0\\|tctl\\|cpu'")
    if out:
        # ambil angka pertama yang valid
        import re
        m = re.search(r"([-+]?\d+\.\d+)", out)
        if m:
            return {"label": "CPU (sensors)", "chip": "coretemp", "temp_c": float(m.group(1))}
    return None


def get_battery():
    """Info baterai laptop (jika ada)."""
    if not hasattr(psutil, "sensors_battery"):
        return None
    try:
        bat = psutil.sensors_battery()
        if bat is None:
            return None
        return {
            "percent": round(bat.percent, 1),
            "plugged_in": bat.power_plugged,
            "seconds_left": bat.secsleft if bat.secsleft != psutil.POWER_TIME_UNLIMITED else None,
        }
    except Exception:
        return None


def get_network():
    """Info network interfaces + statistik upload/download."""
    interfaces = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    io = psutil.net_io_counters(pernic=True)

    for name, stat in stats.items():
        if name == "lo":  # skip loopback
            continue
        # skip interface yang down & tidak punya IP
        if not stat.isup:
            continue
        ip_list = []
        for addr in addrs.get(name, []):
            if addr.family.name == "AF_INET":
                ip_list.append(addr.address)
        io_stat = io.get(name)
        interfaces.append({
            "name": name,
            "is_up": stat.isup,
            "speed_mbps": stat.speed if stat.speed > 0 else None,
            "mtu": stat.mtu,
            "ips": ip_list,
            "bytes_sent": io_stat.bytes_sent if io_stat else 0,
            "bytes_recv": io_stat.bytes_recv if io_stat else 0,
            "packets_sent": io_stat.packets_sent if io_stat else 0,
            "packets_recv": io_stat.packets_recv if io_stat else 0,
        })
    return interfaces


def get_disk():
    part = psutil.disk_usage("/")
    return {
        "path": "/",
        "device": run_cmd("findmnt -n -o SOURCE /") or "unknown",
        "fstype": run_cmd("findmnt -n -o FSTYPE /") or "unknown",
        "total_gb": round(part.total / (1024 ** 3), 2),
        "used_gb": round(part.used / (1024 ** 3), 2),
        "free_gb": round(part.free / (1024 ** 3), 2),
        "percent": part.percent,
    }


def get_top_processes(limit=5):
    """Top proses by CPU & RAM. interval kecil supaya cpu_percent akurat."""
    procs = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(interval=None)  # warm-up
        except Exception:
            continue
    time.sleep(0.1)  # sampling singkat

    for p in psutil.process_iter(["pid", "name"]):
        try:
            with p.oneshot():
                procs.append({
                    "pid": p.info["pid"],
                    "name": p.info["name"] or "unknown",
                    "cpu_percent": round(p.cpu_percent(interval=None), 1),
                    "mem_percent": round(p.memory_percent(), 1),
                    "status": p.status(),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    by_cpu = sorted(procs, key=lambda x: x["cpu_percent"], reverse=True)[:limit]
    by_mem = sorted(procs, key=lambda x: x["mem_percent"], reverse=True)[:limit]
    return {"by_cpu": by_cpu, "by_mem": by_mem}


def get_memory():
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "ram": {
            "total_gb": round(mem.total / (1024 ** 3), 2),
            "used_gb": round(mem.used / (1024 ** 3), 2),
            "free_gb": round(mem.available / (1024 ** 3), 2),  # available, bukan free
            "percent": mem.percent,
        },
        "swap": {
            "total_gb": round(swap.total / (1024 ** 3), 2),
            "used_gb": round(swap.used / (1024 ** 3), 2),
            "free_gb": round(swap.free / (1024 ** 3), 2),
            "percent": swap.percent,
        },
    }


def get_cpu():
    freq = psutil.cpu_freq()
    return {
        "model": get_cpu_model(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "current_mhz": round(freq.current, 1) if freq else None,
        "min_mhz": round(freq.min, 1) if freq else None,
        "max_mhz": round(freq.max, 1) if freq else None,
        "usage_percent": psutil.cpu_percent(interval=0.2),
        "load_avg": [round(x, 2) for x in psutil.getloadavg()],
        "temperature": get_cpu_temp(),
    }


def get_logged_users():
    """
    Ambil user yang sedang login dengan multi-fallback.
    Prioritas:
      1. psutil.users()        -> standar (utmp)
      2. `who` command         -> termasuk TTY
      3. GUI session detection -> Wayland/X11 via env vars
    Return dict {count, names, method}.
    """
    users = set()
    method = None

    # Method 1: psutil (standar)
    try:
        for u in psutil.users():
            if u.name:
                users.add(u.name)
        if users:
            method = "psutil"
    except Exception:
        pass

    # Method 2: fallback ke `who`
    if not users:
        try:
            result = subprocess.run(
                ["who"], capture_output=True, text=True, timeout=3
            )
            for line in result.stdout.strip().splitlines():
                if line.strip():
                    users.add(line.split()[0])
            if users:
                method = "who"
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass

    # Method 3: deteksi sesi GUI (Wayland/X11)
    if not users:
        try:
            current_user = (
                os.environ.get("USER")
                or os.environ.get("LOGNAME")
            )
            if not current_user:
                current_user = subprocess.check_output(
                    ["logname"], stderr=subprocess.DEVNULL
                ).decode().strip()
            if current_user:
                users.add(current_user)
                method = "gui_session"
        except Exception:
            pass

    return {
        "count": len(users),
        "names": sorted(list(users)) if users else [],
        "method": method or "none",
    }


def get_system():
    boot = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
    logged = get_logged_users()
    return {
        "os": f"{platform.system()} {platform.release()}",
        "kernel": platform.version(),
        "hostname": platform.node(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "boot_time_utc": boot.isoformat(),
        "uptime_seconds": int(time.time() - psutil.boot_time()),
        "users": logged,
        "load_average": [round(x, 2) for x in psutil.getloadavg()],
    }


def main():
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": get_system(),
        "cpu": get_cpu(),
        "memory": get_memory(),
        "disk": get_disk(),
        "gpu": get_gpu_info(),
        "network": get_network(),
        "battery": get_battery(),
        "top_processes": get_top_processes(limit=5),
    }
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
