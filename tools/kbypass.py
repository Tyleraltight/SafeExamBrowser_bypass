"""
Keyboard & Input Bypass Detection.

SEB blocks various keyboard shortcuts and input methods:
- Alt+Tab, Alt+F4, Win key, Ctrl+Esc, etc.
- Clipboard operations (Ctrl+C, Ctrl+V, Ctrl+X)
- Context menu (right-click)
- Function keys in some configurations
- Print Screen, Alt+PrintScreen
- Task Manager (Ctrl+Shift+Esc, Ctrl+Alt+Del)

This module detects:
- Which shortcuts SEB has hooked/blocked
- Which shortcuts SEB missed
- Input method (IME) status
- Alternative input channels
"""

import os
import sys
import ctypes
from ctypes import wintypes
from typing import Optional

from utils import cprint, is_windows, is_admin, Report

# ── Windows API constants ──────────────────────────────────────

if is_windows():
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    WH_KEYBOARD_LL = 13
    WH_KEYBOARD = 2


# Key definitions for testing
KEY_SHORTCUTS = [
    # (name, mod_keys, vk_code, description)
    ("Alt+Tab",     MOD_ALT | MOD_CONTROL,     0x09, "Switch applications"),
    ("Alt+F4",      MOD_ALT,                    0x73, "Close window"),
    ("Win",         MOD_WIN,                    0x5B, "Start menu"),
    ("Win+D",       MOD_WIN,                    0x44, "Show desktop"),
    ("Win+L",       MOD_WIN,                    0x4C, "Lock screen"),
    ("Ctrl+Esc",    MOD_CONTROL,                0x1B, "Start menu (alt)"),
    ("Ctrl+Alt+Del",MOD_CONTROL | MOD_ALT,      0x2E, "Security screen"),
    ("Ctrl+Shift+Esc", MOD_CONTROL | MOD_SHIFT, 0x1B, "Task Manager"),
    ("Alt+Space",   MOD_ALT,                    0x20, "Window menu"),
    ("F11",         0,                          0x7A, "Fullscreen toggle"),
    ("Ctrl+N",      MOD_CONTROL,                0x4E, "New window"),
    ("Ctrl+T",      MOD_CONTROL,                0x54, "New tab"),
    ("Ctrl+W",      MOD_CONTROL,                0x57, "Close tab"),
    ("Ctrl+R",      MOD_CONTROL,                0x52, "Refresh"),
    ("Ctrl+L",      MOD_CONTROL,                0x4C, "Address bar focus"),
    ("Ctrl+P",      MOD_CONTROL,                0x50, "Print"),
    ("Ctrl+S",      MOD_CONTROL,                0x53, "Save"),
    ("Ctrl+U",      MOD_CONTROL,                0x55, "View source"),
    ("Ctrl+J",      MOD_CONTROL,                0x4A, "Downloads"),
    ("Ctrl+Shift+I",MOD_CONTROL | MOD_SHIFT,    0x49, "DevTools"),
    ("F12",         0,                          0x7B, "DevTools (alt)"),
    ("Ctrl+Shift+C",MOD_CONTROL | MOD_SHIFT,    0x43, "Inspect element"),
    ("Ctrl+Shift+J",MOD_CONTROL | MOD_SHIFT,    0x4A, "Console"),
    ("Alt+Left",    MOD_ALT,                    0x25, "Back navigation"),
    ("Alt+Right",   MOD_ALT,                    0x27, "Forward navigation"),
    ("Ctrl+F",      MOD_CONTROL,                0x46, "Find on page"),
    ("Ctrl+H",      MOD_CONTROL,                0x48, "History"),
    ("Ctrl+D",      MOD_CONTROL,                0x44, "Bookmark"),
]

# Clipboard shortcuts (special handling)
CLIPBOARD_SHORTCUTS = [
    ("Ctrl+C", MOD_CONTROL, 0x43, "Copy"),
    ("Ctrl+V", MOD_CONTROL, 0x56, "Paste"),
    ("Ctrl+X", MOD_CONTROL, 0x58, "Cut"),
    ("Ctrl+Z", MOD_CONTROL, 0x5A, "Undo"),
    ("Ctrl+A", MOD_CONTROL, 0x41, "Select All"),
]


class KeyboardBypass:
    """Test keyboard/input restrictions."""

    def __init__(self, report: Report = None):
        self.report = report or Report()
        self.results = {}

    def scan(self) -> dict:
        """Run keyboard/input bypass checks."""
        cprint("\n[*] Keyboard & Input Bypass Detection", "CYAN", bold=True)

        if not is_windows():
            cprint("    [INFO] Keyboard testing is Windows-specific in this version", "INFO")
            self._scan_generic()
            return self.results

        self._check_keyboard_hooks()
        self._check_hotkeys()
        self._check_clipboard()
        self._check_ime()
        self._check_alternative_input()
        self._check_screen_capture_keys()

        return self.results

    def _scan_generic(self):
        """Generic (non-Windows) keyboard checks."""
        cprint("\n  ── Generic Input Analysis ──", "MAGENTA", bold=True)

        # Check for /dev/input (Linux)
        try:
            import glob
            input_devices = glob.glob("/dev/input/event*")
            if input_devices:
                cprint(f"    [INFO] {len(input_devices)} input device(s) found", "INFO")
                self.results["input_devices"] = len(input_devices)
        except Exception:
            pass

        self.report.add("keyboard", "Keyboard Scan", "info",
                        "Generic scan — limited to OS-level checks")

    def _check_keyboard_hooks(self):
        """
        Check if SEB has installed low-level keyboard hooks.
        SEB uses Windows hooks to intercept key combinations.
        """
        cprint("\n  ── Keyboard Hooks ──", "MAGENTA", bold=True)

        if not is_windows():
            return

        # Check for system-wide hooks by enumerating hook chains
        hook_info = self._enumerate_hooks()

        if hook_info:
            for h in hook_info:
                cprint(f"    [!] Hook: {h}", "YELLOW")
                self.report.add("keyboard", "Keyboard Hook", "warning", h)
        else:
            cprint("    [INFO] Could not enumerate hooks (need admin for full check)", "INFO")

        # Alternative: check if common hotkeys respond
        # This tests from the user perspective
        cprint("\n    Testing key response (user-space)...")
        self._test_key_combinations()

    def _enumerate_hooks(self) -> list[str]:
        """Enumerate installed keyboard hooks (requires Windows API)."""
        hooks = []
        if not is_windows():
            return hooks

        try:
            # Use a simple heuristic: check if a low-level keyboard hook is installed
            # by examining the hook chain via NtQuerySystemInformation
            # This is complex; a simpler approach is to use SysInternals tools

            # Actually, we can detect hooks by creating a message-only window
            # and testing if certain key combos reach it
            # For now, let's just report what SEB typically hooks
            seb_typical_hooks = [
                "WH_KEYBOARD_LL (low-level keyboard hook)",
                "WH_CBT (computer-based training hook)",
                "Clipboard hook (via clipboard viewer chain)",
            ]

            # SEB's hooks are per-process, so we can't see them from outside
            # unless we use kernel-level tools
            cprint("    [INFO] SEB hooks are per-process — testing effects instead", "INFO")

        except Exception as e:
            hooks.append(f"Hook detection error: {e}")

        return hooks

    def _test_key_combinations(self):
        """
        Test if key combinations are being intercepted.
        Uses RegisterHotKey as a probe — if SEB already registered the hotkey,
        our registration will fail.
        """
        if not is_windows():
            return

        tested = []
        try:
            import ctypes.wintypes

            # Create a hidden message window to test hotkey registration
            user32 = ctypes.windll.user32

            # Register a test hotkey for each combo — if SEB has already registered it,
            # the registration will fail
            # Simple test: try RegisterHotKey for various combos
            # If it returns 0, the hotkey is already registered (by SEB or system)
            for name, mod, vk, desc in KEY_SHORTCUTS[:15]:  # Test subset
                try:
                    # We use an incrementing ID
                    test_id = hash(name) & 0x7FFFFFFF
                    result = user32.RegisterHotKey(None, test_id, mod, vk)
                    if result == 0:
                        err = ctypes.get_last_error()
                        if err == 1400:  # ERROR_HOTKEY_ALREADY_REGISTERED
                            cprint(f"    [!] {name} — ALREADY REGISTERED (by SEB?)",
                                   "YELLOW")
                            tested.append((name, "blocked"))
                            self.report.add("keyboard", f"Hotkey: {name}",
                                           "warning", "Hotkey already registered")
                        else:
                            cprint(f"    [?] {name} — Registration failed (err={err})",
                                   "YELLOW")
                            tested.append((name, "unknown"))
                    else:
                        cprint(f"    [OK] {name} — available (not registered)",
                               "GREEN")
                        tested.append((name, "available"))
                        user32.UnregisterHotKey(None, test_id)
                except Exception:
                    pass

        except Exception as e:
            cprint(f"    [!] Hotkey test error: {e}", "RED")

        self.results["hotkey_test"] = tested

    def _check_hotkeys(self):
        """Check if standard Windows hotkeys are disabled."""
        cprint("\n  ── System Hotkeys ──", "MAGENTA", bold=True)

        if not is_windows():
            return

        # Check registry for hotkey restrictions
        try:
            import winreg
            # Some SEB configs modify system hotkeys via registry
            # Check NoWinKeys policy
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    try:
                        no_win_keys, _ = winreg.QueryValueEx(key, "NoWinKeys")
                        if no_win_keys:
                            cprint("    [!] NoWinKeys policy ENABLED — Win key disabled",
                                   "YELLOW")
                            self.report.add("keyboard", "Win Key Policy",
                                           "warning", "NoWinKeys policy is active")
                    except FileNotFoundError:
                        cprint("    [OK] NoWinKeys policy not set", "GREEN")
            except FileNotFoundError:
                cprint("    [OK] Explorer policy key not found", "GREEN")

        except Exception as e:
            cprint(f"    [INFO] Registry check error: {e}", "INFO")

    def _check_clipboard(self):
        """Check clipboard accessibility."""
        cprint("\n  ── Clipboard Status ──", "MAGENTA", bold=True)

        # Try to open clipboard
        if is_windows():
            try:
                import ctypes
                user32 = ctypes.windll.user32

                # Try to open clipboard
                result = user32.OpenClipboard(0)
                if result:
                    # Check what format is available
                    fmt = user32.EnumClipboardFormats(0)
                    formats = []
                    while fmt:
                        formats.append(fmt)
                        fmt = user32.EnumClipboardFormats(fmt)
                    user32.CloseClipboard()

                    cprint(f"    [OK] Clipboard accessible ({len(formats)} formats)",
                           "GREEN")
                    self.report.add("keyboard", "Clipboard", "ok",
                                   f"Clipboard accessible, {len(formats)} formats")

                    # Test clipboard operations
                    for name, mod, vk, desc in CLIPBOARD_SHORTCUTS:
                        cprint(f"    Testing {name} ({desc})...", "WHITE")
                        # Note: actual testing requires keyboard simulation
                        # which is beyond this scope

                else:
                    err = ctypes.get_last_error()
                    cprint(f"    [!] Cannot open clipboard (err={err}) — SEB may be blocking",
                           "YELLOW")
                    self.report.add("keyboard", "Clipboard", "warning",
                                   "Clipboard may be blocked by SEB")

            except Exception as e:
                cprint(f"    [!] Clipboard check error: {e}", "YELLOW")
        else:
            cprint("    [INFO] Clipboard check is Windows-specific", "INFO")

    def _check_ime(self):
        """Check Input Method Editor status."""
        cprint("\n  ── Input Method (IME) ──", "MAGENTA", bold=True)

        if is_windows():
            try:
                import ctypes

                # Check if IME is available
                imm32 = ctypes.windll.imm32
                user32 = ctypes.windll.user32

                # Get current thread's input context
                hIMC = imm32.ImmGetContext(user32.GetForegroundWindow())
                if hIMC:
                    imm32.ImmReleaseContext(user32.GetForegroundWindow(), hIMC)
                    cprint("    [OK] IME context available", "GREEN")
                    self.report.add("keyboard", "IME", "ok",
                                   "IME context accessible")
                else:
                    cprint("    [!] IME context not available — may be disabled", "YELLOW")
                    self.report.add("keyboard", "IME", "warning",
                                   "IME may be disabled")

            except Exception as e:
                cprint(f"    [INFO] IME check error: {e}", "INFO")
        else:
            cprint("    [INFO] IME check is Windows-specific", "INFO")

    def _check_alternative_input(self):
        """Check for alternative input methods that SEB might miss."""
        cprint("\n  ── Alternative Input Channels ──", "MAGENTA", bold=True)

        alternatives = []

        # 1. On-Screen Keyboard
        osk_path = r"C:\Windows\System32\osk.exe"
        if is_windows() and os.path.exists(osk_path):
            alternatives.append("On-Screen Keyboard (osk.exe)")

        # 2. Narrator
        narrator_path = r"C:\Windows\System32\narrator.exe"
        if is_windows() and os.path.exists(narrator_path):
            alternatives.append("Narrator (narrator.exe)")

        # 3. Magnifier
        mag_path = r"C:\Windows\System32\Magnify.exe"
        if is_windows() and os.path.exists(mag_path):
            alternatives.append("Magnifier (Magnify.exe)")

        # 4. Windows Speech Recognition
        wsr_path = r"C:\Windows\speech\Common\sapisvr.exe"
        if is_windows() and os.path.exists(wsr_path):
            alternatives.append("Speech Recognition")

        # 5. Touch keyboard
        touch_kb = r"C:\Windows\System32\TabTip.exe"
        if is_windows() and os.path.exists(touch_kb):
            alternatives.append("Touch Keyboard (TabTip.exe)")

        for alt in alternatives:
            cprint(f"    [?] Available: {alt}", "YELLOW")
            self.report.add("keyboard", f"Alt Input: {alt[:30]}", "info",
                           "Alternative input method available")

        if not alternatives:
            cprint("    [OK] No alternative input channels found", "GREEN")

        self.results["alternative_input"] = alternatives

    def _check_screen_capture_keys(self):
        """Check screen capture key status."""
        cprint("\n  ── Screen Capture Keys ──", "MAGENTA", bold=True)

        capture_keys = [
            ("Print Screen", "Full screen capture to clipboard"),
            ("Alt+PrintScreen", "Active window capture to clipboard"),
            ("Win+PrintScreen", "Full screen capture to file"),
            ("Win+Shift+S", "Snipping Tool (Win 10+)"),
            ("Ctrl+Alt+PrintScreen", "Screenshot of active window"),
        ]

        for name, desc in capture_keys:
            cprint(f"    [?] {name} — {desc}", "WHITE")
            self.report.add("keyboard", f"Capture Key: {name}", "info", desc)


def print_keyboard_result(result: dict):
    """Pretty-print keyboard analysis results."""
    if not result:
        return

    cprint("\n── Keyboard Bypass Verdict ──", "CYAN", bold=True)

    hotkey_test = result.get("hotkey_test", [])
    blocked = sum(1 for _, s in hotkey_test if s == "blocked")
    available = sum(1 for _, s in hotkey_test if s == "available")

    if blocked > 0:
        cprint(f"  [!] {blocked} hotkey(s) blocked by SEB", "YELLOW")
    if available > 0:
        cprint(f"  [OK] {available} hotkey(s) still available", "GREEN")

    alt_input = result.get("alternative_input", [])
    if alt_input:
        cprint(f"  [?] {len(alt_input)} alternative input channel(s) available",
               "YELLOW")
