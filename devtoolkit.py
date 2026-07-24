#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║               🛠️  SimpleFastAPI Developer Toolkit               ║
║                                                                  ║
║  CLI toolbox untuk mempercepat workflow development sehari-hari  ║
║  pada project SimpleFastAPI.                                     ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
    python devtoolkit.py <command> [options]

Run `python devtoolkit.py --help` untuk melihat semua command.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import importlib
import inspect
import json
import logging
import os
import platform
import re
import secrets
import shutil
import signal
import socket
import sqlite3
import string
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from app.core.database import SessionLocal, engine, Base

# ──────────────────────────────────────────────────────────────────
# Konstanta & Konfigurasi
# ──────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
APP_DIR = PROJECT_ROOT / "app"
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
DB_FILE = PROJECT_ROOT / "app.db"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
TESTS_DIR = PROJECT_ROOT / "tests"
ALEMBIC_DIR = PROJECT_ROOT / "alembic"

# ANSI color codes
class Color:
    """ANSI escape codes untuk output berwarna di terminal."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_RED  = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


def _c(text: str, color: str) -> str:
    """Wrap teks dengan ANSI color code."""
    return f"{color}{text}{Color.RESET}"


def _header(title: str) -> None:
    """Print header section yang cantik."""
    width = 60
    print()
    print(_c("─" * width, Color.CYAN))
    print(_c(f"  ⚡ {title}", Color.BOLD + Color.CYAN))
    print(_c("─" * width, Color.CYAN))


def _success(msg: str) -> None:
    print(f"  {_c('✔', Color.GREEN)} {msg}")


def _warning(msg: str) -> None:
    print(f"  {_c('⚠', Color.YELLOW)} {msg}")


def _error(msg: str) -> None:
    print(f"  {_c('✘', Color.RED)} {msg}")


def _info(msg: str) -> None:
    print(f"  {_c('ℹ', Color.BLUE)} {msg}")


def _dim(msg: str) -> None:
    print(f"  {_c(msg, Color.DIM)}")


# ══════════════════════════════════════════════════════════════════
#  COMMAND: info — Tampilkan informasi project
# ══════════════════════════════════════════════════════════════════

def cmd_info(args: argparse.Namespace) -> None:
    """Tampilkan informasi lengkap tentang project dan environment."""
    _header("Project Information")

    # Python info
    py_ver = platform.python_version()
    py_impl = platform.python_implementation()
    _info(f"Python       : {py_ver} ({py_impl})")
    _info(f"Platform     : {platform.system()} {platform.release()}")
    _info(f"Architecture : {platform.machine()}")
    _info(f"Project Root : {PROJECT_ROOT}")

    # Venv detection
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        _success(f"Virtual Env  : {venv}")
    else:
        _warning("Virtual Env  : Tidak aktif! Jalankan `source .venv/bin/activate`")

    # .env status
    if ENV_FILE.exists():
        _success(f".env file    : Ditemukan ({ENV_FILE.stat().st_size} bytes)")
    else:
        _warning(".env file    : Tidak ditemukan — gunakan `python devtoolkit.py env init`")

    # Database
    if DB_FILE.exists():
        size_kb = DB_FILE.stat().st_size / 1024
        _success(f"Database     : {DB_FILE.name} ({size_kb:.1f} KB)")
    else:
        _info("Database     : Belum ada (akan dibuat saat server pertama kali jalan)")

    # Modules
    modules_dir = APP_DIR / "modules"
    if modules_dir.exists():
        modules = [
            d.name for d in modules_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        ]
        _info(f"Modules      : {', '.join(modules) if modules else 'Tidak ada'}")

    # Dependencies
    if REQUIREMENTS_FILE.exists():
        deps = [
            line.strip() for line in REQUIREMENTS_FILE.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        _info(f"Dependencies : {len(deps)} packages")

    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: doctor — Diagnosa kesehatan project
# ══════════════════════════════════════════════════════════════════

def cmd_doctor(args: argparse.Namespace) -> None:
    """Jalankan diagnosa kesehatan project secara menyeluruh."""
    _header("Project Health Check 🩺")
    issues: list[str] = []
    checks_passed = 0
    checks_total = 0

    def _check(name: str, condition: bool, fix_hint: str = "") -> None:
        nonlocal checks_passed, checks_total
        checks_total += 1
        if condition:
            checks_passed += 1
            _success(name)
        else:
            _error(name)
            if fix_hint:
                _dim(f"    Fix: {fix_hint}")
            issues.append(name)

    # 1. Python version
    py_major, py_minor = sys.version_info[:2]
    _check(
        f"Python >= 3.10 (saat ini: {py_major}.{py_minor})",
        (py_major, py_minor) >= (3, 10),
        "Upgrade Python ke versi 3.10 atau lebih baru.",
    )

    # 2. Virtual environment
    _check(
        "Virtual environment aktif",
        os.environ.get("VIRTUAL_ENV") is not None,
        "Jalankan: source .venv/bin/activate",
    )

    # 3. .env file
    _check(
        ".env file ada",
        ENV_FILE.exists(),
        "Jalankan: python devtoolkit.py env init",
    )

    # 4. Required dirs
    for d in [APP_DIR, TESTS_DIR, ALEMBIC_DIR]:
        _check(f"Direktori {d.name}/ ada", d.is_dir())

    # 5. Cek secret key aman
    if ENV_FILE.exists():
        env_content = ENV_FILE.read_text()
        default_key = "your-super-secret-key-change-this-in-production"
        _check(
            "SECRET_KEY sudah diubah dari default",
            default_key not in env_content,
            "Jalankan: python devtoolkit.py gen secret",
        )

        default_api_key = "demo-api-key-12345"
        _check(
            "API_KEY sudah diubah dari default",
            default_api_key not in env_content,
            "Jalankan: python devtoolkit.py gen apikey",
        )

    # 6. Cek dependensi terinstall
    critical_pkgs = ["fastapi", "uvicorn", "sqlalchemy", "pydantic", "alembic"]
    for pkg in critical_pkgs:
        try:
            importlib.import_module(pkg)
            _check(f"Package '{pkg}' terinstall", True)
        except ImportError:
            _check(
                f"Package '{pkg}' terinstall",
                False,
                f"pip install {pkg}",
            )

    # 7. Database connectivity
    if DB_FILE.exists():
        try:
            conn = sqlite3.connect(str(DB_FILE))
            conn.execute("SELECT 1")
            conn.close()
            _check("Database SQLite bisa diakses", True)
        except Exception as e:
            _check("Database SQLite bisa diakses", False, str(e))

    # 8. Port 8000 availability
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        port_free = s.connect_ex(("127.0.0.1", 8000)) != 0
    _check(
        "Port 8000 tersedia",
        port_free,
        "Port 8000 sudah dipakai. Kill proses atau gunakan port lain.",
    )

    # Summary
    print()
    if issues:
        _warning(f"Score: {checks_passed}/{checks_total} — Ada {len(issues)} masalah yang perlu diperbaiki.")
    else:
        _success(f"Score: {checks_passed}/{checks_total} — Semua pemeriksaan lulus! 🎉")
    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: serve — Jalankan development server
# ══════════════════════════════════════════════════════════════════

def cmd_serve(args: argparse.Namespace) -> None:
    """Jalankan development server dengan konfigurasi optimal."""
    _header("Starting Development Server 🚀")

    host = args.host
    port = args.port
    workers = args.workers
    reload_flag = not args.no_reload

    _info(f"Host    : {host}")
    _info(f"Port    : {port}")
    _info(f"Reload  : {'Ya' if reload_flag else 'Tidak'}")
    _info(f"Workers : {workers}")
    print()

    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", host,
        "--port", str(port),
    ]
    if reload_flag:
        cmd.extend(["--reload", "--reload-dir", str(APP_DIR)])
    if workers > 1 and not reload_flag:
        cmd.extend(["--workers", str(workers)])

    _info(f"Command : {' '.join(cmd)}")
    print()

    try:
        process = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        sys.exit(process.returncode)
    except KeyboardInterrupt:
        print()
        _info("Server dihentikan.")


# ══════════════════════════════════════════════════════════════════
#  COMMAND: db — Database operations
# ══════════════════════════════════════════════════════════════════

def cmd_db(args: argparse.Namespace) -> None:
    """Operasi database: info, tables, query, reset, backup, vacuum."""
    action = args.action

    if action == "info":
        _db_info()
    elif action == "tables":
        _db_tables()
    elif action == "query":
        _db_query(args.sql)
    elif action == "reset":
        _db_reset(args.force)
    elif action == "backup":
        _db_backup()
    elif action == "vacuum":
        _db_vacuum()
    elif action == "migrate":
        _db_migrate(args.message)
    else:
        _error(f"Unknown db action: {action}")


def _db_info() -> None:
    """Tampilkan informasi database."""
    _header("Database Info")
    if not DB_FILE.exists():
        _warning("Database file belum ada.")
        return

    size_kb = DB_FILE.stat().st_size / 1024
    _info(f"File     : {DB_FILE}")
    _info(f"Size     : {size_kb:.1f} KB")

    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    _info(f"Tables   : {len(tables)}")
    for t in tables:
        conn = sqlite3.connect(str(DB_FILE))
        count = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]  # noqa: S608
        conn.close()
        _dim(f"    → {t} ({count} rows)")
    print()


def _db_tables() -> None:
    """List semua tabel dan schema."""
    _header("Database Tables & Schema")
    if not DB_FILE.exists():
        _warning("Database file belum ada.")
        return

    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    for table_name in tables:
        print(f"\n  {_c(table_name, Color.BOLD + Color.MAGENTA)}")
        pragma = conn.execute(f"PRAGMA table_info([{table_name}])").fetchall()
        for col in pragma:
            cid, name, col_type, notnull, default_val, pk = col
            markers = []
            if pk:
                markers.append(_c("PK", Color.YELLOW))
            if notnull:
                markers.append(_c("NOT NULL", Color.RED))
            if default_val is not None:
                markers.append(_c(f"DEFAULT={default_val}", Color.DIM))
            marker_str = f" [{', '.join(markers)}]" if markers else ""
            _dim(f"    {name:<25} {col_type:<15}{marker_str}")

    conn.close()
    print()


def _db_query(sql: str | None) -> None:
    """Eksekusi SQL query ad-hoc."""
    _header("Database Query")
    if not sql:
        _error("SQL query tidak boleh kosong. Gunakan: --sql \"SELECT ...\"")
        return
    if not DB_FILE.exists():
        _warning("Database file belum ada.")
        return

    # Safety check — hanya izinkan SELECT
    normalized = sql.strip().upper()
    if not normalized.startswith("SELECT") and not normalized.startswith("PRAGMA"):
        _error("Hanya query SELECT dan PRAGMA yang diizinkan via toolkit.")
        _dim("Untuk operasi DML/DDL, gunakan alat database khusus.")
        return

    try:
        conn = sqlite3.connect(str(DB_FILE))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        rows = cursor.fetchall()

        if not rows:
            _info("Query berhasil, 0 rows returned.")
        else:
            columns = rows[0].keys()
            # Print header
            header = " | ".join(f"{col:<20}" for col in columns)
            print(f"\n  {_c(header, Color.BOLD)}")
            print(f"  {'─' * len(header)}")
            # Print rows (max 50)
            for i, row in enumerate(rows[:50]):
                vals = " | ".join(f"{str(row[col]):<20}" for col in columns)
                print(f"  {vals}")
            if len(rows) > 50:
                _dim(f"    ... dan {len(rows) - 50} rows lainnya (total: {len(rows)})")
            print(f"\n  {_c(f'{len(rows)} rows returned', Color.GREEN)}")

        conn.close()
    except Exception as e:
        _error(f"Query error: {e}")
    print()


def _db_reset(force: bool) -> None:
    """Reset database (hapus dan buat ulang)."""
    _header("Database Reset")
    if not force:
        _warning("Operasi ini akan MENGHAPUS semua data!")
        _info("Tambahkan --force untuk konfirmasi.")
        return

    if DB_FILE.exists():
        # Backup dulu
        _db_backup()
        DB_FILE.unlink()
        # Hapus WAL & SHM juga
        wal = DB_FILE.with_suffix(".db-wal")
        shm = DB_FILE.with_suffix(".db-shm")
        if wal.exists():
            wal.unlink()
        if shm.exists():
            shm.unlink()
        _success("Database file dihapus.")
    else:
        _info("Database file tidak ditemukan, tidak ada yang perlu dihapus.")

    # Recreate tables
    try:
        subprocess.run(
            [sys.executable, "-c",
             "from app.core.database import Base, engine; Base.metadata.create_all(bind=engine)"],
            cwd=str(PROJECT_ROOT),
            check=True,
        )
        _success("Database baru berhasil dibuat dengan semua tabel.")
    except subprocess.CalledProcessError as e:
        _error(f"Gagal membuat database baru: {e}")
    print()


def _db_backup() -> None:
    """Buat backup database."""
    _header("Database Backup")
    if not DB_FILE.exists():
        _warning("Database file tidak ada, tidak ada yang perlu di-backup.")
        return

    backup_dir = PROJECT_ROOT / "backups"
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"app_backup_{timestamp}.db"

    # Gunakan SQLite backup API untuk konsistensi
    src = sqlite3.connect(str(DB_FILE))
    dst = sqlite3.connect(str(backup_path))
    src.backup(dst)
    src.close()
    dst.close()

    size_kb = backup_path.stat().st_size / 1024
    _success(f"Backup berhasil: {backup_path} ({size_kb:.1f} KB)")
    print()


def _db_vacuum() -> None:
    """Kompres & optimasi database."""
    _header("Database Vacuum")
    if not DB_FILE.exists():
        _warning("Database file tidak ada.")
        return

    before = DB_FILE.stat().st_size
    conn = sqlite3.connect(str(DB_FILE))
    conn.execute("VACUUM")
    conn.close()
    after = DB_FILE.stat().st_size

    saved = before - after
    _success(f"Sebelum : {before / 1024:.1f} KB")
    _success(f"Sesudah : {after / 1024:.1f} KB")
    _success(f"Saved   : {saved / 1024:.1f} KB ({saved * 100 / before:.1f}%)" if before > 0 else "Saved: 0 KB")
    print()


def _db_migrate(message: str | None) -> None:
    """Buat alembic migration baru."""
    _header("Database Migration")
    if not message:
        _error("Pesan migrasi diperlukan. Gunakan: --message \"deskripsi\"")
        return

    try:
        subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", message],
            cwd=str(PROJECT_ROOT),
            check=True,
        )
        _success(f"Migration berhasil dibuat: {message}")

        _info("Jalankan `alembic upgrade head` untuk menerapkan migration.")
    except FileNotFoundError:
        _error("Alembic tidak ditemukan. Install: pip install alembic")
    except subprocess.CalledProcessError as e:
        _error(f"Migration gagal: {e}")
    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: gen — Generator utilitas
# ══════════════════════════════════════════════════════════════════

def cmd_gen(args: argparse.Namespace) -> None:
    """Generator: secret key, API key, password hash, UUID."""
    action = args.action

    if action == "secret":
        _gen_secret(args.length)
    elif action == "apikey":
        _gen_apikey(args.length)
    elif action == "hash":
        _gen_hash(args.password)
    elif action == "uuid":
        _gen_uuid(args.count)
    else:
        _error(f"Unknown gen action: {action}")


def _gen_secret(length: int = 64) -> None:
    """Generate SECRET_KEY yang aman secara kriptografis."""
    _header("Generate Secret Key")
    key = secrets.token_hex(length // 2)
    print(f"\n  {_c(key, Color.GREEN + Color.BOLD)}\n")
    _dim(f"  Panjang: {len(key)} karakter")
    _info("Salin ke .env sebagai SECRET_KEY")
    print()


def _gen_apikey(length: int = 48) -> None:
    """Generate API key yang aman."""
    _header("Generate API Key")
    alphabet = string.ascii_letters + string.digits
    key = "sk-" + "".join(secrets.choice(alphabet) for _ in range(length))
    print(f"\n  {_c(key, Color.GREEN + Color.BOLD)}\n")
    _dim(f"  Panjang: {len(key)} karakter (prefix: sk-)")
    _info("Salin ke .env sebagai API_KEY")
    print()


def _gen_hash(password: str | None) -> None:
    """Generate bcrypt hash dari password."""
    _header("Generate Password Hash")
    if not password:
        _error("Password diperlukan. Gunakan: --password \"yourpassword\"")
        return

    try:
        from passlib.context import CryptContext
        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed = ctx.hash(password)
        print(f"\n  {_c('Plain :', Color.DIM)} {password}")
        print(f"  {_c('Hash  :', Color.DIM)} {_c(hashed, Color.GREEN)}\n")
    except ImportError:
        _error("Package 'passlib' belum terinstall. Jalankan: pip install passlib[bcrypt]")
    print()


def _gen_uuid(count: int = 1) -> None:
    """Generate UUID v4."""
    import uuid as uuid_mod
    _header(f"Generate UUID ({count}x)")
    for _ in range(count):
        print(f"  {_c(str(uuid_mod.uuid4()), Color.GREEN)}")
    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: env — Environment management
# ══════════════════════════════════════════════════════════════════

def cmd_env(args: argparse.Namespace) -> None:
    """Manajemen file .env."""
    action = args.action

    if action == "init":
        _env_init()
    elif action == "show":
        _env_show()
    elif action == "diff":
        _env_diff()
    elif action == "validate":
        _env_validate()
    else:
        _error(f"Unknown env action: {action}")


def _env_init() -> None:
    """Buat .env dari .env.example jika belum ada."""
    _header("Initialize .env")
    if ENV_FILE.exists():
        _warning(".env sudah ada. Tidak akan di-overwrite.")
        _info("Hapus .env terlebih dahulu jika ingin membuat ulang.")
        return

    if not ENV_EXAMPLE.exists():
        _error(".env.example tidak ditemukan!")
        return

    content = ENV_EXAMPLE.read_text()

    # Auto-generate secret key
    new_secret = secrets.token_hex(32)
    content = content.replace(
        "your-super-secret-key-change-this-in-production",
        new_secret,
    )

    # Auto-generate API key
    alphabet = string.ascii_letters + string.digits
    new_api_key = "sk-" + "".join(secrets.choice(alphabet) for _ in range(48))
    content = content.replace("demo-api-key-12345", new_api_key)

    ENV_FILE.write_text(content)
    _success(f".env berhasil dibuat dari .env.example")
    _success("SECRET_KEY dan API_KEY sudah di-generate secara otomatis.")
    print()


def _env_show() -> None:
    """Tampilkan isi .env (dengan masking secret values)."""
    _header("Environment Variables")
    if not ENV_FILE.exists():
        _warning(".env tidak ditemukan.")
        return

    sensitive_keys = {"SECRET_KEY", "API_KEY", "DATABASE_URL", "PASSWORD"}

    for line in ENV_FILE.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            _dim(f"  {line}")
            continue

        if "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if any(sk in key.upper() for sk in sensitive_keys):
                masked = value[:4] + "•" * max(0, len(value) - 8) + value[-4:] if len(value) > 8 else "••••••"
                print(f"  {_c(key, Color.CYAN)} = {_c(masked, Color.YELLOW)}")
            else:
                print(f"  {_c(key, Color.CYAN)} = {value}")
        else:
            _dim(f"  {line}")
    print()


def _env_diff() -> None:
    """Bandingkan .env dengan .env.example — temukan variabel yang hilang."""
    _header("Environment Diff")
    if not ENV_FILE.exists():
        _error(".env tidak ditemukan.")
        return
    if not ENV_EXAMPLE.exists():
        _error(".env.example tidak ditemukan.")
        return

    def _parse_keys(filepath: Path) -> set[str]:
        keys = set()
        for line in filepath.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                keys.add(key)
        return keys

    example_keys = _parse_keys(ENV_EXAMPLE)
    env_keys = _parse_keys(ENV_FILE)

    missing = example_keys - env_keys
    extra = env_keys - example_keys

    if missing:
        _warning(f"Variabel di .env.example tapi TIDAK ADA di .env ({len(missing)}):")
        for k in sorted(missing):
            _error(f"  - {k}")

    if extra:
        _info(f"Variabel di .env tapi TIDAK ADA di .env.example ({len(extra)}):")
        for k in sorted(extra):
            _dim(f"  + {k}")

    if not missing and not extra:
        _success("Semua variabel cocok! 🎉")

    print()


def _env_validate() -> None:
    """Validasi nilai-nilai penting di .env."""
    _header("Environment Validation")
    if not ENV_FILE.exists():
        _error(".env tidak ditemukan.")
        return

    issues: list[str] = []
    env_vars: dict[str, str] = {}

    for line in ENV_FILE.read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, value = stripped.partition("=")
            env_vars[key.strip()] = value.strip().strip('"').strip("'")

    # Validasi SECRET_KEY
    sk = env_vars.get("SECRET_KEY", "")
    if not sk or "change-this" in sk.lower():
        _error("SECRET_KEY masih default / kosong!")
        issues.append("SECRET_KEY")
    elif len(sk) < 32:
        _warning(f"SECRET_KEY terlalu pendek ({len(sk)} chars, rekomendasi >= 32)")
    else:
        _success(f"SECRET_KEY valid ({len(sk)} chars)")

    # Validasi API_KEY
    ak = env_vars.get("API_KEY", "")
    if not ak or ak == "demo-api-key-12345":
        _error("API_KEY masih default!")
        issues.append("API_KEY")
    elif len(ak) < 32:
        _warning(f"API_KEY terlalu pendek ({len(ak)} chars)")
    else:
        _success(f"API_KEY valid ({len(ak)} chars)")

    # Validasi DATABASE_URL
    db_url = env_vars.get("DATABASE_URL", "")
    if not db_url:
        _error("DATABASE_URL tidak ditemukan!")
        issues.append("DATABASE_URL")
    else:
        _success(f"DATABASE_URL: {db_url[:30]}...")

    # Validasi ACCESS_TOKEN_EXPIRE_MINUTES
    expire = env_vars.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    try:
        exp_int = int(expire)
        if exp_int < 5:
            _warning(f"ACCESS_TOKEN_EXPIRE_MINUTES terlalu kecil ({exp_int} min)")
        elif exp_int > 1440:
            _warning(f"ACCESS_TOKEN_EXPIRE_MINUTES terlalu besar ({exp_int} min = {exp_int // 60} jam)")
        else:
            _success(f"ACCESS_TOKEN_EXPIRE_MINUTES: {exp_int} min")
    except ValueError:
        _error(f"ACCESS_TOKEN_EXPIRE_MINUTES bukan angka: {expire}")

    print()
    if issues:
        _warning(f"{len(issues)} masalah ditemukan.")
    else:
        _success("Semua validasi lulus! ✨")
    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: scaffold — Scaffold module baru
# ══════════════════════════════════════════════════════════════════

def cmd_scaffold(args: argparse.Namespace) -> None:
    """Scaffold module CRUD baru dengan boilerplate lengkap."""
    _header("Scaffold New Module")

    module_name = args.name.lower().strip()
    if not re.match(r"^[a-z][a-z0-9_]*$", module_name):
        _error("Nama module harus alphanumeric lowercase (contoh: 'invoice', 'category').")
        return

    module_dir = APP_DIR / "modules" / module_name

    if module_dir.exists():
        _error(f"Module '{module_name}' sudah ada di {module_dir}")
        return

    module_dir.mkdir(parents=True)
    class_name = module_name.capitalize()

    # __init__.py
    (module_dir / "__init__.py").write_text("")

    # models.py
    models_content = textwrap.dedent(f'''\
        from __future__ import annotations

        from sqlalchemy import Column, Integer, String, Boolean, DateTime
        from sqlalchemy.sql import func

        from app.core.database import Base


        class {class_name}(Base):
            """SQLAlchemy model untuk {class_name}."""

            __tablename__ = "{module_name}s"

            id = Column(Integer, primary_key=True, index=True, autoincrement=True)
            name = Column(String(255), nullable=False, index=True)
            description = Column(String(1000), nullable=True)
            is_active = Column(Boolean, default=True, nullable=False)
            created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
            updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

            def __repr__(self) -> str:
                return f"<{class_name}(id={{self.id}}, name={{self.name!r}})>"
    ''')
    (module_dir / "models.py").write_text(models_content)

    # schemas.py
    schemas_content = textwrap.dedent(f'''\
        from __future__ import annotations

        from pydantic import BaseModel, Field
        from typing import Optional
        from datetime import datetime


        class {class_name}Base(BaseModel):
            """Schema dasar untuk {class_name}."""

            name: str = Field(..., min_length=1, max_length=255, description="Nama {module_name}")
            description: Optional[str] = Field(None, max_length=1000, description="Deskripsi {module_name}")


        class {class_name}Create({class_name}Base):
            """Schema untuk membuat {class_name} baru."""
            pass


        class {class_name}Update(BaseModel):
            """Schema untuk mengupdate {class_name} (semua field opsional)."""

            name: Optional[str] = Field(None, min_length=1, max_length=255)
            description: Optional[str] = Field(None, max_length=1000)
            is_active: Optional[bool] = None


        class {class_name}Response({class_name}Base):
            """Schema response untuk {class_name}."""

            id: int
            is_active: bool
            created_at: datetime
            updated_at: datetime

            model_config = {{"from_attributes": True}}
    ''')
    (module_dir / "schemas.py").write_text(schemas_content)

    # service.py
    service_content = textwrap.dedent(f'''\
        from __future__ import annotations

        from sqlalchemy.orm import Session
        from typing import Optional

        from app.modules.{module_name}.models import {class_name}
        from app.modules.{module_name}.schemas import {class_name}Create, {class_name}Update


        def get_{module_name}_list(
            db: Session,
            skip: int = 0,
            limit: int = 20,
            search: Optional[str] = None,
        ) -> tuple[list[{class_name}], int]:
            """
            Ambil daftar {module_name} dengan paginasi dan pencarian.

            Returns:
                Tuple (list of {class_name}, total count).
            """
            query = db.query({class_name}).filter({class_name}.is_active == True)  # noqa: E712

            if search:
                query = query.filter({class_name}.name.ilike(f"%{{search}}%"))

            total = query.count()
            items = query.offset(skip).limit(limit).all()
            return items, total


        def get_{module_name}_by_id(db: Session, {module_name}_id: int) -> Optional[{class_name}]:
            """Ambil satu {module_name} berdasarkan ID."""
            return db.query({class_name}).filter(
                {class_name}.id == {module_name}_id,
                {class_name}.is_active == True,  # noqa: E712
            ).first()


        def create_{module_name}(db: Session, payload: {class_name}Create) -> {class_name}:
            """Buat {module_name} baru."""
            db_item = {class_name}(**payload.model_dump())
            db.add(db_item)
            db.commit()
            db.refresh(db_item)
            return db_item


        def update_{module_name}(
            db: Session,
            {module_name}_id: int,
            payload: {class_name}Update,
        ) -> Optional[{class_name}]:
            """Update {module_name} berdasarkan ID."""
            db_item = get_{module_name}_by_id(db, {module_name}_id)
            if not db_item:
                return None

            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_item, key, value)

            db.commit()
            db.refresh(db_item)
            return db_item


        def delete_{module_name}(db: Session, {module_name}_id: int) -> bool:
            """Soft-delete {module_name} berdasarkan ID."""
            db_item = db.query({class_name}).filter({class_name}.id == {module_name}_id).first()
            if not db_item:
                return False

            db_item.is_active = False
            db.commit()
            return True
    ''')
    (module_dir / "service.py").write_text(service_content)

    # routes.py
    routes_content = textwrap.dedent(f'''\
        from __future__ import annotations

        from fastapi import APIRouter, Depends, HTTPException, Query
        from sqlalchemy.orm import Session

        from app.core.database import get_db
        from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
        from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
        from app.modules.{module_name} import service
        from app.modules.{module_name}.schemas import (
            {class_name}Create,
            {class_name}Response,
            {class_name}Update,
        )

        router = APIRouter(prefix="/{module_name}s", tags=["{class_name}s"])


        @router.get("", response_model=APIResponse, summary="List semua {module_name}")
        def list_{module_name}s(
            skip: int = Query(0, ge=0, description="Offset"),
            limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
            search: str | None = Query(None, description="Search by name"),
            db: Session = Depends(get_db),
        ):
            """Ambil daftar {module_name} dengan paginasi."""
            items, total = service.get_{module_name}_list(db, skip=skip, limit=limit, search=search)
            return StandardJSONResponse.success(
                data=[{class_name}Response.model_validate(i) for i in items],
                message=f"Berhasil mengambil {{len(items)}} {module_name}.",
                meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
            )


        @router.get("/{{id}}", response_model=APIResponse, summary="Get {module_name} by ID")
        def get_{module_name}(id: int, db: Session = Depends(get_db)):
            """Ambil detail {module_name} berdasarkan ID."""
            item = service.get_{module_name}_by_id(db, id)
            if not item:
                raise HTTPException(status_code=404, detail="{class_name} tidak ditemukan.")
            return StandardJSONResponse.success(
                data={class_name}Response.model_validate(item),
                message="{class_name} berhasil ditemukan.",
            )


        @router.post("", response_model=APIResponse, status_code=201, summary="Create {module_name}")
        def create_{module_name}(payload: {class_name}Create, db: Session = Depends(get_db)):
            """Buat {module_name} baru."""
            item = service.create_{module_name}(db, payload)
            return StandardJSONResponse.success(
                data={class_name}Response.model_validate(item),
                message="{class_name} berhasil dibuat.",
            )


        @router.put("/{{id}}", response_model=APIResponse, summary="Update {module_name}")
        def update_{module_name}(id: int, payload: {class_name}Update, db: Session = Depends(get_db)):
            """Update {module_name} berdasarkan ID."""
            item = service.update_{module_name}(db, id, payload)
            if not item:
                raise HTTPException(status_code=404, detail="{class_name} tidak ditemukan.")
            return StandardJSONResponse.success(
                data={class_name}Response.model_validate(item),
                message="{class_name} berhasil diupdate.",
            )


        @router.delete("/{{id}}", response_model=APIResponse, summary="Delete {module_name}")
        def delete_{module_name}(id: int, db: Session = Depends(get_db)):
            """Soft-delete {module_name} berdasarkan ID."""
            success = service.delete_{module_name}(db, id)
            if not success:
                raise HTTPException(status_code=404, detail="{class_name} tidak ditemukan.")
            return StandardJSONResponse.success(message="{class_name} berhasil dihapus.")
    ''')
    (module_dir / "routes.py").write_text(routes_content)

    _success(f"Module '{module_name}' berhasil di-scaffold! 🎉")
    _info(f"Lokasi: {module_dir}")
    print()
    _info("File yang dibuat:")
    for f in sorted(module_dir.iterdir()):
        _dim(f"    📄 {f.name}")

    print()
    _info("Langkah selanjutnya:")
    _dim(f"    1. Register router di app/main.py:")
    _dim(f"       from app.modules.{module_name}.routes import router as {module_name}_router")
    _dim(f"       app.include_router({module_name}_router)")
    _dim(f"    2. Buat migration: python devtoolkit.py db migrate --message \"add {module_name} table\"")
    _dim(f"    3. Apply migration: alembic upgrade head")
    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: test — Jalankan tests
# ══════════════════════════════════════════════════════════════════

def cmd_test(args: argparse.Namespace) -> None:
    """Jalankan test suite dengan pytest."""
    _header("Running Tests 🧪")

    cmd = [sys.executable, "-m", "pytest"]

    if args.verbose:
        cmd.append("-v")
    if args.coverage:
        cmd.extend(["--cov=app", "--cov-report=term-missing"])
    if args.path:
        cmd.append(args.path)
    else:
        cmd.append(str(TESTS_DIR))
    if args.keyword:
        cmd.extend(["-k", args.keyword])

    _info(f"Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    sys.exit(result.returncode)


# ══════════════════════════════════════════════════════════════════
#  COMMAND: lint — Analisis kualitas kode
# ══════════════════════════════════════════════════════════════════

def cmd_lint(args: argparse.Namespace) -> None:
    """Analisis kualitas kode dan keamanan."""
    _header("Code Quality Analysis 🔍")

    target = args.path or str(APP_DIR)
    results: dict[str, Any] = {
        "files_analyzed": 0,
        "total_lines": 0,
        "issues": [],
        "stats": {
            "functions": 0,
            "classes": 0,
            "imports": 0,
            "todos": 0,
            "type_hints": 0,
            "docstrings": 0,
            "long_lines": 0,
        },
    }

    target_path = Path(target)
    py_files = list(target_path.rglob("*.py")) if target_path.is_dir() else [target_path]
    py_files = [f for f in py_files if "__pycache__" not in str(f) and ".venv" not in str(f)]

    for filepath in py_files:
        results["files_analyzed"] += 1
        content = filepath.read_text(errors="ignore")
        lines = content.splitlines()
        results["total_lines"] += len(lines)

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Long lines (> 120 chars)
            if len(line) > 120:
                results["stats"]["long_lines"] += 1

            # Function/class count
            if stripped.startswith("def "):
                results["stats"]["functions"] += 1
            if stripped.startswith("class "):
                results["stats"]["classes"] += 1

            # Import count
            if stripped.startswith(("import ", "from ")):
                results["stats"]["imports"] += 1

            # TODO/FIXME/HACK detection
            if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", stripped, re.IGNORECASE):
                results["stats"]["todos"] += 1
                results["issues"].append({
                    "file": str(filepath.relative_to(PROJECT_ROOT)),
                    "line": i,
                    "type": "TODO",
                    "message": stripped[:80],
                })

            # Type hint detection (pada function defs)
            if stripped.startswith("def ") and "->" in stripped:
                results["stats"]["type_hints"] += 1

            # Docstring detection (simple heuristic)
            if '"""' in stripped or "'''" in stripped:
                results["stats"]["docstrings"] += 1

            # Security concerns
            if "eval(" in stripped or "exec(" in stripped:
                results["issues"].append({
                    "file": str(filepath.relative_to(PROJECT_ROOT)),
                    "line": i,
                    "type": "SECURITY",
                    "message": f"Penggunaan eval/exec terdeteksi: {stripped[:60]}",
                })

            # Hardcoded secrets pattern
            if re.search(r'(password|secret|token|api.?key)\s*=\s*["\'][^"\']{8,}["\']', stripped, re.IGNORECASE):
                results["issues"].append({
                    "file": str(filepath.relative_to(PROJECT_ROOT)),
                    "line": i,
                    "type": "SECURITY",
                    "message": f"Kemungkinan hardcoded secret: {stripped[:60]}",
                })

    # Print results
    _info(f"Files analyzed   : {results['files_analyzed']}")
    _info(f"Total lines      : {results['total_lines']:,}")
    print()

    stats = results["stats"]
    print(f"  📊 {_c('Code Statistics', Color.BOLD)}")
    _dim(f"    Classes          : {stats['classes']}")
    _dim(f"    Functions        : {stats['functions']}")
    _dim(f"    Imports          : {stats['imports']}")
    _dim(f"    Type hints (->)  : {stats['type_hints']}")
    _dim(f"    Docstrings       : {stats['docstrings']}")
    _dim(f"    Long lines (>120): {stats['long_lines']}")
    _dim(f"    TODO/FIXME/HACK  : {stats['todos']}")

    if results["issues"]:
        print(f"\n  🚨 {_c('Issues Found', Color.BOLD + Color.RED)}")
        for issue in results["issues"][:20]:
            icon = "🔒" if issue["type"] == "SECURITY" else "📝"
            print(f"    {icon} {_c(issue['file'], Color.CYAN)}:{issue['line']} — {issue['message']}")
        if len(results["issues"]) > 20:
            _dim(f"    ... dan {len(results['issues']) - 20} lainnya")
    else:
        _success("Tidak ada issue yang ditemukan! 🎉")

    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: routes — Tampilkan semua API routes
# ══════════════════════════════════════════════════════════════════

def cmd_routes(args: argparse.Namespace) -> None:
    """Tampilkan semua API routes yang terdaftar."""
    _header("Registered API Routes 🛣️")

    try:
        from app.main import app as fastapi_app

        routes_info: list[dict[str, Any]] = []
        for route in fastapi_app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                methods = ", ".join(sorted(route.methods - {"HEAD", "OPTIONS"}))
                endpoint_name = route.endpoint.__name__ if route.endpoint else "N/A"
                tags = getattr(route, "tags", []) or []
                routes_info.append({
                    "methods": methods,
                    "path": route.path,
                    "name": endpoint_name,
                    "tags": ", ".join(tags) if tags else "-",
                })

        if not routes_info:
            _warning("Tidak ada routes yang ditemukan.")
            return

        # Group by tag
        grouped: dict[str, list] = {}
        for r in routes_info:
            tag = r["tags"]
            grouped.setdefault(tag, []).append(r)

        for tag, routes in grouped.items():
            print(f"\n  {_c(f'[{tag}]', Color.BOLD + Color.MAGENTA)}")
            for r in routes:
                method_color = {
                    "GET": Color.GREEN,
                    "POST": Color.BLUE,
                    "PUT": Color.YELLOW,
                    "DELETE": Color.RED,
                    "PATCH": Color.CYAN,
                }.get(r["methods"], Color.WHITE)

                method_str = _c(r['methods'].ljust(8), method_color)
                path_str = r['path'].ljust(30)
                name_str = _c(r['name'], Color.DIM)
                print(f"    {method_str} {path_str} → {name_str}")

        _info(f"\nTotal: {len(routes_info)} routes")

    except Exception as e:
        _error(f"Gagal memuat routes: {e}")
        _dim("Pastikan aplikasi bisa diimport tanpa error.")

    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: deps — Dependency management
# ══════════════════════════════════════════════════════════════════

def cmd_deps(args: argparse.Namespace) -> None:
    """Manajemen dependencies."""
    action = args.action

    if action == "check":
        _deps_check()
    elif action == "outdated":
        _deps_outdated()
    elif action == "tree":
        _deps_tree()
    elif action == "install":
        _deps_install()
    else:
        _error(f"Unknown deps action: {action}")


def _deps_check() -> None:
    """Cek apakah semua dependensi dari requirements.txt terinstall."""
    _header("Dependency Check")
    if not REQUIREMENTS_FILE.exists():
        _error("requirements.txt tidak ditemukan.")
        return

    deps = [
        line.strip() for line in REQUIREMENTS_FILE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

    missing: list[str] = []
    installed: list[str] = []

    for dep in deps:
        # Ambil nama package (tanpa versi/extras)
        pkg_name = re.split(r"[>=<!\[\]]", dep)[0].strip()
        import_name = pkg_name.replace("-", "_").lower()

        try:
            importlib.import_module(import_name)
            installed.append(dep)
            _success(f"{dep}")
        except ImportError:
            # Coba nama alternatif (beberapa package punya nama import berbeda)
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "show", pkg_name],
                    capture_output=True, text=True,
                )
                if result.returncode == 0:
                    installed.append(dep)
                    _success(f"{dep}")
                else:
                    missing.append(dep)
                    _error(f"{dep}")
            except Exception:
                missing.append(dep)
                _error(f"{dep}")

    print()
    if missing:
        _warning(f"{len(missing)} package belum terinstall.")
        _info(f"Fix: pip install {' '.join(missing)}")
    else:
        _success(f"Semua {len(installed)} dependencies terinstall! ✨")
    print()


def _deps_outdated() -> None:
    """Cek package yang outdated."""
    _header("Outdated Dependencies")
    _info("Mengecek versi terbaru (membutuhkan koneksi internet)...")
    print()

    result = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        _error(f"pip gagal: {result.stderr}")
        return

    try:
        packages = json.loads(result.stdout)
    except json.JSONDecodeError:
        _warning("Tidak bisa parse output pip.")
        return

    if not packages:
        _success("Semua packages sudah versi terbaru! 🎉")
    else:
        # Read our requirements to filter relevant packages
        our_deps: set[str] = set()
        if REQUIREMENTS_FILE.exists():
            for line in REQUIREMENTS_FILE.read_text().splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    pkg_name = re.split(r"[>=<!\[\]]", stripped)[0].strip().lower()
                    our_deps.add(pkg_name)

        col_pkg = _c('Package'.ljust(25), Color.BOLD)
        col_cur = _c('Current'.ljust(15), Color.BOLD)
        col_lat = _c('Latest', Color.BOLD)
        print(f"  {col_pkg} {col_cur} {col_lat}")
        print(f"  {'─' * 55}")

        relevant_count = 0
        for pkg in packages:
            name = pkg["name"].lower()
            is_ours = name in our_deps
            marker = _c(" ◀ (in requirements)", Color.YELLOW) if is_ours else ""
            if is_ours:
                relevant_count += 1
            print(f"  {pkg['name']:<25} {pkg['version']:<15} {_c(pkg['latest_version'], Color.GREEN)}{marker}")

        _info(f"\n{len(packages)} packages outdated ({relevant_count} di requirements.txt)")
    print()


def _deps_tree() -> None:
    """Tampilkan dependency tree."""
    _header("Dependency Tree")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pipdeptree", "--warn", "silence"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            # Fallback to pip
            _warning("pipdeptree tidak tersedia, menggunakan pip list...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=columns"],
                capture_output=True, text=True,
            )
            print(result.stdout)
    except Exception as e:
        _error(f"Gagal: {e}")
    print()


def _deps_install() -> None:
    """Install semua dependencies dari requirements.txt."""
    _header("Installing Dependencies")
    if not REQUIREMENTS_FILE.exists():
        _error("requirements.txt tidak ditemukan.")
        return

    _info(f"Menginstall dari {REQUIREMENTS_FILE}...")
    print()

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
        cwd=str(PROJECT_ROOT),
    )

    if result.returncode == 0:
        _success("Semua dependencies berhasil diinstall! 🎉")
    else:
        _error("Ada masalah saat instalasi. Periksa output di atas.")
    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: user — User management (create, reset-password, list, delete)
# ══════════════════════════════════════════════════════════════════

def cmd_user(args: argparse.Namespace) -> None:
    """Manajemen user: create, reset-password, list, delete."""
    action = args.action

    if action == "create":
        _user_create(
            username=args.username,
            email=args.email,
            full_name=args.full_name,
            password=args.password,
            inactive=args.inactive,
        )
    elif action == "reset-password":
        _user_reset_password(
            identifier=args.identifier,
            password=args.password,
            no_validate=args.no_validate,
        )
    elif action == "list":
        _user_list(only_active=args.active_only)
    elif action == "delete":
        _user_delete(args.identifier)
    else:
        _error(f"Unknown user action: {action}")


def _get_user_session():
    """
    Buka factory session SQLAlchemy ke database aplikasi.

    Returns:
        Tuple (SessionLocal, engine) — factory untuk membuat session baru.

    Raises:
        ImportError: jika SQLAlchemy atau app modules tidak bisa di-import.
    """
    # Pastikan project root ada di sys.path agar `app.*` bisa di-import
    project_root = str(PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Muat .env agar settings.DATABASE_URL ter-resolve dengan benar
    if ENV_FILE.exists():
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv(ENV_FILE, override=False)
        except ImportError:
            # dotenv opsional; settings.py biasanya sudah load sendiri
            pass

    from sqlalchemy.orm import sessionmaker  # noqa: PLC0415
    from app.core.config import settings  # noqa: PLC0415
    from app.core.database import engine  # noqa: PLC0415

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal, engine


def _prompt(question: str, default: str = "", password: bool = False) -> str:
    """
    Prompt interaktif dengan nilai default. Mendukung input tersembunyi
    untuk password (fallback ke input biasa bila getpass tidak tersedia).
    """
    suffix = f" [{default}]" if default else ""
    prompt_text = f"  {question}{suffix}: "

    if password:
        try:
            value = getpass.getpass(prompt_text)
        except (EOFError, KeyboardInterrupt):
            print()
            raise
        return value or default

    try:
        value = input(prompt_text)
    except (EOFError, KeyboardInterrupt):
        print()
        raise
    return value.strip() or default


def _generate_temp_password(length: int = 16) -> str:
    """Generate password acak yang kuat (memenuhi policy aplikasi)."""
    # Pastikan semua kategori password terwakili agar lulus validate_password_strength
    while True:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        # Tambah minimal satu karakter dari tiap kategori
        candidate = (
            secrets.choice(string.ascii_uppercase)
            + secrets.choice(string.ascii_lowercase)
            + secrets.choice(string.digits)
            + secrets.choice("!@#$%^&*")
            + candidate
        )
        try:
            from app.core.security import validate_password_strength  # noqa: PLC0415
            if not validate_password_strength(candidate):
                return candidate[: length + 4]
        except ImportError:
            return candidate[: length + 4]


def _user_create(
    username: str | None,
    email: str | None,
    full_name: str | None,
    password: str | None,
    inactive: bool,
) -> None:
    """Buat user baru. Jika field kosong & bukan --no-input, akan prompt interaktif."""
    _header("Create User 👤")

    interactive = not all([username, email, password])

    # ── Kumpulkan data ──
    if interactive:
        if not username:
            username = _prompt("Username")
        if not email:
            email = _prompt("Email")
        if full_name is None:
            full_name = _prompt("Full name (opsional)", default="")
        if not password:
            print()
            _info("Password policy: min 8 karakter, huruf besar/kecil, angka, spesial.")
            while True:
                pw1 = _prompt("Password", password=True)
                pw2 = _prompt("Konfirmasi password", password=True)
                if pw1 != pw2:
                    _error("Password tidak cocok, coba lagi.")
                    continue
                if not pw1:
                    _error("Password tidak boleh kosong.")
                    continue
                password = pw1
                break

    # ── Validasi dasar ──
    if not username or len(username) < 3:
        _error("Username minimal 3 karakter.")
        return
    if not email or "@" not in email:
        _error("Email tidak valid.")
        return
    if not password:
        _error("Password tidak boleh kosong.")
        return

    # ── Validasi kekuatan password (reuse policy aplikasi) ──
    try:
        from app.core.security import get_password_hash, validate_password_strength  # noqa: PLC0415
    except ImportError as exc:
        _error(f"Tidak bisa import app.core.security: {exc}")
        _info("Pastikan devtoolkit.py dijalankan dari root project & dependencies terinstall.")
        return

    pw_errors = validate_password_strength(password)
    if pw_errors:
        _error("Password tidak memenuhi policy:")
        for err in pw_errors:
            _dim(f"    • {err}")
        return

    # ── Konek DB & buat user ──
    try:
        _ = _get_user_session()
    except Exception as exc:
        _error(f"Gagal koneksi ke database: {exc}")
        return

    from app.modules.user.crud import (  # noqa: PLC0415
        get_user_by_username,
        get_user_by_email,
        create_user,
    )

    db = SessionLocal()
    try:
        if get_user_by_username(db, username):
            _error(f"Username '{username}' sudah dipakai.")
            return
        if get_user_by_email(db, email):
            _error(f"Email '{email}' sudah dipakai.")
            return

        new_user = create_user(
            db,
            {
                "username": username,
                "email": email,
                "full_name": full_name or None,
                "hashed_password": get_password_hash(password),
                "is_active": not inactive,
            },
        )

        _success(f"User berhasil dibuat! ID: {new_user.id}")
        print()
        _dim(f"    Username    : {new_user.username}")
        _dim(f"    Email       : {new_user.email}")
        _dim(f"    Full name   : {new_user.full_name or '-'}")
        _dim(f"    Active      : {new_user.is_active}")
        _dim(f"    Created at  : {new_user.created_at}")
        print()
    except Exception as exc:
        db.rollback()
        _error(f"Gagal membuat user: {exc}")
    finally:
        db.close()


def _user_reset_password(
    identifier: str | None,
    password: str | None,
    no_validate: bool,
) -> None:
    """Reset password user berdasarkan id/username/email."""
    _header("Reset User Password 🔑")

    if not identifier:
        identifier = _prompt("Identifier (id / username / email)")

    if not identifier:
        _error("Identifier wajib diisi.")
        return

    if not password:
        print()
        _info("Password policy: min 8 karakter, huruf besar/kecil, angka, spesial.")
        while True:
            pw1 = _prompt("Password baru", password=True)
            pw2 = _prompt("Konfirmasi password baru", password=True)
            if pw1 != pw2:
                _error("Password tidak cocok, coba lagi.")
                continue
            if not pw1:
                _error("Password tidak boleh kosong.")
                continue
            password = pw1
            break

    # ── Validasi kekuatan ──
    try:
        from app.core.security import get_password_hash, validate_password_strength  # noqa: PLC0415
    except ImportError as exc:
        _error(f"Tidak bisa import app.core.security: {exc}")
        return

    if not no_validate:
        pw_errors = validate_password_strength(password)
        if pw_errors:
            _error("Password tidak memenuhi policy:")
            for err in pw_errors:
                _dim(f"    • {err}")
            if not _confirm("Tetap gunakan password ini?", default=False):
                _info("Dibatalkan.")
                return

    # ── Konek DB ──
    try:
        _ = _get_user_session()
    except Exception as exc:
        _error(f"Gagal koneksi ke database: {exc}")
        return

    from app.modules.user.crud import (  # noqa: PLC0415
        get_user,
        get_user_by_username,
        get_user_by_email,
        update_user,
    )

    db = SessionLocal()
    try:
        # Tentukan user: coba id (int), lalu username, lalu email
        user = None
        if identifier.isdigit():
            user = get_user(db, int(identifier))
        if not user:
            user = get_user_by_username(db, identifier)
        if not user and "@" in identifier:
            user = get_user_by_email(db, identifier)

        if not user:
            _error(f"User '{identifier}' tidak ditemukan.")
            return

        if user.is_deleted:
            _error(f"User '{user.username}' sudah dihapus (soft delete).")
            return

        if not _confirm(f"Reset password untuk '{user.username}' ({user.email})?", default=False):
            _info("Dibatalkan.")
            return

        update_user(db, user.id, {"hashed_password": get_password_hash(password)})

        _success(f"Password untuk user '{user.username}' berhasil direset.")
        _info("User harus login ulang dengan password baru.")
        print()
    except Exception as exc:
        db.rollback()
        _error(f"Gagal reset password: {exc}")
    finally:
        db.close()


def _user_list(only_active: bool) -> None:
    """Tampilkan daftar user di database."""
    _header("User List 📋")

    try:
        _ = _get_user_session()
    except Exception as exc:
        _error(f"Gagal koneksi ke database: {exc}")
        return

    from app.modules.user.crud import get_users  # noqa: PLC0415

    db = SessionLocal()
    try:
        users = get_users(db, skip=0, limit=500)
        if not users:
            _info("Belum ada user di database.")
            return

        # Filter aktif jika diminta
        if only_active:
            users = [u for u in users if u.is_active]

        # Header tabel
        print()
        _c(
            f"  {'ID':<5} {'Username':<20} {'Email':<30} {'Active':<8} {'Created':<20}",
            Color.BOLD,
        )
        _dim("  " + "─" * 86)
        for u in users:
            created = u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "-"
            active_mark = _c("✔", Color.GREEN) if u.is_active else _c("✘", Color.RED)
            deleted_mark = _c(" [deleted]", Color.RED) if u.is_deleted else ""
            print(
                f"  {u.id:<5} {u.username:<20} {u.email:<30} {active_mark:<15} {created:<20}{deleted_mark}"
            )
        print()
        _info(f"Total: {len(users)} user")
        print()
    except Exception as exc:
        _error(f"Gagal membaca data user: {exc}")
    finally:
        db.close()


def _user_delete(identifier: str | None) -> None:
    """Soft-delete user."""
    _header("Delete User 🗑️")

    if not identifier:
        identifier = _prompt("Identifier (id / username / email)")

    if not identifier:
        _error("Identifier wajib diisi.")
        return

    try:
        _ = _get_user_session()
    except Exception as exc:
        _error(f"Gagal koneksi ke database: {exc}")
        return

    from app.modules.user.crud import (  # noqa: PLC0415
        get_user,
        get_user_by_username,
        get_user_by_email,
        delete_user,
    )

    db = SessionLocal()
    try:
        user = None
        if identifier.isdigit():
            user = get_user(db, int(identifier))
        if not user:
            user = get_user_by_username(db, identifier)
        if not user and "@" in identifier:
            user = get_user_by_email(db, identifier)

        if not user:
            _error(f"User '{identifier}' tidak ditemukan.")
            return

        if user.is_deleted:
            _error(f"User '{user.username}' sudah dihapus sebelumnya.")
            return

        if not _confirm(
            f"Yakin ingin SOFT-DELETE user '{user.username}' ({user.email})?",
            default=False,
        ):
            _info("Dibatalkan.")
            return

        delete_user(db, user.id)
        _success(f"User '{user.username}' berhasil di-soft-delete.")
        _info("Data user masih ada di DB (is_deleted=True).")
        print()
    except Exception as exc:
        db.rollback()
        _error(f"Gagal menghapus user: {exc}")
    finally:
        db.close()


def _confirm(question: str, default: bool = False) -> bool:
    """Prompt konfirmasi yes/no. Default di-highlight."""
    suffix = "(Y/n)" if default else "(y/N)"
    try:
        ans = input(f"  {question} {suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not ans:
        return default
    return ans in ("y", "yes")


# ══════════════════════════════════════════════════════════════════
#  COMMAND: security — Security audit
# ══════════════════════════════════════════════════════════════════

def cmd_security(args: argparse.Namespace) -> None:
    """Audit keamanan project."""
    _header("Security Audit 🔐")

    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    # 1. Cek .env di .gitignore
    gitignore = PROJECT_ROOT / ".gitignore"
    if gitignore.exists():
        gi_content = gitignore.read_text()
        if ".env" in gi_content:
            _success(".env ada di .gitignore")
        else:
            issues.append({"type": "CRITICAL", "msg": ".env TIDAK ada di .gitignore!"})
            _error(".env TIDAK ada di .gitignore!")
    else:
        warnings.append({"type": "WARNING", "msg": ".gitignore tidak ditemukan"})

    # 2. Cek SECRET_KEY
    if ENV_FILE.exists():
        env_content = ENV_FILE.read_text()
        if "change-this" in env_content or "your-super-secret" in env_content:
            issues.append({"type": "CRITICAL", "msg": "SECRET_KEY masih menggunakan nilai default!"})
            _error("SECRET_KEY masih default!")
        else:
            _success("SECRET_KEY sudah diubah dari default")

        if "demo-api-key" in env_content:
            issues.append({"type": "HIGH", "msg": "API_KEY masih menggunakan demo key!"})
            _error("API_KEY masih demo!")
        else:
            _success("API_KEY sudah diubah dari demo")

    # 3. Scan hardcoded secrets di source code
    print(f"\n  {_c('Scanning source code...', Color.DIM)}")
    secret_patterns = [
        (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
        (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret"),
        (r'(sk-|pk-|Bearer\s+)[a-zA-Z0-9]{20,}', "Potential API token"),
    ]

    py_files = list(APP_DIR.rglob("*.py"))
    py_files = [f for f in py_files if "__pycache__" not in str(f)]

    for filepath in py_files:
        content = filepath.read_text(errors="ignore")
        for pattern, desc in secret_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                rel_path = filepath.relative_to(PROJECT_ROOT)
                line_num = content[:match.start()].count("\n") + 1
                # Skip jika ini config/example file
                if "config.py" in str(filepath) and "default" in match.group().lower():
                    continue
                warnings.append({
                    "type": "WARNING",
                    "msg": f"{desc} di {rel_path}:{line_num}",
                })

    # 4. Cek DEBUG mode
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.strip().startswith("DEBUG") and "True" in line:
                warnings.append({"type": "WARNING", "msg": "DEBUG=True aktif di .env"})
                _warning("DEBUG mode aktif!")
                break

    # 5. Cek CORS
    if ENV_FILE.exists():
        env_content = ENV_FILE.read_text()
        if 'CORS_ORIGINS="*"' in env_content or "CORS_ORIGINS='*'" in env_content:
            warnings.append({"type": "WARNING", "msg": "CORS mengizinkan semua origin (*)"})

    # Summary
    print()
    if issues:
        print(f"  {_c(f'🚨 {len(issues)} Critical Issues:', Color.BOLD + Color.RED)}")
        for issue in issues:
            _error(f"  [{issue['type']}] {issue['msg']}")

    if warnings:
        print(f"\n  {_c(f'⚠️  {len(warnings)} Warnings:', Color.BOLD + Color.YELLOW)}")
        for w in warnings:
            _warning(f"  [{w['type']}] {w['msg']}")

    if not issues and not warnings:
        _success("Tidak ada masalah keamanan yang ditemukan! 🎉")

    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: clean — Bersihkan file sementara
# ══════════════════════════════════════════════════════════════════

def cmd_clean(args: argparse.Namespace) -> None:
    """Bersihkan file sementara dan cache."""
    _header("Clean Project 🧹")

    cleaned: list[str] = []
    total_size = 0

    patterns = [
        ("__pycache__", "dir"),
        (".pytest_cache", "dir"),
        (".mypy_cache", "dir"),
        (".ruff_cache", "dir"),
        ("*.pyc", "file"),
        ("*.pyo", "file"),
        (".coverage", "file"),
        ("htmlcov", "dir"),
    ]

    for pattern, kind in patterns:
        if kind == "dir":
            dirs = list(PROJECT_ROOT.rglob(pattern))
            dirs = [d for d in dirs if d.is_dir() and ".venv" not in str(d)]
            for d in dirs:
                size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                total_size += size
                if not args.dry_run:
                    shutil.rmtree(d)
                cleaned.append(f"{d.relative_to(PROJECT_ROOT)}/ ({size / 1024:.1f} KB)")
        else:
            files = list(PROJECT_ROOT.rglob(pattern))
            files = [f for f in files if f.is_file() and ".venv" not in str(f)]
            for f in files:
                total_size += f.stat().st_size
                if not args.dry_run:
                    f.unlink()
                cleaned.append(f"{f.relative_to(PROJECT_ROOT)} ({f.stat().st_size / 1024:.1f} KB)")

    if cleaned:
        prefix = "[DRY RUN] " if args.dry_run else ""
        for item in cleaned:
            _success(f"{prefix}Removed: {item}")
        print()
        _info(f"Total freed: {total_size / 1024:.1f} KB")
    else:
        _success("Tidak ada file sementara yang ditemukan.")

    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: loc — Hitung lines of code
# ══════════════════════════════════════════════════════════════════

def cmd_loc(args: argparse.Namespace) -> None:
    """Hitung Lines of Code (LOC) project."""
    _header("Lines of Code 📊")

    target = Path(args.path) if args.path else APP_DIR
    stats: dict[str, dict[str, int]] = {}

    extensions = {".py", ".html", ".css", ".js", ".json", ".yml", ".yaml", ".toml", ".md", ".txt"}

    for filepath in target.rglob("*"):
        if not filepath.is_file():
            continue
        if ".venv" in str(filepath) or "__pycache__" in str(filepath) or ".git" in str(filepath):
            continue

        ext = filepath.suffix.lower()
        if ext not in extensions:
            continue

        try:
            content = filepath.read_text(errors="ignore")
            lines = content.splitlines()
            total = len(lines)
            blank = sum(1 for l in lines if not l.strip())
            comment = sum(
                1 for l in lines
                if l.strip().startswith(("#", "//", "/*", "*", "'''", '"""'))
            )
            code = total - blank - comment
        except Exception:
            continue

        if ext not in stats:
            stats[ext] = {"files": 0, "total": 0, "code": 0, "blank": 0, "comment": 0}

        stats[ext]["files"] += 1
        stats[ext]["total"] += total
        stats[ext]["code"] += code
        stats[ext]["blank"] += blank
        stats[ext]["comment"] += comment

    if not stats:
        _warning("Tidak ada file yang ditemukan.")
        return

    # Print table
    h_ext = _c('Extension'.ljust(12), Color.BOLD)
    h_files = _c('Files'.ljust(8), Color.BOLD)
    h_code = _c('Code'.ljust(10), Color.BOLD)
    h_comment = _c('Comment'.ljust(10), Color.BOLD)
    h_blank = _c('Blank'.ljust(8), Color.BOLD)
    h_total = _c('Total', Color.BOLD)
    print(f"\n  {h_ext} {h_files} {h_code} {h_comment} {h_blank} {h_total}")
    print(f"  {'─' * 58}")

    grand = {"files": 0, "total": 0, "code": 0, "blank": 0, "comment": 0}

    for ext in sorted(stats, key=lambda e: stats[e]["code"], reverse=True):
        s = stats[ext]
        code_col = _c(str(s['code']), Color.GREEN).ljust(19 + len(Color.GREEN) + len(Color.RESET))
        print(f"  {ext:<12} {s['files']:<8} {code_col} {s['comment']:<10} {s['blank']:<8} {s['total']}")
        for k in grand:
            grand[k] += s[k]

    print(f"  {'─' * 58}")
    total_label = _c('TOTAL', Color.BOLD).ljust(12 + len(Color.BOLD) + len(Color.RESET))
    total_code = _c(str(grand['code']), Color.GREEN + Color.BOLD).ljust(19 + len(Color.GREEN) + len(Color.BOLD) + len(Color.RESET))
    print(f"  {total_label} {grand['files']:<8} {total_code} {grand['comment']:<10} {grand['blank']:<8} {grand['total']}")
    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: api — Panggil API endpoints
# ══════════════════════════════════════════════════════════════════

def cmd_api(args: argparse.Namespace) -> None:
    """Panggil API endpoint langsung dari terminal."""
    _header("API Client 📡")

    try:
        import httpx
    except ImportError:
        _error("Package 'httpx' belum terinstall. Install: pip install httpx")
        return

    base = args.base.rstrip("/")
    url = f"{base}{args.endpoint}"
    method = args.method.upper()

    _info(f"{method} {url}")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    if args.apikey:
        headers["X-API-Key"] = args.apikey

    body = None
    if args.data:
        try:
            body = json.loads(args.data)
        except json.JSONDecodeError:
            _error("Data harus berformat JSON valid.")
            return

    try:
        with httpx.Client(timeout=30) as client:
            response = client.request(method, url, headers=headers, json=body)

        # Status
        status_color = Color.GREEN if response.status_code < 400 else Color.RED
        print(f"\n  {_c('Status', Color.BOLD)}: {_c(str(response.status_code), status_color)} "
              f"{response.reason_phrase}")

        # Headers (condensed)
        _dim(f"  Content-Type: {response.headers.get('content-type', 'N/A')}")
        _dim(f"  Response Time: {response.elapsed.total_seconds() * 1000:.0f}ms")

        # Body
        print(f"\n  {_c('Response Body:', Color.BOLD)}")
        try:
            body_json = response.json()
            formatted = json.dumps(body_json, indent=2, ensure_ascii=False)
            for line in formatted.splitlines():
                _dim(f"  {line}")
        except Exception:
            _dim(f"  {response.text[:500]}")

    except httpx.ConnectError:
        _error(f"Tidak bisa terhubung ke {base}")
        _info("Pastikan server sudah berjalan: python devtoolkit.py serve")
    except Exception as e:
        _error(f"Request gagal: {e}")

    print()


# ══════════════════════════════════════════════════════════════════
#  COMMAND: profile — Profil konfigurasi app
# ══════════════════════════════════════════════════════════════════

def cmd_profile(args: argparse.Namespace) -> None:
    """Tampilkan profil konfigurasi aktif dari Settings."""
    _header("App Configuration Profile ⚙️")

    try:
        from app.core.config import settings

        config_items = {
            "Application": {
                "APP_NAME": settings.APP_NAME,
                "APP_VERSION": settings.APP_VERSION,
                "DEBUG": settings.DEBUG,
                "ENVIRONMENT": settings.ENVIRONMENT,
            },
            "Database": {
                "DATABASE_URL": settings.DATABASE_URL[:40] + "..." if len(settings.DATABASE_URL) > 40 else settings.DATABASE_URL,
            },
            "Security": {
                "ALGORITHM": settings.ALGORITHM,
                "ACCESS_TOKEN_EXPIRE_MINUTES": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
                "SECRET_KEY": f"{settings.SECRET_KEY[:6]}{'•' * 20}",
                "API_KEY": f"{settings.API_KEY[:6]}{'•' * 20}",
                "is_production": settings.is_production,
            },
            "Rate Limiting": {
                "RATE_LIMIT_PER_MINUTE": settings.RATE_LIMIT_PER_MINUTE,
            },
            "CORS": {
                "CORS_ORIGINS": settings.CORS_ORIGINS,
                "CORS_ALLOW_CREDENTIALS": settings.CORS_ALLOW_CREDENTIALS,
                "effective_cors_origins": settings.effective_cors_origins,
            },
            "Pagination": {
                "DEFAULT_PAGE_SIZE": settings.DEFAULT_PAGE_SIZE,
                "MAX_PAGE_SIZE": settings.MAX_PAGE_SIZE,
            },
        }

        for section, items in config_items.items():
            print(f"\n  {_c(f'[{section}]', Color.BOLD + Color.MAGENTA)}")
            for key, value in items.items():
                val_str = str(value)
                # Color-code booleans
                if isinstance(value, bool):
                    val_str = _c(val_str, Color.GREEN if value else Color.RED)
                print(f"    {_c(key, Color.CYAN):<40} {val_str}")

    except Exception as e:
        _error(f"Gagal memuat settings: {e}")
        _dim("Pastikan .env file tersedia dan valid.")

    print()


# ══════════════════════════════════════════════════════════════════
#  CLI Parser — Main entry point
# ══════════════════════════════════════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    """Build argparse parser dengan semua subcommands."""
    parser = argparse.ArgumentParser(
        prog="devtoolkit",
        description=_c(
            "🛠️  SimpleFastAPI Developer Toolkit — CLI toolbox untuk development.",
            Color.BOLD + Color.CYAN,
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(f"""\
            {_c('Examples:', Color.BOLD)}
              python devtoolkit.py info                       # Info project
              python devtoolkit.py doctor                     # Diagnosa kesehatan
              python devtoolkit.py serve --port 8080          # Jalankan server
              python devtoolkit.py db tables                  # Lihat schema DB
              python devtoolkit.py gen secret                 # Generate secret key
              python devtoolkit.py scaffold invoice           # Buat module baru
              python devtoolkit.py lint                       # Analisis kode
              python devtoolkit.py api GET /health            # Panggil API
              python devtoolkit.py env init                   # Setup .env
              python devtoolkit.py security                   # Audit keamanan
        """),
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # info
    subparsers.add_parser("info", help="Tampilkan informasi project")

    # doctor
    subparsers.add_parser("doctor", help="Diagnosa kesehatan project")

    # serve
    sp_serve = subparsers.add_parser("serve", help="Jalankan development server")
    sp_serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    sp_serve.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    sp_serve.add_argument("--workers", type=int, default=1, help="Jumlah workers (default: 1)")
    sp_serve.add_argument("--no-reload", action="store_true", help="Disable auto-reload")

    # db
    sp_db = subparsers.add_parser("db", help="Database operations")
    sp_db.add_argument("action", choices=["info", "tables", "query", "reset", "backup", "vacuum", "migrate"])
    sp_db.add_argument("--sql", help="SQL query (untuk action 'query')")
    sp_db.add_argument("--force", action="store_true", help="Force operasi (bypass konfirmasi)")
    sp_db.add_argument("--message", "-m", help="Pesan migration (untuk action 'migrate')")

    # gen
    sp_gen = subparsers.add_parser("gen", help="Generator (secret, apikey, hash, uuid)")
    sp_gen.add_argument("action", choices=["secret", "apikey", "hash", "uuid"])
    sp_gen.add_argument("--length", type=int, default=64, help="Panjang key (default: 64)")
    sp_gen.add_argument("--password", help="Password untuk di-hash")
    sp_gen.add_argument("--count", type=int, default=1, help="Jumlah UUID (default: 1)")

    # env
    sp_env = subparsers.add_parser("env", help="Environment management")
    sp_env.add_argument("action", choices=["init", "show", "diff", "validate"])

    # scaffold
    sp_scaffold = subparsers.add_parser("scaffold", help="Scaffold module CRUD baru")
    sp_scaffold.add_argument("name", help="Nama module (contoh: invoice, category)")

    # test
    sp_test = subparsers.add_parser("test", help="Jalankan test suite")
    sp_test.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    sp_test.add_argument("--coverage", action="store_true", help="Dengan coverage report")
    sp_test.add_argument("--path", help="Path ke test file/directory spesifik")
    sp_test.add_argument("-k", "--keyword", help="Filter test by keyword")

    # lint
    sp_lint = subparsers.add_parser("lint", help="Analisis kualitas kode")
    sp_lint.add_argument("--path", help="Path target (default: app/)")

    # routes
    subparsers.add_parser("routes", help="Tampilkan semua API routes")

    # deps
    sp_deps = subparsers.add_parser("deps", help="Dependency management")
    sp_deps.add_argument("action", choices=["check", "outdated", "tree", "install"])

    # security
    subparsers.add_parser("security", help="Audit keamanan project")

    # user
    sp_user = subparsers.add_parser("user", help="Manajemen user (create / reset-password / list / delete)")
    sp_user.add_argument(
        "action",
        choices=["create", "reset-password", "list", "delete"],
        help="Aksi yang dilakukan",
    )
    # Argumen umum
    sp_user.add_argument("--username", help="Username (untuk create)")
    sp_user.add_argument("--email", help="Email (untuk create)")
    sp_user.add_argument("--full-name", help="Nama lengkap (untuk create)")
    sp_user.add_argument("--password", help="Password (create/reset). Jika kosong, akan diminta interaktif.")
    sp_user.add_argument("--identifier", help="Identifier user: id, username, atau email (untuk reset-password/delete)")
    sp_user.add_argument("--inactive", action="store_true", help="Buat user dalam keadaan non-aktif (untuk create)")
    sp_user.add_argument("--no-validate", action="store_true", help="Lewati validasi kekuatan password (untuk reset-password)")
    sp_user.add_argument("--active-only", action="store_true", help="Hanya tampilkan user yang aktif (untuk list)")

    # clean
    sp_clean = subparsers.add_parser("clean", help="Bersihkan file cache/sementara")
    sp_clean.add_argument("--dry-run", action="store_true", help="Preview tanpa menghapus")

    # loc
    sp_loc = subparsers.add_parser("loc", help="Hitung Lines of Code")
    sp_loc.add_argument("--path", help="Path target (default: app/)")

    # api
    sp_api = subparsers.add_parser("api", help="Panggil API endpoint")
    sp_api.add_argument("method", choices=["GET", "POST", "PUT", "DELETE", "PATCH"], help="HTTP method")
    sp_api.add_argument("endpoint", help="API endpoint path (contoh: /health)")
    sp_api.add_argument("--base", default="http://127.0.0.1:8000", help="Base URL")
    sp_api.add_argument("--data", "-d", help="Request body JSON")
    sp_api.add_argument("--token", help="Bearer token")
    sp_api.add_argument("--apikey", help="API Key")

    # profile
    subparsers.add_parser("profile", help="Tampilkan konfigurasi aktif")

    return parser


# ──────────────────────────────────────────────────────────────────
# Banner
# ──────────────────────────────────────────────────────────────────

def _print_banner() -> None:
    """Print banner toolkit."""
    banner = f"""\
{_c('╔══════════════════════════════════════════════════════════════╗', Color.CYAN)}
{_c('║', Color.CYAN)}  {_c('🛠️  SimpleFastAPI Developer Toolkit', Color.BOLD + Color.WHITE)}                       {_c('║', Color.CYAN)}
{_c('║', Color.CYAN)}  {_c('Build faster. Debug smarter. Ship confidently.', Color.DIM)}            {_c('║', Color.CYAN)}
{_c('╚══════════════════════════════════════════════════════════════╝', Color.CYAN)}"""
    print(banner)


# ──────────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────────

COMMAND_MAP = {
    "info": cmd_info,
    "doctor": cmd_doctor,
    "serve": cmd_serve,
    "db": cmd_db,
    "gen": cmd_gen,
    "env": cmd_env,
    "scaffold": cmd_scaffold,
    "test": cmd_test,
    "lint": cmd_lint,
    "routes": cmd_routes,
    "deps": cmd_deps,
    "security": cmd_security,
    "user": cmd_user,
    "clean": cmd_clean,
    "loc": cmd_loc,
    "api": cmd_api,
    "profile": cmd_profile,
}


def main() -> None:
    """Entry point utama Developer Toolkit."""
    _print_banner()

    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    handler = COMMAND_MAP.get(args.command)
    if handler:
        try:
            handler(args)
        except KeyboardInterrupt:
            print()
            _info("Dibatalkan oleh user.")
            sys.exit(130)
        except Exception as e:
            _error(f"Error: {e}")
            if os.environ.get("DEBUG"):
                import traceback
                traceback.print_exc()
            sys.exit(1)
    else:
        _error(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
