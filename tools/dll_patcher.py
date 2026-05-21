"""
DLL Patcher - Download and replace SEB core files with patched versions.

Based on nxvvvv/safe-exam-browser-bypass:
  Replaces SafeExamBrowser.Client.exe, .Monitoring.dll, .SystemComponents.dll
  with patched versions that disable VM detection and system monitoring.
"""

import os
import sys
import shutil
import hashlib
import urllib.request
import ssl
import time
from datetime import datetime

PATCHED_FILES = {
    "SafeExamBrowser.Client.exe": {
        "url": "https://github.com/nxvvvv/safe-exam-browser-bypass/raw/main/SafeExamBrowser.Client.exe",
        "description": "Main SEB client (patched to disable VM detection)",
    },
    "SafeExamBrowser.Monitoring.dll": {
        "url": "https://github.com/nxvvvv/safe-exam-browser-bypass/raw/main/SafeExamBrowser.Monitoring.dll",
        "description": "Monitoring module (patched - display/wireless checks removed)",
    },
    "SafeExamBrowser.SystemComponents.dll": {
        "url": "https://github.com/nxvvvv/safe-exam-browser-bypass/raw/main/SafeExamBrowser.SystemComponents.dll",
        "description": "System components (patched - VM/hardware checks removed)",
    },
}

SEB_INSTALL_PATHS = [
    r"C:\Program Files\SafeExamBrowser\Application",
    r"C:\Program Files (x86)\SafeExamBrowser\Application",
    os.path.expandvars(r"%LOCALAPPDATA%\SafeExamBrowser\Application"),
]


def find_seb_install_dir():
    for path in SEB_INSTALL_PATHS:
        if os.path.isdir(path):
            exe_path = os.path.join(path, "SafeExamBrowser.Client.exe")
            if os.path.isfile(exe_path):
                return path
    return None


def file_hash(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(url, dest, verbose=True):
    log = print if verbose else lambda *a, **k: None
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        log(f"  Downloading: {url}")
        log(f"  Destination: {dest}")
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })
        with urllib.request.urlopen(req, context=ctx, timeout=60) as response:
            total = response.headers.get("Content-Length")
            total = int(total) if total else None
            with open(dest, "wb") as f:
                downloaded = 0
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = (downloaded / total) * 100
                        log(f"  Progress: {pct:.1f}%")
        log(f"  [+] Download complete: {dest}")
        return True
    except Exception as e:
        log(f"  [!] Download failed: {e}")
        return False


def backup_originals(install_dir, verbose=True):
    log = print if verbose else lambda *a, **k: None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.path.dirname(install_dir), f"SafeExamBrowser_backup_{timestamp}")
    log(f"\n[*] Backing up originals to: {backup_dir}")
    os.makedirs(backup_dir, exist_ok=True)
    backed_up = []
    for filename in PATCHED_FILES:
        src = os.path.join(install_dir, filename)
        if os.path.isfile(src):
            dst = os.path.join(backup_dir, filename)
            shutil.copy2(src, dst)
            h = file_hash(src)
            log(f"  [+] Backed up: {filename} (SHA256: {h})")
            backed_up.append(filename)
        else:
            log(f"  [!] Not found: {filename}")
    if backed_up:
        info_path = os.path.join(backup_dir, "backup_info.txt")
        with open(info_path, "w") as f:
            f.write(f"Backup: {datetime.now()}\nSource: {install_dir}\n")
            for fn in backed_up:
                f.write(f"  {fn}: {file_hash(os.path.join(backup_dir, fn))}\n")
        log(f"  [+] Backup info saved")
    return backup_dir


def download_patched_files(download_dir, verbose=True):
    log = print if verbose else lambda *a, **k: None
    os.makedirs(download_dir, exist_ok=True)
    results = {}
    log("\n[*] Downloading patched SEB files...")
    for filename, info in PATCHED_FILES.items():
        dest = os.path.join(download_dir, filename)
        log(f"\n  --- {filename} ---")
        log(f"  {info['description']}")
        success = download_file(info["url"], dest, verbose)
        results[filename] = {"success": success, "path": dest, "hash": file_hash(dest) if success else None}
    return results


def apply_patch(install_dir, download_dir, verbose=True):
    log = print if verbose else lambda *a, **k: None
    log("\n[*] Applying patch...")
    count = 0
    for filename in PATCHED_FILES:
        src = os.path.join(download_dir, filename)
        dst = os.path.join(install_dir, filename)
        if not os.path.isfile(src):
            log(f"  [!] Not found: {src}")
            continue
        try:
            shutil.copy2(src, dst)
            log(f"  [+] Replaced: {filename} (SHA256: {file_hash(dst)})")
            count += 1
        except PermissionError:
            log(f"  [!] Permission denied - Run as Administrator!")
            return False
        except Exception as e:
            log(f"  [!] Failed: {e}")
    return count == len(PATCHED_FILES)


def patch_seb(install_dir=None, download_dir=None, verbose=True):
    log = print if verbose else lambda *a, **k: None
    result = {"success": False, "steps": {}}

    if not install_dir:
        install_dir = find_seb_install_dir()
    if not install_dir:
        log("[!] SEB not found! Specify with --install-dir")
        return result

    log(f"[+] SEB found at: {install_dir}")
    result["install_dir"] = install_dir

    try:
        backup_dir = backup_originals(install_dir, verbose)
        result["backup_dir"] = backup_dir
    except Exception as e:
        log(f"[!] Backup failed: {e}")
        return result

    if not download_dir:
        download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patched_files")

    try:
        dl = download_patched_files(download_dir, verbose)
        if not all(r["success"] for r in dl.values()):
            log("\n[!] Some downloads failed.")
            return result
    except Exception as e:
        log(f"[!] Download failed: {e}")
        return result

    try:
        if apply_patch(install_dir, download_dir, verbose):
            log("\n" + "=" * 50)
            log("[+] PATCH APPLIED SUCCESSFULLY!")
            log("=" * 50)
            log("\nSEB will now run without VM detection.")
            log("IMPORTANT: Edit logs if your proctor asks!")
            log(f"Backup: {backup_dir}")
            result["success"] = True
        else:
            log("\n[!] Partially applied. Run as Administrator.")
    except Exception as e:
        log(f"[!] Failed: {e}")

    return result


def restore_backup(backup_dir, install_dir, verbose=True):
    log = print if verbose else lambda *a, **k: None
    log(f"\n[*] Restoring from: {backup_dir}")
    if not os.path.isdir(backup_dir):
        log(f"[!] Not found: {backup_dir}")
        return False
    n = 0
    for filename in PATCHED_FILES:
        src = os.path.join(backup_dir, filename)
        dst = os.path.join(install_dir, filename)
        if os.path.isfile(src):
            try:
                shutil.copy2(src, dst)
                log(f"  [+] Restored: {filename}")
                n += 1
            except Exception as e:
                log(f"  [!] Failed: {e}")
    log(f"\n[+] Restored {n}/{len(PATCHED_FILES)} files")
    return n > 0


def check_patch_status(install_dir=None, verbose=True):
    log = print if verbose else lambda *a, **k: None
    if not install_dir:
        install_dir = find_seb_install_dir()
    if not install_dir:
        log("[!] SEB not found")
        return {"found": False}
    log(f"\n[*] Checking SEB at: {install_dir}")
    status = {"found": True, "install_dir": install_dir, "files": {}}
    for filename in PATCHED_FILES:
        fp = os.path.join(install_dir, filename)
        if os.path.isfile(fp):
            h = file_hash(fp)
            sz = os.path.getsize(fp)
            log(f"  {filename}: {sz:,} bytes, SHA256: {h}")
            status["files"][filename] = {"hash": h, "size": sz}
        else:
            log(f"  {filename}: NOT FOUND")
            status["files"][filename] = None
    return status


def print_patch_help():
    print("""
DLL Patcher - SEB VM Detection Bypass
======================================
Replaces SEB core files with patched versions (VM detection disabled).

Commands:
  patch     Download and apply the patch
  check     Check current SEB file status
  restore   Restore original files from backup

Examples:
  python dll_patcher.py patch
  python dll_patcher.py patch --install-dir "C:\\Program Files\\SafeExamBrowser\\Application"
  python dll_patcher.py check
  python dll_patcher.py restore --backup-dir PATH --install-dir PATH
""")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_patch_help()
        sys.exit(0)
    cmd = sys.argv[1].lower()
    install_dir = None
    for i, arg in enumerate(sys.argv):
        if arg == "--install-dir" and i + 1 < len(sys.argv):
            install_dir = sys.argv[i + 1]
    if cmd == "patch":
        patch_seb(install_dir=install_dir)
    elif cmd == "check":
        check_patch_status(install_dir=install_dir)
    elif cmd == "restore":
        backup_dir = None
        for i, arg in enumerate(sys.argv):
            if arg == "--backup-dir" and i + 1 < len(sys.argv):
                backup_dir = sys.argv[i + 1]
        if backup_dir and install_dir:
            restore_backup(backup_dir, install_dir)
        else:
            print("Usage: restore --backup-dir PATH --install-dir PATH")
    else:
        print_patch_help()
