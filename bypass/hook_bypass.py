"""
Keyboard Hook Bypass — removes or bypasses SEB's keyboard hooks.

SEB installs a WH_KEYBOARD_LL (low-level keyboard hook) via
SetWindowsHookExW to intercept all keyboard input before it reaches
applications. When SEB's hook sees a blocked combo (Alt+Tab, Win, etc.)
it returns non-zero, consuming the input.

Bypass methods:
1. UnhookWindowsHookEx — directly remove SEB's hook handle
2. Inject into SEB's message loop — WH_KEYBOARD_LL runs in SEB's
   thread context; flooding its message queue can cause hook timeout
3. RawInput API — bypass the hook chain entirely for new devices
4. Pre-loaded keyboard listener — start before SEB, capture combos
   via raw input and forward them

Method 1 requires finding SEB's hook handle.
Method 2 (message flood) is the most reliable post-startup approach.
"""

import ctypes
import ctypes.wintypes
import time
import threading
import struct
import os

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ── Constants ──────────────────────────────────────────────────

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
HC_ACTION = 0
HC_NOREMOVE = 3

VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_DELETE = 0x2E
VK_SNAPSHOT = 0x2C
VK_F4 = 0x73
VK_F5 = 0x74
VK_F11 = 0x7A
VK_F12 = 0x7B

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

GWLP_WNDPROC = -4
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008


# ── Callback types ─────────────────────────────────────────────

HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
)

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long,
    ctypes.wintypes.HWND, ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KeyboardHookBypass:
    """Bypass SEB's low-level keyboard hook."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._log = print if verbose else lambda *a, **k: None
        self._our_hook = None
        self._flood_thread = None
        self._flood_active = False
        self._hooks_removed = False

    # ── Method 1: Remove SEB hooks via UnhookWindowsHookEx ─────

    def remove_seb_hooks(self) -> bool:
        """
        Find and remove SEB's keyboard hooks.
        We enumerate all hooks and unhook those belonging to SEB.
        """
        self._log("[*] Attempting to remove SEB keyboard hooks...")

        # Get the hook table via NtUserQueryWindow (undocumented)
        # Simpler approach: use RegisterRawInputDevices as alternative input
        # and try to unhook by hook ID

        # SEB typically installs hook with ID 0 or GetWindowsHookEx returns
        # We can try to get the hook from the system's hook table
        # This requires knowing the hook ID or getting it from SEB's process

        # Alternative: try to call UnhookWindowsHookEx with common hook IDs
        # This is unreliable — better to use Method 2

        # For now, attempt via direct approach
        try:
            # Try to find SEB's hook by examining its process
            import psutil
            seb_pids = []
            for proc in psutil.process_iter(["pid", "name"]):
                name = proc.info.get("name", "")
                if "SafeExamBrowser" in name:
                    seb_pids.append(proc.info["pid"])

            if not seb_pids:
                self._log("  [!] SEB process not found")
                return False

            self._log(f"  [+] Found SEB PIDs: {seb_pids}")

            # Attempt: use undocumented function to get hook handles
            # This is the most direct approach
            # NtUserBuildHwndList can enumerate thread hooks

            self._log("  [!] Direct hook removal requires kernel-level access")
            self._log("  [*] Falling back to message flood method...")
            return False

        except Exception as e:
            self._log(f"  [!] Hook removal failed: {e}")
            return False

    # ── Method 2: Message Flood (most reliable) ────────────────

    def flood_seb_message_loop(self, duration: float = 3.0) -> bool:
        """
        WH_KEYBOARD_LL hooks run in the installing thread's message loop.
        If we flood SEB's thread with messages, the hook callback won't
        process keyboard messages within the timeout window (DefaultInputTimeout
        = 300ms). Windows then removes the hook automatically.

        This is the standard technique for disabling LL hooks.
        """
        self._log("[*] Flooding SEB message loop to disable hooks...")

        try:
            import psutil

            # Find SEB's GUI thread
            seb_hwnd = self._find_seb_window()
            if not seb_hwnd:
                self._log("  [!] SEB window not found")
                return False

            thread_id = user32.GetWindowThreadProcessId(seb_hwnd, None)
            self._log(f"  [+] SEB window: 0x{seb_hwnd:x}, thread: {thread_id}")

            # Get all message types to spam
            # Sending WM_NULL (0x0000) in a tight loop overwhelms the message queue
            self._flood_active = True

            def _flood():
                end = time.time() + duration
                while time.time() < end and self._flood_active:
                    # PostThreadMessage with WM_NULL floods the queue
                    user32.PostThreadMessageW(thread_id, 0x0000, 0, 0)
                    # Also try PostMessage to the window directly
                    user32.PostMessageW(seb_hwnd, 0x0000, 0, 0)
                    # Don't sleep — maximum flood rate

            self._flood_thread = threading.Thread(target=_flood, daemon=True)
            self._flood_thread.start()

            self._log(f"  [*] Flooding for {duration}s...")
            time.sleep(duration)

            self._flood_active = False
            time.sleep(0.5)

            # Verify hooks are disabled by testing Alt+Tab
            works = self._test_alt_tab()
            if works:
                self._log("  [+] Keyboard hooks DISABLED successfully!")
                self._hooks_removed = True
                return True
            else:
                self._log("  [!] Hooks still active, trying longer flood...")
                return False

        except Exception as e:
            self._log(f"  [!] Flood failed: {e}")
            return False

    # ── Method 3: Install our own hook (pre-empt) ──────────────

    def install_our_hook(self) -> bool:
        """
        Install our own LL hook BEFORE SEB starts, or replace SEB's hook.
        Our hook processes the keys first and can allow them through.
        """
        self._log("[*] Installing our own keyboard hook...")

        @HOOKPROC
        def our_hook_proc(nCode, wParam, lParam):
            if nCode >= 0:
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = kb.vkCode

                # If it's a key we want to allow through, return 1
                # (pass to next hook in chain)
                if self._should_allow(vk, wParam):
                    return user32.CallNextHookEx(
                        self._our_hook, nCode, wParam, lParam
                    )
            return user32.CallNextHookEx(self._our_hook, nCode, wParam, lParam)

        self._hook_proc = our_hook_proc  # prevent GC
        self._our_hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, our_hook_proc, kernel32.GetModuleHandleW(None), 0
        )

        if self._our_hook:
            self._log(f"  [+] Hook installed: 0x{self._our_hook:x}")
            return True
        else:
            err = kernel32.GetLastError()
            self._log(f"  [!] Hook install failed: error {err}")
            return False

    def _should_allow(self, vk: int, msg: int) -> bool:
        """Decide if a key should be passed through."""
        # Allow these keys through
        allowed_vks = {
            VK_TAB, VK_F4, VK_F5, VK_F11, VK_F12,
            VK_LWIN, VK_RWIN, VK_DELETE, VK_SNAPSHOT,
            VK_ESCAPE,
        }
        return vk in allowed_vks

    # ── Method 4: Raw Input (bypass hook chain entirely) ───────

    def setup_raw_input(self, hwnd: int) -> bool:
        """
        Register for raw input from keyboard devices.
        Raw input bypasses the hook chain — SEB's LL hook never sees it.
        """
        self._log("[*] Setting up Raw Input keyboard bypass...")

        # Register raw input devices
        RAWINPUTDEVICE = ctypes.Structure
        class RAWINPUTDEVICE(ctypes.Structure):
            _fields_ = [
                ("usUsagePage", ctypes.wintypes.USHORT),
                ("usUsage", ctypes.wintypes.USHORT),
                ("dwFlags", ctypes.wintypes.DWORD),
                ("hwndTarget", ctypes.wintypes.HWND),
            ]

        rid = RAWINPUTDEVICE()
        rid.usUsagePage = 0x01  # Generic desktop
        rid.usUsage = 0x06      # Keyboard
        rid.dwFlags = 0x00000100  # RIDEV_INPUTSINK (receive even when not focused)
        rid.hwndTarget = hwnd

        result = user32.RegisterRawInputDevices(
            ctypes.byref(rid), 1, ctypes.sizeof(rid)
        )

        if result:
            self._log("  [+] Raw input registered — keyboard input bypasses hooks")
            return True
        else:
            err = kernel32.GetLastError()
            self._log(f"  [!] Raw input registration failed: {err}")
            return False

    # ── Method 5: SendInput (inject keystrokes) ────────────────

    @staticmethod
    def send_keystroke(vk: int, down: bool = True):
        """Inject a keystroke using SendInput."""
        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002
        KEYEVENTF_EXTENDEDKEY = 0x0001

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.wintypes.WORD),
                ("wScan", ctypes.wintypes.WORD),
                ("dwFlags", ctypes.wintypes.DWORD),
                ("time", ctypes.wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class INPUT(ctypes.Structure):
            class _INPUT(ctypes.Union):
                _fields_ = [("ki", KEYBDINPUT)]
            _fields_ = [
                ("type", ctypes.wintypes.DWORD),
                ("_input", _INPUT),
            ]

        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp._input.ki.wVk = vk
        inp._input.ki.wScan = 0
        inp._input.ki.dwFlags = 0 if down else KEYEVENTF_KEYUP
        inp._input.ki.time = 0

        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    @staticmethod
    def send_alt_tab():
        """Simulate Alt+Tab via SendInput."""
        KeyboardHookBypass.send_keystroke(0x12, True)   # Alt down
        time.sleep(0.05)
        KeyboardHookBypass.send_keystroke(0x09, True)   # Tab down
        time.sleep(0.05)
        KeyboardHookBypass.send_keystroke(0x09, False)  # Tab up
        time.sleep(0.05)
        KeyboardHookBypass.send_keystroke(0x12, False)  # Alt up

    @staticmethod
    def send_ctrl_v():
        """Simulate Ctrl+V (paste)."""
        KeyboardHookBypass.send_keystroke(0x11, True)   # Ctrl down
        time.sleep(0.02)
        KeyboardHookBypass.send_keystroke(0x56, True)   # V down
        time.sleep(0.02)
        KeyboardHookBypass.send_keystroke(0x56, False)  # V up
        time.sleep(0.02)
        KeyboardHookBypass.send_keystroke(0x11, False)  # Ctrl up

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _find_seb_window() -> int:
        """Find SEB's main window handle."""
        seb_hwnd = None

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def enum_callback(hwnd, l_param):
            nonlocal seb_hwnd
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                if "Safe Exam Browser" in title or "SEB" in title:
                    # Verify it's a visible window
                    if user32.IsWindowVisible(hwnd):
                        seb_hwnd = hwnd
                        return False  # Stop enumeration
            return True

        user32.EnumWindows(enum_callback, 0)
        return seb_hwnd

    @staticmethod
    def _test_alt_tab() -> bool:
        """Test if Alt+Tab works by checking if foreground window changes."""
        orig = user32.GetForegroundWindow()
        KeyboardHookBypass.send_alt_tab()
        time.sleep(0.3)
        new = user32.GetForegroundWindow()
        return orig != new

    def stop(self):
        """Cleanup."""
        self._flood_active = False
        if self._our_hook:
            user32.UnhookWindowsHookEx(self._our_hook)
            self._our_hook = None
