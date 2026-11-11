"""
DLL Patcher - Wrapper and status/restore helper for SEB v3.10.x local C# patchers.

Calls scripts/patch_all.cmd (seb-patcher.exe + DisplayPatcher.exe) in non-interactive
mode and inspects/restores all patched SEB assemblies:
  - SafeExamBrowser.Monitoring.dll
  - SafeExamBrowser.Configuration.dll
  - SafeExamBrowser.Client.exe
  - SafeExamBrowser.exe
  - SafeExamBrowser.UserInterface.Shared.dll
  - SafeExamBrowser.Lockdown.dll (if present/patched)
"""

import os
import sys
import shutil
import hashlib
import subprocess
import urllib.request
import ssl
from datetime import datetime

V3_10_PATCHED_FILES = [
    "SafeExamBrowser.Monitoring.dll",
    "SafeExamBrowser.Configuration.dll",
    "SafeExamBrowser.Client.exe",
    "SafeExamBrowser.exe",
    "SafeExamBrowser.UserInterface.Shared.dll",
]

OPTIONAL_PATCHED_FILES = [
    "SafeExamBrowser.Lockdown.dll",
]

# Legacy v3.6.x remote file list (deprecated; kept only for reference)
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


def _get_candidate_install_paths():
    candidates = []
    for env_var in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env_var)
        if base:
            candidates.append(os.path.join(base, "SafeExamBrowser", "Application"))
    for fallback in (
        r"C:\Program Files\SafeExamBrowser\Application",
        r"C:\Program Files (x86)\SafeExamBrowser\Application",
    ):
        if fallback not in candidates:
            candidates.append(fallback)
    return candidates


SEB_INSTALL_PATHS = _get_candidate_install_paths()


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_seb_install_dir():
    for path in _get_candidate_install_paths():
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
        log(f"  Downloading: {url}")
        log(f"  Destination: {dest}")
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })
        # Try with default SSL verification first
        ctx = None
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
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
                        if total and downloaded % (64 * 1024) < 8192:
                            pct = (downloaded / total) * 100
                            log(f"  Progress: {pct:.1f}%")
        except ssl.SSLError as ssl_err:
            log(f"  [!] SSL verification failed: {ssl_err}")
            log(f"  [!] Retrying without SSL verification (less secure)...")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
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
                        if total and downloaded % (64 * 1024) < 8192:
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

    target_dir = install_dir or find_seb_install_dir()
    if not target_dir or not os.path.isdir(target_dir):
        log("[!] SEB installation directory not found. Pass --install-dir PATH.")
        return result

    script_path = os.path.join(_repo_root(), "scripts", "patch_all.cmd")
    if not os.path.isfile(script_path):
        log(f"[!] Cannot find unified patch script at: {script_path}")
        return result

    log("[*] Running local C# patchers for SEB v3.10.x via patch_all.cmd...")
    log(f"[*] Target SEB directory: {target_dir}")

    try:
        # Outer quotes protect cmd.exe /c quote-stripping when paths contain spaces.
        cmd_str = f'cmd.exe /c ""{script_path}" --nopause "{target_dir}""'
        log(f"[*] Executing: {cmd_str}")
        proc = subprocess.run(cmd_str, shell=False, stdin=subprocess.DEVNULL, timeout=600)
        result["returncode"] = proc.returncode
        result["install_dir"] = target_dir
        if proc.returncode == 0:
            result["success"] = True
            log("\n[+] Local patchers executed successfully.")
        else:
            log(f"\n[!] Patch script returned error code: {proc.returncode}")
    except Exception as e:
        log(f"[!] Failed to execute patch script: {e}")

    return result


def restore_backup(backup_dir=None, install_dir=None, verbose=True):
    log = print if verbose else lambda *a, **k: None
    target_dir = install_dir or find_seb_install_dir()
    if not target_dir or not os.path.isdir(target_dir):
        log("[!] SEB installation directory not found. Pass --install-dir PATH.")
        return False

    if backup_dir:
        log(f"\n[*] Restoring from: {backup_dir}")
        if not os.path.isdir(backup_dir):
            log(f"[!] Not found: {backup_dir}")
            return False
        candidates = list(dict.fromkeys(V3_10_PATCHED_FILES + OPTIONAL_PATCHED_FILES + list(PATCHED_FILES.keys())))
        n = 0
        present = 0
        for filename in candidates:
            src = os.path.join(backup_dir, filename)
            dst = os.path.join(target_dir, filename)
            if os.path.isfile(src):
                present += 1
                try:
                    shutil.copy2(src, dst)
                    log(f"  [+] Restored: {filename}")
                    n += 1
                except Exception as e:
                    log(f"  [!] Failed: {e}")
        log(f"\n[+] Restored {n}/{present} files")
        return n > 0

    # Restore from .bak files in target_dir via seb-patcher.exe if present, else copy .bak directly
    seb_patcher = os.path.join(_repo_root(), "bin", "final", "seb-patcher.exe")
    if os.path.isfile(seb_patcher):
        log(f"\n[*] Running seb-patcher.exe restore on: {target_dir}")
        try:
            proc = subprocess.run([seb_patcher, "restore", target_dir], stdin=subprocess.DEVNULL, timeout=600)
            if proc.returncode == 0:
                return True
            log(f"[!] seb-patcher restore exited with code {proc.returncode}; falling back to .bak copy")
        except Exception as e:
            log(f"[!] Failed to run seb-patcher restore: {e}")

    n = 0
    for filename in V3_10_PATCHED_FILES + OPTIONAL_PATCHED_FILES:
        bak = os.path.join(target_dir, filename + ".bak")
        dst = os.path.join(target_dir, filename)
        if os.path.isfile(bak):
            try:
                shutil.copy2(bak, dst)
                log(f"  [+] Restored from .bak: {filename}")
                n += 1
            except Exception as e:
                log(f"  [!] Failed to restore {filename}: {e}")
    log(f"\n[+] Restored {n} file(s) from .bak backups")
    return n > 0


def check_patch_status(install_dir=None, verbose=True):
    log = print if verbose else lambda *a, **k: None
    if not install_dir:
        install_dir = find_seb_install_dir()
    if not install_dir or not os.path.isdir(install_dir):
        log("[!] SEB not found")
        return {"found": False}
    log(f"\n[*] Checking SEB at: {install_dir}")
    status = {"found": True, "install_dir": install_dir, "files": {}}

    all_targets = list(V3_10_PATCHED_FILES)
    for opt in OPTIONAL_PATCHED_FILES:
        if os.path.isfile(os.path.join(install_dir, opt)):
            all_targets.append(opt)

    for filename in all_targets:
        fp = os.path.join(install_dir, filename)
        bak_exists = os.path.isfile(fp + ".bak")
        if os.path.isfile(fp):
            h = file_hash(fp)
            sz = os.path.getsize(fp)
            log(f"  {filename}: {sz:,} bytes, SHA256: {h[:16]}... (backup: {'yes' if bak_exists else 'no'})")
            status["files"][filename] = {"hash": h, "size": sz, "backup": bak_exists}
        else:
            log(f"  {filename}: NOT FOUND")
            status["files"][filename] = None

    seb_patcher = os.path.join(_repo_root(), "bin", "final", "seb-patcher.exe")
    if os.path.isfile(seb_patcher):
        log("\n[*] Running seb-patcher.exe check...")
        try:
            proc = subprocess.run(
                [seb_patcher, "check", install_dir],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if proc.stdout:
                log(proc.stdout.rstrip())
            if proc.stderr:
                log(proc.stderr.rstrip())
            status["seb_patcher_check_rc"] = proc.returncode
        except Exception as e:
            log(f"[!] seb-patcher check failed: {e}")

    return status


def print_patch_help():
    print("""
DLL Patcher - SEB VM & RDP Detection Bypass
===========================================
Runs local C# IL patchers (seb-patcher + DisplayPatcher) against SEB v3.10.x.

Commands:
  patch     Run scripts/patch_all.cmd --nopause against SEB installation
  check     Check current SEB file hashes, backups, and IL patch status
  restore   Restore original files from .bak backups or --backup-dir

Examples:
  python dll_patcher.py patch
  python dll_patcher.py patch --install-dir "C:\\Program Files\\SafeExamBrowser\\Application"
  python dll_patcher.py check
  python dll_patcher.py restore --install-dir "C:\\Program Files\\SafeExamBrowser\\Application"
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
        res = patch_seb(install_dir=install_dir)
        sys.exit(0 if res.get("success") else 1)
    elif cmd == "check":
        res = check_patch_status(install_dir=install_dir)
        sys.exit(0 if res.get("found") else 1)
    elif cmd == "restore":
        backup_dir = None
        for i, arg in enumerate(sys.argv):
            if arg == "--backup-dir" and i + 1 < len(sys.argv):
                backup_dir = sys.argv[i + 1]
        ok = restore_backup(backup_dir=backup_dir, install_dir=install_dir)
        sys.exit(0 if ok else 1)
    else:
        print_patch_help()
