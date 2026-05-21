"""
Shared utilities for SEB bypass tool.
Crypto helpers, system utilities, and common functions.
"""

import os
import sys
import json
import hashlib
import struct
import datetime
from pathlib import Path

# ── Color helpers ──────────────────────────────────────────────

try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

    class _FakeFore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = BLUE = RESET = ""
    class _FakeStyle:
        BRIGHT = DIM = RESET_ALL = ""
    Fore = _FakeFore()
    Style = _FakeStyle()


def cprint(text: str, color: str = "WHITE", bold: bool = False):
    """Colored print."""
    fore = getattr(Fore, color.upper(), "")
    style = Style.BRIGHT if bold else ""
    print(f"{style}{fore}{text}{Style.RESET_ALL}")


def banner():
    """Print tool banner."""
    cprint("=" * 60, "CYAN")
    cprint("  SEB Bypass Tool  —  Safe Exam Browser Analysis", "CYAN", bold=True)
    cprint("  For internal security evaluation only", "YELLOW")
    cprint("=" * 60, "CYAN")


# ── JSON report ────────────────────────────────────────────────

class Report:
    """Collects findings and saves as JSON."""

    def __init__(self):
        self.findings = []
        self.metadata = {
            "tool": "seb-bypass",
            "timestamp": datetime.datetime.now().isoformat(),
            "platform": sys.platform,
        }

    def add(self, category: str, name: str, status: str, detail: str = ""):
        self.findings.append({
            "category": category,
            "name": name,
            "status": status,  # "ok", "warning", "vulnerable", "info"
            "detail": detail,
        })

    def save(self, path: str = "report.json"):
        data = {
            "metadata": self.metadata,
            "findings": self.findings,
            "summary": self._summary(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        cprint(f"\n[+] Report saved to {path}", "GREEN")

    def _summary(self) -> dict:
        counts = {}
        for f in self.findings:
            s = f["status"]
            counts[s] = counts.get(s, 0) + 1
        return counts

    def print_summary(self):
        cprint("\n── Summary ──", "CYAN", bold=True)
        summary = self._summary()
        for status, count in summary.items():
            color = {
                "ok": "GREEN", "info": "BLUE",
                "warning": "YELLOW", "vulnerable": "RED"
            }.get(status, "WHITE")
            cprint(f"  [{status.upper():>10}] {count}", color)
        cprint(f"  {'TOTAL':>12}  {len(self.findings)}", "WHITE", bold=True)


# ── Windows Registry Helpers ───────────────────────────────────

def winreg_read(key_path: str, value_name: str, hive: int = None) -> str | None:
    """Read a Windows registry value. Returns None if not found."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        if hive is None:
            hive = winreg.HKEY_LOCAL_MACHINE
        with winreg.OpenKey(hive, key_path) as key:
            val, _ = winreg.QueryValueEx(key, value_name)
            return str(val)
    except (FileNotFoundError, OSError):
        return None


def winreg_exists(key_path: str, hive: int = None) -> bool:
    """Check if a registry key exists."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        if hive is None:
            hive = winreg.HKEY_LOCAL_MACHINE
        with winreg.OpenKey(hive, key_path):
            return True
    except (FileNotFoundError, OSError):
        return False


# ── Process helpers ────────────────────────────────────────────

def find_procs_by_name(name: str) -> list[dict]:
    """Find processes by name (case-insensitive)."""
    results = []
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "username"]):
            try:
                if name.lower() in proc.info["name"].lower():
                    results.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except ImportError:
        pass
    return results


def get_all_processes() -> list[dict]:
    """Get all running processes."""
    results = []
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                results.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except ImportError:
        pass
    return results


# ── Crypto helpers ─────────────────────────────────────────────

def derive_key_pbkdf2(password: str, salt: bytes, iterations: int = 10000,
                       key_len: int = 32) -> bytes:
    """Derive a key using PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                salt, iterations, dklen=key_len)


def hex_dump(data: bytes, length: int = 16) -> str:
    """Pretty hex dump of bytes."""
    lines = []
    for i in range(0, min(len(data), 256), length):
        chunk = data[i:i + length]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"  {i:04x}  {hex_part:<{length * 3}}  {ascii_part}")
    return "\n".join(lines)


def file_hash(path: str) -> dict:
    """Compute MD5, SHA1, SHA256 of a file."""
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
    return {
        "md5": md5.hexdigest(),
        "sha1": sha1.hexdigest(),
        "sha256": sha256.hexdigest(),
    }


# ── Platform check ─────────────────────────────────────────────

def is_windows() -> bool:
    return sys.platform == "win32"


def is_admin() -> bool:
    """Check if running with admin privileges (Windows)."""
    if not is_windows():
        return False
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False
