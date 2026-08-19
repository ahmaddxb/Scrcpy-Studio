import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import AdbManager


class QuickActionBar(QGroupBox):
    """Dock widget for sending instant physical key events, screenshots, and device utilities."""

    action_triggered = Signal(str, str)  # action_name, message
    disconnect_requested = Signal(str)  # serial or empty for all
    open_apps_requested = Signal()

    def __init__(self, adb: AdbManager, parent=None):
        super().__init__("⚡ Quick Actions & Device Controls", parent)
        self.adb = adb
        self.selected_serial: Optional[str] = None
        self._setup_ui()

    def set_device(self, serial: Optional[str]):
        self.selected_serial = serial
        self.setEnabled(bool(serial))

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(6)

        # Row 0: Hardware Keys & Unlock
        self.btn_power = self._create_btn("⏻ Power", lambda: self._send_key(26, "Power Button"))
        self.btn_unlock = self._create_btn("🔓 Unlock", self._unlock_device)
        self.btn_vol_up = self._create_btn("🔊 Vol +", lambda: self._send_key(24, "Volume Up"))
        self.btn_vol_down = self._create_btn("🔉 Vol -", lambda: self._send_key(25, "Volume Down"))

        grid.addWidget(self.btn_power, 0, 0)
        grid.addWidget(self.btn_unlock, 0, 1)
        grid.addWidget(self.btn_vol_up, 0, 2)
        grid.addWidget(self.btn_vol_down, 0, 3)

        # Row 1: Navigation Keys
        self.btn_back = self._create_btn("◀ Back", lambda: self._send_key(4, "Back"))
        self.btn_home = self._create_btn("🏠 Home", lambda: self._send_key(3, "Home"))
        self.btn_app_switch = self._create_btn("🔲 Recents", lambda: self._send_key(187, "App Switch"))
        self.btn_notif = self._create_btn("🔔 Notifs", lambda: self._send_key(83, "Notifications"))

        grid.addWidget(self.btn_back, 1, 0)
        grid.addWidget(self.btn_home, 1, 1)
        grid.addWidget(self.btn_app_switch, 1, 2)
        grid.addWidget(self.btn_notif, 1, 3)

        # Row 2: Utilities
        self.btn_screenshot = self._create_btn("📸 Screenshot", self._take_screenshot)
        self.btn_apps = self._create_btn("📱 Apps", lambda: self.open_apps_requested.emit())
        self.btn_wake = self._create_btn("💡 Wake", lambda: self._send_key(224, "Wake Up"))
        self.btn_disconnect = self._create_btn("🔌 Disconnect", self._disconnect_device)

        grid.addWidget(self.btn_screenshot, 2, 0)
        grid.addWidget(self.btn_apps, 2, 1)
        grid.addWidget(self.btn_wake, 2, 2)
        grid.addWidget(self.btn_disconnect, 2, 3)

        layout.addLayout(grid)

    def _unlock_device(self):
        if not self.selected_serial:
            return
        ok = self.adb.unlock_device(self.selected_serial)
        if ok:
            self.action_triggered.emit("Unlock", f"Sent wake & unlock swipe to {self.selected_serial}")

    def _create_btn(self, text: str, callback) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("class", "quickAction")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(callback)
        return btn

    def _send_key(self, keycode: int, name: str):
        if not self.selected_serial:
            return
        ok = self.adb.send_keyevent(self.selected_serial, keycode)
        if ok:
            self.action_triggered.emit(name, f"Sent keyevent {keycode} ({name}) to {self.selected_serial}")
        else:
            self.action_triggered.emit(name, f"Failed to send keyevent to {self.selected_serial}")

    def _take_screenshot(self):
        if not self.selected_serial:
            return

        pics_dir = Path.home() / "Pictures" / "Scrcpy_Screenshots"
        pics_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = pics_dir / f"screenshot_{self.selected_serial}_{timestamp}.png"

        ok = self.adb.take_screenshot(self.selected_serial, str(filepath))
        if ok:
            self.action_triggered.emit("Screenshot", f"Saved screenshot to {filepath}")
            try:
                os.startfile(str(filepath))
            except Exception:
                pass
        else:
            self.action_triggered.emit("Screenshot", f"Failed to capture screenshot from {self.selected_serial}")

    def _disconnect_device(self):
        if not self.selected_serial:
            return
        self.disconnect_requested.emit(self.selected_serial)

    def _restart_adb(self):
        ok, msg = self.adb.restart_server()
        status = "Success" if ok else "Error"
        self.action_triggered.emit("Restart ADB", f"ADB Server Restarted: {status}")
