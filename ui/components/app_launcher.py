from typing import List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import AdbAppListWorker, AdbManager
from core.config_manager import ConfigManager
from core.icon_manager import BulkIconScraperWorker, IconManager


class AddDisplayPresetDialog(QDialog):
    """Dialog to create or edit custom virtual display presets with resolution, DPI, and PC window sizing."""

    def __init__(self, title: str = "Add Virtual Display Preset", initial_name: str = "", initial_w: int = 1080, initial_h: int = 1920, initial_dpi: int = 0, initial_win_w: int = 0, initial_win_h: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(440, 360)
        self.setModal(True)
        self.preset_label = ""
        self.preset_value = ""
        self.preset_win_w = ""
        self.preset_win_h = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Preset Name
        layout.addWidget(QLabel("Preset Name / Label:"))
        self.edit_label = QLineEdit(initial_name)
        self.edit_label.setPlaceholderText("e.g. Financisto Compact, DeX Desktop, Galaxy Fold")
        layout.addWidget(self.edit_label)

        # 1. Android Virtual Display Section
        lbl_sec1 = QLabel("📱 Android Virtual Screen (Rendering Resolution & DPI):")
        lbl_sec1.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 11px; margin-top: 4px;")
        layout.addWidget(lbl_sec1)

        dim_layout = QHBoxLayout()
        dim_layout.setSpacing(8)

        v_w = QVBoxLayout()
        v_w.addWidget(QLabel("Render Width:"))
        self.spin_w = QSpinBox()
        self.spin_w.setRange(240, 7680)
        self.spin_w.setValue(initial_w)
        self.spin_w.setSingleStep(10)
        v_w.addWidget(self.spin_w)
        dim_layout.addLayout(v_w)

        v_h = QVBoxLayout()
        v_h.addWidget(QLabel("Render Height:"))
        self.spin_h = QSpinBox()
        self.spin_h.setRange(240, 7680)
        self.spin_h.setValue(initial_h)
        self.spin_h.setSingleStep(10)
        v_h.addWidget(self.spin_h)
        dim_layout.addLayout(v_h)

        v_dpi = QVBoxLayout()
        v_dpi.addWidget(QLabel("DPI Density:"))
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(0, 1000)
        self.spin_dpi.setValue(initial_dpi)
        self.spin_dpi.setSpecialValueText("Auto")
        v_dpi.addWidget(self.spin_dpi)
        dim_layout.addLayout(v_dpi)

        layout.addLayout(dim_layout)

        # 2. PC Desktop Window Sizing Section
        lbl_sec2 = QLabel("🪟 PC Window Size on Desktop (--window-width / --window-height):")
        lbl_sec2.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 11px; margin-top: 4px;")
        layout.addWidget(lbl_sec2)

        win_dim_layout = QHBoxLayout()
        win_dim_layout.setSpacing(8)

        v_win_w = QVBoxLayout()
        v_win_w.addWidget(QLabel("Window Width (px):"))
        self.spin_win_w = QSpinBox()
        self.spin_win_w.setRange(0, 7680)
        self.spin_win_w.setValue(initial_win_w)
        self.spin_win_w.setSpecialValueText("Auto")
        self.spin_win_w.setSingleStep(10)
        v_win_w.addWidget(self.spin_win_w)
        win_dim_layout.addLayout(v_win_w)

        v_win_h = QVBoxLayout()
        v_win_h.addWidget(QLabel("Window Height (px):"))
        self.spin_win_h = QSpinBox()
        self.spin_win_h.setRange(0, 7680)
        self.spin_win_h.setValue(initial_win_h)
        self.spin_win_h.setSpecialValueText("Auto")
        self.spin_win_h.setSingleStep(10)
        v_win_h.addWidget(self.spin_win_h)
        win_dim_layout.addLayout(v_win_h)

        layout.addLayout(win_dim_layout)

        layout.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Save Preset")
        btn_save.setObjectName("primaryBtn")
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def _on_save(self):
        name = self.edit_label.text().strip()
        w = self.spin_w.value()
        h = self.spin_h.value()
        dpi = self.spin_dpi.value()
        win_w = self.spin_win_w.value()
        win_h = self.spin_win_h.value()

        if not name:
            name = f"Custom {w}x{h}"

        val = f"{w}x{h}"
        if dpi > 0:
            val = f"{w}x{h}/{dpi}"

        label_parts = [name, f"({val}"]
        if win_w > 0 and win_h > 0:
            label_parts.append(f"→ {win_w}x{win_h} win)")
            self.preset_win_w = str(win_w)
            self.preset_win_h = str(win_h)
        else:
            label_parts[-1] += ")"
            self.preset_win_w = ""
            self.preset_win_h = ""

        full_label = f"📱 {' '.join(label_parts)}" if h >= w else f"💻 {' '.join(label_parts)}"
        self.preset_label = full_label
        self.preset_value = val
        self.accept()

# Common popular Android apps with friendly names & default package names
COMMON_APPS = [
    ("⚙️ Settings", "com.android.settings"),
    ("🌐 Chrome", "com.android.chrome"),
    ("📷 Camera", "com.sec.android.app.camera"),
    ("▶️ YouTube", "com.google.android.youtube"),
    ("📁 Files", "com.google.android.documentsui"),
    ("🛍️ Play Store", "com.android.vending"),
    ("🧮 Calculator", "com.google.android.calculator"),
    ("🖼️ Photos / Gallery", "com.google.android.apps.photos"),
    ("🗺️ Maps", "com.google.android.apps.maps"),
    ("💬 Messages", "com.google.android.apps.messaging"),
    ("📞 Phone", "com.google.android.dialer"),
]


class AppLauncherWidget(QWidget):
    """Interactive Android App Launcher & Package Manager."""

    app_launched = Signal(str, str)  # package_name, message
    action_completed = Signal(str, str)  # action_type, details
    app_display_launch_requested = Signal(str, dict, str, str)  # serial, settings, package_name, title
    favorite_toggled = Signal()

    def __init__(self, adb: AdbManager, config: Optional[ConfigManager] = None, parent=None):
        super().__init__(parent)
        self.adb = adb
        self.config = config
        self.selected_serial: Optional[str] = None
        self.packages: List[str] = []
        self.worker: Optional[AdbAppListWorker] = None
        self.icon_manager = IconManager.get_instance()
        self.icon_manager.icon_ready.connect(self._on_table_icon_ready)

        self._setup_ui()

    def _on_table_icon_ready(self, pkg: str, icon_path: str, source: str = "", detail: str = ""):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.text() == pkg:
                item.setIcon(QIcon(icon_path))
                if source:
                    src_label = f"Device APK ({detail})" if source == "adb" else f"Online HD ({detail})"
                    item.setToolTip(f"{pkg}\nIcon Source: {src_label}")
                break

    def set_device(self, serial: Optional[str]):
        """Update active target device without auto-populating until user clicks Refresh."""
        prev_serial = self.selected_serial
        self.selected_serial = serial
        if serial:
            self.lbl_target.setText(f"Target: {serial}")
            self.setEnabled(True)
            if serial != prev_serial:
                # Clear previous table entries until refresh is clicked
                self.table.setRowCount(0)
                self.packages = []
                self.lbl_count.setText("(Click '🔄 Refresh' to load apps)")
        else:
            self.lbl_target.setText("Target: (No Device Connected)")
            self.setEnabled(False)
            self.table.setRowCount(0)
            self.packages = []
            self.lbl_count.setText("(0 apps)")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 1. Quick Launch Chips Ribbon
        quick_box = QFrame()
        quick_box.setStyleSheet("background-color: #161820; border-radius: 6px; border: 1px solid #282C37; padding: 4px;")
        quick_layout = QVBoxLayout(quick_box)
        quick_layout.setContentsMargins(8, 6, 8, 6)
        quick_layout.setSpacing(6)

        lbl_quick_title = QLabel("⚡ QUICK LAUNCH")
        lbl_quick_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #94A3B8; letter-spacing: 0.5px; border: none;")
        quick_layout.addWidget(lbl_quick_title)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)
        for label, pkg in COMMON_APPS:
            btn_chip = QPushButton(label)
            btn_chip.setFixedHeight(26)
            btn_chip.setStyleSheet(
                "QPushButton { background: #21242D; color: #E2E8F0; border: 1px solid #333846; border-radius: 4px; font-size: 11px; padding: 2px 8px; }"
                "QPushButton:hover { background: #2B303C; border-color: #3B82F6; color: #60A5FA; }"
            )
            btn_chip.setCursor(Qt.PointingHandCursor)
            btn_chip.clicked.connect(lambda _, p=pkg, n=label: self._launch_package(p, n))
            chips_row.addWidget(btn_chip)
        chips_row.addStretch(1)
        quick_layout.addLayout(chips_row)

        main_layout.addWidget(quick_box)

        # 2. Display Mode & Window Options Bar
        mode_box = QFrame()
        mode_box.setStyleSheet("background-color: #161820; border-radius: 6px; border: 1px solid #282C37; padding: 4px;")
        mode_layout = QHBoxLayout(mode_box)
        mode_layout.setContentsMargins(8, 6, 8, 6)
        mode_layout.setSpacing(12)

        self.chk_new_display = QCheckBox("🪟 Open Apps in New Virtual Display Window (--new-display)")
        init_new_disp = self.config.get("app_launcher_new_display", True) if self.config else True
        self.chk_new_display.setChecked(init_new_disp)
        self.chk_new_display.setStyleSheet("font-weight: bold; color: #38BDF8;")
        self.chk_new_display.setToolTip(
            "Creates an independent virtual display and opens the app in a standalone PC window.\n"
            "The app will run seamlessly without interrupting or changing what is on the phone's physical screen!"
        )
        self.chk_new_display.toggled.connect(
            lambda checked: self.config.set("app_launcher_new_display", checked) if self.config else None
        )
        mode_layout.addWidget(self.chk_new_display)

        lbl_res = QLabel("Display Size:")
        lbl_res.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 500;")
        mode_layout.addWidget(lbl_res)

        self.combo_disp_res = QComboBox()
        self.combo_disp_res.view().setMinimumWidth(300)
        self._populate_disp_presets()
        self.combo_disp_res.currentIndexChanged.connect(self._on_disp_preset_changed)
        mode_layout.addWidget(self.combo_disp_res)

        # ＋ Add Custom Preset Button
        self.btn_add_disp_preset = QPushButton("＋ Add Preset")
        self.btn_add_disp_preset.setToolTip("Create custom virtual display resolution (Width x Height / DPI)")
        self.btn_add_disp_preset.setFixedHeight(24)
        self.btn_add_disp_preset.setStyleSheet(
            "QPushButton { background: #21242D; color: #38BDF8; border: 1px solid #333846; border-radius: 4px; font-size: 10px; padding: 2px 8px; }"
            "QPushButton:hover { background: #2B303C; border-color: #38BDF8; }"
        )
        self.btn_add_disp_preset.setCursor(Qt.PointingHandCursor)
        self.btn_add_disp_preset.clicked.connect(self._open_add_preset_dialog)
        mode_layout.addWidget(self.btn_add_disp_preset)

        # ✏️ Edit Preset Button
        self.btn_edit_disp_preset = QPushButton("✏️ Edit")
        self.btn_edit_disp_preset.setToolTip("Edit selected virtual display preset")
        self.btn_edit_disp_preset.setFixedHeight(24)
        self.btn_edit_disp_preset.setStyleSheet(
            "QPushButton { background: #21242D; color: #F59E0B; border: 1px solid #333846; border-radius: 4px; font-size: 10px; padding: 2px 8px; }"
            "QPushButton:hover { background: #2B303C; border-color: #F59E0B; }"
        )
        self.btn_edit_disp_preset.setCursor(Qt.PointingHandCursor)
        self.btn_edit_disp_preset.clicked.connect(self._open_edit_preset_dialog)
        mode_layout.addWidget(self.btn_edit_disp_preset)

        # 🗑 Delete Custom Preset Button
        self.btn_del_disp_preset = QPushButton("🗑")
        self.btn_del_disp_preset.setToolTip("Delete current custom preset")
        self.btn_del_disp_preset.setFixedHeight(24)
        self.btn_del_disp_preset.setFixedWidth(24)
        self.btn_del_disp_preset.setStyleSheet(
            "QPushButton { background: transparent; color: #64748B; border: 1px solid #333846; border-radius: 4px; font-size: 10px; padding: 0px; }"
            "QPushButton:hover { color: #EF4444; border-color: #EF4444; background: #EF444422; }"
        )
        self.btn_del_disp_preset.setCursor(Qt.PointingHandCursor)
        self.btn_del_disp_preset.clicked.connect(self._delete_disp_preset)
        mode_layout.addWidget(self.btn_del_disp_preset)

        mode_layout.addStretch(1)
        main_layout.addWidget(mode_box)

        # 3. Search, Filter & Controls Bar
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(8)

        # Search Input
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("🔍 Filter installed apps by package name...")
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.textChanged.connect(self._filter_table)
        ctrl_bar.addWidget(self.edit_search, 1)

        # Filter Checkbox
        self.chk_3rd_party = QCheckBox("3rd-Party Only")
        init_3rd = self.config.get("app_launcher_3rd_party_only", True) if self.config else True
        self.chk_3rd_party.setChecked(init_3rd)
        self.chk_3rd_party.setToolTip("Show only user-installed third-party apps (uncheck to view system apps)")
        self.chk_3rd_party.toggled.connect(self._on_filter_toggled)
        ctrl_bar.addWidget(self.chk_3rd_party)

        # Refresh Button
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setFixedHeight(28)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh_packages)
        ctrl_bar.addWidget(self.btn_refresh)

        # ⚡ Scrape Icons (ADB) Button
        self.btn_scrape_icons = QPushButton("⚡ Scrape Icons (ADB)")
        self.btn_scrape_icons.setToolTip("Extract all app launcher icons directly from device APKs via ADB")
        self.btn_scrape_icons.setFixedHeight(28)
        self.btn_scrape_icons.setStyleSheet(
            "QPushButton { background: #212530; color: #38BDF8; border: 1px solid #38BDF866; border-radius: 4px; font-weight: 600; font-size: 11px; padding: 2px 8px; }"
            "QPushButton:hover { background: #38BDF822; border-color: #38BDF8; }"
        )
        self.btn_scrape_icons.setCursor(Qt.PointingHandCursor)
        self.btn_scrape_icons.clicked.connect(self._start_bulk_icon_scraping)
        ctrl_bar.addWidget(self.btn_scrape_icons)

        # Target label & Count
        self.lbl_target = QLabel("Target: (No device)")
        self.lbl_target.setStyleSheet("color: #64748B; font-size: 11px; font-family: monospace;")
        ctrl_bar.addWidget(self.lbl_target)

        self.lbl_count = QLabel("(0 apps)")
        self.lbl_count.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold;")
        ctrl_bar.addWidget(self.lbl_count)

        main_layout.addLayout(ctrl_bar)

        # Loading Progress Bar
        self.progress = QProgressBar()
        self.progress.setFixedHeight(3)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        main_layout.addWidget(self.progress)

        # 3. Installed Packages Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Package Name", "Type", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 280)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setStyleSheet(
            "QTableWidget { background-color: #171920; border: 1px solid #282C37; border-radius: 6px; gridline-color: #21242D; font-size: 12px; }"
            "QTableWidget::item { padding: 4px; }"
            "QHeaderView::section { background-color: #1C1E26; color: #94A3B8; border: none; padding: 6px; font-weight: bold; }"
        )
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        main_layout.addWidget(self.table, 1)

    def _populate_disp_presets(self):
        self.combo_disp_res.blockSignals(True)
        self.combo_disp_res.clear()
        presets = self.config.get_virtual_display_presets() if self.config else []
        if not presets:
            presets = [
                {"label": "📱 Native Resolution (Auto)", "value": ""},
                {"label": "📱 1080x1920 (FHD Portrait Phone)", "value": "1080x1920"},
                {"label": "💻 1920x1080 (FHD Landscape / DeX)", "value": "1920x1080"},
                {"label": "📱 720x1280 (Compact Portrait)", "value": "720x1280"},
                {"label": "💻 1280x720 (Compact Landscape)", "value": "1280x720"},
                {"label": "📱 1440x2560 (2K Ultra Portrait)", "value": "1440x2560"},
                {"label": "💻 2560x1440 (2K Ultra Landscape)", "value": "2560x1440"},
            ]
        for p in presets:
            self.combo_disp_res.addItem(p["label"], p["value"])

        saved_res = self.config.get("app_launcher_disp_res", "") if self.config else ""
        idx = self.combo_disp_res.findData(saved_res)
        if idx >= 0:
            self.combo_disp_res.setCurrentIndex(idx)
        else:
            self.combo_disp_res.setCurrentIndex(0)
        self.combo_disp_res.blockSignals(False)

    def _on_disp_preset_changed(self):
        if self.config:
            val = self.combo_disp_res.currentData()
            self.config.set("app_launcher_disp_res", val)

    def _open_add_preset_dialog(self):
        dlg = AddDisplayPresetDialog(title="Add Virtual Display Preset", parent=self)
        if dlg.exec() == QDialog.Accepted:
            if self.config:
                self.config.add_virtual_display_preset(dlg.preset_label, dlg.preset_value, dlg.preset_win_w, dlg.preset_win_h)
                self.config.set("app_launcher_disp_res", dlg.preset_value)
            self._populate_disp_presets()
            idx = self.combo_disp_res.findData(dlg.preset_value)
            if idx >= 0:
                self.combo_disp_res.setCurrentIndex(idx)
            self.action_completed.emit("Preset Added", f"Added virtual display preset: {dlg.preset_label}")

    def _open_edit_preset_dialog(self):
        val = self.combo_disp_res.currentData()
        if val is None:
            return
        if not val:
            QMessageBox.information(self, "Cannot Edit", "The default Native Resolution (Auto) preset cannot be edited.")
            return

        label = self.combo_disp_res.currentText()
        clean_name = label
        if "(" in clean_name:
            clean_name = clean_name.split("(")[0].strip()
        for prefix in ("📱", "💻", "🌐"):
            clean_name = clean_name.replace(prefix, "").strip()

        w, h, dpi, win_w, win_h = 1080, 1920, 0, 0, 0
        try:
            if "/" in val:
                res_part, dpi_part = val.split("/")
                dpi = int(dpi_part)
            else:
                res_part = val
            if "x" in res_part:
                w_str, h_str = res_part.split("x")
                w, h = int(w_str), int(h_str)
        except Exception:
            pass

        # Check existing preset object for window dimensions
        if self.config:
            p_obj = self.config.get_preset_by_value(val)
            if p_obj:
                try:
                    win_w = int(p_obj.get("win_w", 0) or 0)
                    win_h = int(p_obj.get("win_h", 0) or 0)
                except Exception:
                    pass

        dlg = AddDisplayPresetDialog(
            title="Edit Virtual Display Preset",
            initial_name=clean_name,
            initial_w=w,
            initial_h=h,
            initial_dpi=dpi,
            initial_win_w=win_w,
            initial_win_h=win_h,
            parent=self
        )
        if dlg.exec() == QDialog.Accepted:
            if self.config:
                self.config.update_virtual_display_preset(val, dlg.preset_label, dlg.preset_value, dlg.preset_win_w, dlg.preset_win_h)
                self.config.set("app_launcher_disp_res", dlg.preset_value)
            self._populate_disp_presets()
            idx = self.combo_disp_res.findData(dlg.preset_value)
            if idx >= 0:
                self.combo_disp_res.setCurrentIndex(idx)
            self.action_completed.emit("Preset Updated", f"Updated virtual display preset: {dlg.preset_label}")

    def _delete_disp_preset(self):
        val = self.combo_disp_res.currentData()
        if not val:
            QMessageBox.information(self, "Cannot Delete", "The default Native Resolution preset cannot be deleted.")
            return
        label = self.combo_disp_res.currentText()
        ret = QMessageBox.question(
            self,
            "Delete Preset",
            f"Are you sure you want to delete preset '{label}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            if self.config:
                self.config.remove_virtual_display_preset(val)
                self.config.set("app_launcher_disp_res", "")
            self._populate_disp_presets()
            self.action_completed.emit("Preset Deleted", f"Deleted preset: {label}")

    def _on_filter_toggled(self, checked: bool):
        if self.config:
            self.config.set("app_launcher_3rd_party_only", checked)
        if self.packages:
            self.refresh_packages()

    def _start_bulk_icon_scraping(self):
        if not self.selected_serial or not self.packages:
            QMessageBox.information(self, "No Apps", "Please select a connected device and refresh the app list first.")
            return

        self.btn_scrape_icons.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, len(self.packages))
        self.progress.setValue(0)

        adb_bin = str(getattr(self.adb, "adb_path", getattr(self.adb, "adb_bin", "adb")))
        self.scraper_worker = BulkIconScraperWorker(
            adb_bin=adb_bin,
            serial=self.selected_serial,
            packages=self.packages,
            icon_manager=self.icon_manager,
            parent=self,
        )
        self.scraper_worker.progress_updated.connect(self._on_bulk_icon_progress)
        self.scraper_worker.icon_extracted.connect(self._on_bulk_icon_extracted)
        self.scraper_worker.finished_scraping.connect(self._on_bulk_icon_finished)
        self.scraper_worker.start()

    def _on_bulk_icon_progress(self, current: int, total: int, pkg: str):
        self.progress.setValue(current)
        self.lbl_count.setText(f"({current}/{total} scraped)")

    def _on_bulk_icon_extracted(self, pkg: str, path: str, source: str, detail: str):
        self._on_table_icon_ready(pkg, path, source, detail)

    def _on_bulk_icon_finished(self, success_count: int, total: int):
        self.btn_scrape_icons.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self.progress.setVisible(False)
        self.lbl_count.setText(f"({total} apps)")
        self.action_completed.emit(
            "Icon Scraping Complete",
            f"Successfully scraped {success_count}/{total} app icons directly via ADB.",
        )

    def refresh_packages(self):
        """Fetch package list asynchronously from device."""
        if not self.selected_serial:
            return

        self.btn_refresh.setEnabled(False)
        self.progress.setVisible(True)
        self.table.setRowCount(0)

        third_party = self.chk_3rd_party.isChecked()
        self.worker = AdbAppListWorker(self.adb, self.selected_serial, third_party, self)
        self.worker.packages_loaded.connect(self._on_packages_loaded)
        self.worker.error_occurred.connect(self._on_load_error)
        self.worker.start()

    def _on_packages_loaded(self, serial: str, packages: List[str]):
        if serial != self.selected_serial:
            return

        self.btn_refresh.setEnabled(True)
        self.progress.setVisible(False)
        self.packages = packages
        self._populate_table(packages)

    def _on_load_error(self, serial: str, err: str):
        self.btn_refresh.setEnabled(True)
        self.progress.setVisible(False)
        self.action_completed.emit("Error", f"Failed to load packages: {err}")

    def _populate_table(self, packages: List[str]):
        self.table.setRowCount(0)
        is_3rd = self.chk_3rd_party.isChecked()

        for pkg in packages:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Package Name
            item_pkg = QTableWidgetItem(pkg)
            item_pkg.setForeground(Qt.white)
            icon = self.icon_manager.get_icon(pkg, self.selected_serial)
            if icon:
                item_pkg.setIcon(icon)
            self.table.setItem(row, 0, item_pkg)

            # Type
            type_str = "📦 3rd-Party" if is_3rd else "🌐 System/Other"
            item_type = QTableWidgetItem(type_str)
            item_type.setForeground(Qt.lightGray)
            self.table.setItem(row, 1, item_type)

            # Actions Box
            act_widget = QWidget()
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(2, 2, 2, 2)
            act_layout.setSpacing(4)

            # Launch Button
            btn_launch = QPushButton("🚀 Launch")
            btn_launch.setFixedHeight(24)
            btn_launch.setObjectName("primaryBtn")
            btn_launch.setStyleSheet("font-size: 11px; padding: 2px 6px;")
            btn_launch.clicked.connect(lambda _, p=pkg: self._launch_package(p))
            act_layout.addWidget(btn_launch)

            # Stop Button
            btn_stop = QPushButton("⏹ Stop")
            btn_stop.setFixedHeight(24)
            btn_stop.setStyleSheet(
                "QPushButton { background: #262933; color: #F59E0B; border: 1px solid #373C4B; border-radius: 4px; font-size: 11px; padding: 2px 6px; }"
                "QPushButton:hover { background: #F59E0B22; border-color: #F59E0B; }"
            )
            btn_stop.clicked.connect(lambda _, p=pkg: self._stop_package(p))
            act_layout.addWidget(btn_stop)

            # App Info Button
            btn_info = QPushButton("ℹ️ Info")
            btn_info.setFixedHeight(24)
            btn_info.setStyleSheet(
                "QPushButton { background: #262933; color: #94A3B8; border: 1px solid #373C4B; border-radius: 4px; font-size: 11px; padding: 2px 6px; }"
                "QPushButton:hover { color: #38BDF8; border-color: #38BDF8; }"
            )
            btn_info.clicked.connect(lambda _, p=pkg: self._open_info(p))
            act_layout.addWidget(btn_info)

            # Favorite Star Button
            is_fav = bool(self.config and self.config.is_favorite_app(pkg))
            btn_fav = QPushButton("⭐" if is_fav else "☆")
            btn_fav.setToolTip("Remove from Favorites" if is_fav else "Add to Favorite Apps sidebar")
            btn_fav.setFixedHeight(24)
            btn_fav.setFixedWidth(24)
            fav_style = "color: #F59E0B; background: #F59E0B22; border-color: #F59E0B66;" if is_fav else "color: #64748B; background: transparent; border-color: #373C4B;"
            btn_fav.setStyleSheet(f"QPushButton {{ {fav_style} border: 1px solid; border-radius: 4px; font-size: 11px; padding: 0px; }} QPushButton:hover {{ color: #F59E0B; border-color: #F59E0B; }}")
            btn_fav.clicked.connect(lambda _, p=pkg: self._toggle_favorite(p))
            act_layout.addWidget(btn_fav)

            # Uninstall Button
            btn_uninst = QPushButton("🗑")
            btn_uninst.setToolTip("Uninstall application")
            btn_uninst.setFixedHeight(24)
            btn_uninst.setFixedWidth(24)
            btn_uninst.setStyleSheet(
                "QPushButton { background: transparent; color: #64748B; border: 1px solid #373C4B; border-radius: 4px; font-size: 11px; padding: 0px; }"
                "QPushButton:hover { background: #EF444422; color: #EF4444; border-color: #EF4444; }"
            )
            btn_uninst.clicked.connect(lambda _, p=pkg: self._uninstall_package(p))
            act_layout.addWidget(btn_uninst)

            self.table.setCellWidget(row, 2, act_widget)

        self.lbl_count.setText(f"({len(packages)} apps)")

    def _toggle_favorite(self, package: str):
        if not self.config:
            return
        if self.config.is_favorite_app(package):
            self.config.remove_favorite_app(package)
            self.action_completed.emit("Favorite Removed", f"Removed {package} from favorites")
        else:
            clean_name = package.split(".")[-1].capitalize()
            self.config.add_favorite_app(package, clean_name)
            self.action_completed.emit("Favorite Added", f"Added {clean_name} ({package}) to favorites")
        self.favorite_toggled.emit()
        self._filter_table(self.edit_search.text())

    def _filter_table(self, query: str):
        query = query.strip().lower()
        if not query:
            filtered = self.packages
        else:
            filtered = [p for p in self.packages if query in p.lower()]
        self._populate_table(filtered)

    def _launch_package(self, package_name: str, friendly_name: str = ""):
        if not self.selected_serial:
            return
        display = friendly_name or package_name

        if self.chk_new_display.isChecked():
            res = self.combo_disp_res.currentData() or ""
            title = f"[{display}] {self.selected_serial}"
            settings = {
                "start_app": package_name,
                "new_display": True,
                "new_display_res": res,
                "stay_awake": True,
                "force_stay_awake": True,
                "sync_clipboard": True,
            }
            if self.config and res:
                preset = self.config.get_preset_by_value(res)
                if preset:
                    if preset.get("win_w"):
                        settings["window_width"] = preset["win_w"]
                    if preset.get("win_h"):
                        settings["window_height"] = preset["win_h"]

            self.app_display_launch_requested.emit(self.selected_serial, settings, package_name, title)
            res_label = res if res else "Native"
            self.app_launched.emit(package_name, f"Launched {display} in new virtual display window ({res_label})")
        else:
            self.adb.wake_up(self.selected_serial)
            ok, msg = self.adb.launch_app(self.selected_serial, package_name)
            if ok:
                self.app_launched.emit(package_name, f"Launched {display} on device screen")
            else:
                self.action_completed.emit("Launch Failed", f"Could not launch {display}: {msg}")

    def _stop_package(self, package_name: str):
        if not self.selected_serial:
            return
        ok = self.adb.force_stop_app(self.selected_serial, package_name)
        if ok:
            self.action_completed.emit("Force Stop", f"Force stopped {package_name}")

    def _open_info(self, package_name: str):
        if not self.selected_serial:
            return
        self.adb.open_app_info(self.selected_serial, package_name)
        self.action_completed.emit("App Info", f"Opened app settings for {package_name}")

    def _uninstall_package(self, package_name: str):
        if not self.selected_serial:
            return
        ret = QMessageBox.question(
            self,
            "Confirm Uninstall",
            f"Are you sure you want to uninstall '{package_name}' from {self.selected_serial}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            ok, msg = self.adb.uninstall_package(self.selected_serial, package_name)
            if ok:
                self.action_completed.emit("Uninstalled", f"Successfully uninstalled {package_name}")
                self.refresh_packages()
            else:
                QMessageBox.warning(self, "Uninstall Failed", f"Failed to uninstall: {msg}")

    def _show_table_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        pkg_item = self.table.item(row, 0)
        if not pkg_item:
            return
        pkg = pkg_item.text()
        clean_name = pkg.split(".")[-1].capitalize()

        menu = QMenu(self)
        act_launch_vd = menu.addAction(f"🚀 Launch '{clean_name}' (Virtual Display Window)")
        act_launch_main = menu.addAction(f"📱 Launch '{clean_name}' on Device")
        menu.addSeparator()

        act_shortcut = menu.addAction("📌 Create Desktop Shortcut (.lnk)")
        is_fav = self.config.is_favorite_app(pkg) if self.config else False
        act_fav = menu.addAction("⭐ Remove from Favorites" if is_fav else "⭐ Add to Favorites")
        act_web_icon = menu.addAction("🌐 Fetch Official Icon from Web Store (Google Play)")
        menu.addSeparator()

        act_stop = menu.addAction("⏹ Force Stop")
        act_info = menu.addAction("ℹ️ App Info")
        act_uninst = menu.addAction("🗑 Uninstall Application")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act_launch_vd:
            self._launch_package(pkg, clean_name)
        elif action == act_launch_main:
            self.adb.wake_up(self.selected_serial)
            self.adb.launch_app(self.selected_serial, pkg)
        elif action == act_shortcut:
            scrcpy_exe = str(self.config.get_scrcpy_bin_dir() / "scrcpy.exe")
            icon_path = self.icon_manager.get_icon_path(pkg) or ""
            res = self.combo_disp_res.currentData() or ""
            preset = self.config.get_preset_by_value(res) if self.config else None
            win_w = str(preset.get("win_w", "")) if preset else ""
            win_h = str(preset.get("win_h", "")) if preset else ""
            from core.shortcut_manager import create_app_desktop_shortcut

            ok, msg = create_app_desktop_shortcut(
                scrcpy_exe=scrcpy_exe,
                serial=self.selected_serial or "",
                package=pkg,
                app_name=clean_name,
                display_res=res,
                win_w=win_w,
                win_h=win_h,
                icon_png=icon_path,
            )
            if ok:
                QMessageBox.information(self, "Shortcut Created", f"Successfully created desktop shortcut:\n\n{msg}")
            else:
                QMessageBox.warning(self, "Shortcut Error", f"Failed to create shortcut:\n{msg}")
        elif action == act_fav:
            self._toggle_favorite(pkg)
        elif action == act_web_icon:
            self.icon_manager.force_web_icon(pkg)
        elif action == act_stop:
            self._stop_package(pkg)
        elif action == act_info:
            self._open_info(pkg)
        elif action == act_uninst:
            self._uninstall_package(pkg)
