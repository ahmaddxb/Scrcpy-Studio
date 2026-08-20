from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
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
    QTabWidget,
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
    """Full-featured dialog to edit favorite app metadata, virtual display resolution, video framerate, bitrate, codecs, audio, and window flags."""

    def __init__(
        self,
        config: ConfigManager,
        package: str = "",
        name: str = "",
        icon: str = "📱",
        display_res: str = "",
        # Video settings
        bitrate: str = "",
        max_fps: str = "",
        video_codec: str = "",
        rotation: str = "",
        # Audio settings
        audio_enabled: bool = True,
        audio_codec: str = "",
        audio_dup: bool = False,
        # Window & Display flags
        no_vd_system_decorations: bool = False,
        always_on_top: bool = False,
        borderless: bool = False,
        turn_screen_off: bool = False,
        stay_awake: bool = True,
        show_touches: bool = False,
        display_ime_policy: str = "",
        custom_args: str = "",
        active_defaults: Optional[Dict[str, Any]] = None,
        is_edit: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.config = config
        self.package_name = package
        self.display_name = name
        self.icon = icon
        self.display_res = display_res

        self.bitrate = bitrate
        self.max_fps = max_fps
        self.video_codec = video_codec
        self.rotation = rotation

        self.audio_enabled = audio_enabled
        self.audio_codec = audio_codec
        self.audio_dup = audio_dup

        self.no_vd_system_decorations = no_vd_system_decorations
        self.always_on_top = always_on_top
        self.borderless = borderless
        self.turn_screen_off = turn_screen_off
        self.stay_awake = stay_awake
        self.show_touches = show_touches
        self.display_ime_policy = display_ime_policy
        self.custom_args = custom_args

        # Extract live global stream defaults
        defs = active_defaults or {}
        act_bitrate = defs.get("bitrate", "8M")
        act_fps = defs.get("max_fps", "0")
        act_fps_lbl = f"{act_fps} FPS" if act_fps and act_fps != "0" else "Device Max"
        act_vcodec = defs.get("video_codec", "h264").upper()
        act_acodec = defs.get("audio_codec", "opus").capitalize()

        self.setWindowTitle(f"Configure '{name or package}'" if is_edit else "Add Favorite App")
        self.setFixedWidth(580)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        self.tabs = QTabWidget()

        # ==========================================
        # TAB 1: 📱 General & Display Resolution
        # ==========================================
        tab_gen = QWidget()
        l_gen = QVBoxLayout(tab_gen)
        l_gen.setContentsMargins(12, 14, 12, 14)
        l_gen.setSpacing(10)

        # App Display Name
        l_gen.addWidget(QLabel("App Display Name / Label:"))
        self.edit_name = QLineEdit(name)
        self.edit_name.setPlaceholderText("e.g. WhatsApp, Banking, YouTube")
        l_gen.addWidget(self.edit_name)

        # Package Name
        l_gen.addWidget(QLabel("Package Name:"))
        self.edit_pkg = QLineEdit(package)
        self.edit_pkg.setPlaceholderText("e.g. com.whatsapp")
        if is_edit:
            self.edit_pkg.setReadOnly(True)
            self.edit_pkg.setStyleSheet("background-color: #171920; color: #64748B;")
        l_gen.addWidget(self.edit_pkg)

        # Icon Row
        row_icon = QHBoxLayout()
        row_icon.setSpacing(10)
        lbl_icon = QLabel("Fallback Icon:")
        lbl_icon.setFixedWidth(110)
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
        l_gen.addLayout(row_icon)

        # Display Size Preset Row
        row_preset = QHBoxLayout()
        row_preset.setSpacing(10)
        lbl_preset = QLabel("Display Size Preset:")
        lbl_preset.setFixedWidth(110)
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
        l_gen.addLayout(row_preset)

        # Clean Display Checkbox
        self.chk_clean_vd = QCheckBox("🪟 Clean Display (Hide status && navigation bars: --no-vd-system-decorations)")
        self.chk_clean_vd.setChecked(bool(no_vd_system_decorations))
        self.chk_clean_vd.setToolTip("Gives an edge-to-edge full-bleed window without top clock or bottom back/home buttons")
        l_gen.addWidget(self.chk_clean_vd)

        l_gen.addStretch(1)
        self.tabs.addTab(tab_gen, "📱 General && Display")

        # ==========================================
        # TAB 2: 🎥 Video & Audio (Framerate, Bitrate, Codecs)
        # ==========================================
        tab_media = QWidget()
        l_media = QVBoxLayout(tab_media)
        l_media.setContentsMargins(12, 14, 12, 14)
        l_media.setSpacing(10)

        form_v = QFormLayout()
        form_v.setLabelAlignment(Qt.AlignLeft)
        form_v.setSpacing(10)

        # Video Bitrate
        self.combo_bitrate = QComboBox()
        self.combo_bitrate.addItem(f"🌐 Global Default ({act_bitrate})", "")
        self.combo_bitrate.addItem("2 Mbps (Low Bandwidth)", "2M")
        self.combo_bitrate.addItem("4 Mbps (Moderate)", "4M")
        self.combo_bitrate.addItem("8 Mbps (Standard FHD)", "8M")
        self.combo_bitrate.addItem("12 Mbps (High Quality)", "12M")
        self.combo_bitrate.addItem("16 Mbps (Crisp 2K / 60fps)", "16M")
        self.combo_bitrate.addItem("24 Mbps (Ultra High Quality)", "24M")
        self.combo_bitrate.addItem("32 Mbps (Lossless / High Bitrate)", "32M")
        if bitrate:
            b_idx = self.combo_bitrate.findData(bitrate)
            if b_idx >= 0:
                self.combo_bitrate.setCurrentIndex(b_idx)
            else:
                self.combo_bitrate.addItem(f"Custom ({bitrate})", bitrate)
                self.combo_bitrate.setCurrentIndex(self.combo_bitrate.count() - 1)
        form_v.addRow("Video Bitrate:", self.combo_bitrate)

        # Max Framerate
        self.combo_fps = QComboBox()
        self.combo_fps.addItem(f"🌐 Global Default ({act_fps_lbl})", "")
        self.combo_fps.addItem("30 FPS", "30")
        self.combo_fps.addItem("60 FPS (Smooth)", "60")
        self.combo_fps.addItem("90 FPS (High Refresh)", "90")
        self.combo_fps.addItem("120 FPS (Ultra Smooth)", "120")
        if max_fps:
            fps_idx = self.combo_fps.findData(max_fps)
            if fps_idx >= 0:
                self.combo_fps.setCurrentIndex(fps_idx)
            else:
                self.combo_fps.addItem(f"Custom ({max_fps} FPS)", max_fps)
                self.combo_fps.setCurrentIndex(self.combo_fps.count() - 1)
        form_v.addRow("Max Framerate:", self.combo_fps)

        # Video Codec
        self.combo_vcodec = QComboBox()
        self.combo_vcodec.addItem(f"🌐 Global Default ({act_vcodec})", "")
        self.combo_vcodec.addItem("H.264 (Highest Compatibility)", "h264")
        self.combo_vcodec.addItem("H.265 / HEVC (High Efficiency)", "h265")
        self.combo_vcodec.addItem("AV1 (Next-Gen)", "av1")
        if video_codec:
            vc_idx = self.combo_vcodec.findData(video_codec.lower())
            if vc_idx >= 0:
                self.combo_vcodec.setCurrentIndex(vc_idx)
        form_v.addRow("Video Codec:", self.combo_vcodec)

        # Video Orientation Lock
        self.combo_rotation = QComboBox()
        self.combo_rotation.addItem("Auto / Natural Orientation (0°)", "")
        self.combo_rotation.addItem("90° (Clockwise Landscape)", "90")
        self.combo_rotation.addItem("180° (Inverted Portrait)", "180")
        self.combo_rotation.addItem("270° (Counter-Clockwise Landscape)", "270")
        if rotation:
            r_idx = self.combo_rotation.findData(rotation)
            if r_idx >= 0:
                self.combo_rotation.setCurrentIndex(r_idx)
        form_v.addRow("Orientation Lock:", self.combo_rotation)

        l_media.addLayout(form_v)

        # Audio Section
        grp_audio = QGroupBox("🔊 Audio Streaming")
        l_aud = QVBoxLayout(grp_audio)
        l_aud.setSpacing(6)

        self.chk_audio = QCheckBox("Forward Audio to PC")
        self.chk_audio.setChecked(bool(audio_enabled))
        l_aud.addWidget(self.chk_audio)

        row_acodec = QHBoxLayout()
        row_acodec.addWidget(QLabel("Audio Codec:"))
        self.combo_acodec = QComboBox()
        self.combo_acodec.addItem(f"🌐 Global Default ({act_acodec})", "")
        self.combo_acodec.addItem("Opus (Recommended)", "opus")
        self.combo_acodec.addItem("AAC", "aac")
        self.combo_acodec.addItem("RAW (Low Latency)", "raw")
        self.combo_acodec.addItem("FLAC (Lossless)", "flac")
        if audio_codec:
            ac_idx = self.combo_acodec.findData(audio_codec.lower())
            if ac_idx >= 0:
                self.combo_acodec.setCurrentIndex(ac_idx)
        row_acodec.addWidget(self.combo_acodec, 1)
        l_aud.addLayout(row_acodec)

        self.chk_audio_dup = QCheckBox("Duplicate Audio (Play simultaneously on PC and Device)")
        self.chk_audio_dup.setChecked(bool(audio_dup))
        l_aud.addWidget(self.chk_audio_dup)

        l_media.addWidget(grp_audio)
        l_media.addStretch(1)
        self.tabs.addTab(tab_media, "🎥 Video && Audio")

        # ==========================================
        # TAB 3: 🪟 Window & Device Flags
        # ==========================================
        tab_adv = QWidget()
        l_adv = QVBoxLayout(tab_adv)
        l_adv.setContentsMargins(12, 14, 12, 14)
        l_adv.setSpacing(10)

        # Window Behavior
        grp_win = QGroupBox("🪟 Desktop Window Behavior")
        l_win = QVBoxLayout(grp_win)
        l_win.setSpacing(8)

        self.chk_always_on_top = QCheckBox("📌 Always on Top (--always-on-top)")
        self.chk_always_on_top.setChecked(bool(always_on_top))
        l_win.addWidget(self.chk_always_on_top)

        self.chk_borderless = QCheckBox("🔲 Borderless Window (--window-borderless)")
        self.chk_borderless.setChecked(bool(borderless))
        l_win.addWidget(self.chk_borderless)

        l_adv.addWidget(grp_win)

        # Device & Power
        grp_dev = QGroupBox("📱 Device & Input Behavior")
        l_dev = QVBoxLayout(grp_dev)
        l_dev.setSpacing(8)

        self.chk_turn_screen_off = QCheckBox("🌑 Turn Physical Screen Off during session (--turn-screen-off)")
        self.chk_turn_screen_off.setChecked(bool(turn_screen_off))
        l_dev.addWidget(self.chk_turn_screen_off)

        self.chk_stay_awake = QCheckBox("💡 Keep Device Awake (--stay-awake)")
        self.chk_stay_awake.setChecked(bool(stay_awake))
        l_dev.addWidget(self.chk_stay_awake)

        self.chk_show_touches = QCheckBox("👆 Show Touches / Tap Circles (--show-touches)")
        self.chk_show_touches.setChecked(bool(show_touches))
        l_dev.addWidget(self.chk_show_touches)

        # IME Policy
        row_ime = QHBoxLayout()
        row_ime.addWidget(QLabel("IME Policy:"))
        self.combo_ime = QComboBox()
        self.combo_ime.addItem("🌐 Global Setting Default", "")
        self.combo_ime.addItem("⌨️ Local (Show soft keyboard on PC Display)", "local")
        self.combo_ime.addItem("🚫 Hidden (Suppress soft keyboard)", "hide")
        self.combo_ime.addItem("📱 Phone (Show soft keyboard on Phone Display 0)", "fallback")
        if display_ime_policy:
            ime_idx = self.combo_ime.findData(display_ime_policy)
            if ime_idx >= 0:
                self.combo_ime.setCurrentIndex(ime_idx)
        row_ime.addWidget(self.combo_ime, 1)
        l_dev.addLayout(row_ime)

        l_adv.addWidget(grp_dev)

        # Custom Arguments
        row_args = QHBoxLayout()
        lbl_args = QLabel("Custom Args:")
        lbl_args.setFixedWidth(80)
        row_args.addWidget(lbl_args)
        self.edit_custom_args = QLineEdit(custom_args)
        self.edit_custom_args.setPlaceholderText("e.g. --max-size=1920 --video-bit-rate=12M")
        row_args.addWidget(self.edit_custom_args, 1)
        l_adv.addLayout(row_args)

        l_adv.addStretch(1)
        self.tabs.addTab(tab_adv, "🛠️ Window && Controls")

        main_layout.addWidget(self.tabs)

        # Bottom Action Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Save Settings" if is_edit else "Add Favorite")
        btn_save.setObjectName("primaryBtn")
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_save)

        main_layout.addLayout(btn_row)

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

        self.bitrate = self.combo_bitrate.currentData() or ""
        self.max_fps = self.combo_fps.currentData() or ""
        self.video_codec = self.combo_vcodec.currentData() or ""
        self.rotation = self.combo_rotation.currentData() or ""

        self.audio_enabled = self.chk_audio.isChecked()
        self.audio_codec = self.combo_acodec.currentData() or "opus"
        self.audio_dup = self.chk_audio_dup.isChecked()

        self.no_vd_system_decorations = self.chk_clean_vd.isChecked()
        self.always_on_top = self.chk_always_on_top.isChecked()
        self.borderless = self.chk_borderless.isChecked()
        self.turn_screen_off = self.chk_turn_screen_off.isChecked()
        self.stay_awake = self.chk_stay_awake.isChecked()
        self.show_touches = self.chk_show_touches.isChecked()
        self.display_ime_policy = self.combo_ime.currentData() or ""
        self.custom_args = self.edit_custom_args.text().strip()
        self.accept()


class FavoriteAppsBar(QFrame):
    """Spacious quick-launch dock for user favorite apps with individual display presets & custom labels."""

    launch_app_requested = Signal(str, str, str, str)  # serial, package_name, display_name, display_res
    pull_active_app_requested = Signal(str)  # serial
    open_apps_manager_requested = Signal()

    def __init__(self, config: ConfigManager, adb: AdbManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.adb = adb
        self.selected_serial: Optional[str] = None
        self.icon_manager = IconManager.get_instance()
        self.icon_manager.icon_ready.connect(self._on_icon_ready)
        self.chip_buttons: Dict[str, QPushButton] = {}
        self.active_stream_getter = None

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
        self.btn_pull_phone.setVisible(should_show)
        self.btn_more.setVisible(should_show)

    def enterEvent(self, event):
        if not self.is_pinned_expanded:
            self.scroll_area.setVisible(True)
            self.btn_add_fav.setVisible(True)
            self.btn_pull_phone.setVisible(True)
            self.btn_more.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_pinned_expanded:
            self.scroll_area.setVisible(False)
            self.btn_add_fav.setVisible(False)
            self.btn_pull_phone.setVisible(False)
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

        self.btn_pull_phone = QPushButton("🔀 Move to PC")
        self.btn_pull_phone.setToolTip("Detect whatever app is open on the phone and move it to a PC Virtual Display window")
        self.btn_pull_phone.setFixedHeight(22)
        self.btn_pull_phone.setStyleSheet(
            "QPushButton { background: #1E293B; color: #38BDF8; border: 1px solid #38BDF844; border-radius: 4px; font-size: 11px; font-weight: 600; padding: 2px 8px; }"
            "QPushButton:hover { background: #0284C7; color: #FFFFFF; border-color: #38BDF8; }"
        )
        self.btn_pull_phone.setCursor(Qt.PointingHandCursor)
        self.btn_pull_phone.clicked.connect(self._on_pull_phone_clicked)
        header_row.addWidget(self.btn_pull_phone)

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

    def _on_pull_phone_clicked(self):
        if not self.selected_serial:
            return
        self.pull_active_app_requested.emit(self.selected_serial)

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

        act_edit = menu.addAction("⚙️ Configure App Settings...")

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

        menu_presets.addSeparator()
        if cur_res:
            act_edit_cur = menu_presets.addAction("✏️ Edit Selected Preset...")
            act_edit_cur.triggered.connect(lambda _, v=cur_res: self._edit_preset_dialog(v))

        act_add_new = menu_presets.addAction("➕ Create New Preset...")
        act_add_new.triggered.connect(self._create_new_preset_dialog)

        act_manage_app = menu_presets.addAction("⚙️ Manage Presets in App Launcher...")
        act_manage_app.triggered.connect(lambda: self.open_apps_manager_requested.emit())

        menu.addSeparator()
        act_shortcut = menu.addAction("📌 Create Desktop Shortcut (.lnk)")
        act_remove = menu.addAction("🗑 Remove from Favorites")

        action = menu.exec(source_btn.mapToGlobal(pos))
        if action == act_launch:
            self._on_chip_clicked(package, name, cur_res)
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
                no_vd_decorations=fav.get("no_vd_system_decorations", False),
                always_on_top=fav.get("always_on_top", False),
                borderless=fav.get("borderless", False),
                custom_args=fav.get("custom_args", ""),
                ime_policy=fav.get("display_ime_policy", ""),
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
        fav = next((f for f in self.config.get_favorite_apps() if f.get("package") == package), {})
        self.config.update_favorite_app(
            package=package,
            name=name,
            icon=icon,
            display_res=preset_val,
            no_vd_system_decorations=fav.get("no_vd_system_decorations", False),
            always_on_top=fav.get("always_on_top", False),
            borderless=fav.get("borderless", False),
            audio_enabled=fav.get("audio_enabled", True),
            custom_args=fav.get("custom_args", ""),
            display_ime_policy=fav.get("display_ime_policy", ""),
        )
        self.refresh_favorites()

    def _open_edit_dialog(self, fav: Dict):
        active_stream = self.active_stream_getter() if callable(self.active_stream_getter) else {}
        dlg = FavoriteAppEditDialog(
            config=self.config,
            package=fav.get("package", ""),
            name=fav.get("name", ""),
            icon=fav.get("icon", "📱"),
            display_res=fav.get("display_res", ""),
            bitrate=fav.get("bitrate", ""),
            max_fps=fav.get("max_fps", ""),
            video_codec=fav.get("video_codec", ""),
            rotation=fav.get("rotation", ""),
            audio_enabled=fav.get("audio_enabled", True),
            audio_codec=fav.get("audio_codec", ""),
            audio_dup=fav.get("audio_dup", False),
            no_vd_system_decorations=fav.get("no_vd_system_decorations", False),
            always_on_top=fav.get("always_on_top", False),
            borderless=fav.get("borderless", False),
            turn_screen_off=fav.get("turn_screen_off", False),
            stay_awake=fav.get("stay_awake", True),
            show_touches=fav.get("show_touches", False),
            display_ime_policy=fav.get("display_ime_policy", ""),
            custom_args=fav.get("custom_args", ""),
            active_defaults=active_stream,
            is_edit=True,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            self.config.update_favorite_app(
                package=dlg.package_name,
                name=dlg.display_name,
                icon=dlg.icon,
                display_res=dlg.display_res,
                bitrate=dlg.bitrate,
                max_fps=dlg.max_fps,
                video_codec=dlg.video_codec,
                rotation=dlg.rotation,
                audio_enabled=dlg.audio_enabled,
                audio_codec=dlg.audio_codec,
                audio_dup=dlg.audio_dup,
                no_vd_system_decorations=dlg.no_vd_system_decorations,
                always_on_top=dlg.always_on_top,
                borderless=dlg.borderless,
                turn_screen_off=dlg.turn_screen_off,
                stay_awake=dlg.stay_awake,
                show_touches=dlg.show_touches,
                display_ime_policy=dlg.display_ime_policy,
                custom_args=dlg.custom_args,
            )
            self.refresh_favorites()

    def _open_add_dialog(self):
        active_stream = self.active_stream_getter() if callable(self.active_stream_getter) else {}
        dlg = FavoriteAppEditDialog(
            config=self.config,
            active_defaults=active_stream,
            is_edit=False,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            self.config.add_favorite_app(
                package=dlg.package_name,
                name=dlg.display_name,
                icon=dlg.icon,
                display_res=dlg.display_res,
                bitrate=dlg.bitrate,
                max_fps=dlg.max_fps,
                video_codec=dlg.video_codec,
                rotation=dlg.rotation,
                audio_enabled=dlg.audio_enabled,
                audio_codec=dlg.audio_codec,
                audio_dup=dlg.audio_dup,
                no_vd_system_decorations=dlg.no_vd_system_decorations,
                always_on_top=dlg.always_on_top,
                borderless=dlg.borderless,
                turn_screen_off=dlg.turn_screen_off,
                stay_awake=dlg.stay_awake,
                show_touches=dlg.show_touches,
                display_ime_policy=dlg.display_ime_policy,
                custom_args=dlg.custom_args,
            )
            self.refresh_favorites()

    def _create_new_preset_dialog(self):
        from ui.components.app_launcher import AddDisplayPresetDialog
        dlg = AddDisplayPresetDialog(title="Create Virtual Display Preset", parent=self)
        if dlg.exec() == QDialog.Accepted:
            if self.config:
                self.config.add_virtual_display_preset(dlg.preset_label, dlg.preset_value, dlg.preset_win_w, dlg.preset_win_h)
            self.refresh_favorites()

    def _edit_preset_dialog(self, cur_val: str):
        from ui.components.app_launcher import AddDisplayPresetDialog
        preset = self.config.get_preset_by_value(cur_val) if self.config else None
        if not preset:
            return

        label = preset.get("label", "")
        clean_name = label
        if "(" in clean_name:
            clean_name = clean_name.split("(")[0].strip()
        for prefix in ("📱", "💻", "🌐"):
            clean_name = clean_name.replace(prefix, "").strip()

        w, h, dpi = 1080, 1920, 0
        try:
            if "/" in cur_val:
                res_part, dpi_part = cur_val.split("/")
                dpi = int(dpi_part)
            else:
                res_part = cur_val
            if "x" in res_part:
                w_str, h_str = res_part.split("x")
                w, h = int(w_str), int(h_str)
        except Exception:
            pass

        win_w = int(preset.get("win_w", 0)) if str(preset.get("win_w", "")).isdigit() else 0
        win_h = int(preset.get("win_h", 0)) if str(preset.get("win_h", "")).isdigit() else 0

        dlg = AddDisplayPresetDialog(
            title=f"Edit Preset ({cur_val})",
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
                self.config.update_virtual_display_preset(
                    old_value=cur_val,
                    new_label=dlg.preset_label,
                    new_value=dlg.preset_value,
                    win_w=str(dlg.preset_win_w),
                    win_h=str(dlg.preset_win_h),
                )
            self.refresh_favorites()
