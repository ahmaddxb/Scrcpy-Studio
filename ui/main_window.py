import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QThread, Qt, QTimer, Signal
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
from ui.components.companion_bar import CompanionToolBar
from ui.components.device_profile_dialog import DeviceProfileDialog
from ui.components.app_updater_dialog import AppUpdaterDialog
from core.app_updater import APP_VERSION, AppUpdateChecker


class AdbScanWorker(QThread):
    devices_ready = Signal(list)

    def __init__(self, adb: AdbManager, parent=None):
        super().__init__(parent)
        self.adb = adb

    def run(self):
        try:
            devs = self.adb.list_devices()
            self.devices_ready.emit(devs)
        except Exception:
            self.devices_ready.emit([])


class AutoReconnectWorker(QThread):
    finished_reconnect = Signal()

    def __init__(self, adb: AdbManager, serials: List[str], parent=None):
        super().__init__(parent)
        self.adb = adb
        self.serials = serials

    def run(self):
        for s in self.serials:
            try:
                self.adb.connect_wireless(s)
            except Exception:
                pass
        self.finished_reconnect.emit()


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
        self.companion_bars: Dict[str, CompanionToolBar] = {}
        self.pending_app_transfers: Dict[str, Tuple[str, str, str]] = {}

        self.setWindowTitle("Scrcpy Studio — Android Control & Mirroring")
        self.resize(1220, 820)
        self.setMinimumSize(960, 640)

        self._setup_ui()
        self._update_header_runtime_status()
        self._setup_tray_icon()
        self._wire_signals()
        # Immediately render initial pinned offline devices
        self._on_devices_updated([])
        self._start_scanner()
        # Attempt auto-connecting to pinned wireless devices on startup
        QTimer.singleShot(500, self._auto_connect_pinned_devices)
        # Check if scrcpy is downloaded on first launch
        QTimer.singleShot(800, self._check_startup_scrcpy_status)
        # Check for Scrcpy Studio app updates in background
        QTimer.singleShot(2500, self._check_app_updates_in_background)

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

        self.btn_app_update = QPushButton(f"🚀 Update Studio")
        self.btn_app_update.setFixedHeight(22)
        self.btn_app_update.setCursor(Qt.PointingHandCursor)
        self.btn_app_update.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8); color: #FFFFFF; border: none; border-radius: 4px; font-size: 10px; font-weight: bold; padding: 2px 8px; }"
            "QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369A1, stop:1 #0284C7); }"
        )
        self.btn_app_update.clicked.connect(self._open_app_updater_dialog)
        self.btn_app_update.setVisible(False)
        title_box.addWidget(self.btn_app_update)

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
        self.btn_refresh.setFixedWidth(110)
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
        self.quick_actions = QuickActionBar(self.adb, self.config, self.process_manager)
        left_layout.addWidget(self.quick_actions, 0)

        # Drag & Drop Zone
        self.drop_zone = DropZoneWidget(self.adb, self.config)
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

    def _append_log(self, source: str, msg: str):
        self.log_viewer_mini.append_log(source, msg)
        self.log_viewer.append_log(source, msg)

    def _wire_signals(self):
        # Stream panel buttons
        self.stream_panel.launch_requested.connect(self._on_launch_current)
        self.stream_panel.stop_requested.connect(self._on_stop_current)
        self.stream_panel.settings_changed.connect(self._save_settings)

        # Favorite Apps Bar
        self.favorites_bar.active_stream_getter = lambda: self.stream_panel.get_settings()
        self.favorites_bar.launch_app_requested.connect(self._on_favorite_app_launch)
        self.favorites_bar.pull_active_app_requested.connect(self._on_pull_active_phone_app)
        self.favorites_bar.open_apps_manager_requested.connect(lambda: self._switch_page(1))

        # Quick actions
        self.quick_actions.action_triggered.connect(
            lambda act, msg: self._append_log(act, msg)
        )
        self.quick_actions.open_apps_requested.connect(lambda: self._switch_page(1))
        self.quick_actions.pull_active_app_requested.connect(self._on_pull_active_phone_app)

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
        self.settings_panel.app_update_requested.connect(self._open_app_updater_dialog)
        self.settings_panel.refresh_rate_changed.connect(self._on_refresh_rate_changed)
        self.settings_panel.settings_changed.connect(self._save_settings)

        # Process manager signals
        self.process_manager.session_started.connect(self._on_session_started)
        self.process_manager.session_stopped.connect(self._on_session_stopped)
        self.process_manager.display_id_ready.connect(self._on_virtual_display_id_ready)
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

        # Per-app customization from favorite apps configuration
        fav_entry = next((f for f in self.config.get_favorite_apps() if f.get("package") == package), {})
        active_stream = self.stream_panel.get_settings() if hasattr(self, "stream_panel") else {}

        # Use specific preset configured for this favorite app, or fallback to global launcher preset
        res = display_res if display_res else fav_entry.get("display_res", "")
        if not res:
            res = self.config.get("app_launcher_disp_res", "")

        ime_policy = fav_entry.get("display_ime_policy") or self.config.get("display_ime_policy", "local")

        settings = {
            "start_app": package,
            "new_display": True,
            "new_display_res": res,
            "bitrate": fav_entry.get("bitrate") or active_stream.get("bitrate", "8M"),
            "max_fps": fav_entry.get("max_fps") or active_stream.get("max_fps", "0"),
            "video_codec": fav_entry.get("video_codec") or active_stream.get("video_codec", "h264"),
            "rotation": fav_entry.get("rotation") or active_stream.get("rotation", "0"),
            "audio_enabled": fav_entry.get("audio_enabled", active_stream.get("audio_enabled", True)),
            "audio_codec": fav_entry.get("audio_codec") or active_stream.get("audio_codec", "opus"),
            "audio_dup": fav_entry.get("audio_dup", active_stream.get("audio_dup", False)),
            "no_vd_system_decorations": fav_entry.get("no_vd_system_decorations", False),
            "always_on_top": fav_entry.get("always_on_top", False),
            "borderless": fav_entry.get("borderless", False),
            "turn_screen_off": fav_entry.get("turn_screen_off", False),
            "stay_awake": fav_entry.get("stay_awake", True),
            "show_touches": fav_entry.get("show_touches", False),
            "display_ime_policy": ime_policy,
            "custom_args": fav_entry.get("custom_args", ""),
            "sync_clipboard": True,
            "force_stay_awake": True,
        }
        if res:
            preset = self.config.get_preset_by_value(res)
            if preset:
                if preset.get("win_w"):
                    settings["window_width"] = preset["win_w"]
                if preset.get("win_h"):
                    settings["window_height"] = preset["win_h"]

        res_info = f" ({res})" if res else " (Native)"
        clean_info = " (Clean)" if settings.get("no_vd_system_decorations") else ""
        fps_info = f" {settings.get('max_fps')}fps" if settings.get("max_fps") and settings.get("max_fps") != "0" else ""
        bit_info = f" {settings.get('bitrate')}" if settings.get("bitrate") else ""
        self._append_log("FavoriteApps", f"Launching favorite app '{name}' in virtual display window{res_info}{clean_info}{fps_info}{bit_info}...")
        self.process_manager.start_session(serial, settings, title, session_id=session_id)

    def _on_move_favorite_app_to_display(self, serial: str, package: str, name: str, display_res: str = ""):
        if not self._check_runtime_installed():
            return

        session_id = f"{serial}::{package}"
        # Check if a dedicated virtual display window is ALREADY running specifically for this app
        active_disp_id = self.process_manager.get_active_display_id(session_id)

        if active_disp_id is not None:
            ok, msg = self.adb.move_app_to_display(serial, package, active_disp_id)
            status = "Success" if ok else "Notice"
            self._append_log("AppTransfer", f"[{status}] {msg}")
        else:
            # Always open a new, independent dedicated Virtual Display window for this app
            self._append_log("AppTransfer", f"Opening dedicated Virtual Display window for '{name}' (awaiting display ID)...")
            self.pending_app_transfers[session_id] = (serial, package, name)

            fav_entry = next((f for f in self.config.get_favorite_apps() if f.get("package") == package), {})
            active_stream = self.stream_panel.get_settings() if hasattr(self, "stream_panel") else {}
            res = display_res if display_res else fav_entry.get("display_res", "")
            if not res:
                res = self.config.get("app_launcher_disp_res", "")

            ime_policy = fav_entry.get("display_ime_policy") or self.config.get("display_ime_policy", "local")
            title = f"[{name}] {serial}"
            settings = {
                "new_display": True,
                "new_display_res": res,
                "bitrate": fav_entry.get("bitrate") or active_stream.get("bitrate", "8M"),
                "max_fps": fav_entry.get("max_fps") or active_stream.get("max_fps", "0"),
                "video_codec": fav_entry.get("video_codec") or active_stream.get("video_codec", "h264"),
                "rotation": fav_entry.get("rotation") or active_stream.get("rotation", "0"),
                "audio_enabled": fav_entry.get("audio_enabled", active_stream.get("audio_enabled", True)),
                "audio_codec": fav_entry.get("audio_codec") or active_stream.get("audio_codec", "opus"),
                "audio_dup": fav_entry.get("audio_dup", active_stream.get("audio_dup", False)),
                "no_vd_system_decorations": fav_entry.get("no_vd_system_decorations", False),
                "always_on_top": fav_entry.get("always_on_top", False),
                "borderless": fav_entry.get("borderless", False),
                "turn_screen_off": fav_entry.get("turn_screen_off", False),
                "stay_awake": fav_entry.get("stay_awake", True),
                "show_touches": fav_entry.get("show_touches", False),
                "display_ime_policy": ime_policy,
                "custom_args": fav_entry.get("custom_args", ""),
                "sync_clipboard": True,
                "force_stay_awake": True,
                # Explicitly NO start_app so it pulls the existing task!
            }
            if res:
                preset = self.config.get_preset_by_value(res)
                if preset:
                    if preset.get("win_w"):
                        settings["window_width"] = preset["win_w"]
                    if preset.get("win_h"):
                        settings["window_height"] = preset["win_h"]

            self.process_manager.start_session(serial, settings, title, session_id=session_id)

    def _on_virtual_display_id_ready(self, session_key: str, display_id: int):
        if session_key in self.pending_app_transfers:
            serial, package, name = self.pending_app_transfers.pop(session_key)
            self._append_log("AppTransfer", f"Virtual Display #{display_id} is ready! Moving live authenticated '{name}' from phone...")
            # 200ms delay to let SurfaceFlinger finish window composition
            QTimer.singleShot(200, lambda: self._do_transfer(serial, package, name, display_id))

    def _do_transfer(self, serial: str, package: str, name: str, display_id: int):
        ok, msg = self.adb.move_app_to_display(serial, package, display_id)
        status = "Success" if ok else "Notice"
        self._append_log("AppTransfer", f"[{status}] {msg}")

    def _on_pull_active_phone_app(self, serial: str):
        """Auto-detect whichever app is currently open on the phone and transfer it to PC Virtual Display."""
        if not serial or not self._check_runtime_installed():
            return

        pkg = self.adb.get_current_focused_package(serial)
        if not pkg or "launcher" in pkg.lower() or "systemui" in pkg.lower():
            self._append_log("AppTransfer", "[Notice] No active foreground app found open on phone screen.")
            if not self.isVisible() and hasattr(self, "tray_icon") and self.tray_icon.isVisible():
                self.tray_icon.showMessage(
                    "Move to PC",
                    "No active foreground app open on phone screen.",
                    QSystemTrayIcon.MessageIcon.Warning,
                    3000,
                )
            return

        # Check if we have a friendly name or custom resolution preset in favorites
        name = pkg.split(".")[-1].capitalize()
        preset_res = ""
        favorites = self.config.get_favorite_apps()
        fav = next((f for f in favorites if f.get("package") == pkg), None)
        if fav:
            name = fav.get("name", name)
            preset_res = fav.get("display_res", "")

        self._append_log("AppTransfer", f"Detected active app '{name}' ({pkg}) on phone. Transferring to PC...")
        if not self.isVisible() and hasattr(self, "tray_icon") and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "Move to PC",
                f"Transferring '{name}' to PC Virtual Display...",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
        self._on_move_favorite_app_to_display(serial, pkg, name, preset_res)

    def _on_app_display_launch(self, serial: str, settings: Dict, package: str, title: str):
        if not self._check_runtime_installed():
            return
        session_id = f"{serial}::{package}"

        # Merge with active global stream defaults (framerate, bitrate, codecs, etc.)
        active_stream = self.stream_panel.get_settings() if hasattr(self, "stream_panel") else {}
        fav_entry = next((f for f in self.config.get_favorite_apps() if f.get("package") == package), {})

        final_settings = {
            "bitrate": fav_entry.get("bitrate") or active_stream.get("bitrate", "8M"),
            "max_fps": fav_entry.get("max_fps") or active_stream.get("max_fps", "0"),
            "video_codec": fav_entry.get("video_codec") or active_stream.get("video_codec", "h264"),
            "rotation": fav_entry.get("rotation") or active_stream.get("rotation", "0"),
            "audio_enabled": fav_entry.get("audio_enabled", active_stream.get("audio_enabled", True)),
            "audio_codec": fav_entry.get("audio_codec") or active_stream.get("audio_codec", "opus"),
            "audio_dup": fav_entry.get("audio_dup", active_stream.get("audio_dup", False)),
            "no_vd_system_decorations": fav_entry.get("no_vd_system_decorations", False),
            "always_on_top": fav_entry.get("always_on_top", False),
            "borderless": fav_entry.get("borderless", False),
            "turn_screen_off": fav_entry.get("turn_screen_off", active_stream.get("turn_screen_off", False)),
            "stay_awake": fav_entry.get("stay_awake", active_stream.get("stay_awake", True)),
            "show_touches": fav_entry.get("show_touches", active_stream.get("show_touches", False)),
            "display_ime_policy": fav_entry.get("display_ime_policy") or self.config.get("display_ime_policy", "local"),
            "custom_args": fav_entry.get("custom_args", ""),
            "sync_clipboard": True,
            "force_stay_awake": True,
        }
        # Overlay settings provided by launcher (start_app, new_display, new_display_res, window_width, window_height)
        final_settings.update({k: v for k, v in settings.items() if v is not None and v != ""})

        fps_info = f" {final_settings.get('max_fps')}fps" if final_settings.get("max_fps") and final_settings.get("max_fps") != "0" else ""
        bit_info = f" {final_settings.get('bitrate')}" if final_settings.get("bitrate") else ""
        codec_info = f" {final_settings.get('video_codec', '').upper()}" if final_settings.get("video_codec") else ""
        self._append_log("AppLauncher", f"Launching '{package}' in virtual display window{fps_info}{bit_info}{codec_info}...")
        self.process_manager.start_session(serial, final_settings, title, session_id=session_id)

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
        if not self.config.get("auto_reconnect_pinned", True):
            return
        pinned = self.config.get_pinned_devices()
        to_connect = []
        for p in pinned:
            serial = p.get("serial", "")
            # Only connect to wireless endpoints
            if serial and (":" in serial or p.get("is_wireless", False)):
                if serial not in self.devices:
                    to_connect.append(serial)

        if not to_connect:
            return

        self._append_log("System", f"Auto-reconnecting {len(to_connect)} pinned wireless device(s)...")
        self._reconnect_worker = AutoReconnectWorker(self.adb, to_connect, self)
        self._reconnect_worker.finished_reconnect.connect(self._manual_refresh)
        self._reconnect_worker.finished.connect(self._reconnect_worker.deleteLater)
        self._reconnect_worker.start()

    def _create_device_card(
        self,
        dev: AdbDevice,
        alias: str,
        is_active: bool = False,
        is_running: bool = False,
        is_pinned: bool = False,
        is_offline: bool = False
    ) -> DeviceCard:
        card = DeviceCard(
            dev,
            alias=alias,
            is_active=is_active,
            is_running=is_running,
            is_pinned=is_pinned,
            is_offline=is_offline,
            parent=self
        )
        card.selected.connect(self._on_device_selected)
        card.launch_requested.connect(lambda s=dev.serial: self._launch_device(s))
        card.otg_requested.connect(lambda s=dev.serial: self._launch_device_otg(s))
        card.stop_requested.connect(lambda s=dev.serial: self._stop_device(s))
        card.disconnect_requested.connect(lambda s=dev.serial: self._on_disconnect_device(s))
        card.remove_requested.connect(lambda s=dev.serial: self._on_remove_device(s))
        card.connect_requested.connect(self._on_reconnect_pinned_device)
        card.pin_toggled.connect(self._on_pin_toggled)
        card.profile_requested.connect(self._open_device_profile_dialog)
        return card

    def _on_devices_updated(self, device_list: List[AdbDevice]):
        self.devices = {d.serial: d for d in device_list}
        pinned_list = self.config.get_pinned_devices()
        pinned_map = {p["serial"]: p for p in pinned_list}

        # Count total active
        self.lbl_dev_count.setText(f"({len(device_list)})")

        if not device_list and not pinned_list:
            for card in list(self.card_widgets.values()):
                self.device_list_layout.removeWidget(card)
                card.setParent(None)
                card.deleteLater()
            self.card_widgets.clear()
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

        rendered_serials = set()
        valid_serials = set(self.devices.keys()) | set(pinned_map.keys())

        # 1. Update existing or render new currently connected devices
        for dev in device_list:
            rendered_serials.add(dev.serial)
            is_active = (dev.serial == self.selected_serial)
            is_running = self.process_manager.is_running(dev.serial)
            is_pinned = self.config.is_pinned(dev.serial, hardware_serial=dev.hardware_serial)
            alias = self.config.get_device_alias(dev.serial, fallback=dev.display_name, hardware_serial=dev.hardware_serial)

            if is_pinned:
                cur_pinfo = pinned_map.get(dev.serial)
                if not cur_pinfo and dev.hardware_serial:
                    for p in pinned_list:
                        if p.get("hardware_serial") == dev.hardware_serial:
                            cur_pinfo = p
                            break
                if cur_pinfo and (cur_pinfo.get("connection_type") != dev.connection_type or not cur_pinfo.get("hardware_serial")):
                    cur_pinfo["connection_type"] = dev.connection_type
                    if dev.hardware_serial:
                        cur_pinfo["hardware_serial"] = dev.hardware_serial
                    self.config.pin_device(
                        dev.serial,
                        alias,
                        is_wireless=dev.is_wireless or (":" in dev.serial),
                        connection_type=dev.connection_type,
                        hardware_serial=dev.hardware_serial
                    )

            if dev.serial in self.card_widgets:
                self.card_widgets[dev.serial].update_device(
                    dev,
                    alias=alias,
                    is_active=is_active,
                    is_running=is_running,
                    is_pinned=is_pinned,
                    is_offline=False
                )
            else:
                card = self._create_device_card(
                    dev,
                    alias=alias,
                    is_active=is_active,
                    is_running=is_running,
                    is_pinned=is_pinned,
                    is_offline=False
                )
                self.device_list_layout.addWidget(card)
                self.card_widgets[dev.serial] = card

        # 2. Update existing or render pinned devices that are currently offline / disconnected
        for serial, pinfo in pinned_map.items():
            if serial not in rendered_serials:
                hw_s = pinfo.get("hardware_serial", "")
                alias = self.config.get_device_alias(serial, fallback=pinfo.get("name", serial), hardware_serial=hw_s)
                is_wireless = pinfo.get("is_wireless", (":" in serial))
                conn_type = pinfo.get("connection_type", "wifi" if is_wireless else "usb")
                offline_dev = AdbDevice(
                    serial=serial,
                    state="offline",
                    model=alias,
                    is_wireless=is_wireless,
                    connection_type=conn_type,
                    hardware_serial=hw_s
                )
                if serial in self.card_widgets:
                    self.card_widgets[serial].update_device(
                        offline_dev,
                        alias=alias,
                        is_active=False,
                        is_running=False,
                        is_pinned=True,
                        is_offline=True
                    )
                else:
                    card = self._create_device_card(
                        offline_dev,
                        alias=alias,
                        is_active=False,
                        is_running=False,
                        is_pinned=True,
                        is_offline=True
                    )
                    self.device_list_layout.addWidget(card)
                    self.card_widgets[serial] = card

        # 3. Clean up stale cards
        for serial in list(self.card_widgets.keys()):
            if serial not in valid_serials:
                card = self.card_widgets.pop(serial)
                self.device_list_layout.removeWidget(card)
                card.setParent(None)
                card.deleteLater()

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
            is_wireless = ":" in serial
            conn_type = "wifi" if is_wireless else "usb"
            if serial in self.devices:
                dev = self.devices[serial]
                is_wireless = dev.is_wireless or (":" in serial)
                conn_type = getattr(dev, "connection_type", "wifi" if is_wireless else "usb")
            self.config.pin_device(serial, dev_name, is_wireless, connection_type=conn_type)
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

    def _on_remove_device(self, serial: str):
        if not serial:
            return
        # Stop active mirroring session first if running
        if self.process_manager.is_running(serial):
            self.process_manager.stop_session(serial)

        # Unpin device from persistent config
        if self.config.is_pinned(serial):
            self.config.unpin_device(serial)
            self._append_log("System", f"Removed and unpinned device {serial}")

        # If it is a wireless endpoint, disconnect it
        if ":" in serial or (serial in self.devices and self.devices[serial].is_wireless):
            self.adb.disconnect_wireless(serial)

        self._manual_refresh()

    def _open_device_profile_dialog(self, serial: str):
        dev = self.devices.get(serial)
        dlg = DeviceProfileDialog(serial, self.config, device=dev, parent=self)
        dlg.profile_saved.connect(lambda s: self._manual_refresh())
        dlg.exec()

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

    def _check_app_updates_in_background(self):
        """Quiet background check for Scrcpy Studio releases on GitHub."""
        self._bg_app_checker = AppUpdateChecker(APP_VERSION, self)
        self._bg_app_checker.check_finished.connect(self._on_bg_app_update_checked)
        self._bg_app_checker.start()

    def _on_bg_app_update_checked(self, has_update: bool, release_info: dict, message: str):
        """If a newer Scrcpy Studio version is available on GitHub, reveal the app update button."""
        if has_update and release_info:
            tag = release_info.get("tag", "")
            self.btn_app_update.setText(f"🚀 Update Studio: {tag}")
            self.btn_app_update.setToolTip(f"A newer version of Scrcpy Studio ({tag}) is available on GitHub. Click to update.")
            self.btn_app_update.setVisible(True)
            if self.config.get("notifications_enabled", True) and hasattr(self, "tray_icon"):
                self.tray_icon.showMessage(
                    "Scrcpy Studio Update Available",
                    f"Scrcpy Studio {tag} is available on GitHub with new features and improvements!",
                    QSystemTrayIcon.Information,
                    5000,
                )
        else:
            self.btn_app_update.setVisible(False)

    def _open_app_updater_dialog(self):
        dlg = AppUpdaterDialog(self)
        dlg.exec()

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
        real_serial = serial.split("::")[0]
        if real_serial in self.card_widgets:
            self.card_widgets[real_serial].set_running(True)
        if serial in self.card_widgets:
            self.card_widgets[serial].set_running(True)

        # Spawn magnetic companion toolbar if enabled
        if self.config.get("enable_companion_toolbar", True):
            if serial not in self.companion_bars:
                try:
                    bar = CompanionToolBar(
                        session_key=serial,
                        process_manager=self.process_manager,
                        adb=self.adb,
                        config=self.config,
                        on_pull_app=self._on_pull_active_phone_app,
                        parent=None,
                    )
                    bar.action_triggered.connect(
                        lambda act, msg: self._append_log(f"Toolbar:{act}", msg)
                    )
                    self.companion_bars[serial] = bar
                    bar.show()
                except Exception as e:
                    self._append_log("Toolbar", f"Failed to initialize companion bar: {e}")

    def _on_session_stopped(self, serial: str, exit_code: int):
        real_serial = serial.split("::")[0]
        if real_serial in self.card_widgets:
            self.card_widgets[real_serial].set_running(False)
        if serial in self.card_widgets:
            self.card_widgets[serial].set_running(False)

        # Close and cleanup companion bar
        if serial in self.companion_bars:
            bar = self.companion_bars.pop(serial)
            try:
                bar.close()
                bar.deleteLater()
            except Exception:
                pass

    def _save_settings(self):
        current = self.stream_panel.get_settings()
        self.config.set("current_settings", current)

    def _manual_refresh(self):
        self._append_log("System", "Refreshing devices...")
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("🔄 Refreshing...")

        self._refresh_worker = AdbScanWorker(self.adb, self)
        self._refresh_worker.devices_ready.connect(self._on_manual_refresh_done)
        self._refresh_worker.finished.connect(self._refresh_worker.deleteLater)
        self._refresh_worker.start()

    def _on_manual_refresh_done(self, devs: List[AdbDevice]):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("🔄 Refresh")
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
        self.tray_menu.aboutToShow.connect(self._update_tray_menu)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self._update_tray_menu()
        self.tray_icon.show()

    def _update_tray_menu(self):
        """Rebuild the system tray context menu with live device & favorite apps."""
        if not hasattr(self, "tray_menu") or self.tray_menu is None:
            return

        self.tray_menu.clear()

        # Determine target device (selected or first online connected device)
        online_serials = [
            s for s, d in self.devices.items()
            if getattr(d, "status", "") == "device"
        ]
        target_serial = (
            self.selected_serial
            if (self.selected_serial and self.selected_serial in self.devices and getattr(self.devices[self.selected_serial], "status", "") == "device")
            else (online_serials[0] if online_serials else None)
        )

        # Title / Device Header & Actions
        if target_serial:
            dev = self.devices.get(target_serial)
            dev_name = self.config.get_device_alias(target_serial, dev.display_name if dev else target_serial)
            header_act = self.tray_menu.addAction(f"📱 Connected: {dev_name}")
            header_act.setEnabled(False)
            font = header_act.font()
            font.setBold(True)
            header_act.setFont(font)

            act_mirror = self.tray_menu.addAction("🚀 Mirror Phone Screen")
            act_mirror.triggered.connect(lambda _, s=target_serial: self._launch_device(s))

            act_pull = self.tray_menu.addAction("🔀 Move to PC (Active App)")
            act_pull.setToolTip("Detect active app open on phone screen and transfer to PC Virtual Display")
            act_pull.triggered.connect(lambda _, s=target_serial: self._on_pull_active_phone_app(s))

            # Multi-device switcher if multiple devices are online
            if len(online_serials) > 1:
                dev_menu = self.tray_menu.addMenu("🔄 Switch Active Device")
                for s in online_serials:
                    d = self.devices.get(s)
                    d_alias = self.config.get_device_alias(s, d.display_name if d else s)
                    prefix = "✓ " if s == target_serial else "   "
                    dev_act = dev_menu.addAction(f"{prefix}{d_alias}")
                    dev_act.triggered.connect(lambda _, sel=s: self._on_device_selected(sel))
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
                app_icon = self.icon_manager.get_icon(pkg, target_serial) if target_serial else None
                if app_icon:
                    act_fav = menu_favs.addAction(app_icon, name)
                else:
                    act_fav = menu_favs.addAction(f"{fav.get('icon', '📱')} {name}")
                act_fav.triggered.connect(
                    lambda _, p=pkg, n=name, r=res, s=target_serial: self._on_favorite_app_launch(s or "", p, n, r)
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
