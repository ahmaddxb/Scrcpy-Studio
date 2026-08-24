from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.system_manager import SystemManager
from core.app_updater import APP_VERSION


class SettingsPanel(QWidget):
    """Configuration panel for application settings, Windows startup, tray behavior, and cache."""

    settings_changed = Signal()
    runtime_update_requested = Signal()
    app_update_requested = Signal()
    refresh_rate_changed = Signal(int)  # ms

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self._block_signals = False
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Scroll Area for clean scrolling on smaller screens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(16)

        # --- SECTION 1: WINDOWS & STARTUP INTEGRATION ---
        grp_windows = QGroupBox("🪟 Windows & System Tray Integration")
        w_layout = QVBoxLayout(grp_windows)
        w_layout.setContentsMargins(14, 16, 14, 16)
        w_layout.setSpacing(12)

        self.chk_start_on_boot = QCheckBox("🚀 Launch Scrcpy Studio automatically on Windows Startup")
        self.chk_start_on_boot.setStyleSheet("font-size: 13px; font-weight: 500; color: #F1F5F9;")
        self.chk_start_on_boot.toggled.connect(self._on_start_on_boot_toggled)
        w_layout.addWidget(self.chk_start_on_boot)

        # Sub-option: Start Minimized
        self.chk_start_minimized = QCheckBox("📥 Start minimized to System Tray (silent background startup)")
        self.chk_start_minimized.setStyleSheet("font-size: 12px; color: #94A3B8; margin-left: 24px;")
        self.chk_start_minimized.toggled.connect(self._on_setting_changed)
        w_layout.addWidget(self.chk_start_minimized)

        # Close to Tray
        self.chk_close_to_tray = QCheckBox("❎ Close button [X] minimizes to System Tray (keeps mirroring running)")
        self.chk_close_to_tray.setStyleSheet("font-size: 13px; font-weight: 500; color: #F1F5F9;")
        self.chk_close_to_tray.toggled.connect(self._on_setting_changed)
        w_layout.addWidget(self.chk_close_to_tray)

        # Magnetic Companion Toolbar
        self.chk_companion_toolbar = QCheckBox("🧰 Enable Magnetic Companion Toolbar by default (QtScrcpy style)")
        self.chk_companion_toolbar.setStyleSheet("font-size: 13px; font-weight: 500; color: #F1F5F9;")
        self.chk_companion_toolbar.setToolTip("Attach a floating quick-actions toolbar directly to the right edge of any active Scrcpy mirror or app window.")
        self.chk_companion_toolbar.toggled.connect(self._on_setting_changed)
        w_layout.addWidget(self.chk_companion_toolbar)

        # Notifications
        self.chk_notifications = QCheckBox("🔔 Display Windows notifications on device connect / disconnect")
        self.chk_notifications.setStyleSheet("font-size: 13px; font-weight: 500; color: #F1F5F9;")
        self.chk_notifications.toggled.connect(self._on_setting_changed)
        w_layout.addWidget(self.chk_notifications)

        layout.addWidget(grp_windows)

        # --- SECTION 2: DEVICE DISCOVERY & AUTOMATION ---
        grp_devices = QGroupBox("📱 Device Discovery & Automation")
        d_layout = QVBoxLayout(grp_devices)
        d_layout.setContentsMargins(14, 16, 14, 16)
        d_layout.setSpacing(12)

        self.chk_auto_reconnect = QCheckBox("⚡ Automatically reconnect to pinned wireless devices on startup (even if disconnected on exit)")
        self.chk_auto_reconnect.setStyleSheet("font-size: 13px; font-weight: 500; color: #F1F5F9;")
        self.chk_auto_reconnect.toggled.connect(self._on_setting_changed)
        d_layout.addWidget(self.chk_auto_reconnect)

        self.chk_screen_awake_safety = QCheckBox("⏱️ Smart Screen Awake Safety (prevents phone sleep during sessions & restores timeout on exit)")
        self.chk_screen_awake_safety.setStyleSheet("font-size: 13px; font-weight: 500; color: #F1F5F9;")
        self.chk_screen_awake_safety.toggled.connect(self._on_setting_changed)
        d_layout.addWidget(self.chk_screen_awake_safety)

        # Scan Interval Row
        scan_row = QHBoxLayout()
        scan_row.setSpacing(10)
        lbl_scan = QLabel("Background Device Scan Interval:")
        lbl_scan.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        scan_row.addWidget(lbl_scan)

        self.combo_scan_interval = QComboBox()
        self.combo_scan_interval.setFixedWidth(200)
        self.combo_scan_interval.addItem("⚡ Fast (1 second)", 1000)
        self.combo_scan_interval.addItem("⚖️ Balanced (2 seconds)", 2000)
        self.combo_scan_interval.addItem("🔋 Power Saver (5 seconds)", 5000)
        self.combo_scan_interval.currentIndexChanged.connect(self._on_scan_interval_changed)
        scan_row.addWidget(self.combo_scan_interval)
        scan_row.addStretch(1)
        d_layout.addLayout(scan_row)

        layout.addWidget(grp_devices)

        # --- SECTION 3: SCRCPY RUNTIME & STORAGE ---
        grp_runtime = QGroupBox("📦 Scrcpy Engine & Storage Management")
        r_layout = QVBoxLayout(grp_runtime)
        r_layout.setContentsMargins(14, 16, 14, 16)
        r_layout.setSpacing(12)

        # Runtime Status Row
        runtime_row = QHBoxLayout()
        runtime_row.setSpacing(10)
        lbl_rt_title = QLabel("Scrcpy Runtime Engine:")
        lbl_rt_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        runtime_row.addWidget(lbl_rt_title)

        self.lbl_runtime_badge = QLabel("v4.1")
        self.lbl_runtime_badge.setStyleSheet(
            "background-color: #1E293B; color: #38BDF8; font-weight: bold; padding: 3px 10px; border-radius: 4px; border: 1px solid #38BDF844;"
        )
        runtime_row.addWidget(self.lbl_runtime_badge)

        self.btn_update_scrcpy = QPushButton("🔄 Check / Repair Scrcpy")
        self.btn_update_scrcpy.setCursor(Qt.PointingHandCursor)
        self.btn_update_scrcpy.clicked.connect(self.runtime_update_requested.emit)
        runtime_row.addWidget(self.btn_update_scrcpy)
        runtime_row.addStretch(1)
        r_layout.addLayout(runtime_row)

        # Recording Output Folder Row
        rec_row = QHBoxLayout()
        rec_row.setSpacing(8)
        lbl_rec = QLabel("Default Media Recordings Folder:")
        lbl_rec.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        r_layout.addWidget(lbl_rec)

        rec_input_row = QHBoxLayout()
        self.edit_record_dir = QLineEdit()
        self.edit_record_dir.setPlaceholderText("Default: Scrcpy-UI/recordings (or device DCIM)")
        self.edit_record_dir.textChanged.connect(self._on_setting_changed)
        rec_input_row.addWidget(self.edit_record_dir, 1)

        self.btn_browse_rec = QPushButton("📂 Browse...")
        self.btn_browse_rec.setCursor(Qt.PointingHandCursor)
        self.btn_browse_rec.clicked.connect(self._browse_record_dir)
        rec_input_row.addWidget(self.btn_browse_rec)
        r_layout.addLayout(rec_input_row)

        # Icon Cache Maintenance Row
        cache_row = QHBoxLayout()
        cache_row.setSpacing(10)
        self.lbl_cache_info = QLabel("App Icon Cache: Calculating...")
        self.lbl_cache_info.setStyleSheet("color: #94A3B8; font-size: 12px;")
        cache_row.addWidget(self.lbl_cache_info, 1)

        self.btn_clear_cache = QPushButton("🧹 Clear Icon Cache")
        self.btn_clear_cache.setCursor(Qt.PointingHandCursor)
        self.btn_clear_cache.clicked.connect(self._clear_cache)
        cache_row.addWidget(self.btn_clear_cache)
        r_layout.addLayout(cache_row)

        layout.addWidget(grp_runtime)

        # --- SECTION 4: ABOUT SCRCPY STUDIO ---
        grp_about = QGroupBox("ℹ️ About Scrcpy Studio")
        a_layout = QVBoxLayout(grp_about)
        a_layout.setContentsMargins(14, 16, 14, 16)
        a_layout.setSpacing(8)

        lbl_about_app = QLabel("⚡ Scrcpy Studio — High-Performance Android Desktop GUI")
        lbl_about_app.setStyleSheet("font-size: 13px; font-weight: bold; color: #38BDF8;")
        a_layout.addWidget(lbl_about_app)

        lbl_desc = QLabel(
            "Designed for power users, developers, and multi-app multitasking. "
            "Features independent virtual displays, HD dual-engine icon extraction, "
            "per-device profile persistence, and lossless streaming via official Scrcpy v4.1."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #94A3B8; font-size: 12px; line-height: 1.4;")
        a_layout.addWidget(lbl_desc)

        # App Version & Update Row
        row_app_ver = QHBoxLayout()
        row_app_ver.setSpacing(10)
        lbl_app_v_title = QLabel("Scrcpy Studio Version:")
        lbl_app_v_title.setStyleSheet("color: #F1F5F9; font-size: 12px; font-weight: 500;")
        row_app_ver.addWidget(lbl_app_v_title)

        self.lbl_app_ver_badge = QLabel(APP_VERSION)
        self.lbl_app_ver_badge.setStyleSheet(
            "background-color: #1E293B; color: #38BDF8; font-weight: bold; padding: 2px 8px; border-radius: 4px; border: 1px solid #38BDF844; font-family: monospace;"
        )
        row_app_ver.addWidget(self.lbl_app_ver_badge)

        row_app_ver.addStretch(1)

        self.btn_check_app_updates = QPushButton("🔄 Check for App Updates")
        self.btn_check_app_updates.setCursor(Qt.PointingHandCursor)
        self.btn_check_app_updates.clicked.connect(self.app_update_requested.emit)
        row_app_ver.addWidget(self.btn_check_app_updates)

        a_layout.addLayout(row_app_ver)

        layout.addWidget(grp_about)

        layout.addStretch(1)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def load_settings(self):
        """Load values from config.json and Windows system state into UI."""
        self._block_signals = True
        try:
            # 1. Startup & System Tray
            is_boot = SystemManager.is_start_on_boot_enabled()
            self.chk_start_on_boot.setChecked(is_boot)
            self.chk_start_minimized.setEnabled(is_boot)
            self.chk_start_minimized.setChecked(self.config.get("start_minimized", False))
            self.chk_close_to_tray.setChecked(self.config.get("close_to_tray", True))
            self.chk_companion_toolbar.setChecked(self.config.get("enable_companion_toolbar", True))
            self.chk_notifications.setChecked(self.config.get("notifications_enabled", True))

            # 2. Devices & Automation
            self.chk_auto_reconnect.setChecked(self.config.get("auto_reconnect_pinned", True))
            self.chk_screen_awake_safety.setChecked(self.config.get("smart_screen_awake", True))

            # Scan interval
            interval = self.config.get("auto_refresh_interval_ms", 2000)
            idx = self.combo_scan_interval.findData(interval)
            if idx >= 0:
                self.combo_scan_interval.setCurrentIndex(idx)

            # 3. Runtime & Directories
            if self.config.is_scrcpy_installed():
                self.lbl_runtime_badge.setText(self.config.get_scrcpy_version())
                self.lbl_runtime_badge.setStyleSheet(
                    "background-color: #1E293B; color: #38BDF8; font-weight: bold; padding: 3px 10px; border-radius: 4px; border: 1px solid #38BDF844;"
                )
            else:
                self.lbl_runtime_badge.setText("Not Downloaded")
                self.lbl_runtime_badge.setStyleSheet(
                    "background-color: #7F1D1D; color: #FCA5A5; font-weight: bold; padding: 3px 10px; border-radius: 4px;"
                )

            self.edit_record_dir.setText(self.config.get("default_record_dir", ""))
            self.update_cache_stats()
        finally:
            self._block_signals = False

    def update_cache_stats(self):
        stats = SystemManager.get_icon_cache_stats()
        self.lbl_cache_info.setText(f"App Icon Cache: {stats['count']} cached icons ({stats['size_mb']} MB)")

    def _on_start_on_boot_toggled(self, checked: bool):
        self.chk_start_minimized.setEnabled(checked)
        if not self._block_signals:
            minimized = self.chk_start_minimized.isChecked()
            SystemManager.set_start_on_boot(checked, start_minimized=minimized)
            self.config.set("start_on_boot", checked)
            self.settings_changed.emit()

    def _on_scan_interval_changed(self, index: int):
        if self._block_signals:
            return
        interval = self.combo_scan_interval.currentData()
        self.config.set("auto_refresh_interval_ms", interval)
        self.refresh_rate_changed.emit(interval)
        self.settings_changed.emit()

    def _on_setting_changed(self):
        if self._block_signals:
            return
        self.config.set("start_minimized", self.chk_start_minimized.isChecked())
        self.config.set("close_to_tray", self.chk_close_to_tray.isChecked())
        self.config.set("enable_companion_toolbar", self.chk_companion_toolbar.isChecked())
        self.config.set("notifications_enabled", self.chk_notifications.isChecked())
        self.config.set("auto_reconnect_pinned", self.chk_auto_reconnect.isChecked())
        self.config.set("smart_screen_awake", self.chk_screen_awake_safety.isChecked())
        self.config.set("default_record_dir", self.edit_record_dir.text().strip())

        # If start on boot is checked and minimized setting changed, update registry
        if self.chk_start_on_boot.isChecked():
            SystemManager.set_start_on_boot(True, start_minimized=self.chk_start_minimized.isChecked())

        self.settings_changed.emit()

    def _browse_record_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Media & Recordings Directory")
        if folder:
            self.edit_record_dir.setText(folder)
            self._on_setting_changed()

    def _clear_cache(self):
        res = QMessageBox.question(
            self,
            "Clear Icon Cache",
            "This will delete all locally cached app icons.\nIcons will be re-fetched on demand via ADB and Play Store metadata.\n\nProceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res == QMessageBox.Yes:
            count = SystemManager.clear_icon_cache()
            self.update_cache_stats()
            QMessageBox.information(self, "Cache Cleared", f"Successfully cleared {count} cached app icon files.")
