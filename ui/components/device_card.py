from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import AdbDevice


class DeviceCard(QFrame):
    """Card widget representing a connected or pinned Android device."""

    selected = Signal(str)  # serial
    launch_requested = Signal(str)  # serial
    otg_requested = Signal(str)  # serial
    stop_requested = Signal(str)  # serial
    disconnect_requested = Signal(str)  # serial
    connect_requested = Signal(str)  # serial (for offline pinned devices)
    pin_toggled = Signal(str, bool)  # serial, is_pinned

    def __init__(
        self,
        device: AdbDevice,
        is_active: bool = False,
        is_running: bool = False,
        is_pinned: bool = False,
        is_offline: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.device = device
        self.is_active = is_active
        self.is_running = is_running
        self.is_pinned = is_pinned
        self.is_offline = is_offline

        self.setObjectName("deviceCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(95)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._setup_ui()
        self.update_state(self.is_active, self.is_running, self.is_pinned, self.is_offline)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(6)

        # 1. Top Row: Status Dot, Device Name, Badges, Pin Button, Close Button
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.status_dot = QLabel()
        self.status_dot.setFixedSize(10, 10)
        top_row.addWidget(self.status_dot)

        self.name_label = QLabel(self.device.display_name)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #FFFFFF;")
        top_row.addWidget(self.name_label, 1)

        # Pin button
        self.btn_pin = QPushButton("📍")
        self.btn_pin.setFixedSize(22, 22)
        self.btn_pin.setToolTip("Pin device to remember across restarts")
        self.btn_pin.clicked.connect(self._toggle_pin)
        top_row.addWidget(self.btn_pin)

        # Connection badge (USB vs WiFi)
        is_wireless = self.device.is_wireless or (":" in self.device.serial) or ("._tcp" in self.device.serial)
        conn_text = "📶 WiFi" if is_wireless else "🔌 USB"
        conn_color = "#0284C7" if is_wireless else "#6366F1"
        self.conn_badge = QLabel(conn_text)
        self.conn_badge.setStyleSheet(
            f"background-color: {conn_color}33; color: {conn_color}; "
            f"border: 1px solid {conn_color}66; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;"
        )
        top_row.addWidget(self.conn_badge)

        # Close/Disconnect icon button for wireless endpoints
        self.btn_close = QPushButton("✕")
        self.btn_close.setToolTip("Disconnect wireless device")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setStyleSheet(
            "QPushButton { background: transparent; color: #64748B; border: none; font-weight: bold; font-size: 11px; padding: 0px; }"
            "QPushButton:hover { color: #EF4444; background: #EF444422; border-radius: 4px; }"
        )
        self.btn_close.clicked.connect(lambda: self.disconnect_requested.emit(self.device.serial))
        self.btn_close.setVisible(is_wireless and not self.is_offline)
        top_row.addWidget(self.btn_close)

        main_layout.addLayout(top_row)

        # 2. Middle Row: Serial Number, Screen Timeout & Battery Indicator
        mid_row = QHBoxLayout()
        mid_row.setSpacing(8)

        self.serial_label = QLabel(self.device.serial)
        self.serial_label.setStyleSheet("color: #64748B; font-size: 11px; font-family: monospace;")
        mid_row.addWidget(self.serial_label, 1)

        self.timeout_label = QLabel()
        mid_row.addWidget(self.timeout_label)

        self.bat_label = QLabel()
        mid_row.addWidget(self.bat_label)

        main_layout.addLayout(mid_row)

        # 3. Bottom Row: Control Buttons
        self.btn_row = QHBoxLayout()
        self.btn_row.setSpacing(6)

        # Offline Reconnect button
        self.btn_reconnect = QPushButton("⚡ Reconnect")
        self.btn_reconnect.setObjectName("primaryBtn")
        self.btn_reconnect.setFixedHeight(28)
        self.btn_reconnect.clicked.connect(lambda: self.connect_requested.emit(self.device.serial))
        self.btn_row.addWidget(self.btn_reconnect)

        # Launch Mirror button
        self.btn_launch = QPushButton("🚀 Mirror")
        self.btn_launch.setObjectName("primaryBtn")
        self.btn_launch.setFixedHeight(28)
        self.btn_launch.clicked.connect(lambda: self.launch_requested.emit(self.device.serial))
        self.btn_row.addWidget(self.btn_launch)

        # OTG Mode button
        self.btn_otg = QPushButton("🎮 OTG")
        self.btn_otg.setToolTip("Control with PC keyboard/mouse (no video)")
        self.btn_otg.setFixedHeight(28)
        self.btn_otg.clicked.connect(lambda: self.otg_requested.emit(self.device.serial))
        self.btn_row.addWidget(self.btn_otg)

        # Disconnect button on card
        self.btn_card_disc = QPushButton("🔌 Disconnect")
        self.btn_card_disc.setFixedHeight(28)
        self.btn_card_disc.setStyleSheet("font-size: 11px; padding: 4px 8px; color: #94A3B8;")
        self.btn_card_disc.clicked.connect(lambda: self.disconnect_requested.emit(self.device.serial))
        self.btn_card_disc.setVisible(is_wireless and not self.is_offline)
        self.btn_row.addWidget(self.btn_card_disc)

        # Stop Session button
        self.btn_stop = QPushButton("⏹ Stop Mirroring")
        self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.setFixedHeight(28)
        self.btn_stop.clicked.connect(lambda: self.stop_requested.emit(self.device.serial))
        self.btn_row.addWidget(self.btn_stop)

        # Unauthorized / Offline warning label
        self.unauth_label = QLabel()
        self.unauth_label.setStyleSheet("color: #F59E0B; font-size: 11px; font-style: italic;")
        self.btn_row.addWidget(self.unauth_label)

        main_layout.addLayout(self.btn_row)

    def _toggle_pin(self):
        self.is_pinned = not self.is_pinned
        self._update_pin_button_style()
        self.pin_toggled.emit(self.device.serial, self.is_pinned)

    def _update_pin_button_style(self):
        if self.is_pinned:
            self.btn_pin.setText("📌")
            self.btn_pin.setToolTip("Device is pinned across restarts (Click to unpin)")
            self.btn_pin.setStyleSheet(
                "QPushButton { background: #F59E0B22; color: #F59E0B; border: 1px solid #F59E0B66; border-radius: 4px; font-size: 11px; padding: 0px; }"
                "QPushButton:hover { background: #F59E0B44; }"
            )
        else:
            self.btn_pin.setText("📍")
            self.btn_pin.setToolTip("Pin device to remember across restarts")
            self.btn_pin.setStyleSheet(
                "QPushButton { background: transparent; color: #64748B; border: 1px solid #282C37; border-radius: 4px; font-size: 11px; padding: 0px; }"
                "QPushButton:hover { color: #F59E0B; border-color: #F59E0B; background: #F59E0B11; }"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.device.serial)
        super().mousePressEvent(event)

    def set_active(self, active: bool):
        self.is_active = active
        self.update_state(self.is_active, self.is_running, self.is_pinned, self.is_offline)

    def set_running(self, running: bool):
        self.is_running = running
        self.update_state(self.is_active, self.is_running, self.is_pinned, self.is_offline)

    def update_state(self, is_active: bool, is_running: bool, is_pinned: bool = False, is_offline: bool = False):
        self.is_active = is_active
        self.is_running = is_running
        self.is_pinned = is_pinned
        self.is_offline = is_offline

        self._update_pin_button_style()

        # 1. Update status dot color
        if self.is_offline:
            dot_color = "#64748B"  # gray
        elif self.device.state == "device":
            dot_color = "#10B981"  # green
        elif self.device.state == "unauthorized":
            dot_color = "#F59E0B"  # yellow
        else:
            dot_color = "#EF4444"  # red
        self.status_dot.setStyleSheet(f"background-color: {dot_color}; border-radius: 5px;")

        # 2. Update screen timeout badge & battery info
        if not self.is_offline and self.device.screen_off_timeout is not None:
            ms = self.device.screen_off_timeout
            if ms >= 86400000 or ms >= 2000000000:
                t_str = "⏱️ 24h (Awake)"
                t_color = "#38BDF8"  # Cyan/Blue
            elif ms >= 3600000:
                h = ms // 3600000
                t_str = f"⏱️ {h}h"
                t_color = "#94A3B8"
            elif ms >= 60000:
                m = ms // 60000
                t_str = f"⏱️ {m}m"
                t_color = "#94A3B8"
            else:
                s = ms // 1000
                t_str = f"⏱️ {s}s"
                t_color = "#F59E0B" if s <= 30 else "#94A3B8"
            self.timeout_label.setText(t_str)
            self.timeout_label.setToolTip(f"Screen sleep timeout: {ms // 1000}s ({ms} ms)")
            self.timeout_label.setStyleSheet(f"color: {t_color}; font-size: 11px; font-weight: 500;")
            self.timeout_label.setVisible(True)
        else:
            self.timeout_label.setVisible(False)

        if not self.is_offline and self.device.battery_level is not None:
            bat_icon = "⚡" if self.device.is_charging else "🔋"
            bat_color = "#10B981" if self.device.battery_level > 20 else "#EF4444"
            self.bat_label.setText(f"{bat_icon} {self.device.battery_level}%")
            self.bat_label.setStyleSheet(f"color: {bat_color}; font-size: 11px; font-weight: 600;")
            self.bat_label.setVisible(True)
        else:
            self.bat_label.setVisible(False)

        # 3. Toggle button visibility based on device state
        if self.is_offline:
            self.btn_reconnect.setVisible(True)
            self.btn_launch.setVisible(False)
            self.btn_otg.setVisible(False)
            self.btn_stop.setVisible(False)
            self.btn_card_disc.setVisible(False)
            self.unauth_label.setText("⚪ Disconnected (Click Reconnect)")
            self.unauth_label.setStyleSheet("color: #64748B; font-size: 11px;")
            self.unauth_label.setVisible(True)
        else:
            self.btn_reconnect.setVisible(False)
            is_device_ok = (self.device.state == "device")
            if is_device_ok:
                self.unauth_label.setVisible(False)
                if is_running:
                    self.btn_stop.setVisible(True)
                    self.btn_launch.setVisible(False)
                    self.btn_otg.setVisible(False)
                else:
                    self.btn_stop.setVisible(False)
                    self.btn_launch.setVisible(True)
                    self.btn_otg.setVisible(True)
            else:
                self.unauth_label.setText(f"Status: {self.device.state.upper()} (Check phone screen)")
                self.unauth_label.setStyleSheet("color: #F59E0B; font-size: 11px; font-style: italic;")
                self.unauth_label.setVisible(True)
                self.btn_stop.setVisible(False)
                self.btn_launch.setVisible(False)
                self.btn_otg.setVisible(False)

        # 4. Apply border styling
        if self.is_active:
            border = "2px solid #3B82F6"
            bg = "#1F2432"
        elif self.is_running:
            border = "1px solid #10B981"
            bg = "#1A222A"
        elif self.is_offline:
            border = "1px dashed #2E3342"
            bg = "#15171E"
        else:
            border = "1px solid #282C37"
            bg = "#191B22"

        self.setStyleSheet(f"""
            QFrame#deviceCard {{
                background-color: {bg};
                border: {border};
                border-radius: 8px;
            }}
            QFrame#deviceCard:hover {{
                border-color: #3B82F6;
                background-color: #202636;
            }}
        """)
