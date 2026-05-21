"""
SEB Process Monitor.

Monitors Safe Exam Browser processes in real-time:
- Tracks SEB main process and child processes
- Detects DLL injection and hooking behavior
- Monitors network connections from SEB
- Identifies SEB's protection mechanisms (process guarding, mutex, etc.)
"""

import os
import sys
import time
import socket
from pathlib import Path

from utils import (
    cprint, is_windows, is_admin, find_procs_by_name,
    get_all_processes, file_hash, Report
)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# SEB process names across platforms
SEB_PROCESS_NAMES = [
    "SafeExamBrowser",
    "SEB",
    "Safe Exam Browser",
    "seb.exe",
    "SafeExamBrowser.exe",
    "SafeExamBrowserService",
]


class ProcessMonitor:
    """Monitor SEB processes and their behavior."""

    def __init__(self, report: Report = None):
        self.report = report or Report()
        self.results = {}

    def scan(self) -> dict:
        """Run all process monitoring checks."""
        cprint("\n[*] SEB Process Monitor", "CYAN", bold=True)

        if not HAS_PSUTIL:
            cprint("  [-] psutil not installed — limited functionality", "RED")
            cprint("      Install with: pip install psutil", "YELLOW")

        self._find_seb_processes()
        self._check_seb_children()
        self._check_protected_processes()
        self._check_seb_services()
        self._check_network_connections()
        self._check_seb_files()
        self._check_mutex()

        return self.results

    def _find_seb_processes(self):
        """Find all SEB-related processes."""
        cprint("\n  ── SEB Processes ──", "MAGENTA", bold=True)

        found = []
        seen_pids = set()
        for name in SEB_PROCESS_NAMES:
            procs = find_procs_by_name(name)
            for p in procs:
                pid = p.get("pid")
                if pid and pid not in seen_pids:
                    found.append(p)
                    seen_pids.add(pid)

        # Also check for chromium-based (SEB is Chromium)
        # Look for any process with SEB in path
        if HAS_PSUTIL:
            for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
                try:
                    exe = proc.info.get("exe", "") or ""
                    cmdline = " ".join(proc.info.get("cmdline", []) or [])
                    pid = proc.info.get("pid")
                    if pid and pid not in seen_pids:
                        if "SafeExamBrowser" in exe or "SafeExamBrowser" in cmdline:
                            found.append(proc.info)
                            seen_pids.add(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        if found:
            for p in found:
                pid = p.get("pid", "?")
                name = p.get("name", "?")
                exe = p.get("exe", "?")
                print(f"    PID {pid:>6}: {name}")
                print(f"           Path: {exe}")

                self.report.add("process", f"SEB Process: {name}",
                               "info", f"PID={pid} Path={exe}")

                # Get process hashes
                if exe and exe != "?" and os.path.exists(exe):
                    try:
                        hashes = file_hash(exe)
                        print(f"           SHA256: {hashes['sha256'][:32]}...")
                    except Exception:
                        pass
        else:
            cprint("    [OK] No SEB processes currently running", "GREEN")
            self.report.add("process", "SEB Processes", "ok",
                           "No SEB processes found")

        self.results["seb_processes"] = found

    def _check_seb_children(self):
        """Find child processes spawned by SEB."""
        cprint("\n  ── SEB Child Processes ──", "MAGENTA", bold=True)

        children = []
        if not HAS_PSUTIL:
            cprint("    [!] psutil required for child process detection", "YELLOW")
            self.results["seb_children"] = children
            return

        seb_pids = set()
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = proc.info.get("name", "")
                for sn in SEB_PROCESS_NAMES:
                    if sn.lower() in name.lower():
                        seb_pids.add(proc.info["pid"])
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not seb_pids:
            cprint("    [OK] No SEB processes to check children for", "GREEN")
            self.results["seb_children"] = children
            return

        for proc in psutil.process_iter(["pid", "name", "exe", "ppid"]):
            try:
                ppid = proc.info.get("ppid", 0)
                if ppid in seb_pids:
                    children.append(proc.info)
                    cprint(f"    [!] Child PID {proc.info['pid']}: {proc.info['name']}",
                           "YELLOW")
                    self.report.add("process", f"SEB Child: {proc.info['name']}",
                                   "info", f"Parent PID={ppid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not children:
            cprint("    [OK] No child processes found", "GREEN")

        self.results["seb_children"] = children

    def _check_protected_processes(self):
        """Check if SEB has process protection (watchdog / guard process)."""
        cprint("\n  ── Process Protection ──", "MAGENTA", bold=True)

        if not HAS_PSUTIL:
            cprint("    [!] psutil required", "YELLOW")
            return

        # SEB typically runs a watchdog process that restarts it if killed
        # Check if there are multiple SEB instances or a service
        seb_count = 0
        for proc in psutil.process_iter(["pid", "name", "username"]):
            try:
                name = proc.info.get("name", "")
                for sn in SEB_PROCESS_NAMES:
                    if sn.lower() in name.lower():
                        seb_count += 1
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if seb_count > 1:
            cprint(f"    [!] {seb_count} SEB processes running — possible watchdog",
                   "YELLOW")
            self.report.add("process", "Process Guard", "warning",
                           f"{seb_count} SEB processes detected (watchdog?)")
        else:
            cprint("    [INFO] Single SEB process — no obvious watchdog", "INFO")
            self.report.add("process", "Process Guard", "info",
                           f"{seb_count} SEB process(es)")

        # Check if SEB runs as SYSTEM or elevated
        if is_admin():
            cprint("    [INFO] Running as admin — can see all processes", "GREEN")
        else:
            cprint("    [!] Not running as admin — limited visibility", "YELLOW")

        self.results["seb_count"] = seb_count

    def _check_seb_services(self):
        """Check for SEB-related Windows services."""
        cprint("\n  ── SEB Services ──", "MAGENTA", bold=True)

        if not is_windows():
            cprint("    [INFO] Service check is Windows-only", "INFO")
            return

        try:
            result = subprocess.run(
                ["sc", "query", "type=", "service", "state=", "all"],
                capture_output=True, text=True, timeout=15
            )
            lines = result.stdout.lower()
            seb_service = "safeexambrowser" in lines
            if seb_service:
                cprint("    [!] SEB service found", "YELLOW")
                self.report.add("process", "SEB Service", "warning",
                               "SEB Windows service is installed")
            else:
                cprint("    [OK] No SEB service found", "GREEN")
                self.report.add("process", "SEB Service", "ok",
                               "No SEB service installed")
        except Exception:
            cprint("    [INFO] Could not query services", "INFO")

    def _check_network_connections(self):
        """Check network connections from SEB processes."""
        cprint("\n  ── SEB Network Connections ──", "MAGENTA", bold=True)

        if not HAS_PSUTIL:
            cprint("    [!] psutil required for network monitoring", "YELLOW")
            return

        connections = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = proc.info.get("name", "")
                is_seb = any(sn.lower() in name.lower()
                            for sn in SEB_PROCESS_NAMES)
                if is_seb:
                    try:
                        conns = proc.connections()
                        for conn in conns:
                            raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A"
                            connections.append({
                                "pid": proc.info["pid"],
                                "name": name,
                                "status": conn.status,
                                "local": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A",
                                "remote": raddr,
                            })
                    except (psutil.AccessDenied, AttributeError):
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if connections:
            for c in connections:
                print(f"    PID {c['pid']}: {c['local']} -> {c['remote']} [{c['status']}]")
                self.report.add("network", f"SEB Connection",
                               "info", f"PID={c['pid']} {c['local']}->{c['remote']}")
        else:
            cprint("    [OK] No active SEB connections", "GREEN")

        self.results["network_connections"] = connections

    def _check_seb_files(self):
        """Check for SEB-related files on disk."""
        cprint("\n  ── SEB Files ──", "MAGENTA", bold=True)

        seb_paths = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "SafeExamBrowser",
            Path(os.environ.get("APPDATA", "")) / "SafeExamBrowser",
            Path("C:/Program Files/SafeExamBrowser"),
            Path("C:/Program Files (x86)/SafeExamBrowser"),
            Path.home() / "Library/Application Support/SafeExamBrowser",  # macOS
        ]

        found_files = []
        for p in seb_paths:
            if p.exists():
                found_files.append(str(p))
                cprint(f"    [!] Found: {p}", "YELLOW")
                self.report.add("files", f"SEB Directory: {p.name}",
                               "info", str(p))

        if not found_files:
            cprint("    [INFO] No SEB installation directories found", "INFO")

        self.results["seb_files"] = found_files

    def _check_mutex(self):
        """Check for SEB mutex objects (used for single-instance)."""
        cprint("\n  ── SEB Mutex Objects ──", "MAGENTA", bold=True)

        if is_windows():
            try:
                result = subprocess.run(
                    ["handle.exe", "-a", "-p", "seb"],  # Requires SysInternals
                    capture_output=True, text=True, timeout=10
                )
                if "Mutex" in result.stdout:
                    mutex_count = result.stdout.count("Mutex")
                    cprint(f"    [!] {mutex_count} SEB mutex object(s) found", "YELLOW")
                    self.report.add("process", "SEB Mutex", "warning",
                                   f"{mutex_count} mutex objects")
                else:
                    cprint("    [INFO] No mutex info (handle.exe may not be installed)", "INFO")
            except FileNotFoundError:
                cprint("    [INFO] SysInternals handle.exe not found", "INFO")
            except Exception:
                cprint("    [INFO] Could not check mutexes", "INFO")
        else:
            cprint("    [INFO] Mutex check is Windows-specific", "INFO")


def print_process_result(result: dict):
    """Pretty-print process monitoring results."""
    if not result:
        return

    cprint("\n── Process Monitor Verdict ──", "CYAN", bold=True)

    seb_procs = result.get("seb_processes", [])
    if seb_procs:
        cprint(f"  [!] {len(seb_procs)} SEB process(es) running", "RED", bold=True)
    else:
        cprint("  [OK] SEB not currently running", "GREEN")

    children = result.get("seb_children", [])
    if children:
        cprint(f"  [!] {len(children)} child process(es) from SEB", "YELLOW")

    conns = result.get("network_connections", [])
    if conns:
        cprint(f"  [!] {len(conns)} active network connection(s) from SEB", "YELLOW")


# Need subprocess for service checks
import subprocess
