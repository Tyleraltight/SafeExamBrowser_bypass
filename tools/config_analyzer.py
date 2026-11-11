"""
SEB Configuration File Analyzer.

Parses and decrypts .seb configuration files.
SEB configs are encrypted plist files using AES-256-CBC.

File format (older SEB 2.x):
  [32 bytes salt][rest is AES-CBC ciphertext]
  Key = PBKDF2(password, salt, 10000, SHA256, 32)

File format (SEB 3.x):
  May use different encryption: AES-CTR or include a keychain-encrypted key.
  First bytes indicate the version/format.

Plist key meanings (partial list — SEB uses hundreds of keys):
  quitURL                    — URL opened when SEB quits
  examKeySalt                — salt for browser exam key
  browserExamKey             — browser exam key (32 bytes)
  urlFilterBlacklist         — blocked URL patterns
  urlFilterWhitelist         — allowed URL patterns
  allowSwitchToApplications  — can user alt-tab?
  enableQuit                 — can user quit?
  hideMenuBar                — hide menu bar?
  enableLockSpellCheck       — spell check enabled?
  allowedKeys                — keys not blocked
  blockedKeys                — keys that are blocked
  userDefined               — custom config dict
"""

import os
import sys
import plistlib
import struct
from pathlib import Path

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    HAS_CRYPTO = True
except ImportError:
    try:
        from Cryptodome.Cipher import AES
        from Cryptodome.Util.Padding import unpad
        HAS_CRYPTO = True
    except ImportError:
        HAS_CRYPTO = False

from utils import (
    cprint, derive_key_pbkdf2, hex_dump, file_hash, Report
)


# ── SEB key name mapping (common keys) ────────────────────────

SEB_KEY_NAMES = {
    "quitURL": "Quit URL",
    "startURL": "Start URL",
    "browserExamKey": "Browser Exam Key",
    "examKeySalt": "Exam Key Salt",
    "urlFilterBlacklist": "URL Blacklist",
    "urlFilterWhitelist": "URL Whitelist",
    "allowSwitchToApplications": "Allow App Switching",
    "enableQuit": "Quit Enabled",
    "hideMenuBar": "Hide Menu Bar",
    "enableLockSpellCheck": "Lock Spell Check",
    "allowBrowsingBackForward": "Allow Back/Forward",
    "newBrowserWindowByLink": "Allow New Window by Link",
    "openLinksNewWindow": "Open Links in New Window",
    "removeProfile": "Remove Profile on Quit",
    "allowDictionaryLookup": "Allow Dictionary Lookup",
    "enableScrollLock": "Scroll Lock",
    "allowPrinting": "Allow Printing",
    "allowCopy": "Allow Copy",
    "allowCut": "Allow Cut",
    "allowPaste": "Allow Paste",
    "allowSelectAll": "Allow Select All",
    "allowExport": "Allow Export",
    "blockPopUpWindows": "Block Pop-ups",
    "allowVideoCapture": "Allow Video Capture",
    "allowAudioCapture": "Allow Audio Capture",
    "allowScreenSharing": "Allow Screen Sharing (RDP / Capture)",
    "allowScreenCapture": "Allow Screen Capture (Legacy)",
    "createNewDesktop": "Create New Desktop (Kiosk Mode)",
    "disableSessionChangeLockScreen": "Disable Session Change Lock Screen",
    "sebServicePolicy": "SEB Service Policy",
    "sebServiceIgnore": "Ignore SEB Service",
    "enableVirtualMachineDetection": "VM Detection",
    "allowVirtualMachine": "Allow VM",
    "blockAccessToLocalFiles": "Block Local Files",
    "allowDownloads": "Allow Downloads",
    "downloadDirectory": "Download Directory",
    "autoQuit": "Auto Quit",
    "allowLogQuery": "Allow Log Query",
    "userAgent": "User Agent",
    "browserUserAgent": "Browser User Agent",
    "sendBrowserExamKey": "Send Browser Exam Key",
    "thirdPartyStopKeys": "Third Party Stop Keys",
    "enableAppSwitcherCheck": "App Switcher Check",
    "blacklistedProcesses": "Blacklisted Processes",
    "whitelistedProcesses": "Whitelisted Processes",
    "allowedProcesses": "Allowed Processes",
    "blockedProcesses": "Blocked Processes",
    "allowSiri": "Allow Siri",
    "allowAccessibility": "Allow Accessibility",
    "allowFlashFullscreen": "Allow Flash Fullscreen",
    "enableUIInterrupts": "UI Interrupts Enabled",
    "originatorVersion": "SEB Version",
    "sebMode": "SEB Mode",
}


SERVICE_POLICY_NAMES = {
    0: "Mandatory (0)",
    1: "Optional (1)",
    2: "Warn (2)",
}


class SEBConfigAnalyzer:
    """Analyze SEB .seb configuration files."""

    def __init__(self, report: Report = None):
        self.report = report or Report()

    def analyze(self, filepath: str, password: str = "") -> dict:
        """
        Full analysis of a .seb file.
        Returns a dict with all extracted information.
        """
        path = Path(filepath)
        if not path.exists():
            cprint(f"[-] File not found: {filepath}", "RED")
            return {}

        cprint(f"\n[*] Analyzing: {filepath}", "CYAN", bold=True)

        result = {
            "file": str(path.absolute()),
            "hashes": file_hash(filepath),
            "size": path.stat().st_size,
            "header": {},
            "encryption": {},
            "config": {},
            "security_settings": {},
            "rdp_vmware_notes": [],
            "findings": [],
        }

        with open(filepath, "rb") as f:
            data = f.read()

        # Parse header
        result["header"] = self._parse_header(data)

        # Detect format version
        fmt = self._detect_format(data)
        result["encryption"]["format"] = fmt
        cprint(f"  Format: {fmt}", "WHITE")

        # Try decryption (or direct parse for plaintext plist)
        if password or fmt == "plaintext_plist":
            plist_data = self._decrypt(data, password, fmt)
            if plist_data:
                result["encryption"]["decrypted"] = True
                result["encryption"]["method"] = (
                    "None (plaintext plist)"
                    if fmt == "plaintext_plist"
                    else "AES-256-CBC with PBKDF2"
                )

                # Parse plist
                try:
                    config = plistlib.loads(plist_data)
                    result["config"] = self._sanitize_config(config)
                    result["security_settings"] = self._extract_security(config)
                    result["rdp_vmware_notes"] = self._analyze_rdp_vmware_notes(config)
                    cprint(f"  [+] Decrypted successfully — {len(config)} keys", "GREEN")
                except Exception as e:
                    cprint(f"  [-] Plist parse error: {e}", "RED")
                    result["encryption"]["parse_error"] = str(e)
            else:
                result["encryption"]["decrypted"] = False
                cprint("  [-] Decryption failed — wrong password or unknown format", "RED")
                self.report.add("config", "Decryption", "warning",
                               f"Failed to decrypt {filepath}")
        else:
            cprint("  [!] No password provided — skipping decryption", "YELLOW")
            cprint("      Use: --password <password>", "YELLOW")
            result["encryption"]["decrypted"] = False

        # Analyze header info regardless of decryption
        self._analyze_header_findings(result)

        return result

    def _detect_format(self, data: bytes) -> str:
        """Detect the SEB config file format version."""
        # SEB 2.x: starts with salt (random bytes), no magic
        # SEB 3.x+: may have version markers

        # Check if it starts with a plist header (unencrypted)
        if data[:6] == b"<?xml " or data[:6] == b"bplist":
            return "plaintext_plist"

        # SEB 3.x uses a different structure
        # The first 32 bytes could be a salt (SEB 2.x style)
        # or could contain a version marker

        # Heuristic: if file starts with bytes that look like UTF-8
        # text for plist, it might be unencrypted
        try:
            data[:50].decode("utf-8")
            # Could be plaintext or garbled
        except UnicodeDecodeError:
            pass

        return "encrypted_v2"  # Default assumption: SEB 2.x style

    def _parse_header(self, data: bytes) -> dict:
        """Parse the first bytes of a .seb file for version info."""
        header = {
            "first_16_hex": data[:16].hex(),
            "size": len(data),
        }

        # Check for known SEB format markers
        if len(data) >= 4:
            # Try to interpret first 4 bytes
            header["first_4_hex"] = data[:4].hex()

        if len(data) >= 32:
            header["first_32_hex"] = data[:32].hex()

        return header

    def _decrypt(self, data: bytes, password: str, fmt: str) -> bytes | None:
        """Decrypt a .seb config file."""
        if fmt == "plaintext_plist":
            return data

        if not HAS_CRYPTO:
            cprint("  [-] pycryptodome not installed!", "RED")
            return None

        if fmt == "encrypted_v2":
            return self._decrypt_v2(data, password)

        return None

    def _decrypt_v2(self, data: bytes, password: str) -> bytes | None:
        """
        Decrypt SEB 2.x format.
        First 32 bytes = salt, rest = AES-256-CBC ciphertext.
        Padding: PKCS7.
        """
        try:
            salt = data[:32]
            ciphertext = data[32:]

            # Derive key
            key = derive_key_pbkdf2(password, salt, iterations=10000, key_len=32)

            # Decrypt
            cipher = AES.new(key, AES.MODE_CBC, iv=b"\x00" * 16)
            # SEB uses zero IV or the first block of ciphertext as IV
            # Actually, SEB typically uses a 16-byte IV. Let's check:
            # In some implementations, the IV is prepended after the salt.
            # Let's try with the first 16 bytes of ciphertext as IV:

            if len(ciphertext) > 16:
                iv = ciphertext[:16]
                actual_ciphertext = ciphertext[16:]
                cipher = AES.new(key, AES.MODE_CBC, iv=iv)
                plaintext = unpad(cipher.decrypt(actual_ciphertext), AES.block_size)
                return plaintext
            else:
                return None

        except Exception as e:
            cprint(f"  [!] Decrypt error: {e}", "YELLOW")
            return None

    def _sanitize_config(self, config: dict) -> dict:
        """Clean up config for display — truncate large values."""
        sanitized = {}
        for k, v in config.items():
            if isinstance(v, bytes) and len(v) > 64:
                sanitized[k] = f"<bytes[{len(v)}]>"
            elif isinstance(v, dict) and len(v) > 20:
                sanitized[k] = f"<dict with {len(v)} keys>"
            elif isinstance(v, list) and len(v) > 20:
                sanitized[k] = f"<list with {len(v)} items>"
            else:
                sanitized[k] = v
        return sanitized

    def _extract_security(self, config: dict) -> dict:
        """Extract security-relevant settings from decrypted config."""
        security = {}

        # Key security settings to check
        checks = [
            ("allowSwitchToApplications", "App Switching", True),
            ("enableQuit", "Quit Allowed", True),
            ("allowCopy", "Copy Allowed", True),
            ("allowPaste", "Paste Allowed", True),
            ("allowPrinting", "Printing Allowed", True),
            ("allowScreenSharing", "Screen Sharing (RDP / Capture)", True),
            ("allowScreenCapture", "Screen Capture (Legacy)", True),
            ("allowVideoCapture", "Video Capture", True),
            ("allowAudioCapture", "Audio Capture", True),
            ("createNewDesktop", "Create New Desktop", True),
            ("disableSessionChangeLockScreen", "Disable Session Change Lock Screen", True),
            ("sebServiceIgnore", "Ignore SEB Service", True),
            ("allowVirtualMachine", "VM Allowed (Config)", True),
            ("enableVirtualMachineDetection", "VM Detection", True),
            ("blockPopUpWindows", "Pop-up Blocking", True),
            ("blockAccessToLocalFiles", "Local File Access Blocked", True),
            ("hideMenuBar", "Menu Bar Hidden", True),
            ("enableLockSpellCheck", "Spell Check Locked", True),
            ("allowAccessibility", "Accessibility Allowed", True),
            ("allowSiri", "Siri Allowed", True),
            ("allowBrowsingBackForward", "Back/Forward Navigation", True),
            ("allowDictionaryLookup", "Dictionary Lookup", True),
            ("allowDownloads", "Downloads Allowed", True),
            ("sendBrowserExamKey", "Browser Exam Key Sent", True),
        ]

        for key, name, restrict_by_default in checks:
            if key in config:
                val = config[key]
                if isinstance(val, bool):
                    security[name] = val
                elif isinstance(val, (int, float)):
                    security[name] = bool(val)
                else:
                    security[name] = str(val)

        if "sebServicePolicy" in config:
            raw_policy = config["sebServicePolicy"]
            if isinstance(raw_policy, int):
                security["SEB Service Policy"] = SERVICE_POLICY_NAMES.get(
                    raw_policy, f"Unknown ({raw_policy})"
                )
            else:
                security["SEB Service Policy"] = str(raw_policy)

        # Process lists
        for list_key in ["blacklistedProcesses", "whitelistedProcesses",
                         "allowedProcesses", "blockedProcesses"]:
            if list_key in config:
                procs = config[list_key]
                if isinstance(procs, list):
                    security[list_key] = [p.get("identifier", str(p))
                                          for p in procs if isinstance(p, dict)]

        # URL filters
        for filter_key in ["urlFilterBlacklist", "urlFilterWhitelist"]:
            if filter_key in config:
                flt = config[filter_key]
                if isinstance(flt, (list, dict)):
                    security[filter_key] = flt

        return security

    @staticmethod
    def _as_bool(value):
        """Normalize bool/int/string plist values to bool or None."""
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            low = value.strip().lower()
            if low in ("true", "1", "yes"):
                return True
            if low in ("false", "0", "no"):
                return False
        return None

    def _analyze_rdp_vmware_notes(self, config: dict) -> list[dict]:
        """Generate RDP and VMware behavior notes from SEB configuration keys."""
        notes = []

        # Table-driven boolean keys (key, default, scope, true_detail, false_detail, include_when)
        bool_specs = [
            (
                "allowScreenSharing",
                False,
                "RDP",
                "allowScreenSharing is true: SEB allows remote sessions and skips WDA_EXCLUDEFROMCAPTURE.",
                "SEB blocks RDP via RemoteSessionOperation and applies WDA_EXCLUDEFROMCAPTURE (windows render black/invisible over RDP unless patched).",
                "always",
            ),
            (
                "createNewDesktop",
                True,
                "RDP",
                "SEB creates a custom desktop and calls SwitchDesktop/CreateProcess, which often fails or freezes in Windows RDP sessions unless KioskModeOperation is patched.",
                "createNewDesktop is false: SEB runs on the active desktop (DisableExplorerShell or None), avoiding custom-desktop RDP failures.",
                "always",
            ),
            (
                "disableSessionChangeLockScreen",
                False,
                "RDP / VMware",
                "",
                "RDP reconnects or VMware console/session switches trigger the red lock screen unless SafeExamBrowser.Client.exe (MonitoringResponsibility) is patched.",
                "false_only",
            ),
            (
                "allowVirtualMachine",
                False,
                "VMware",
                "allowVirtualMachine is true in config.",
                "allowVirtualMachine is false: requires VirtualMachineDetector and VirtualMachineOperation patches in VMware (does not affect browser WebGL/face-detection).",
                "present_only",
            ),
        ]

        for key, default, scope, true_detail, false_detail, mode in bool_specs:
            present = key in config
            if mode == "present_only" and not present:
                continue
            parsed = self._as_bool(config.get(key))
            effective = parsed if parsed is not None else default
            if mode == "false_only" and effective:
                continue
            if present and parsed is not None:
                val = effective
                status_txt = "true" if effective else "false"
            else:
                status_txt = f"unset (defaults to {'true' if default else 'false'})"
                val = status_txt

            if effective:
                detail = true_detail if mode == "present_only" or key != "createNewDesktop" else f"{key} is {status_txt}: {true_detail}"
            else:
                detail = false_detail if mode == "present_only" else f"{key} is {status_txt}: {false_detail}"

            notes.append({"key": key, "value": val, "scope": scope, "detail": detail})

        if "allowScreenCapture" in config and "allowScreenSharing" not in config:
            notes.append({
                "key": "allowScreenCapture",
                "value": config["allowScreenCapture"],
                "scope": "RDP",
                "detail": (
                    "Legacy allowScreenCapture is present, but SEB 3.10.x maps "
                    "window capture and remote-connection policy from allowScreenSharing."
                ),
            })

        # sebServicePolicy & sebServiceIgnore
        raw_policy = config.get("sebServicePolicy")
        service_policy = raw_policy if isinstance(raw_policy, int) and not isinstance(raw_policy, bool) else None
        service_ignore = bool(self._as_bool(config.get("sebServiceIgnore")))
        policy_label = SERVICE_POLICY_NAMES.get(
            service_policy,
            f"unset (defaults to {SERVICE_POLICY_NAMES[0]})" if raw_policy is None else str(raw_policy),
        )
        if not service_ignore and (service_policy is None or service_policy == 0):
            notes.append({
                "key": "sebServicePolicy / sebServiceIgnore",
                "value": f"policy={policy_label}, ignore={service_ignore}",
                "scope": "RDP / VMware",
                "detail": (
                    "SEB requires SafeExamBrowser.Service (Mandatory). Running the "
                    "service enforces fDenyTSConnections=1 (drops RDP) and VMware VDM "
                    "EnableShade; stopping the service requires ServiceOperation to be patched."
                ),
            })
        else:
            notes.append({
                "key": "sebServicePolicy / sebServiceIgnore",
                "value": f"policy={policy_label}, ignore={service_ignore}",
                "scope": "RDP / VMware",
                "detail": (
                    "SEB does not strictly require SafeExamBrowser.Service "
                    "(Optional/Warn or sebServiceIgnore=true)."
                ),
            })

        return notes

    def _analyze_header_findings(self, result: dict):
        """Add findings based on header analysis."""
        header = result["header"]
        encryption = result["encryption"]
        security = result.get("security_settings", {})

        # Check encryption status
        if encryption.get("decrypted"):
            self.report.add("config", "Config Encrypted", "ok",
                           "Config file is encrypted (standard)")
        elif encryption.get("format") == "plaintext_plist":
            self.report.add("config", "Config Plaintext", "vulnerable",
                           "Config file is NOT encrypted!")
        else:
            self.report.add("config", "Config Encrypted", "info",
                           "Config is encrypted; provide password to analyze")

        # Check specific security settings
        for setting, val in security.items():
            if isinstance(val, bool):
                if "Allowed" in setting and val:
                    self.report.add("security", setting, "warning",
                                   f"Setting is enabled (less restrictive)")
                elif "Detection" in setting and not val:
                    self.report.add("security", setting, "warning",
                                   f"VM detection is disabled")

        # Process blacklists/whitelists
        if "blacklistedProcesses" in security:
            procs = security["blacklistedProcesses"]
            self.report.add("security", "Process Blacklist", "info",
                           f"{len(procs)} blacklisted processes")

        if "whitelistedProcesses" in security:
            procs = security["whitelistedProcesses"]
            self.report.add("security", "Process Whitelist", "info",
                           f"{len(procs)} whitelisted processes")

        for note in result.get("rdp_vmware_notes", []):
            self.report.add(
                "rdp_vmware",
                f"{note['scope']}: {note['key']}",
                "info",
                note["detail"],
            )


def print_config_result(result: dict):
    """Pretty-print config analysis results."""
    if not result:
        return

    cprint("\n── File Info ──", "CYAN", bold=True)
    print(f"  Path: {result['file']}")
    print(f"  Size: {result['size']:,} bytes")
    for algo, h in result["hashes"].items():
        print(f"  {algo.upper():>8}: {h}")

    cprint("\n── Encryption ──", "CYAN", bold=True)
    enc = result["encryption"]
    for k, v in enc.items():
        if k != "format":
            print(f"  {k}: {v}")

    if result["config"]:
        cprint("\n── Configuration Keys ──", "CYAN", bold=True)
        for k, v in sorted(result["config"].items()):
            name = SEB_KEY_NAMES.get(k, k)
            val_str = str(v)[:80]
            print(f"  {name:>35}: {val_str}")

    if result["security_settings"]:
        cprint("\n── Security Settings ──", "CYAN", bold=True)
        for k, v in sorted(result["security_settings"].items()):
            if isinstance(v, bool):
                icon = "WARNING" if v else "OK"
                color = "YELLOW" if v else "GREEN"
                cprint(f"  [{icon:>7}] {k}", color)
            elif isinstance(v, list):
                print(f"  {k}: {len(v)} entries")
            else:
                print(f"  {k}: {str(v)[:60]}")

    if result.get("rdp_vmware_notes"):
        cprint("\n── RDP & VMware Behavior Notes ──", "CYAN", bold=True)
        for note in result["rdp_vmware_notes"]:
            cprint(f"  [{note['scope']}] {note['key']} = {note['value']}", "YELLOW")
            print(f"      {note['detail']}")
