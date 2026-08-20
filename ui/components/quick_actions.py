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
from core.config_manager import ConfigManager


class QuickActionBar(QFrame):
    """Dock widget for sending instant physical key events, screenshots, and device utilities."""

    action_triggered = Signal(str, str)  # action_name, message
    open_apps_requested = Signal()
    pull_active_app_requested = Signal(str)  # serial

    def __init__(self, adb: AdbManager, config: Optional[ConfigManager] = None, process_manager=None, parent=None):
        super().__init__(parent)
        self.adb = adb
        self.config = config
        self.process_manager = process_manager
        self.selected_serial: Optional[str] = None

        self.setObjectName("quickActionsCard")
        self.setStyleSheet(
            "QFrame#quickActionsCard { background-color: #171922; border: 1px solid #2B303E; border-radius: 8px; }"
        )

        pinned_map = self.config.get("pinned_sidebar_sections", {}) if self.config else {}
        self.is_pinned_expanded = pinned_map.get("quick_actions", True)

        self._setup_ui()
        self._update_expanded_state()

    def _update_pin_style(self):
        if self.is_pinned_expanded:
            self.btn_pin.setText("📌")
            self.btn_pin.setToolTip("Section is Pinned Open (Click to auto-collapse on mouse hover)")
            self.btn_pin.setStyleSheet(
                "QPushButton { background: #38BDF822; color: #38BDF8; border: 1px solid #38BDF855; border-radius: 4px; font-size: 10px; padding: 0px; }"
                "QPushButton:hover { background: #38BDF844; }"
            )
        else:
            self.btn_pin.setText("📍")
            self.btn_pin.setToolTip("Auto-collapsing on hover (Click to pin permanently expanded)")
            self.btn_pin.setStyleSheet(
                "QPushButton { background: transparent; color: #64748B; border: 1px solid #282C37; border-radius: 4px; font-size: 10px; padding: 0px; }"
                "QPushButton:hover { color: #38BDF8; border-color: #38BDF8; background: #38BDF811; }"
            )

    def _toggle_pin(self):
        self.is_pinned_expanded = not self.is_pinned_expanded
        self._update_pin_style()
        if self.config:
            pinned_map = self.config.get("pinned_sidebar_sections", {})
            pinned_map["quick_actions"] = self.is_pinned_expanded
            self.config.set("pinned_sidebar_sections", pinned_map)
        self._update_expanded_state()

    def _update_expanded_state(self):
        should_show = self.is_pinned_expanded or self.underMouse()
        self.body_widget.setVisible(should_show)

    def enterEvent(self, event):
        if not self.is_pinned_expanded:
            self.body_widget.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_pinned_expanded:
            self.body_widget.setVisible(False)
        super().leaveEvent(event)

    def set_device(self, serial: Optional[str]):
        self.selected_serial = serial
        self.setEnabled(bool(serial))

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        # Header Row
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        lbl_title = QLabel("⚡ Quick Actions & Device Controls")
        lbl_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #38BDF8; border: none;")
        header_row.addWidget(lbl_title)
        header_row.addStretch(1)

        self.btn_pin = QPushButton("📌" if self.is_pinned_expanded else "📍")
        self.btn_pin.setFixedSize(22, 22)
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self._update_pin_style()
        self.btn_pin.clicked.connect(self._toggle_pin)
        header_row.addWidget(self.btn_pin)

        main_layout.addLayout(header_row)

        # Body Widget containing Grid
        self.body_widget = QWidget()
        self.body_widget.setStyleSheet("background: transparent;")
        grid = QGridLayout(self.body_widget)
        grid.setContentsMargins(0, 2, 0, 2)
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

        # Row 2: Utilities (Screenshot, Screen On, Screen Off, Move to PC)
        self.btn_screenshot = self._create_btn("📸 Screenshot", self._take_screenshot)
        self.btn_screen_on = self._create_btn("💡 Screen On", self._turn_screen_on)
        self.btn_screen_off = self._create_btn("🌑 Screen Off", self._turn_screen_off)
        self.btn_pull_app = self._create_btn("🔀 Move to PC", self._pull_active_app)
        self.btn_pull_app.setToolTip("Detect whatever app is open on the phone and move it to a PC Virtual Display window")

        grid.addWidget(self.btn_screenshot, 2, 0)
        grid.addWidget(self.btn_screen_on, 2, 1)
        grid.addWidget(self.btn_screen_off, 2, 2)
        grid.addWidget(self.btn_pull_app, 2, 3)

        # Row 3: ADB Server Recovery
        self.btn_restart_adb = self._create_btn("🔄 Restart ADB Server", self._restart_adb)
        self.btn_restart_adb.setToolTip("Restart the local ADB server daemon")
        grid.addWidget(self.btn_restart_adb, 3, 0, 1, 4)

        main_layout.addWidget(self.body_widget)

    def _pull_active_app(self):
        if not self.selected_serial:
            return
        self.pull_active_app_requested.emit(self.selected_serial)

    def _turn_screen_on(self):
        if not self.selected_serial:
            return
        scrcpy_ok = False
        if self.process_manager:
            scrcpy_ok = self.process_manager.send_scrcpy_shortcut(self.selected_serial, "screen_on")
        self.adb.wake_up(self.selected_serial)
        mode = "Scrcpy Live Display Mode" if scrcpy_ok else "ADB Keyevent"
        self.action_triggered.emit("Screen On", f"Turned on physical display for {self.selected_serial} via {mode}")

    def _turn_screen_off(self):
        if not self.selected_serial:
            return
        scrcpy_ok = False
        if self.process_manager:
            scrcpy_ok = self.process_manager.send_scrcpy_shortcut(self.selected_serial, "screen_off")
        if not scrcpy_ok:
            self.adb.turn_off_screen(self.selected_serial)
        mode = "Scrcpy Live Display Mode (keeps mirroring active)" if scrcpy_ok else "ADB Keyevent (Sleep)"
        self.action_triggered.emit("Screen Off", f"Turned off physical display for {self.selected_serial} via {mode}")

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

    def _restart_adb(self):
        ok, msg = self.adb.restart_server()
        status = "Success" if ok else "Error"
        self.action_triggered.emit("Restart ADB", f"ADB Server Restarted: {status}")
