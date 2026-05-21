"""
Environment Detector — VM, remote desktop, and SEB monitoring detection.

SEB checks for:
- Virtual machine artifacts (registry, BIOS, CPUID, MAC address, drivers)
- Remote desktop connections (RDP, VNC, TeamViewer, etc.)
- Screen sharing / recording software
- Debugging / analysis tools
- Non-standard input devices

This module detects what SEB can see, so the user knows their exposure.
"""

import os
import sys
import platform
import subprocess
import re
import uuid
from pathlib import Path

from utils import (
    cprint, is_windows, is_admin, winreg_read, winreg_exists,
    find_procs_by_name, get_all_processes, Report
)


class EnvDetector:
    """Detect environment characteristics that SEB monitors."""

    def __init__(self, report: Report = None):
        self.report = report or Report()
        self.results = {}

    def scan(self) -> dict:
        """Run all environment checks."""
        cprint("\n[*] Environment Detection Scan", "CYAN", bold=True)

        self._check_vm()
        self._check_remote_desktop()
        self._check_monitoring_software()
        self._check_debug_tools()
        self._check_system_info()
        self._check_network_artifacts()

        return self.results

    # ── VM Detection ───────────────────────────────────────────

    def _check_vm(self):
        """Check for virtual machine indicators."""
        cprint("\n  ── Virtual Machine Detection ──", "MAGENTA", bold=True)
        vm_indicators = []

        if is_windows():
            vm_indicators.extend(self._check_vm_windows())
        else:
            vm_indicators.extend(self._check_vm_macos())

        # Check processes for VM-related processes
        vm_processes = [
            ("vmtoolsd", "VMware Tools"),
            ("vmwaretray", "VMware Tray"),
            ("vmwareuser", "VMware User"),
            (" VBoxService", "VirtualBox Service"),
            ("VBoxTray", "VirtualBox Tray"),
            ("qemu-ga", "QEMU Guest Agent"),
            ("vdagent", "SPICE Agent"),
            ("xendriver", "Xen Driver"),
        ]

        for proc_name, desc in vm_processes:
            procs = find_procs_by_name(proc_name.strip())
            if procs:
                vm_indicators.append(f"VM process: {desc} ({proc_name})")

        # Check for VM-specific hardware IDs
        if is_windows():
            try:
                result = subprocess.run(
                    ["wmic", "csproduct", "get", "name"],
                    capture_output=True, text=True, timeout=10
                )
                product = result.stdout.strip()
                vm_keywords = ["virtual", "vmware", "virtualbox", "qemu",
                               "parallels", "xen", "hyper-v"]
                for kw in vm_keywords:
                    if kw.lower() in product.lower():
                        vm_indicators.append(f"Product name contains '{kw}': {product}")
                        break
            except Exception:
                pass

            # Check BIOS
            try:
                result = subprocess.run(
                    ["wmic", "bios", "get", "serialnumber,manufacturer"],
                    capture_output=True, text=True, timeout=10
                )
                bios_info = result.stdout.strip().lower()
                vm_bios = ["vmware", "virtualbox", "qemu", "parallels", "xen"]
                for kw in vm_bios:
                    if kw in bios_info:
                        vm_indicators.append(f"BIOS indicates VM: {kw}")
                        break
            except Exception:
                pass

            # Check MAC address OUI
            mac = self._get_mac()
            vm_macs = {
                "00:0c:29": "VMware",
                "00:50:56": "VMware",
                "00:05:69": "VMware",
                "08:00:27": "VirtualBox",
                "0a:00:27": "VirtualBox",
                "52:54:00": "QEMU/KVM",
                "00:16:3e": "Xen",
                "00:1c:42": "Parallels",
            }
            if mac:
                prefix = mac[:8].lower()
                if prefix in vm_macs:
                    vm_indicators.append(f"MAC OUI matches {vm_macs[prefix]}: {mac}")

        # Check for VM-related drivers
        if is_windows():
            vm_driver_paths = [
                r"C:\Windows\System32\drivers\vmhgfs.sys",
                r"C:\Windows\System32\drivers\VBoxGuest.sys",
                r"C:\Windows\System32\drivers\VBoxMouse.sys",
                r"C:\Windows\System32\drivers\VBoxSF.sys",
                r"C:\Windows\System32\drivers\qemu-ga.sys",
            ]
            for dp in vm_driver_paths:
                if os.path.exists(dp):
                    name = Path(dp).stem
                    vm_indicators.append(f"VM driver found: {name}")

            # Check registry for VM artifacts
            vm_reg_keys = [
                (r"SOFTWARE\VMware, Inc.\VMware Tools", "VMware Tools"),
                (r"SOFTWARE\Oracle\VirtualBox Guest Additions", "VirtualBox GA"),
            ]
            for key, desc in vm_reg_keys:
                if winreg_exists(key):
                    vm_indicators.append(f"VM registry key: {desc}")

        is_vm = len(vm_indicators) > 0
        status = "warning" if is_vm else "ok"

        if is_vm:
            for ind in vm_indicators:
                cprint(f"    [!] {ind}", "YELLOW")
                self.report.add("env", f"VM: {ind}", "warning", ind)
        else:
            cprint("    [OK] No VM indicators detected", "GREEN")
            self.report.add("env", "VM Detection", "ok", "No VM indicators found")

        self.results["is_vm"] = is_vm
        self.results["vm_indicators"] = vm_indicators

    def _check_vm_windows(self) -> list[str]:
        """Windows-specific VM checks."""
        indicators = []

        # WMI query for computer system
        try:
            result = subprocess.run(
                ["wmic", "computersystem", "get", "manufacturer,model"],
                capture_output=True, text=True, timeout=10
            )
            info = result.stdout.strip().lower()
            vm_strings = ["vmware", "virtualbox", "qemu", "parallels",
                          "microsoft corporation"]
            for vs in vm_strings:
                if vs in info and "virtual" in info:
                    indicators.append(f"System manufacturer: {info.split(chr(10))[1].strip()}")
                    break
        except Exception:
            pass

        return indicators

    def _check_vm_macos(self) -> list[str]:
        """macOS-specific VM checks."""
        indicators = []
        try:
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True, text=True, timeout=10
            )
            hw = result.stdout.lower()
            if "vmware" in hw or "virtualbox" in hw or "parallels" in hw:
                indicators.append("macOS hardware profile indicates VM")
        except Exception:
            pass
        return indicators

    # ── Remote Desktop Detection ───────────────────────────────

    def _check_remote_desktop(self):
        """Check for remote desktop / screen sharing."""
        cprint("\n  ── Remote Desktop Detection ──", "MAGENTA", bold=True)
        rd_procs = [
            ("mstsc", "RDP Client"),
            ("rdpclip", "RDP Clipboard"),
            ("vnc", "VNC"),
            ("TeamViewer", "TeamViewer"),
            ("AnyDesk", "AnyDesk"),
            ("Splashtop", "Splashtop"),
            ("Chrome Remote Desktop", "Chrome RD"),
            ("Zoom", "Zoom (screen share)"),
            ("msra", "Remote Assistance"),
            ("raserver", "Remote Access"),
            ("parsec", "Parsec"),
        ]

        found = []
        all_procs = get_all_processes()
        proc_names = [p.get("name", "").lower() for p in all_procs]

        for proc_name, desc in rd_procs:
            for pn in proc_names:
                if proc_name.lower() in pn:
                    found.append(desc)
                    break

        if found:
            for f in found:
                cprint(f"    [!] Remote access software: {f}", "YELLOW")
                self.report.add("env", f"Remote Desktop: {f}", "warning",
                               f"Remote access software detected")
        else:
            cprint("    [OK] No remote desktop software detected", "GREEN")
            self.report.add("env", "Remote Desktop", "ok", "None detected")

        self.results["remote_desktop"] = found

    # ── Monitoring / Analysis Tools ────────────────────────────

    def _check_monitoring_software(self):
        """Check for monitoring, recording, and analysis tools."""
        cprint("\n  ── Monitoring & Analysis Tools ──", "MAGENTA", bold=True)
        tools = [
            ("wireshark", "Wireshark"),
            ("fiddler", "Fiddler"),
            ("charles", "Charles Proxy"),
            ("procmon", "Process Monitor"),
            ("procexp", "Process Explorer"),
            ("ollydbg", "OllyDbg"),
            ("x64dbg", "x64dbg"),
            ("ida", "IDA Pro"),
            ("ghidra", "Ghidra"),
            ("cheat engine", "Cheat Engine"),
            ("dnspy", "dnSpy"),
            ("de4dot", "de4dot"),
            ("mitmproxy", "mitmproxy"),
            ("burp", "Burp Suite"),
        ]

        all_procs = get_all_processes()
        proc_names = [p.get("name", "").lower() for p in all_procs]

        found = []
        for proc_name, desc in tools:
            for pn in proc_names:
                if proc_name.lower() in pn:
                    found.append(desc)
                    break

        if found:
            for f in found:
                cprint(f"    [!] Analysis tool running: {f}", "YELLOW")
                self.report.add("env", f"Analysis Tool: {f}", "warning",
                               "Analysis/debugging tool detected")
        else:
            cprint("    [OK] No analysis tools detected", "GREEN")
            self.report.add("env", "Analysis Tools", "ok", "None detected")

        self.results["analysis_tools"] = found

    # ── Debug / Hook Detection ─────────────────────────────────

    def _check_debug_tools(self):
        """Check for debugging artifacts."""
        cprint("\n  ── Debug Environment ──", "MAGENTA", bold=True)

        # Check if debugger is attached
        is_debugged = False
        if is_windows():
            try:
                import ctypes
                is_debugged = ctypes.windll.kernel32.IsDebuggerPresent()
            except Exception:
                pass

        # Check for common hooking DLLs in current process
        hooked_dlls = []
        try:
            import ctypes
            import ctypes.wintypes

            known_hook_dlls = [
                "frida", "detour", "easyhook", "minhook",
                "deviare", "mhook", "syehook"
            ]
            # This is a heuristic — check loaded modules
            # A full implementation would enumerate process modules
        except Exception:
            pass

        if is_debugged:
            cprint("    [!] Debugger detected attached to current process", "YELLOW")
            self.report.add("env", "Debugger Detected", "warning",
                           "Active debugger detected")
        else:
            cprint("    [OK] No debugger attached", "GREEN")
            self.report.add("env", "Debugger", "ok", "No debugger attached")

        self.results["debugger"] = is_debugged

    # ── System Info ────────────────────────────────────────────

    def _check_system_info(self):
        """Gather general system information."""
        cprint("\n  ── System Information ──", "MAGENTA", bold=True)

        info = {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "admin": is_admin(),
        }

        # Get disk serial / volume serial (VM artifact)
        if is_windows():
            try:
                result = subprocess.run(
                    ["vol", "C:"],
                    capture_output=True, text=True, timeout=10
                )
                volume_match = re.search(
                    r"Volume Serial Number is (\S+)",
                    result.stdout
                )
                if volume_match:
                    info["volume_serial"] = volume_match.group(1)
            except Exception:
                pass

        for k, v in info.items():
            print(f"    {k:>15}: {v}")

        self.results["system_info"] = info

    # ── Network Artifacts ──────────────────────────────────────

    def _check_network_artifacts(self):
        """Check network for VM/proxy indicators."""
        cprint("\n  ── Network Artifacts ──", "MAGENTA", bold=True)

        # Check for proxy settings
        proxy_indicators = []
        if is_windows():
            proxy = winreg_read(
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                "ProxyServer"
            )
            if proxy and proxy != "":
                proxy_indicators.append(f"System proxy configured: {proxy[:50]}")

            proxy_enable = winreg_read(
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                "ProxyEnable"
            )
            if proxy_enable == "1":
                proxy_indicators.append("System proxy is ENABLED")

        if proxy_indicators:
            for p in proxy_indicators:
                cprint(f"    [!] {p}", "YELLOW")
                self.report.add("env", f"Proxy: {p[:40]}", "warning", p)
        else:
            cprint("    [OK] No proxy indicators", "GREEN")
            self.report.add("env", "Proxy Settings", "ok", "No proxy detected")

        self.results["proxy"] = proxy_indicators

    # ── Helpers ────────────────────────────────────────────────

    def _get_mac(self) -> str | None:
        """Get the MAC address of the first network interface."""
        mac = uuid.getnode()
        mac_str = ":".join(
            f"{(mac >> (8 * i)) & 0xff:02x}"
            for i in reversed(range(6))
        )
        return mac_str


def print_env_result(result: dict):
    """Pretty-print environment detection results."""
    if not result:
        return

    is_vm = result.get("is_vm", False)
    cprint("\n── Environment Verdict ──", "CYAN", bold=True)
    if is_vm:
        cprint("  [!] VIRTUAL MACHINE DETECTED", "RED", bold=True)
        cprint("  SEB will likely detect this environment.", "YELLOW")
        count = len(result.get("vm_indicators", []))
        cprint(f"  {count} VM indicator(s) found", "YELLOW")
    else:
        cprint("  [OK] No obvious VM indicators", "GREEN")

    if result.get("remote_desktop"):
        cprint("  [!] Remote desktop software may be detected by SEB", "YELLOW")

    if result.get("analysis_tools"):
        cprint("  [!] Analysis tools will be flagged by SEB", "YELLOW")

    if result.get("debugger"):
        cprint("  [!] Debugger presence may be detected", "YELLOW")
