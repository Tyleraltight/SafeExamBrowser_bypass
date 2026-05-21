"""
VMX Helper - Configure VMware .vmx files to hide VM indicators.

Adds smbios.reflecthost = "TRUE" to make the VM report the host
computer's manufacturer and model, reducing VM detection chances.

Also provides additional anti-detection VMX settings.
"""

import os
import sys
import glob
from datetime import datetime

# Default VMware VM locations
VMX_SEARCH_PATHS = [
    os.path.expandvars(r"%USERPROFILE%\Documents\Virtual Machines"),
    os.path.expandvars(r"%USERPROFILE%\VMware VMs"),
    os.path.expandvars(r"%PUBLIC%\Documents\Virtual Machines"),
]

# Recommended VMX settings to hide VM
RECOMMENDED_SETTINGS = {
    "smbios.reflecthost": "TRUE",
    "isolation.tools.hgfs.disable": "TRUE",
    "isolation.tools.dnd.disable": "TRUE",
    "isolation.tools.copy.disable": "TRUE",
    "isolation.tools.paste.disable": "TRUE",
    "monitor_control.restrict_backdoor": "TRUE",
    "tools.syncTime": "FALSE",
    "time.synchronize.continue": "FALSE",
    "time.synchronize.restore": "FALSE",
    "time.synchronize.resume.disk": "FALSE",
    "time.synchronize.shrink": "FALSE",
    "time.synchronize.tools.startup": "FALSE",
    "tools.upgrade.policy": "manual",
}


def find_vmx_files(search_paths=None) -> list:
    """Find all .vmx files in common VMware directories."""
    if search_paths is None:
        search_paths = VMX_SEARCH_PATHS

    vmx_files = []
    for base_path in search_paths:
        expanded = os.path.expandvars(base_path)
        if os.path.isdir(expanded):
            for root, dirs, files in os.walk(expanded):
                for f in files:
                    if f.lower().endswith(".vmx"):
                        vmx_files.append(os.path.join(root, f))

    return vmx_files


def read_vmx(filepath: str) -> dict:
    """Parse a .vmx file into a dictionary."""
    settings = {}
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip().strip('"')
                value = value.strip().strip('"')
                settings[key] = value
    return settings


def write_vmx(filepath: str, settings: dict):
    """Write settings back to a .vmx file."""
    lines = []
    written_keys = set()

    # Read existing file, preserving comments and structure
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                lines.append(line)
                continue
            if "=" in stripped:
                key, _, _ = stripped.partition("=")
                key = key.strip().strip('"')
                if key in settings:
                    lines.append(f'{key} = "{settings[key]}"\n')
                    written_keys.add(key)
                else:
                    lines.append(line)
            else:
                lines.append(line)

    # Append new settings that weren't in the file
    for key, value in settings.items():
        if key not in written_keys:
            lines.append(f'{key} = "{value}"\n')

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)


def check_vmx_status(filepath: str, verbose=True) -> dict:
    """Check if a VMX file has anti-detection settings."""
    log = print if verbose else lambda *a, **k: None
    settings = read_vmx(filepath)

    log(f"\n[*] Checking: {filepath}")

    result = {"filepath": filepath, "settings": {}, "all_set": True}

    for key, expected in RECOMMENDED_SETTINGS.items():
        current = settings.get(key)
        is_set = current and current.upper() == expected.upper()
        status = "[+]" if is_set else "[-]"
        log(f"  {status} {key}: {current or 'NOT SET'} (want: {expected})")
        result["settings"][key] = {
            "current": current,
            "expected": expected,
            "is_set": is_set,
        }
        if not is_set:
            result["all_set"] = False

    return result


def apply_anti_detection(filepath: str, verbose=True) -> bool:
    """Apply anti-detection settings to a VMX file."""
    log = print if verbose else lambda *a, **k: None

    log(f"\n[*] Applying anti-detection settings to: {filepath}")

    if not os.path.isfile(filepath):
        log(f"[!] File not found: {filepath}")
        return False

    # Backup first
    backup_path = filepath + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    with open(filepath, "r", encoding="utf-8", errors="ignore") as src:
        with open(backup_path, "w", encoding="utf-8") as dst:
            dst.write(src.read())
    log(f"  [+] Backup: {backup_path}")

    # Read current settings
    settings = read_vmx(filepath)

    # Apply recommended settings
    applied = 0
    for key, value in RECOMMENDED_SETTINGS.items():
        current = settings.get(key)
        if not current or current.upper() != value.upper():
            settings[key] = value
            log(f"  [+] Set: {key} = {value}")
            applied += 1
        else:
            log(f"  [=] Already set: {key} = {value}")

    # Write back
    write_vmx(filepath, settings)
    log(f"\n[+] Applied {applied} settings to {filepath}")
    return True


def print_vmx_help():
    """Print usage instructions."""
    print("""
VMX Helper - VMware Anti-Detection Configuration
=================================================

Configures VMware .vmx files to hide virtual machine indicators.

Key setting: smbios.reflecthost = "TRUE"
  Makes the VM report the host computer's hardware info
  (manufacturer, model, serial) instead of VMware defaults.

Other settings disable:
  - VMware tools sync (time, clipboard, drag-drop)
  - Backdoor detection mechanisms
  - HGFS shared folders

Commands:
  find      Find all .vmx files on the system
  check     Check if anti-detection settings are applied
  apply     Apply anti-detection settings

Examples:
  python vmx_helper.py find
  python vmx_helper.py check
  python vmx_helper.py check --vmx "C:\\path\\to\\vm.vmx"
  python vmx_helper.py apply --vmx "C:\\path\\to\\vm.vmx"
""")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_vmx_help()
        sys.exit(0)

    cmd = sys.argv[1].lower()

    # Parse --vmx
    vmx_path = None
    for i, arg in enumerate(sys.argv):
        if arg == "--vmx" and i + 1 < len(sys.argv):
            vmx_path = sys.argv[i + 1]

    if cmd == "find":
        files = find_vmx_files()
        if files:
            print(f"\nFound {len(files)} VMX file(s):")
            for f in files:
                print(f"  {f}")
        else:
            print("\nNo VMX files found in default locations.")
            print("Use --vmx to specify a path manually.")

    elif cmd == "check":
        if vmx_path:
            check_vmx_status(vmx_path)
        else:
            files = find_vmx_files()
            if not files:
                print("No VMX files found. Use --vmx to specify path.")
            for f in files:
                check_vmx_status(f)

    elif cmd == "apply":
        if not vmx_path:
            files = find_vmx_files()
            if not files:
                print("No VMX files found. Use --vmx to specify path.")
                sys.exit(1)
            print(f"Found {len(files)} VMX file(s). Applying to all...")
            for f in files:
                apply_anti_detection(f)
        else:
            apply_anti_detection(vmx_path)

    elif cmd == "help":
        print_vmx_help()

    else:
        print(f"Unknown command: {cmd}")
        print_vmx_help()
