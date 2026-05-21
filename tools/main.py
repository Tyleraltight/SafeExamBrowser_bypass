#!/usr/bin/env python3
"""
SEB Bypass Tool — Safe Exam Browser Analysis & Bypass Toolkit

Usage:
    python main.py scan                      Full environment scan
    python main.py config --file exam.seb    Analyze SEB config file
    python main.py env                       Environment detection only
    python main.py monitor                   Process monitoring only
    python main.py keys                      Keyboard/input analysis only
    python main.py patch                     Download & apply DLL patch (VM bypass)
    python main.py patch --check             Check patch status
    python main.py patch --restore           Restore original files
    python main.py vmx                       Configure VMware anti-detection
    python main.py logs                      Clean SEB log files
    python main.py logs --scan               Scan logs for VM references
"""

import sys
import os
import json

try:
    import click
    HAS_CLICK = True
except ImportError:
    HAS_CLICK = False

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import cprint, banner, Report, is_windows, is_admin
from config_analyzer import SEBConfigAnalyzer, print_config_result
from env_detector import EnvDetector, print_env_result
from process_monitor import ProcessMonitor, print_process_result
from kbypass import KeyboardBypass, print_keyboard_result
from dll_patcher import patch_seb, check_patch_status, restore_backup, find_seb_install_dir
from vmx_helper import find_vmx_files, check_vmx_status, apply_anti_detection
from log_cleaner import scan_logs, clean_all_logs


def full_scan(password: str = "", config_file: str = ""):
    """Run a full environment scan."""
    banner()
    report = Report()

    cprint("\n" + "=" * 60, "CYAN")
    cprint("  FULL SECURITY SCAN", "CYAN", bold=True)
    cprint("=" * 60, "CYAN")

    # 1. Environment Detection
    env = EnvDetector(report)
    env_result = env.scan()
    print_env_result(env_result)

    # 2. Process Monitor
    proc = ProcessMonitor(report)
    proc_result = proc.scan()
    print_process_result(proc_result)

    # 3. Keyboard Bypass
    kb = KeyboardBypass(report)
    kb_result = kb.scan()
    print_keyboard_result(kb_result)

    # 4. Config Analysis (if file provided)
    if config_file:
        config = SEBConfigAnalyzer(report)
        cfg_result = config.analyze(config_file, password)
        print_config_result(cfg_result)

    # Summary
    report.print_summary()

    # Save report
    report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "report.json"
    )
    report.save(report_path)

    return report


def config_scan(filepath: str, password: str):
    """Analyze a SEB configuration file."""
    banner()
    report = Report()

    analyzer = SEBConfigAnalyzer(report)
    result = analyzer.analyze(filepath, password)
    print_config_result(result)

    report.print_summary()
    report.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.json"))

    return report


def env_scan():
    """Run environment detection only."""
    banner()
    report = Report()

    detector = EnvDetector(report)
    result = detector.scan()
    print_env_result(result)

    report.print_summary()
    report.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.json"))

    return report


def process_scan():
    """Run process monitoring only."""
    banner()
    report = Report()

    monitor = ProcessMonitor(report)
    result = monitor.scan()
    print_process_result(result)

    report.print_summary()
    report.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.json"))

    return report


def keyboard_scan():
    """Run keyboard/input analysis only."""
    banner()
    report = Report()

    kb = KeyboardBypass(report)
    result = kb.scan()
    print_keyboard_result(result)

    report.print_summary()
    report.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.json"))

    return report


# ── Click CLI ──────────────────────────────────────────────────

if HAS_CLICK:
    @click.group()
    @click.version_option(version="1.0.0")
    def cli():
        """SEB Bypass Tool — Safe Exam Browser Analysis"""
        pass

    @cli.command()
    def scan():
        """Run full environment scan."""
        full_scan()

    @cli.command()
    @click.option("--file", "-f", required=True, help="Path to .seb config file")
    @click.option("--password", "-p", default="", help="Config decryption password")
    def config(file, password):
        """Analyze SEB configuration file."""
        config_scan(file, password)

    @cli.command()
    def env():
        """Run environment detection."""
        env_scan()

    @cli.command()
    def monitor():
        """Run process monitoring."""
        process_scan()

    @cli.command()
    def keys():
        """Run keyboard/input analysis."""
        keyboard_scan()

    @cli.command()
    @click.option("--check", is_flag=True, help="Check patch status only")
    @click.option("--restore", is_flag=True, help="Restore original files")
    @click.option("--install-dir", default=None, help="SEB installation directory")
    @click.option("--backup-dir", default=None, help="Backup directory (for restore)")
    def patch(check, restore, install_dir, backup_dir):
        """Download & apply DLL patch to bypass VM detection."""
        if check:
            check_patch_status(install_dir=install_dir)
        elif restore:
            if not backup_dir or not install_dir:
                print("Usage: python main.py patch --restore --backup-dir PATH --install-dir PATH")
            else:
                restore_backup(backup_dir, install_dir)
        else:
            patch_seb(install_dir=install_dir)

    @cli.command()
    @click.option("--find", "find_mode", is_flag=True, help="Find VMX files")
    @click.option("--check", is_flag=True, help="Check anti-detection status")
    @click.option("--apply", "apply_mode", is_flag=True, help="Apply anti-detection settings")
    @click.option("--vmx", "vmx_path", default=None, help="Path to .vmx file")
    def vmx(find_mode, check, apply_mode, vmx_path):
        """Configure VMware anti-detection settings."""
        if find_mode:
            files = find_vmx_files()
            if files:
                print(f"\nFound {len(files)} VMX file(s):")
                for f in files:
                    print(f"  {f}")
            else:
                print("\nNo VMX files found. Use --vmx to specify path.")
        elif check:
            if vmx_path:
                check_vmx_status(vmx_path)
            else:
                files = find_vmx_files()
                for f in files:
                    check_vmx_status(f)
        elif apply_mode:
            if vmx_path:
                apply_anti_detection(vmx_path)
            else:
                files = find_vmx_files()
                for f in files:
                    apply_anti_detection(f)
        else:
            # Default: find + check
            files = find_vmx_files()
            if files:
                for f in files:
                    check_vmx_status(f)
            else:
                print("No VMX files found. Use --vmx to specify path.")

    @cli.command()
    @click.option("--scan", "scan_mode", is_flag=True, help="Scan logs (read-only)")
    @click.option("--log-dir", default=None, help="SEB log directory")
    def logs(scan_mode, log_dir):
        """Clean SEB log files to remove VM traces."""
        log_dirs = [log_dir] if log_dir else None
        if scan_mode:
            scan_logs(log_dirs)
        else:
            changes = clean_all_logs(log_dirs)
            if changes > 0:
                print(f"\n[+] Done! {changes} changes made. Review cleaned logs before submitting.")
            else:
                print("\n[=] No changes needed.")

    if __name__ == "__main__":
        cli()

else:
    # Fallback: no click, use simple arg parsing
    def main():
        banner()

        if len(sys.argv) < 2:
            print(__doc__)
            return

        cmd = sys.argv[1].lower()

        if cmd == "scan":
            full_scan()
        elif cmd == "config":
            filepath = ""
            password = ""
            i = 2
            while i < len(sys.argv):
                if sys.argv[i] in ("--file", "-f") and i + 1 < len(sys.argv):
                    filepath = sys.argv[i + 1]
                    i += 2
                elif sys.argv[i] in ("--password", "-p") and i + 1 < len(sys.argv):
                    password = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1
            if filepath:
                config_scan(filepath, password)
            else:
                print("Error: --file required for config command")
        elif cmd == "env":
            env_scan()
        elif cmd == "monitor":
            process_scan()
        elif cmd == "keys":
            keyboard_scan()
        elif cmd == "patch":
            check = "--check" in sys.argv
            restore = "--restore" in sys.argv
            install_dir = None
            backup_dir = None
            i = 2
            while i < len(sys.argv):
                if sys.argv[i] == "--install-dir" and i + 1 < len(sys.argv):
                    install_dir = sys.argv[i + 1]
                    i += 2
                elif sys.argv[i] == "--backup-dir" and i + 1 < len(sys.argv):
                    backup_dir = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1
            if check:
                check_patch_status(install_dir=install_dir)
            elif restore:
                if backup_dir and install_dir:
                    restore_backup(backup_dir, install_dir)
                else:
                    print("Usage: patch --restore --backup-dir PATH --install-dir PATH")
            else:
                patch_seb(install_dir=install_dir)
        elif cmd == "vmx":
            find_mode = "--find" in sys.argv
            check_mode = "--check" in sys.argv
            apply_mode = "--apply" in sys.argv
            vmx_path = None
            i = 2
            while i < len(sys.argv):
                if sys.argv[i] == "--vmx" and i + 1 < len(sys.argv):
                    vmx_path = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1
            if find_mode:
                files = find_vmx_files()
                if files:
                    print(f"\nFound {len(files)} VMX file(s):")
                    for f in files:
                        print(f"  {f}")
                else:
                    print("\nNo VMX files found.")
            elif check_mode:
                if vmx_path:
                    check_vmx_status(vmx_path)
                else:
                    for f in find_vmx_files():
                        check_vmx_status(f)
            elif apply_mode:
                if vmx_path:
                    apply_anti_detection(vmx_path)
                else:
                    for f in find_vmx_files():
                        apply_anti_detection(f)
            else:
                files = find_vmx_files()
                for f in files:
                    check_vmx_status(f)
        elif cmd == "logs":
            scan_mode = "--scan" in sys.argv
            log_dir = None
            i = 2
            while i < len(sys.argv):
                if sys.argv[i] == "--log-dir" and i + 1 < len(sys.argv):
                    log_dir = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1
            log_dirs = [log_dir] if log_dir else None
            if scan_mode:
                scan_logs(log_dirs)
            else:
                changes = clean_all_logs(log_dirs)
                if changes > 0:
                    print(f"\n[+] Done! {changes} changes made.")
                else:
                    print("\n[=] No changes needed.")
        else:
            print(f"Unknown command: {cmd}")
            print(__doc__)

    if __name__ == "__main__":
        main()
