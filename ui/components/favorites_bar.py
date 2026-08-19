from typing import Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import AdbManager
from core.config_manager import ConfigManager
from core.icon_manager import IconManager

ICON_CHOICES = [
    ("📱", "Phone / Default"),
    ("🏦", "Banking"),
    ("💳", "Finance / Card"),
    ("🌐", "Browser / Web"),
    ("▶️", "Video / Stream"),
    ("🎵", "Music / Audio"),
    ("💬", "Chat / Messaging"),
    ("📷", "Camera / Photos"),
    ("🛍️", "Shopping / Store"),
    ("📁", "Files / Docs"),
    ("⚙️", "Settings / System"),
    ("🎮", "Games"),
    ("📊", "Tools / Productivity"),
    ("⭐", "Star / Bookmark"),
]


class FavoriteAppEditDialog(QDialog):
    """Dialog to add or edit a favorite app with custom name, icon, and display size preset."""

    def __init__(self, config: ConfigManager, package: str = "", name: str = "", icon: str = "📱", display_res: str = "", is_edit: bool = False, parent=None):
        super().__init__(parent)
        self.config = config
        self.package_name = package
        self.display_name = name
        self.icon = icon
        self.display_res = display_res

        self.setWindowTitle("Edit Favorite App" if is_edit else "Add Favorite App")
        self.setFixedSize(480, 310)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # App Display Name
        layout.addWidget(QLabel("App Display Name / Label:"))
        self.edit_name = QLineEdit(name)
        self.edit_name.setPlaceholderText("e.g. Mashreq Banking, YouTube, Chrome")
        layout.addWidget(self.edit_name)

        # Package Name
        layout.addWidget(QLabel("Package Name:"))
        self.edit_pkg = QLineEdit(package)
        self.edit_pkg.setPlaceholderText("e.g. com.mashreq.mobile")
        if is_edit:
            self.edit_pkg.setReadOnly(True)
            self.edit_pkg.setStyleSheet("background-color: #171920; color: #64748B;")
        layout.addWidget(self.edit_pkg)

        # Icon Row
        row_icon = QHBoxLayout()
        row_icon.setSpacing(10)
        lbl_icon = QLabel("Fallback Icon:")
        lbl_icon.setFixedWidth(130)
        row_icon.addWidget(lbl_icon)
        self.combo_icon = QComboBox()
        self.combo_icon.view().setMinimumWidth(240)
        for ico, lbl in ICON_CHOICES:
            self.combo_icon.addItem(f"{ico} {lbl}", ico)
        idx = self.combo_icon.findData(icon)
        if idx >= 0:
            self.combo_icon.setCurrentIndex(idx)
        row_icon.addWidget(self.combo_icon, 1)

        btn_fetch_web = QPushButton("🌐 Web Store Icon")
        btn_fetch_web.setToolTip("Fetch crisp official icon from Google Play Store")
        btn_fetch_web.setStyleSheet("font-size: 11px; padding: 2px 8px; color: #38BDF8;")
        btn_fetch_web.clicked.connect(self._fetch_web_icon)
        row_icon.addWidget(btn_fetch_web)

        layout.addLayout(row_icon)

        # Display Preset Row
        row_preset = QHBoxLayout()
        row_preset.setSpacing(10)
        lbl_preset = QLabel("Display Size Preset:")
        lbl_preset.setFixedWidth(130)
        row_preset.addWidget(lbl_preset)
        self.combo_preset = QComboBox()
        self.combo_preset.view().setMinimumWidth(320)
        self.combo_preset.addItem("🌐 Use App Launcher Global Size", "")
        presets = self.config.get_virtual_display_presets()
        for p in presets:
            self.combo_preset.addItem(p["label"], p["value"])
        if display_res:
            p_idx = self.combo_preset.findData(display_res)
            if p_idx >= 0:
                self.combo_preset.setCurrentIndex(p_idx)
        row_preset.addWidget(self.combo_preset, 1)
        layout.addLayout(row_preset)

        layout.addStretch(1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Save" if is_edit else "Add Favorite")
        btn_save.setObjectName("primaryBtn")
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def _fetch_web_icon(self):
        pkg = self.edit_pkg.text().strip()
        if not pkg:
            QMessageBox.warning(self, "Missing Package", "Please enter a package name first.")
            return
        IconManager.get_instance().force_web_icon(pkg)
        QMessageBox.information(self, "Fetching Icon", f"Fetching official high-res icon for {pkg} from Google Play Store...")

    def _on_save(self):
        pkg = self.edit_pkg.text().strip()
        name = self.edit_name.text().strip()
        if not pkg:
            QMessageBox.warning(self, "Missing Package", "Please enter a valid package name.")
            return
        self.package_name = pkg
        self.display_name = name or pkg.split(".")[-1].capitalize()
        self.icon = self.combo_icon.currentData() or "📱"
        self.display_res = self.combo_preset.currentData() or ""
        self.accept()


class FavoriteAppsBar(QFrame):
    """Spacious quick-launch dock for user favorite apps with individual display presets & custom labels."""

    launch_app_requested = Signal(str, str, str, str)  # serial, package_name, display_name, display_res
    move_app_requested = Signal(str, str, str, str)  # serial, package_name, display_name, display_res
    open_apps_manager_requested = Signal()

    def __init__(self, config: ConfigManager, adb: AdbManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.adb = adb
        self.selected_serial: Optional[str] = None
        self.icon_manager = IconManager.get_instance()
        self.icon_manager.icon_ready.connect(self._on_icon_ready)
        self.chip_buttons: Dict[str, QPushButton] = {}

        self.setObjectName("favoriteAppsCard")
        self.setStyleSheet(
            "QFrame#favoriteAppsCard { background-color: #171922; border: 1px solid #2B303E; border-radius: 8px; }"
        )

        # Load pinned state
        pinned_map = self.config.get("pinned_sidebar_sections", {})
        self.is_pinned_expanded = pinned_map.get("favorites", True)

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
        pinned_map = self.config.get("pinned_sidebar_sections", {})
        pinned_map["favorites"] = self.is_pinned_expanded
        self.config.set("pinned_sidebar_sections", pinned_map)
        self._update_expanded_state()

    def _update_expanded_state(self):
        should_show = self.is_pinned_expanded or self.underMouse()
        self.scroll_area.setVisible(should_show)
        self.btn_add_fav.setVisible(should_show)
        self.btn_more.setVisible(should_show)

    def enterEvent(self, event):
        if not self.is_pinned_expanded:
            self.scroll_area.setVisible(True)
            self.btn_add_fav.setVisible(True)
            self.btn_more.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_pinned_expanded:
            self.scroll_area.setVisible(False)
            self.btn_add_fav.setVisible(False)
            self.btn_more.setVisible(False)
        super().leaveEvent(event)

    def _on_icon_ready(self, pkg: str, icon_path: str, source: str = "", detail: str = ""):
        if pkg in self.chip_buttons:
            btn = self.chip_buttons[pkg]
            favorites = self.config.get_favorite_apps()
            fav = next((f for f in favorites if f.get("package") == pkg), None)
            name = fav.get("name", pkg.split(".")[-1]) if fav else pkg.split(".")[-1]
            disp_res = fav.get("display_res", "") if fav else ""

            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(18, 18))
            btn.setText(f" {name}")

            src_label = f"Device APK ({detail})" if source == "adb" else f"Online HD ({detail})"
            tooltip_lines = [f"{name} ({pkg})"]
            if disp_res:
                tooltip_lines.append(f"Resolution Preset: {disp_res}")
            tooltip_lines.append(f"Icon: {src_label}")
            tooltip_lines.append("Left click: Launch | Right click: Options")
            btn.setToolTip("\n".join(tooltip_lines))

    def set_device(self, serial: Optional[str]):
        self.selected_serial = serial
        self.setEnabled(bool(serial))

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 10, 12, 10)
        self.main_layout.setSpacing(8)

        # 1. Header Toolbar Row
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        lbl_title = QLabel("⭐ Favorite Apps")
        lbl_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #38BDF8; border: none;")
        header_row.addWidget(lbl_title)
        header_row.addStretch(1)

        self.btn_add_fav = QPushButton("＋ Add")
        self.btn_add_fav.setToolTip("Add custom app to favorites")
        self.btn_add_fav.setFixedHeight(22)
        self.btn_add_fav.setStyleSheet(
            "QPushButton { background: #212530; color: #94A3B8; border: 1px dashed #3D4457; border-radius: 4px; font-size: 11px; padding: 2px 8px; }"
            "QPushButton:hover { background: #2B303C; color: #38BDF8; border-color: #38BDF8; }"
        )
        self.btn_add_fav.setCursor(Qt.PointingHandCursor)
        self.btn_add_fav.clicked.connect(self._open_add_dialog)
        header_row.addWidget(self.btn_add_fav)

        self.btn_more = QPushButton("📱 All Apps...")
        self.btn_more.setToolTip("Switch to full App Launcher & Manager")
        self.btn_more.setFixedHeight(22)
        self.btn_more.setStyleSheet(
            "QPushButton { background: transparent; color: #38BDF8; border: none; font-size: 11px; font-weight: 600; padding: 2px 6px; }"
            "QPushButton:hover { text-decoration: underline; color: #60A5FA; }"
        )
        self.btn_more.setCursor(Qt.PointingHandCursor)
        self.btn_more.clicked.connect(lambda: self.open_apps_manager_requested.emit())
        header_row.addWidget(self.btn_more)

        # Pin / Expand toggle button
        self.btn_pin = QPushButton("📌" if self.is_pinned_expanded else "📍")
        self.btn_pin.setFixedSize(22, 22)
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self._update_pin_style()
        self.btn_pin.clicked.connect(self._toggle_pin)
        header_row.addWidget(self.btn_pin)

        self.main_layout.addLayout(header_row)

        # 2. Scroll Area for Favorite Chips
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 4px; background: transparent; border-radius: 2px; }"
            "QScrollBar::handle:vertical { background: #373C4B; border-radius: 2px; min-height: 20px; }"
            "QScrollBar::handle:vertical:hover { background: #60A5FA; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        )

        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 2, 2, 2)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.grid_widget)
        self.main_layout.addWidget(self.scroll_area)

        self.refresh_favorites()

    def refresh_favorites(self):
        """Re-render favorite app buttons."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        favorites = self.config.get_favorite_apps()
        row, col = 0, 0
        cols_per_row = 3  # 3 items per row in sidebar dock

        rows = (len(favorites) + cols_per_row - 1) // cols_per_row if favorites else 1
        calculated_h = max(76, min(220, rows * 36 + 8))
        self.scroll_area.setFixedHeight(calculated_h)

        self.chip_buttons.clear()
        for fav in favorites:
            name = fav.get("name", "App")
            pkg = fav.get("package", "")
            icon_fallback = fav.get("icon", "📱")
            disp_res = fav.get("display_res", "")

            tooltip_lines = [f"{name} ({pkg})"]
            if disp_res:
                tooltip_lines.append(f"Resolution Preset: {disp_res}")

            src_info = self.icon_manager.get_icon_source(pkg)
            if src_info:
                source = src_info.get("source", "")
                detail = src_info.get("detail", "")
                if source == "adb":
                    src_label = f"📱 Device APK ({detail})"
                elif source == "web":
                    src_label = f"🌐 Online HD ({detail})"
                else:
                    src_label = f"💾 {detail}"
                tooltip_lines.append(f"Icon Source: {src_label}")

            tooltip_lines.append("Left click: Launch")
            tooltip_lines.append("Right click: Edit, Change Preset, Remove")

            app_icon = self.icon_manager.get_icon(pkg, self.selected_serial) if pkg else None
            if app_icon:
                btn = QPushButton(f" {name}")
                btn.setIcon(app_icon)
                btn.setIconSize(QSize(18, 18))
            else:
                btn = QPushButton(f"{icon_fallback} {name}")

            btn.setProperty("class", "quickAction")
            btn.setFixedHeight(28)
            btn.setToolTip("\n".join(tooltip_lines))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, p=pkg, n=name, r=disp_res: self._on_chip_clicked(p, n, r))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, f=fav, b=btn: self._show_context_menu(pos, f, b)
            )

            self.chip_buttons[pkg] = btn
            self.grid_layout.addWidget(btn, row, col)
            col += 1
            if col >= cols_per_row:
                col = 0
                row += 1

    def _on_chip_clicked(self, package: str, name: str, display_res: str = ""):
        if not self.selected_serial:
            return
        self.launch_app_requested.emit(self.selected_serial, package, name, display_res)

    def _show_context_menu(self, pos, fav: Dict, source_btn: QPushButton):
        package = fav.get("package", "")
        name = fav.get("name", "App")
        cur_res = fav.get("display_res", "")

        menu = QMenu(self)
        act_launch = menu.addAction(f"🚀 Launch '{name}'")
        menu.addSeparator()

        src_info = self.icon_manager.get_icon_source(package)
        if src_info:
            source = src_info.get("source", "")
            detail = src_info.get("detail", "")
            if source == "adb":
                src_label = f"📱 Icon Source: Device APK ({detail})"
            elif source == "web":
                src_label = f"🌐 Icon Source: Online HD ({detail})"
            else:
                src_label = f"💾 Icon Source: {detail}"
            act_info = menu.addAction(src_label)
            act_info.setEnabled(False)

        act_reextract = menu.addAction("📱 Re-extract Icon from Phone (ADB)")
        act_web_icon = menu.addAction("🌐 Fetch Official Icon from Web Store (Google Play)")
        menu.addSeparator()

        act_edit = menu.addAction(f"✏️ Rename & Customize...")

        # Submenu for Display Presets
        menu_presets = menu.addMenu(f"📐 Display Size Preset ({cur_res if cur_res else 'Global Default'})")
        act_def_res = menu_presets.addAction("🌐 Use App Launcher Global Size")
        if not cur_res:
            act_def_res.setIcon(menu.style().standardIcon(menu.style().StandardPixmap.SP_DialogApplyButton))
        act_def_res.triggered.connect(lambda: self._set_fav_preset(package, name, fav.get("icon", "📱"), ""))

        menu_presets.addSeparator()
        for p in self.config.get_virtual_display_presets():
            p_val = p.get("value", "")
            p_lbl = p.get("label", "")
            act_p = menu_presets.addAction(p_lbl)
            if cur_res == p_val and p_val:
                act_p.setIcon(menu.style().standardIcon(menu.style().StandardPixmap.SP_DialogApplyButton))
            act_p.triggered.connect(lambda _, v=p_val: self._set_fav_preset(package, name, fav.get("icon", "📱"), v))

        menu.addSeparator()
        act_move = menu.addAction(f"🔀 Move '{name}' from Phone to PC Display")
        act_shortcut = menu.addAction("📌 Create Desktop Shortcut (.lnk)")
        act_remove = menu.addAction("🗑 Remove from Favorites")

        action = menu.exec(source_btn.mapToGlobal(pos))
        if action == act_launch:
            self._on_chip_clicked(package, name, cur_res)
        elif action == act_move:
            if self.selected_serial:
                self.move_app_requested.emit(self.selected_serial, package, name, cur_res)
        elif action == act_reextract:
            self.icon_manager.get_icon(package, self.selected_serial, force_refresh=True)
        elif action == act_web_icon:
            self.icon_manager.force_web_icon(package)
        elif action == act_shortcut:
            scrcpy_exe = str(self.config.get_scrcpy_bin_dir() / "scrcpy.exe")
            icon_path = self.icon_manager.get_icon_path(package) or ""
            preset = self.config.get_preset_by_value(cur_res)
            win_w = str(preset.get("win_w", "")) if preset else ""
            win_h = str(preset.get("win_h", "")) if preset else ""
            from core.shortcut_manager import create_app_desktop_shortcut

            ok, msg = create_app_desktop_shortcut(
                scrcpy_exe=scrcpy_exe,
                serial=self.selected_serial or "",
                package=package,
                app_name=name,
                display_res=cur_res,
                win_w=win_w,
                win_h=win_h,
                icon_png=icon_path,
            )
            if ok:
                QMessageBox.information(self, "Shortcut Created", f"Successfully created desktop shortcut:\n\n{msg}")
            else:
                QMessageBox.warning(self, "Shortcut Error", f"Failed to create shortcut:\n{msg}")
        elif action == act_edit:
            self._open_edit_dialog(fav)
        elif action == act_remove:
            self.config.remove_favorite_app(package)
            self.refresh_favorites()

    def _set_fav_preset(self, package: str, name: str, icon: str, preset_val: str):
        self.config.update_favorite_app(package, name, icon, preset_val)
        self.refresh_favorites()

    def _open_edit_dialog(self, fav: Dict):
        dlg = FavoriteAppEditDialog(
            config=self.config,
            package=fav.get("package", ""),
            name=fav.get("name", ""),
            icon=fav.get("icon", "📱"),
            display_res=fav.get("display_res", ""),
            is_edit=True,
            parent=self
        )
        if dlg.exec() == QDialog.Accepted:
            self.config.update_favorite_app(dlg.package_name, dlg.display_name, dlg.icon, dlg.display_res)
            self.refresh_favorites()

    def _open_add_dialog(self):
        dlg = FavoriteAppEditDialog(
            config=self.config,
            is_edit=False,
            parent=self
        )
        if dlg.exec() == QDialog.Accepted:
            self.config.add_favorite_app(dlg.package_name, dlg.display_name, dlg.icon, dlg.display_res)
            self.refresh_favorites()
