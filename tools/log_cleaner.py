"""
Log Cleaner - Edit SEB log files to remove VM/traces.

SEB writes detailed logs that can reveal:
  - VM detection (display count, wireless adapter)
  - VMware tools services
  - Patched file hashes

After applying the DLL patch, logs must be cleaned before
submitting to exam proctors.
"""

import os
import re
import sys
import glob
from datetime import datetime

# SEB log paths (version-dependent)
SEB_LOG_PATHS = [
    # SEB v3.x
    os.path.expandvars(r"%LOCALAPPDATA%\SafeExamBrowser"),
    # SEB v2.x
    os.path.expandvars(r"%APPDATA%\SafeExamBrowser"),
]

# Replacements for Runtime.log
RUNTIME_REPLACEMENTS = [
    {
        "find": r"Detected 0 active displays, 1 are allowed",
        "replace": "Detected 1 active displays, 1 are allowed",
        "reason": "Hide that VM has no physical display",
    },
    {
        "find": r"Wireless networks cannot be monitored, as there is no hardware adapter available or it is turned off",
        "replace": "Started monitoring the wireless network adapter",
        "reason": "Hide missing wireless adapter in VM",
    },
    {
        "find": r"VMware",
        "replace": "VMware",  # Will be removed entirely
        "action": "remove_line",
        "reason": "Remove any VMware references",
    },
]

# Replacements for Client.log
CLIENT_REPLACEMENTS = [
    {
        "patterns": ["vm3dservice", "VGAuthService", "vmtoolsd", "vmware", "VMware Tools"],
        "action": "remove_line",
        "reason": "Remove VMware tools service references",
    },
    {
        "find": r"Virtual",
        "action": "remove_line",
        "reason": "Remove virtualization references",
    },
]

# Broader patterns to clean from any log
CLEAN_PATTERNS = [
    r"(?i)vmware",
    r"(?i)virtual\s*machine",
    r"(?i)hypervisor",
    r"(?i)virtualbox",
    r"(?i)vbox",
    r"(?i)qemu",
    r"(?i)0 active display",
    r"(?i)no hardware adapter",
    r"(?i)vm3dservice",
    r"(?i)vgauthservice",
    r"(?i)vmtoolsd",
]


def find_log_dirs(search_paths=None) -> list:
    """Find SEB log directories."""
    if search_paths is None:
        search_paths = SEB_LOG_PATHS

    found = []
    for path in search_paths:
        expanded = os.path.expandvars(path)
        if os.path.isdir(expanded):
            found.append(expanded)

    return found


def find_log_files(log_dir: str) -> dict:
    """Find all log files in a directory."""
    result = {"runtime": [], "client": [], "other": []}

    if not os.path.isdir(log_dir):
        return result

    for f in os.listdir(log_dir):
        full = os.path.join(log_dir, f)
        if not os.path.isfile(full):
            continue
        fl = f.lower()
        if "runtime" in fl and fl.endswith(".log"):
            result["runtime"].append(full)
        elif "client" in fl and fl.endswith(".log"):
            result["client"].append(full)
        elif fl.endswith(".log"):
            result["other"].append(full)

    return result


def backup_log(filepath: str) -> str:
    """Create a backup of a log file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{filepath}.bak_{timestamp}"
    with open(filepath, "r", encoding="utf-8", errors="ignore") as src:
        with open(backup, "w", encoding="utf-8") as dst:
            dst.write(src.read())
    return backup


def clean_line(line: str, patterns: list) -> bool:
    """Check if a line should be removed based on patterns."""
    for pattern in patterns:
        if re.search(pattern, line):
            return True
    return False


def apply_replacements(content: str, replacements: list) -> tuple:
    """Apply text replacements to log content."""
    lines = content.split("\n")
    new_lines = []
    changes = 0

    for line in lines:
        should_remove = False
        modified = False

        for rule in replacements:
            if rule.get("action") == "remove_line":
                # Check patterns
                patterns = rule.get("patterns", [])
                if rule.get("find"):
                    patterns.append(rule["find"])
                if clean_line(line, patterns):
                    should_remove = True
                    changes += 1
                    break
            elif "find" in rule and "replace" in rule:
                if re.search(rule["find"], line):
                    line = re.sub(rule["find"], rule["replace"], line)
                    modified = True
                    changes += 1

        if not should_remove:
            new_lines.append(line)

    return "\n".join(new_lines), changes


def clean_log_file(filepath: str, verbose=True) -> int:
    """Clean a single log file."""
    log = print if verbose else lambda *a, **k: None

    if not os.path.isfile(filepath):
        log(f"  [!] File not found: {filepath}")
        return 0

    log(f"\n  Cleaning: {os.path.basename(filepath)}")

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    original_size = len(content)

    # Determine which replacements to use
    fl = filepath.lower()
    if "runtime" in fl:
        replacements = RUNTIME_REPLACEMENTS
    elif "client" in fl:
        replacements = CLIENT_REPLACEMENTS
    else:
        # Generic cleaning for unknown logs
        replacements = [{"patterns": CLEAN_PATTERNS, "action": "remove_line"}]

    cleaned, changes = apply_replacements(content, replacements)

    if changes > 0:
        # Backup original
        backup = backup_log(filepath)
        log(f"    Backup: {os.path.basename(backup)}")

        # Write cleaned version
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(cleaned)

        new_size = len(cleaned)
        log(f"    Changes: {changes} lines modified/removed")
        log(f"    Size: {original_size} -> {new_size} bytes")
    else:
        log(f"    No changes needed")

    return changes


def clean_all_logs(log_dirs=None, verbose=True) -> int:
    """Clean all SEB log files."""
    log = print if verbose else lambda *a, **k: None

    if log_dirs is None:
        log_dirs = find_log_dirs()

    if not log_dirs:
        log("[!] No SEB log directories found!")
        log("    Searched in:")
        for p in SEB_LOG_PATHS:
            log(f"      - {p}")
        return 0

    total_changes = 0

    for log_dir in log_dirs:
        log(f"\n[*] Processing: {log_dir}")
        files = find_log_files(log_dir)

        all_files = files["runtime"] + files["client"] + files["other"]
        if not all_files:
            log("  No log files found")
            continue

        log(f"  Found {len(all_files)} log file(s)")

        for filepath in all_files:
            changes = clean_log_file(filepath, verbose)
            total_changes += changes

    return total_changes


def scan_logs(log_dirs=None, verbose=True) -> dict:
    """Scan log files for VM-related content without modifying them."""
    log = print if verbose else lambda *a, **k: None

    if log_dirs is None:
        log_dirs = find_log_dirs()

    result = {"dirs": log_dirs, "files": []}

    for log_dir in log_dirs:
        log(f"\n[*] Scanning: {log_dir}")
        files = find_log_files(log_dir)

        all_files = files["runtime"] + files["client"] + files["other"]
        if not all_files:
            log("  No log files found")
            continue

        for filepath in all_files:
            log(f"\n  File: {os.path.basename(filepath)}")
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            hits = []
            for i, line in enumerate(lines, 1):
                for pattern in CLEAN_PATTERNS:
                    if re.search(pattern, line):
                        hits.append({"line_num": i, "content": line.strip(), "pattern": pattern})
                        log(f"    Line {i}: {line.strip()[:100]}")
                        break

            result["files"].append({
                "path": filepath,
                "total_lines": len(lines),
                "hits": len(hits),
                "details": hits,
            })

            if not hits:
                log("    Clean - no VM references found")

    return result


def print_log_help():
    """Print usage instructions."""
    print("""
Log Cleaner - SEB Log File Editor
==================================

Cleans SEB log files to remove VM/virtualization traces.
Must be run AFTER the DLL patch and BEFORE submitting logs.

What gets cleaned:
  Runtime.log:
    - "0 active displays" -> "1 active displays"
    - "no hardware adapter" -> "Started monitoring wireless"
    - VMware references removed

  Client.log:
    - vm3dservice, VGAuthService, vmtoolsd lines removed
    - VMware tools references removed

Commands:
  scan      Scan logs for VM references (read-only)
  clean     Clean all log files (modifies files, creates backups)

Examples:
  python log_cleaner.py scan
  python log_cleaner.py clean
  python log_cleaner.py scan --log-dir "C:\\Users\\You\\AppData\\Local\\SafeExamBrowser"
  python log_cleaner.py clean --log-dir "C:\\Users\\You\\AppData\\Local\\SafeExamBrowser"

After cleaning:
  - Original files are backed up with .bak_TIMESTAMP extension
  - Review the cleaned logs before submitting
""")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_log_help()
        sys.exit(0)

    cmd = sys.argv[1].lower()

    # Parse --log-dir
    log_dir = None
    for i, arg in enumerate(sys.argv):
        if arg == "--log-dir" and i + 1 < len(sys.argv):
            log_dir = sys.argv[i + 1]

    log_dirs = [log_dir] if log_dir else None

    if cmd == "scan":
        scan_logs(log_dirs)
    elif cmd == "clean":
        changes = clean_all_logs(log_dirs)
        if changes > 0:
            print(f"\n[+] Done! {changes} changes made. Review cleaned logs before submitting.")
        else:
            print("\n[=] No changes needed.")
    elif cmd == "help":
        print_log_help()
    else:
        print(f"Unknown command: {cmd}")
        print_log_help()
