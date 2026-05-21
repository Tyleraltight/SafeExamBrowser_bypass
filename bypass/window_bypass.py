"""
Window Bypass — manipulate SEB's window and switch to other apps.

SEB locks the desktop by:
- Setting itself as topmost window
- Hiding the taskbar
- Blocking Alt+Tab / Win+D
- Monitoring focus loss and alerting the exam

This module provides:
1. Window manipulation (resize, move, minimize SEB)
2. Force taskbar visible
3. Launch Task Manager / Explorer
4. Create a "shadow desktop" overlay
5. Multi-window management
"""

import ctypes
import ctypes.wintypes
import os
import subprocess
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

# ── Constants ──────────────────────────────────────────────────

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
HWND_TOP = 0
SW_MINIMIZE = 6
SW_RESTORE = 9
SW_HIDE = 0
SW_SHOW = 5
SW_MAXIMIZE = 3
ABM_GETSTATE = 0x00000004
ABM_SETSTATE = 0x00000001
ABS_AUTOHIDE = 0x0000001
ABS_ALWAYSONTOP = 0x0000002
SPI_SETWORKAREA = 0x002F
SPIF_SENDCHANGE = 0x0002
SMTO_ABORTIFHUNG = 0x0002


class APPBARDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("hWnd", ctypes.wintypes.HWND),
        ("uCallbackMessage", ctypes.wintypes.UINT),
        ("uEdge", ctypes.wintypes.UINT),
        ("rc", ctypes.wintypes.RECT),
        ("lParam", ctypes.wintypes.LPARAM),
    ]


class WindowBypass:
    """Manipulate windows to bypass SEB's desktop lockdown."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._log = print if verbose else lambda *a, **k: None
        self._seb_hwnd = None

    # ── Find SEB Window ────────────────────────────────────────

    def find_seb_window(self) -> int | None:
        """Find SEB's main window."""
        self._log("[*] Searching for SEB window...")

        results = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def enum_cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value

            # Also get the class name
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)
            cls = cls_buf.value

            if any(kw in title.lower() for kw in ["safe exam browser", "seb"]):
                results.append((hwnd, title, cls))
            elif "chromium" in cls.lower() and "seb" in cls.lower():
                results.append((hwnd, title, cls))
            return True

        user32.EnumWindows(enum_cb, 0)

        if results:
            for hwnd, title, cls in results:
                self._log(f"  [+] Found: 0x{hwnd:x} [{cls}] '{title}'")
            self._seb_hwnd = results[0][0]
            return self._seb_hwnd

        # Try by process name
        try:
            import psutil
            for proc in psutil.process_iter(["pid", "name"]):
                if "SafeExamBrowser" in proc.info.get("name", ""):
                    # Get window from PID
                    pid = proc.info["pid"]
                    hwnd_list = []

                    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
                    def pid_enum(hwnd, _):
                        p = ctypes.wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
                        if p.value == pid and user32.IsWindowVisible(hwnd):
                            hwnd_list.append(hwnd)
                        return True

                    user32.EnumWindows(pid_enum, 0)
                    if hwnd_list:
                        self._seb_hwnd = hwnd_list[0]
                        self._log(f"  [+] Found via PID: 0x{self._seb_hwnd:x}")
                        return self._seb_hwnd
        except ImportError:
            pass

        self._log("  [-] SEB window not found")
        return None

    # ── Remove Topmost ─────────────────────────────────────────

    def remove_topmost(self, hwnd: int = None) -> bool:
        """Remove WS_EX_TOPMOST from SEB's window."""
        hwnd = hwnd or self._seb_hwnd or self.find_seb_window()
        if not hwnd:
            return False

        self._log(f"[*] Removing topmost flag from 0x{hwnd:x}...")

        # Get current extended style
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        was_topmost = bool(ex_style & WS_EX_TOPMOST)
        self._log(f"  Current topmost: {was_topmost}")

        # Set to non-topmost
        result = user32.SetWindowPos(
            hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_FRAMECHANGED
        )

        if result:
            self._log("  [+] Topmost removed!")
            return True
        else:
            self._log("  [-] Failed to remove topmost")
            return False

    # ── Resize SEB Window ──────────────────────────────────────

    def resize_seb(self, hwnd: int = None, width: int = 800, height: int = 600) -> bool:
        """Resize SEB to a smaller window."""
        hwnd = hwnd or self._seb_hwnd or self.find_seb_window()
        if not hwnd:
            return False

        self._log(f"[*] Resizing SEB to {width}x{height}...")

        # Get screen dimensions
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)

        # Calculate centered position
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2

        result = user32.MoveWindow(hwnd, x, y, width, height, True)
        if result:
            self._log(f"  [+] SEB resized and moved to ({x}, {y})")
            return True
        else:
            self._log("  [-] Resize failed")
            return False

    # ── Minimize SEB ───────────────────────────────────────────

    def minimize_seb(self, hwnd: int = None) -> bool:
        """Minimize SEB's window."""
        hwnd = hwnd or self._seb_hwnd or self.find_seb_window()
        if not hwnd:
            return False

        self._log("[*] Minimizing SEB...")
        result = user32.ShowWindow(hwnd, SW_MINIMIZE)
        if result:
            self._log("  [+] SEB minimized!")
            return True
        return False

    # ── Hide SEB ───────────────────────────────────────────────

    def hide_seb(self, hwnd: int = None) -> bool:
        """Hide SEB's window completely."""
        hwnd = hwnd or self._seb_hwnd or self.find_seb_window()
        if not hwnd:
            return False

        self._log("[*] Hiding SEB window...")
        result = user32.ShowWindow(hwnd, SW_HIDE)
        if result:
            self._log("  [+] SEB hidden!")
            return True
        return False

    # ── Show Taskbar ───────────────────────────────────────────

    def show_taskbar(self) -> bool:
        """Force the taskbar to be visible."""
        self._log("[*] Restoring taskbar...")

        # Find the taskbar window
        taskbar = user32.FindWindowW("Shell_TrayWnd", None)
        if taskbar:
            user32.ShowWindow(taskbar, SW_SHOW)
            # Remove auto-hide
            abd = APPBARDATA()
            abd.cbSize = ctypes.sizeof(APPBARDATA)
            state = shell32.SHAppBarMessage(ABM_GETSTATE, ctypes.byref(abd))
            if state & ABS_AUTOHIDE:
                abd.lParam = ABS_ALWAYSONTOP
                shell32.SHAppBarMessage(ABM_SETSTATE, ctypes.byref(abd))
            self._log("  [+] Taskbar restored")

        # Also try the secondary taskbar (multi-monitor)
        sec_taskbar = user32.FindWindowW("Shell_SecondaryTrayWnd", None)
        if sec_taskbar:
            user32.ShowWindow(sec_taskbar, SW_SHOW)

        return bool(taskbar)

    # ── Restore Focus to Desktop ───────────────────────────────

    def switch_to_window(self, hwnd: int) -> bool:
        """Switch foreground focus to a specific window."""
        # Try multiple methods
        try:
            # Method 1: SetForegroundWindow
            result = user32.SetForegroundWindow(hwnd)
            if result:
                return True

            # Method 2: BringWindowToTop
            user32.BringWindowToTop(hwnd)

            # Method 3: Attach thread input and force it
            target_tid = user32.GetWindowThreadProcessId(hwnd, None)
            current_tid = kernel32.GetCurrentThreadId()

            if target_tid != current_tid:
                attached = user32.AttachThreadInput(current_tid, target_tid, True)
                if attached:
                    user32.SetForegroundWindow(hwnd)
                    user32.BringWindowToTop(hwnd)
                    user32.AttachThreadInput(current_tid, target_tid, False)
                    return True

            return bool(user32.IsWindow(hwnd))
        except Exception:
            return False

    # ── Launch Applications ────────────────────────────────────

    @staticmethod
    def launch_task_manager() -> bool:
        """Launch Task Manager."""
        try:
            os.startfile("taskmgr.exe")
            return True
        except Exception:
            try:
                subprocess.Popen(["taskmgr.exe"])
                return True
            except Exception:
                return False

    @staticmethod
    def launch_explorer() -> bool:
        """Launch Windows Explorer."""
        try:
            os.startfile("explorer.exe")
            return True
        except Exception:
            return False

    @staticmethod
    def launch_cmd() -> bool:
        """Launch Command Prompt."""
        try:
            subprocess.Popen(["cmd.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            return True
        except Exception:
            return False

    @staticmethod
    def launch_browser(url: str = "") -> bool:
        """Launch a web browser."""
        try:
            if url:
                os.startfile(url)
            else:
                os.startfile("msedge.exe")
            return True
        except Exception:
            try:
                subprocess.Popen(["cmd", "/c", "start", "msedge.exe"])
                return True
            except Exception:
                return False

    @staticmethod
    def launch_powershell() -> bool:
        """Launch PowerShell."""
        try:
            subprocess.Popen(
                ["powershell.exe"],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            return True
        except Exception:
            return False

    # ── Multi-window layout ────────────────────────────────────

    def create_split_screen(self, seb_hwnd: int = None, other_hwnd: int = None):
        """
        Put SEB on the left half, another window on the right half.
        Useful for having notes/browser visible alongside the exam.
        """
        seb_hwnd = seb_hwnd or self._seb_hwnd or self.find_seb_window()
        if not seb_hwnd:
            return False

        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        half_w = screen_w // 2

        # SEB on left half
        user32.MoveWindow(seb_hwnd, 0, 0, half_w, screen_h, True)

        # Other window on right half
        if other_hwnd:
            user32.MoveWindow(other_hwnd, half_w, 0, half_w, screen_h, True)
            self.switch_to_window(other_hwnd)

        self._log(f"[+] Split screen: SEB on left, app on right")
        return True
