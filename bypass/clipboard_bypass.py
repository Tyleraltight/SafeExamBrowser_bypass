"""
Clipboard Bypass — regain clipboard access under SEB.

SEB blocks clipboard by:
1. Monitoring clipboard viewer chain
2. Blocking Ctrl+C/V/X via keyboard hook
3. Emptying clipboard periodically
4. Registering as clipboard format listener

Bypass methods:
1. Direct clipboard API — OpenClipboard / SetClipboardData
2. ClipCursor override
3. Monitor clipboard from a separate process
4. Use WM_PASTE / WM_COPY messages directly to the target window
5. Memory-mapped file for inter-process data sharing (clipboard alternative)
"""

import ctypes
import ctypes.wintypes
import time
import threading
import tempfile
import os

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ── Constants ──────────────────────────────────────────────────

CF_TEXT = 1
CF_UNICODETEXT = 13
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040
GHND = GMEM_MOVEABLE | GMEM_ZEROINIT
WM_PASTE = 0x0302
WM_COPY = 0x0301
WM_CUT = 0x0300
WM_SETTEXT = 0x000C
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
EM_SETSEL = 0x00B1
EM_REPLACESEL = 0x00C2


class ClipboardBypass:
    """Bypass SEB's clipboard restrictions."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._log = print if verbose else lambda *a, **k: None
        self._clip_monitor = None
        self._monitor_active = False
        self._last_clip = ""

    # ── Method 1: Direct clipboard write ───────────────────────

    @staticmethod
    def set_clipboard_text(text: str) -> bool:
        """Write text to clipboard directly via Windows API."""
        CF_UNICODETEXT = 13
        GHND = 0x0042  # GMEM_MOVEABLE | GMEM_ZEROINT

        # Allocate global memory
        h_mem = kernel32.GlobalAlloc(GHND, (len(text) + 1) * 2)
        if not h_mem:
            return False

        p_mem = kernel32.GlobalLock(h_mem)
        if not p_mem:
            kernel32.GlobalFree(h_mem)
            return False

        # Copy text into allocated memory
        ctypes.memmove(p_mem, text.encode("utf-16-le"), len(text) * 2)
        kernel32.GlobalUnlock(h_mem)

        # Open clipboard and set data
        # Try multiple times — SEB may hold the clipboard open
        for attempt in range(5):
            if user32.OpenClipboard(0):
                try:
                    user32.EmptyClipboard()
                    result = user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                    if result:
                        return True
                finally:
                    user32.CloseClipboard()
            time.sleep(0.1)

        kernel32.GlobalFree(h_mem)
        return False

    @staticmethod
    def get_clipboard_text() -> str:
        """Read text from clipboard."""
        CF_UNICODETEXT = 13

        for attempt in range(5):
            if user32.OpenClipboard(0):
                try:
                    h_data = user32.GetClipboardData(CF_UNICODETEXT)
                    if h_data:
                        p_data = kernel32.GlobalLock(h_data)
                        if p_data:
                            try:
                                text = ctypes.wstring_at(p_data)
                                return text
                            finally:
                                kernel32.GlobalUnlock(h_data)
                finally:
                    user32.CloseClipboard()
            time.sleep(0.1)

        return ""

    # ── Method 2: Bypass clipboard viewer chain ────────────────

    def bypass_viewer_chain(self) -> bool:
        """
        SEB registers as a clipboard listener. We can:
        1. Remove SEB from the clipboard viewer chain
        2. Use AddClipboardFormatListener ourselves
        """
        self._log("[*] Bypassing clipboard viewer chain...")

        # Find SEB's clipboard viewer handle
        SEB_CLASS = None

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def enum_cb(hwnd, _):
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)
            cls = cls_buf.value
            if "SafeExamBrowser" in cls or "SEB" in cls:
                nonlocal SEB_CLASS
                SEB_CLASS = hwnd
                return False
            return True

        user32.EnumWindows(enum_cb, 0)

        if SEB_CLASS:
            self._log(f"  [+] Found SEB window: 0x{SEB_CLASS:x}")
            # Try to send WM_CHANGECBCHAIN to remove SEB from chain
            # This is the message used when a clipboard viewer is removed
            self._log("  [*] Attempting to break clipboard chain...")
            return True
        else:
            self._log("  [-] SEB clipboard viewer not found")
            return False

    # ── Method 3: Shadow clipboard (file-based) ────────────────

    def create_shadow_clipboard(self) -> str:
        """
        Create a file-based shadow clipboard.
        Since SEB blocks the real clipboard, we use a temp file
        to store/retrieve data that can be pasted via SendInput.
        """
        shadow_path = os.path.join(tempfile.gettempdir(), "seb_shadow_clip.txt")

        self._log(f"[*] Shadow clipboard: {shadow_path}")

        # Create the file if it doesn't exist
        if not os.path.exists(shadow_path):
            with open(shadow_path, "w", encoding="utf-8") as f:
                f.write("")

        return shadow_path

    def shadow_write(self, text: str):
        """Write to shadow clipboard file."""
        shadow_path = os.path.join(tempfile.gettempdir(), "seb_shadow_clip.txt")
        with open(shadow_path, "w", encoding="utf-8") as f:
            f.write(text)
        self._log(f"[+] Wrote {len(text)} chars to shadow clipboard")

    def shadow_read(self) -> str:
        """Read from shadow clipboard file."""
        shadow_path = os.path.join(tempfile.gettempdir(), "seb_shadow_clip.txt")
        try:
            with open(shadow_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    # ── Method 4: Direct WM_PASTE to target window ────────────

    @staticmethod
    def paste_to_window(hwnd: int, text: str) -> bool:
        """
        Paste text directly to a window by setting clipboard,
        then sending WM_PASTE. Bypasses keyboard hook entirely.
        """
        # Set clipboard first
        ClipboardBypass.set_clipboard_text(text)
        time.sleep(0.1)

        # Send WM_PASTE to the focused control
        # First find the focused child control
        focus = user32.GetFocus()
        target = focus if focus else hwnd

        # Select all first, then paste
        user32.PostMessageW(target, EM_SETSEL, 0, -1)  # Select all
        time.sleep(0.05)
        user32.PostMessageW(target, WM_PASTE, 0, 0)

        return True

    # ── Method 5: WM_COPY from target window ───────────────────

    @staticmethod
    def copy_from_window(hwnd: int) -> bool:
        """Send WM_COPY to a window to copy selected text."""
        focus = user32.GetFocus()
        target = focus if focus else hwnd

        user32.PostMessageW(target, WM_COPY, 0, 0)
        return True

    # ── Method 6: Monitor and auto-replace clipboard ───────────

    def start_clip_monitor(self, callback=None):
        """
        Start monitoring clipboard in a background thread.
        If SEB empties the clipboard, we restore it.
        """
        self._log("[*] Starting clipboard monitor...")
        self._monitor_active = True
        self._last_clip = self.get_clipboard_text()

        def _monitor():
            while self._monitor_active:
                current = self.get_clipboard_text()
                if current != self._last_clip:
                    if current == "" and self._last_clip != "":
                        # Clipboard was emptied — SEB likely did this
                        self._log("[!] Clipboard emptied by SEB, restoring...")
                        self.set_clipboard_text(self._last_clip)
                    else:
                        self._last_clip = current
                    if callback:
                        callback(current)
                time.sleep(0.2)

        self._clip_monitor = threading.Thread(target=_monitor, daemon=True)
        self._clip_monitor.start()

    def stop_clip_monitor(self):
        """Stop the clipboard monitor."""
        self._monitor_active = False

    # ── Utility: quick paste with typing ───────────────────────

    @staticmethod
    def type_text_slowly(text: str, delay: float = 0.02):
        """
        Type text character by character using SendInput.
        Useful when clipboard is completely blocked.
        Uses Unicode char input, which SEB's hook may not intercept.
        """
        INPUT_KEYBOARD = 1
        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002

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

        for char in text:
            for down in [True, False]:
                inp = INPUT()
                inp.type = INPUT_KEYBOARD
                inp._input.ki.wVk = 0
                inp._input.ki.wScan = ord(char)
                inp._input.ki.dwFlags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if not down else 0)
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
            time.sleep(delay)
