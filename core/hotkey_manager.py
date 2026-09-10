import ctypes
from ctypes import wintypes
from typing import Any, Dict, Optional, Tuple

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal
from PySide6.QtGui import QKeySequence

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

HOTKEY_ID_MIRROR = 2001
HOTKEY_ID_MOVE_TO_PC = 2002
HOTKEY_ID_SHOW_APP = 2003

ACTION_IDS = {
    "mirror_screen": HOTKEY_ID_MIRROR,
    "move_to_pc": HOTKEY_ID_MOVE_TO_PC,
    "show_app": HOTKEY_ID_SHOW_APP,
}


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


def parse_shortcut_to_win32(seq_str: str) -> Tuple[int, int]:
    """Parse a Qt key sequence string like 'Ctrl+Shift+M' into Win32 (fsModifiers, vk)."""
    if not seq_str:
        return 0, 0
    parts = [p.strip().lower() for p in seq_str.split("+")]
    mod = MOD_NOREPEAT
    vk = 0
    for p in parts:
        if p in ("ctrl", "control"):
            mod |= MOD_CONTROL
        elif p == "alt":
            mod |= MOD_ALT
        elif p == "shift":
            mod |= MOD_SHIFT
        elif p in ("win", "meta", "cmd"):
            mod |= MOD_WIN
        elif len(p) == 1 and p.isalnum():
            vk = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit():
            vk = 0x70 + int(p[1:]) - 1  # VK_F1 = 0x70
        elif p == "space":
            vk = 0x20
        elif p in ("return", "enter"):
            vk = 0x0D
        elif p == "tab":
            vk = 0x09
        elif p == "escape" or p == "esc":
            vk = 0x1B
        elif p == "pause":
            vk = 0x13
        elif p in ("insert", "ins"):
            vk = 0x2D
        elif p in ("delete", "del"):
            vk = 0x2E
        elif p == "home":
            vk = 0x24
        elif p == "end":
            vk = 0x23
        elif p in ("pageup", "pgup"):
            vk = 0x21
        elif p in ("pagedown", "pgdn"):
            vk = 0x22
    return mod, vk


class _Win32HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, manager: "GlobalHotkeyManager"):
        super().__init__()
        self.manager = manager

    def nativeEventFilter(self, eventType, message):
        if eventType in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            try:
                msg = _MSG.from_address(int(message))
                if msg.message == 0x0312:  # WM_HOTKEY
                    hotkey_id = int(msg.wParam)
                    self.manager._on_hotkey_received(hotkey_id)
                    return True, 0
            except Exception:
                pass
        return False, 0


class GlobalHotkeyManager(QObject):
    """System-wide Windows global hotkey manager using Win32 RegisterHotKey."""

    mirror_triggered = Signal()
    move_to_pc_triggered = Signal()
    show_app_triggered = Signal()
    status_changed = Signal(str)

    def __init__(self, hwnd: int, parent=None):
        super().__init__(parent)
        self.hwnd = hwnd
        self._user32 = ctypes.windll.user32
        self._registered_ids: Dict[int, str] = {}
        self._filter: Optional[_Win32HotkeyFilter] = None
        self._installed_filter = False

    def setup(self):
        """Install native event filter on Qt application."""
        if not self._installed_filter:
            self._filter = _Win32HotkeyFilter(self)
            app = QCoreApplication.instance()
            if app:
                app.installNativeEventFilter(self._filter)
                self._installed_filter = True

    def unregister_all(self):
        """Unregister all registered Win32 hotkeys."""
        for hid in list(self._registered_ids.keys()):
            try:
                self._user32.UnregisterHotKey(self.hwnd, hid)
            except Exception:
                pass
        self._registered_ids.clear()

    def register_hotkey(self, action: str, shortcut_str: str) -> Tuple[bool, str]:
        """Register a single hotkey for a named action."""
        if action not in ACTION_IDS:
            return False, f"Unknown action '{action}'"

        hid = ACTION_IDS[action]
        # Unregister existing if currently registered
        if hid in self._registered_ids:
            try:
                self._user32.UnregisterHotKey(self.hwnd, hid)
            except Exception:
                pass
            self._registered_ids.pop(hid, None)

        if not shortcut_str.strip():
            return True, "Hotkey cleared"

        mod, vk = parse_shortcut_to_win32(shortcut_str)
        if vk == 0:
            return False, f"Invalid shortcut key: '{shortcut_str}'"

        success = self._user32.RegisterHotKey(self.hwnd, hid, mod, vk)
        if success:
            self._registered_ids[hid] = action
            return True, f"Registered '{shortcut_str}' successfully"
        else:
            err = ctypes.GetLastError()
            if err == 1409:
                return False, f"'{shortcut_str}' is already registered by another application."
            return False, f"Failed to register '{shortcut_str}' (Win32 Error {err})"

    def apply_config(self, shortcuts_cfg: Dict[str, Any]) -> Dict[str, Tuple[bool, str]]:
        """Apply all shortcuts from configuration."""
        self.setup()
        self.unregister_all()

        results = {}
        enabled = shortcuts_cfg.get("global_hotkeys_enabled", True)
        if not enabled:
            self.status_changed.emit("Global hotkeys disabled in Settings.")
            return results

        for action in ("mirror_screen", "move_to_pc", "show_app"):
            seq = shortcuts_cfg.get(action, "")
            if seq:
                ok, msg = self.register_hotkey(action, seq)
                results[action] = (ok, msg)
            else:
                results[action] = (True, "None")

        # Emit summary
        failed = [f"{act}: {msg}" for act, (ok, msg) in results.items() if not ok]
        if failed:
            self.status_changed.emit("Hotkey conflicts: " + "; ".join(failed))
        else:
            self.status_changed.emit("Global hotkeys active.")
        return results

    def _on_hotkey_received(self, hotkey_id: int):
        if hotkey_id == HOTKEY_ID_MIRROR:
            self.mirror_triggered.emit()
        elif hotkey_id == HOTKEY_ID_MOVE_TO_PC:
            self.move_to_pc_triggered.emit()
        elif hotkey_id == HOTKEY_ID_SHOW_APP:
            self.show_app_triggered.emit()

    def cleanup(self):
        """Unregister all hotkeys and remove native event filter."""
        self.unregister_all()
        if self._installed_filter and self._filter:
            app = QCoreApplication.instance()
            if app:
                try:
                    app.removeNativeEventFilter(self._filter)
                except Exception:
                    pass
            self._installed_filter = False
