import os
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import AdbDevice, AdbDeviceScanner, AdbManager
from core.config_manager import ConfigManager
from core.icon_manager import IconManager
from core.process_manager import ProcessManager
from ui.components.app_launcher import AppLauncherWidget
from ui.components.command_injector import CommandInjectorWidget
from ui.components.device_card import DeviceCard
from ui.components.drop_zone import DropZoneWidget
from ui.components.favorites_bar import FavoriteAppsBar
from ui.components.log_viewer import LogViewer
from ui.components.quick_actions import QuickActionBar
from ui.components.settings_panel import SettingsPanel
from ui.components.stream_panel import StreamPanel
from ui.components.wireless_dialog import WirelessDialog


class MainWindow(QMainWindow):
    """Main application window for Scrcpy Studio."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.adb = AdbManager(self.config.get_scrcpy_bin_dir())
        self.process_manager = ProcessManager(self.config.get_scrcpy_bin_dir(), adb=self.adb, parent=self)
        self.icon_manager = IconManager.get_instance(str(self.config.get_scrcpy_bin_dir() / "adb.exe"))
        self.icon_manager.icon_ready.connect(self._on_icon_ready_log)

        self.devices: Dict[str, AdbDevice] = {}
        self.selected_serial: Optional[str] = None
        self.card_widgets: Dict[str, DeviceCard] = {}

        self.setWindowTitle("Scrcpy Studio — Android Control & Mirroring")
        self.resize(1220, 820)
        self.setMinimumSize(960, 640)

        self._setup_ui()
        self._update_header_runtime_status()
        self._setup_tray_icon()
        self._wire_signals()
        self._start_scanner()
        # Attempt auto-connecting to pinned wireless devices on startup
        QTimer.singleShot(500, self._auto_connect_pinned_devices)
        # Check if scrcpy is downloaded on first launch
        QTimer.singleShot(800, self._check_startup_scrcpy_status)

    def _setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(16, 14, 16, 12)
        root_layout.setSpacing(12)

        # 1. Modern Top Header Bar
        header = QFrame()
        header.setStyleSheet("background-color: #161820; border-radius: 10px; border: 1px solid #282C37;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(12)

        # App Logo & Title
        title_box = QHBoxLayout()
        title_box.setSpacing(8)
        lbl_icon = QLabel("⚡")
        lbl_icon.setStyleSheet("font-size: 20px;")
        title_box.addWidget(lbl_icon)

        lbl_title = QLabel("Scrcpy Studio")
        lbl_title.setObjectName("headingLabel")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #38BDF8; letter-spacing: 0.5px;")
        title_box.addWidget(lbl_title)

        self.lbl_ver = QLabel("Checking...")
        self.lbl_ver.setObjectName("badge")
        self.lbl_ver.mousePressEvent = lambda event: self._open_updater_dialog()
        title_box.addWidget(self.lbl_ver)

        self.btn_header_update = QPushButton("⬇️ Download Scrcpy")
        self.btn_header_update.setFixedHeight(22)
        self.btn_header_update.setCursor(Qt.PointingHandCursor)
        self.btn_header_update.clicked.connect(self._open_updater_dialog)
        self.btn_header_update.setVisible(False)
        title_box.addWidget(self.btn_header_update)

        header_layout.addLayout(title_box)

        header_layout.addSpacing(16)

        # Top Navigation Segmented Tab Bar
        nav_box = QFrame()
        nav_box.setStyleSheet("background-color: #111319; border-radius: 8px; border: 1px solid #232734; padding: 2px;")
        nav_layout = QHBoxLayout(nav_box)
        nav_layout.setContentsMargins(4, 2, 4, 2)
        nav_layout.setSpacing(4)

        self.nav_btn_mirror = QPushButton("🎮 Mirroring")
        self.nav_btn_mirror.setProperty("class", "navPill")
        self.nav_btn_mirror.setCursor(Qt.PointingHandCursor)
        self.nav_btn_mirror.clicked.connect(lambda: self._switch_page(0))
        nav_layout.addWidget(self.nav_btn_mirror)

        self.nav_btn_apps = QPushButton("📱 App Launcher")
        self.nav_btn_apps.setProperty("class", "navPill")
        self.nav_btn_apps.setCursor(Qt.PointingHandCursor)
        self.nav_btn_apps.clicked.connect(lambda: self._switch_page(1))
        nav_layout.addWidget(self.nav_btn_apps)

        self.nav_btn_console = QPushButton("💻 ADB Console")
        self.nav_btn_console.setProperty("class", "navPill")
        self.nav_btn_console.setCursor(Qt.PointingHandCursor)
        self.nav_btn_console.clicked.connect(lambda: self._switch_page(2))
        nav_layout.addWidget(self.nav_btn_console)

        self.nav_btn_logs = QPushButton("📋 Logs")
        self.nav_btn_logs.setProperty("class", "navPill")
        self.nav_btn_logs.setCursor(Qt.PointingHandCursor)
        self.nav_btn_logs.clicked.connect(lambda: self._switch_page(3))
        nav_layout.addWidget(self.nav_btn_logs)

        self.nav_btn_settings = QPushButton("⚙️ Settings")
        self.nav_btn_settings.setProperty("class", "navPill")
        self.nav_btn_settings.setCursor(Qt.PointingHandCursor)
        self.nav_btn_settings.clicked.connect(lambda: self._switch_page(4))
        nav_layout.addWidget(self.nav_btn_settings)

        header_layout.addWidget(nav_box)

        header_layout.addStretch(1)

        # Header Action Buttons
        self.btn_wireless = QPushButton("🔍 Scan & Wireless ADB")
        self.btn_wireless.setObjectName("primaryBtn")
        self.btn_wireless.setCursor(Qt.PointingHandCursor)
        self.btn_wireless.clicked.connect(self._open_wireless_dialog)
        header_layout.addWidget(self.btn_wireless)

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self._manual_refresh)
        header_layout.addWidget(self.btn_refresh)

        root_layout.addWidget(header)

        # ====================================================
        # 2. Main Stacked Pages View
        # ====================================================
        self.main_stack = QStackedWidget()

        # --- PAGE 0: 🎮 MIRRORING STUDIO ---
        page_mirror = QWidget()
        l_page_mirror = QVBoxLayout(page_mirror)
        l_page_mirror.setContentsMargins(0, 0, 0, 0)
        l_page_mirror.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #21242D; width: 2px; }")

        # Left Column: Devices & Quick Controls
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(10)

        dev_header = QHBoxLayout()
        lbl_devs = QLabel("CONNECTED DEVICES")
        lbl_devs.setStyleSheet("font-size: 12px; font-weight: bold; color: #94A3B8; letter-spacing: 0.5px;")
        dev_header.addWidget(lbl_devs)

        self.lbl_dev_count = QLabel("(0)")
        self.lbl_dev_count.setStyleSheet("color: #64748B; font-size: 11px;")
        dev_header.addWidget(self.lbl_dev_count)
        dev_header.addStretch(1)
        left_layout.addLayout(dev_header)

        # Scroll area for device cards
        self.device_scroll = QScrollArea()
        self.device_scroll.setWidgetResizable(True)
        self.device_scroll.setMinimumHeight(200)
        self.device_scroll.setMaximumHeight(360)

        self.device_container = QWidget()
        self.device_list_layout = QVBoxLayout(self.device_container)
        self.device_list_layout.setContentsMargins(6, 6, 6, 6)
        self.device_list_layout.setSpacing(10)
        self.device_list_layout.setAlignment(Qt.AlignTop)

        # Polished Empty State Widget
        self.empty_state_widget = QFrame()
        self.empty_state_widget.setMinimumHeight(160)
        self.empty_state_widget.setStyleSheet(
            "QFrame { background-color: #161820; border: 1px dashed #2E3342; border-radius: 8px; }"
        )
        empty_layout = QVBoxLayout(self.empty_state_widget)
        empty_layout.setContentsMargins(16, 20, 16, 20)
        empty_layout.setSpacing(12)

        lbl_empty_title = QLabel("📱 No Devices Connected")
        lbl_empty_title.setAlignment(Qt.AlignCenter)
        lbl_empty_title.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 14px; border: none;")
        empty_layout.addWidget(lbl_empty_title)

        lbl_empty_desc = QLabel("Connect phone via USB with USB Debugging enabled, or scan your Wi-Fi network below.")
        lbl_empty_desc.setAlignment(Qt.AlignCenter)
        lbl_empty_desc.setWordWrap(True)
        lbl_empty_desc.setStyleSheet("color: #94A3B8; font-size: 12px; border: none;")
        empty_layout.addWidget(lbl_empty_desc)

        btn_empty_scan = QPushButton("🔍 Auto-Scan Wi-Fi")
        btn_empty_scan.setObjectName("primaryBtn")
        btn_empty_scan.setFixedHeight(32)
        btn_empty_scan.setFixedWidth(160)
        btn_empty_scan.setCursor(Qt.PointingHandCursor)
        btn_empty_scan.clicked.connect(self._open_wireless_dialog)
        empty_layout.addWidget(btn_empty_scan, 0, Qt.AlignCenter)

        self.device_list_layout.addWidget(self.empty_state_widget)

        self.device_scroll.setWidget(self.device_container)
        left_layout.addWidget(self.device_scroll, 1)

        # ⭐ Favorite Apps Bar (Placed directly above Quick Actions)
        self.favorites_bar = FavoriteAppsBar(self.config, self.adb)
        left_layout.addWidget(self.favorites_bar, 0)

        # Quick Actions Bar
        self.quick_actions = QuickActionBar(self.adb)
        left_layout.addWidget(self.quick_actions, 0)

        # Drag & Drop Zone
        self.drop_zone = DropZoneWidget(self.adb)
        left_layout.addWidget(self.drop_zone, 0)

        splitter.addWidget(left_container)

        # Right Column: Stream Configuration & Logs
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(10)

        # Stream Panel
        self.stream_panel = StreamPanel(self.config)
        right_layout.addWidget(self.stream_panel, 1)

        # Quick Log Preview on Mirroring Page
        self.log_viewer_mini = LogViewer()
        self.log_viewer_mini.setMinimumHeight(150)
        right_layout.addWidget(self.log_viewer_mini, 0)

        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)

        l_page_mirror.addWidget(splitter)
        self.main_stack.addWidget(page_mirror)

        # --- PAGE 1: 📱 FULL-SIZE APP LAUNCHER ---
        self.app_launcher = AppLauncherWidget(self.adb, self.config)
        self.main_stack.addWidget(self.app_launcher)

        # --- PAGE 2: 💻 FULL-SIZE ADB COMMAND INJECTOR & CONSOLE ---
        page_console = QWidget()
        l_page_console = QVBoxLayout(page_console)
        l_page_console.setContentsMargins(0, 0, 0, 0)
        self.command_injector = CommandInjectorWidget(self.adb)
        l_page_console.addWidget(self.command_injector)
        self.main_stack.addWidget(page_console)

        # --- PAGE 3: 📋 DEDICATED SYSTEM LOGS VIEWER ---
        page_logs = QWidget()
        l_page_logs = QVBoxLayout(page_logs)
        l_page_logs.setContentsMargins(0, 0, 0, 0)
        self.log_viewer = LogViewer()
        l_page_logs.addWidget(self.log_viewer)
        self.main_stack.addWidget(page_logs)

        # --- PAGE 4: ⚙️ SETTINGS PANEL ---
        self.settings_panel = SettingsPanel(self.config)
        self.main_stack.addWidget(self.settings_panel)

        root_layout.addWidget(self.main_stack, 1)

        # Initialize active nav button
        self._switch_page(0)

        # 3. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_status_device = QLabel("No device selected")
        self.lbl_status_engine = QLabel(f"Scrcpy Engine: {self.adb.adb_dir}")
        self.lbl_status_engine.setStyleSheet("color: #475569;")
        self.status_bar.addWidget(self.lbl_status_device, 1)
        self.status_bar.addPermanentWidget(self.lbl_status_engine)

    def _switch_page(self, index: int):
        self.main_stack.setCurrentIndex(index)
        buttons = [
            self.nav_btn_mirror,
            self.nav_btn_apps,
            self.nav_btn_console,
            self.nav_btn_logs,
            self.nav_btn_settings,
        ]
        for i, b in enumerate(buttons):
            b.setProperty("selected", str(i == index).lower())
            b.style().unpolish(b)
            b.style().polish(b)

        if index == 4:
            self.settings_panel.load_settings()

    def _append_log(self, source: str, msg: str):
        self.log_viewer_mini.append_log(source, msg)
        self.log_viewer.append_log(source, msg)

    def _wire_signals(self):
        # Stream panel buttons
        self.stream_panel.launch_requested.connect(self._on_launch_current)
        self.stream_panel.stop_requested.connect(self._on_stop_current)
        self.stream_panel.settings_changed.connect(self._save_settings)

        # Favorite Apps Bar
        self.favorites_bar.launch_app_requested.connect(self._on_favorite_app_launch)
        self.favorites_bar.open_apps_manager_requested.connect(lambda: self._switch_page(1))

        # Quick actions
        self.quick_actions.action_triggered.connect(
            lambda act, msg: self._append_log(act, msg)
        )
        self.quick_actions.disconnect_requested.connect(self._on_disconnect_device)
        self.quick_actions.open_apps_requested.connect(lambda: self._switch_page(1))

        # Drop zone
        self.drop_zone.status_message.connect(
            lambda msg: self._append_log("FileTransfer", msg)
        )

        # Command injector
        self.command_injector.command_executed.connect(
            lambda cmd, res: self._append_log(f"ADB:{cmd}", res[:120].replace('\n', ' '))
        )

        # App Launcher
        self.app_launcher.app_launched.connect(
            lambda pkg, msg: self._append_log("AppLauncher", msg)
        )
        self.app_launcher.action_completed.connect(
            lambda act, msg: self._append_log(act, msg)
        )
        self.app_launcher.app_display_launch_requested.connect(self._on_app_display_launch)
        self.app_launcher.favorite_toggled.connect(self.favorites_bar.refresh_favorites)

        # Settings panel
        self.settings_panel.runtime_update_requested.connect(self._open_updater_dialog)
        self.settings_panel.refresh_rate_changed.connect(self._on_refresh_rate_changed)
        self.settings_panel.settings_changed.connect(self._save_settings)

        # Process manager signals
        self.process_manager.session_started.connect(self._on_session_started)
        self.process_manager.session_stopped.connect(self._on_session_stopped)
        self.process_manager.log_output.connect(
            lambda serial, msg: self._append_log(f"Scrcpy:{serial}", msg)
        )
        self.process_manager.error_occurred.connect(
            lambda serial, err: self._append_log(f"Error:{serial}", err)
        )

    def _on_favorite_app_launch(self, serial: str, package: str, name: str, display_res: str = ""):
        if not self._check_runtime_installed():
            return
        session_id = f"{serial}::{package}"
        title = f"[{name}] {serial}"
        
        # Use specific preset configured for this favorite app, or fallback to global launcher preset
        res = display_res if display_res else self.config.get("app_launcher_disp_res", "")
        settings = {
            "start_app": package,
            "new_display": True,
            "new_display_res": res,
            "stay_awake": True,
            "force_stay_awake": True,
            "sync_clipboard": True,
        }
        if res:
            preset = self.config.get_preset_by_value(res)
            if preset:
                if preset.get("win_w"):
                    settings["window_width"] = preset["win_w"]
                if preset.get("win_h"):
                    settings["window_height"] = preset["win_h"]

        res_info = f" ({res})" if res else " (Native)"
        self._append_log("FavoriteApps", f"Launching favorite app '{name}' in virtual display window{res_info}...")
        self.process_manager.start_session(serial, settings, title, session_id=session_id)

    def _on_app_display_launch(self, serial: str, settings: Dict, package: str, title: str):
        if not self._check_runtime_installed():
            return
        session_id = f"{serial}::{package}"
        self._append_log("AppLauncher", f"Launching '{package}' in new virtual display window...")
        self.process_manager.start_session(serial, settings, title, session_id=session_id)

    def _on_icon_ready_log(self, pkg: str, path: str, source: str, detail: str):
        if source == "adb":
            self._append_log("IconManager", f"Extracted '{pkg}' icon directly from device APK ({detail}) via ADB")
        else:
            self._append_log("IconManager", f"Retrieved '{pkg}' icon from {detail} metadata")

    def _start_scanner(self):
        interval = self.config.get("auto_refresh_interval_ms", 2000)
        self.scanner = AdbDeviceScanner(self.adb, interval_ms=interval, parent=self)
        self.scanner.devices_updated.connect(self._on_devices_updated)
        self.scanner.start()

    def _auto_connect_pinned_devices(self):
        pinned = self.config.get_pinned_devices()
        for p in pinned:
            serial = p.get("serial", "")
            # Only connect to wireless endpoints
            if serial and (":" in serial or p.get("is_wireless", False)):
                if serial not in self.devices:
                    self._append_log("System", f"Auto-reconnecting pinned device: {serial}...")
                    self.adb.connect_wireless(serial)

    def _on_devices_updated(self, device_list: List[AdbDevice]):
        self.devices = {d.serial: d for d in device_list}
        pinned_list = self.config.get_pinned_devices()
        pinned_map = {p["serial"]: p for p in pinned_list}

        # Clean existing cards
        for card in list(self.card_widgets.values()):
            self.device_list_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self.card_widgets.clear()

        # Count total active
        self.lbl_dev_count.setText(f"({len(device_list)})")

        if not device_list and not pinned_list:
            self.empty_state_widget.setVisible(True)
            self.selected_serial = None
            self.quick_actions.set_device(None)
            self.favorites_bar.set_device(None)
            self.drop_zone.set_device(None)
            self.command_injector.set_device(None)
            self.app_launcher.set_device(None)
            self.lbl_status_device.setText("No device connected")
            return

        self.empty_state_widget.setVisible(False)

        # Preserve selection or pick first active device
        last_serial = self.config.get("last_selected_serial", "")
        if self.selected_serial not in self.devices:
            if last_serial in self.devices:
                self.selected_serial = last_serial
            elif device_list:
                self.selected_serial = device_list[0].serial

        # 1. Render currently connected devices
        rendered_serials = set()
        for dev in device_list:
            rendered_serials.add(dev.serial)
            is_active = (dev.serial == self.selected_serial)
            is_running = self.process_manager.is_running(dev.serial)
            is_pinned = self.config.is_pinned(dev.serial)
            alias = self.config.get_device_alias(dev.serial, fallback=dev.display_name)

            card = DeviceCard(
                dev,
                alias=alias,
                is_active=is_active,
                is_running=is_running,
                is_pinned=is_pinned,
                is_offline=False
            )
            card.selected.connect(self._on_device_selected)
            card.launch_requested.connect(lambda s=dev.serial: self._launch_device(s))
            card.otg_requested.connect(lambda s=dev.serial: self._launch_device_otg(s))
            card.stop_requested.connect(lambda s=dev.serial: self._stop_device(s))
            card.disconnect_requested.connect(lambda s=dev.serial: self._on_disconnect_device(s))
            card.pin_toggled.connect(self._on_pin_toggled)
            card.profile_requested.connect(self._open_device_profile_dialog)
            self.device_list_layout.addWidget(card)
            self.card_widgets[dev.serial] = card

        # 2. Render pinned devices that are currently offline / disconnected
        for serial, pinfo in pinned_map.items():
            if serial not in rendered_serials:
                alias = self.config.get_device_alias(serial, fallback=pinfo.get("name", serial))
                offline_dev = AdbDevice(
                    serial=serial,
                    state="offline",
                    model=alias,
                    is_wireless=pinfo.get("is_wireless", True)
                )
                card = DeviceCard(
                    offline_dev,
                    alias=alias,
                    is_active=False,
                    is_running=False,
                    is_pinned=True,
                    is_offline=True
                )
                card.connect_requested.connect(self._on_reconnect_pinned_device)
                card.pin_toggled.connect(self._on_pin_toggled)
                card.profile_requested.connect(self._open_device_profile_dialog)
                self.device_list_layout.addWidget(card)
                self.card_widgets[serial] = card

        self._update_selected_device_state()

    def _open_device_profile_dialog(self, serial: str):
        from ui.components.device_profile_dialog import DeviceProfileDialog
        dev = self.devices.get(serial)
        dlg = DeviceProfileDialog(serial, self.config, dev, self)
        dlg.profile_saved.connect(self._on_device_profile_saved)
        dlg.exec()

    def _on_device_profile_saved(self, serial: str):
        alias = self.config.get_device_alias(serial)
        if serial in self.card_widgets:
            self.card_widgets[serial].set_alias(alias)
        if serial == self.selected_serial:
            self._update_selected_device_state()
        self._manual_refresh()

    def _on_pin_toggled(self, serial: str, is_pinned: bool):
        if is_pinned:
            dev_name = self.config.get_device_alias(serial, serial)
            is_wireless = True
            if serial in self.devices:
                is_wireless = self.devices[serial].is_wireless or (":" in serial)
            self.config.pin_device(serial, dev_name, is_wireless)
            self._append_log("System", f"Pinned device {dev_name} ({serial})")
        else:
            self.config.unpin_device(serial)
            self._append_log("System", f"Unpinned device {serial}")

        # Refresh device list view
        self._manual_refresh()

    def _on_reconnect_pinned_device(self, serial: str):
        self._append_log("System", f"Connecting to pinned device: {serial}...")
        ok, msg = self.adb.connect_wireless(serial)
        if ok:
            self._append_log("ADB", f"Successfully reconnected to {serial}")
            self.config.add_recent_ip(serial)
        else:
            self._append_log("ADB", f"Failed to reconnect to {serial}: {msg}")
        self._manual_refresh()

    def _on_device_selected(self, serial: str):
        self.selected_serial = serial
        self.config.set("last_selected_serial", serial)
        for s, card in self.card_widgets.items():
            card.set_active(s == serial)
        self._update_selected_device_state()

    def _update_selected_device_state(self):
        if not self.selected_serial or self.selected_serial not in self.devices:
            self.stream_panel.set_active_device(None)
            self.quick_actions.set_device(None)
            self.favorites_bar.set_device(None)
            self.drop_zone.set_device(None)
            self.command_injector.set_device(None)
            self.app_launcher.set_device(None)
            self.lbl_status_device.setText("No device selected")
            return

        dev = self.devices[self.selected_serial]
        alias = self.config.get_device_alias(dev.serial, dev.display_name)
        self.stream_panel.set_active_device(dev.serial, alias)
        self.quick_actions.set_device(dev.serial)
        self.favorites_bar.set_device(dev.serial)
        self.drop_zone.set_device(dev.serial)
        self.command_injector.set_device(dev.serial)
        self.app_launcher.set_device(dev.serial)
        self.lbl_status_device.setText(f"Active Device: {alias} ({dev.serial})")
        self._update_tray_menu()

    def _on_launch_current(self):
        if not self.selected_serial:
            QMessageBox.warning(self, "No Device", "Please select a connected device first.")
            return
        self._launch_device(self.selected_serial)

    def _on_stop_current(self):
        if not self.selected_serial:
            return
        self._stop_device(self.selected_serial)

    def _on_disconnect_device(self, serial: str):
        if not serial:
            return
        # Stop active mirroring session first if running
        if self.process_manager.is_running(serial):
            self.process_manager.stop_session(serial)

        self._append_log("System", f"Disconnecting {serial}...")
        ok, msg = self.adb.disconnect_wireless(serial)
        self._append_log("ADB", f"Disconnected {serial}: {msg or ('OK' if ok else 'Failed')}")
        self._manual_refresh()

    def _update_header_runtime_status(self):
        """Update header version badge and download/update button styling based on runtime availability."""
        if self.config.is_scrcpy_installed():
            scrcpy_version = self.config.get_scrcpy_version()
            self.lbl_ver.setText(scrcpy_version)
            self.lbl_ver.setToolTip(f"Active Scrcpy Runtime: {scrcpy_version} (Click to manage runtime)")
            self.lbl_ver.setStyleSheet(
                "background-color: #1E222D; color: #38BDF8; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; border: 1px solid #38BDF833;"
            )
            self.lbl_ver.setCursor(Qt.PointingHandCursor)
            # Hide the action button when already installed and up to date
            self.btn_header_update.setVisible(False)
        else:
            self.lbl_ver.setText("🔴 Not Installed")
            self.lbl_ver.setToolTip("Scrcpy runtime binaries are not downloaded yet.")
            self.lbl_ver.setStyleSheet(
                "background-color: #7F1D1D; color: #FCA5A5; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;"
            )
            self.lbl_ver.setCursor(Qt.PointingHandCursor)
            self.btn_header_update.setText("⬇️ Download Scrcpy")
            self.btn_header_update.setToolTip("Download official 64-bit Scrcpy binaries from GitHub")
            self.btn_header_update.setStyleSheet(
                "QPushButton { background-color: #0284C7; color: #FFFFFF; border: none; border-radius: 4px; font-size: 10px; font-weight: bold; padding: 2px 8px; }"
                "QPushButton:hover { background-color: #38BDF8; }"
            )
            self.btn_header_update.setVisible(True)

    def _check_startup_scrcpy_status(self):
        """Prompt if missing or quietly check for updates in background if installed."""
        if not self.config.is_scrcpy_installed():
            res = QMessageBox.question(
                self,
                "Download Scrcpy Runtime",
                "Scrcpy runtime binaries were not found.\n\n"
                "Would you like to download the official 64-bit Scrcpy binaries from GitHub now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if res == QMessageBox.Yes:
                self._open_updater_dialog()
        else:
            # Quiet background check for new releases
            current_ver = self.config.get_scrcpy_version()
            from core.scrcpy_updater import ScrcpyUpdateChecker
            self._bg_checker = ScrcpyUpdateChecker(current_ver, self)
            self._bg_checker.check_finished.connect(self._on_bg_update_check_finished)
            self._bg_checker.start()

    def _on_bg_update_check_finished(self, has_update: bool, release_info: dict, message: str):
        """If a newer Scrcpy version is available on GitHub, reveal the update pill."""
        if has_update and release_info:
            tag = release_info.get("tag", "")
            self.btn_header_update.setText(f"✨ Update to {tag}")
            self.btn_header_update.setToolTip(f"A newer Scrcpy release ({tag}) is available on GitHub. Click to update.")
            self.btn_header_update.setStyleSheet(
                "QPushButton { background-color: #0369A1; color: #E0F2FE; border: 1px solid #38BDF8; border-radius: 4px; font-size: 10px; font-weight: bold; padding: 2px 8px; }"
                "QPushButton:hover { background-color: #0284C7; color: #FFFFFF; }"
            )
            self.btn_header_update.setVisible(True)
        else:
            self.btn_header_update.setVisible(False)

    def _check_runtime_installed(self) -> bool:
        """Verify Scrcpy runtime is available before attempting to launch mirroring or ADB actions."""
        if not self.config.is_scrcpy_installed():
            res = QMessageBox.question(
                self,
                "Scrcpy Runtime Required",
                "Official Scrcpy runtime binaries are required to perform this action.\n\n"
                "Would you like to download Scrcpy from GitHub now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if res == QMessageBox.Yes:
                self._open_updater_dialog()
            return False
        return True

    def _launch_device(self, serial: str, extra_override: Optional[Dict] = None):
        if not self._check_runtime_installed():
            return

        if serial == self.selected_serial:
            settings = self.stream_panel.get_settings()
        else:
            settings = self.config.get_device_settings(serial).copy()

        if extra_override:
            settings.update(extra_override)

        dev_name = self.config.get_device_alias(serial)
        if not dev_name and serial in self.devices:
            dev_name = self.devices[serial].display_name

        self._append_log("System", f"Starting mirroring session for {dev_name} ({serial})...")
        self.process_manager.start_session(serial, settings, dev_name)

    def _launch_device_otg(self, serial: str):
        self._launch_device(serial, extra_override={"otg_mode": True})

    def _stop_device(self, serial: str):
        self._append_log("System", f"Stopping session for {serial}...")
        self.process_manager.stop_session(serial)

    def _on_session_started(self, serial: str):
        if serial in self.card_widgets:
            self.card_widgets[serial].set_running(True)

    def _on_session_stopped(self, serial: str, exit_code: int):
        if serial in self.card_widgets:
            self.card_widgets[serial].set_running(False)

    def _save_settings(self):
        current = self.stream_panel.get_settings()
        self.config.set("current_settings", current)

    def _manual_refresh(self):
        self._append_log("System", "Refreshing devices...")
        devs = self.adb.list_devices()
        self._on_devices_updated(devs)

    def _open_wireless_dialog(self):
        if not self._check_runtime_installed():
            return
        dlg = WirelessDialog(self.adb, self.config, self.selected_serial, self)
        dlg.connection_successful.connect(lambda ip: self._manual_refresh())
        dlg.exec()

    def _setup_tray_icon(self):
        """Create and configure the Windows System Tray icon with dynamic quick actions."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.windowIcon() if not self.windowIcon().isNull() else self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self.tray_icon.setToolTip("Scrcpy Studio — Android Control & Mirroring")

        self.tray_menu = QMenu()
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self._update_tray_menu()
        self.tray_icon.show()

    def _update_tray_menu(self):
        """Rebuild the system tray context menu with live device & favorite apps."""
        if not hasattr(self, "tray_menu") or self.tray_menu is None:
            return

        self.tray_menu.clear()

        # Title / Device Header
        if self.selected_serial:
            dev_name = self.devices[self.selected_serial].display_name if self.selected_serial in self.devices else self.selected_serial
            header_act = self.tray_menu.addAction(f"📱 Connected: {dev_name}")
            header_act.setEnabled(False)
            font = header_act.font()
            font.setBold(True)
            header_act.setFont(font)

            act_mirror = self.tray_menu.addAction("🚀 Mirror Phone Screen")
            act_mirror.triggered.connect(lambda: self._launch_device(self.selected_serial))
        else:
            header_act = self.tray_menu.addAction("📱 No Device Connected")
            header_act.setEnabled(False)

        self.tray_menu.addSeparator()

        # ⭐ Favorite Apps Quick-Launch Submenu
        favs = self.config.get_favorite_apps()
        if favs:
            menu_favs = self.tray_menu.addMenu("⭐ Quick-Launch Favorite Apps")
            for fav in favs:
                pkg = fav.get("package", "")
                name = fav.get("name", pkg)
                res = fav.get("display_res", "")
                app_icon = self.icon_manager.get_icon(pkg, self.selected_serial)
                if app_icon:
                    act_fav = menu_favs.addAction(app_icon, name)
                else:
                    act_fav = menu_favs.addAction(f"{fav.get('icon', '📱')} {name}")
                act_fav.triggered.connect(
                    lambda _, p=pkg, n=name, r=res: self._on_favorite_app_launch(self.selected_serial or "", p, n, r)
                )

        self.tray_menu.addSeparator()

        # Window Controls
        act_show = self.tray_menu.addAction("🪟 Show Scrcpy Studio")
        act_show.triggered.connect(self._restore_from_tray)

        act_refresh = self.tray_menu.addAction("🔄 Refresh Devices")
        act_refresh.triggered.connect(self._manual_refresh)

        act_update = self.tray_menu.addAction("🔄 Check / Download Scrcpy...")
        act_update.triggered.connect(self._open_updater_dialog)

        self.tray_menu.addSeparator()
        act_quit = self.tray_menu.addAction("❌ Quit Scrcpy Studio")
        act_quit.triggered.connect(self._force_quit)

    def _open_updater_dialog(self):
        from ui.components.scrcpy_updater_dialog import ScrcpyUpdaterDialog

        dlg = ScrcpyUpdaterDialog(self.config, self)
        dlg.scrcpy_updated.connect(self._on_scrcpy_updated)
        dlg.exec()

    def _on_scrcpy_updated(self, new_version: str):
        self._update_header_runtime_status()
        bin_dir = self.config.get_scrcpy_bin_dir()
        self.adb = AdbManager(bin_dir)
        self.process_manager.scrcpy_dir = bin_dir
        self.process_manager.scrcpy_bin = bin_dir / "scrcpy.exe"
        self.process_manager.adb = self.adb
        self.icon_manager.adb_bin = str(bin_dir / "adb.exe")
        self._append_log("Updater", f"Scrcpy runtime successfully deployed ({new_version})!")
        self._start_scanner()
        self._manual_refresh()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self._restore_from_tray()

    def _restore_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_refresh_rate_changed(self, interval_ms: int):
        if hasattr(self, "scanner"):
            self.scanner.interval_ms = interval_ms
            self._append_log("System", f"Device scan interval updated to {interval_ms} ms")

    def _force_quit(self):
        self._append_log("System", "Quitting Scrcpy Studio...")
        self.tray_icon.hide()
        self.scanner.stop()
        self.command_injector.stop()
        self.process_manager.stop_all()
        self._save_settings()
        QApplication.quit()

    def closeEvent(self, event):
        close_to_tray = self.config.get("close_to_tray", True)
        if close_to_tray and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            notify_enabled = self.config.get("notifications_enabled", True)
            if notify_enabled and not getattr(self, "_tray_notified", False):
                self._tray_notified = True
                self.tray_icon.showMessage(
                    "Scrcpy Studio",
                    "Running in background. Click tray icon to restore or launch favorite apps.",
                    QSystemTrayIcon.Information,
                    3000,
                )
        else:
            self._force_quit()
            super().closeEvent(event)
