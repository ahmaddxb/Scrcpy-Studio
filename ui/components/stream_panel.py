from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager


class StreamPanel(QWidget):
    """Configuration panel for scrcpy parameters, presets, video/audio options."""

    settings_changed = Signal()
    launch_requested = Signal()
    stop_requested = Signal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.active_serial: Optional[str] = None
        self._block_signals = False
        self._setup_ui()
        self.load_presets_to_combo()
        self.load_settings(self.config.get("current_settings", {}))

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 0. Active Device Profile Header Banner
        self.device_banner = QFrame()
        self.device_banner.setStyleSheet("background-color: #141620; border: 1px solid #232734; border-radius: 6px; padding: 2px;")
        d_layout = QHBoxLayout(self.device_banner)
        d_layout.setContentsMargins(8, 4, 8, 4)
        d_layout.setSpacing(8)

        self.lbl_device_title = QLabel("📱 Device Profile: (None selected)")
        self.lbl_device_title.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 11px;")
        d_layout.addWidget(self.lbl_device_title, 1)

        self.chk_device_custom = QCheckBox("Save Custom Settings for this Device")
        self.chk_device_custom.setStyleSheet("color: #CBD5E1; font-size: 11px; font-weight: 500;")
        self.chk_device_custom.toggled.connect(self._on_custom_profile_toggled)
        d_layout.addWidget(self.chk_device_custom)

        main_layout.addWidget(self.device_banner)
        self.device_banner.setVisible(False)

        # 1. Preset Header Bar
        preset_bar = QHBoxLayout()
        preset_bar.setSpacing(8)

        preset_lbl = QLabel("Preset:")
        preset_lbl.setStyleSheet("font-weight: 600; color: #94A3B8;")
        preset_bar.addWidget(preset_lbl)

        self.combo_presets = QComboBox()
        self.combo_presets.currentIndexChanged.connect(self._on_preset_changed)
        preset_bar.addWidget(self.combo_presets, 1)

        self.btn_save_preset = QPushButton("💾 Save Preset")
        self.btn_save_preset.clicked.connect(self._save_custom_preset)
        preset_bar.addWidget(self.btn_save_preset)

        self.btn_delete_preset = QPushButton("🗑️")
        self.btn_delete_preset.setToolTip("Delete custom preset")
        self.btn_delete_preset.clicked.connect(self._delete_custom_preset)
        preset_bar.addWidget(self.btn_delete_preset)

        main_layout.addLayout(preset_bar)

        # 2. Tabs for Video, Audio, Display, Advanced
        self.tabs = QTabWidget()

        # === TAB 1: VIDEO ===
        tab_video = QWidget()
        v_layout = QVBoxLayout(tab_video)
        v_layout.setContentsMargins(8, 12, 8, 12)
        v_layout.setSpacing(12)

        form_v = QFormLayout()
        form_v.setLabelAlignment(Qt.AlignLeft)
        form_v.setSpacing(10)

        # Resolution / Max Size
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems([
            "Original / Native",
            "1080p (1920)",
            "720p (1280)",
            "1440p 2K (2560)",
            "4K (3840)",
            "480p (854)",
            "Custom"
        ])
        self.combo_resolution.currentIndexChanged.connect(self._on_setting_changed)
        form_v.addRow("Resolution / Size:", self.combo_resolution)

        # Custom size row
        self.lbl_custom_size = QLabel("Custom Max Width/Height:")
        self.edit_custom_size = QLineEdit()
        self.edit_custom_size.setPlaceholderText("e.g. 1600")
        self.lbl_custom_size.setVisible(False)
        self.edit_custom_size.setVisible(False)
        self.edit_custom_size.textChanged.connect(self._on_setting_changed)
        form_v.addRow(self.lbl_custom_size, self.edit_custom_size)

        # Bitrate Slider
        bitrate_box = QHBoxLayout()
        self.slider_bitrate = QSlider(Qt.Horizontal)
        self.slider_bitrate.setRange(2, 32)
        self.slider_bitrate.setValue(8)
        self.slider_bitrate.setSingleStep(1)
        self.lbl_bitrate_val = QLabel("8 Mbps")
        self.lbl_bitrate_val.setFixedWidth(55)
        self.slider_bitrate.valueChanged.connect(self._on_bitrate_slider_changed)
        bitrate_box.addWidget(self.slider_bitrate)
        bitrate_box.addWidget(self.lbl_bitrate_val)
        form_v.addRow("Video Bitrate:", bitrate_box)

        # Max FPS
        self.combo_fps = QComboBox()
        self.combo_fps.addItems(["Default / Max", "30 FPS", "60 FPS", "90 FPS", "120 FPS"])
        self.combo_fps.currentIndexChanged.connect(self._on_setting_changed)
        form_v.addRow("Max Framerate:", self.combo_fps)

        # Video Codec
        self.combo_vcodec = QComboBox()
        self.combo_vcodec.addItems(["H.264 (Default - Highest Compatibility)", "H.265 (HEVC - High Efficiency)", "AV1 (Next-Gen)"])
        self.combo_vcodec.currentIndexChanged.connect(self._on_setting_changed)
        form_v.addRow("Video Codec:", self.combo_vcodec)

        # Video Orientation Lock
        self.combo_rotation = QComboBox()
        self.combo_rotation.addItems(["Auto / Natural (0°)", "90° (Clockwise)", "180° (Inverted)", "270° (Counter-Clockwise)"])
        self.combo_rotation.currentIndexChanged.connect(self._on_setting_changed)
        form_v.addRow("Orientation Lock:", self.combo_rotation)

        v_layout.addLayout(form_v)
        v_layout.addStretch(1)
        self.tabs.addTab(tab_video, "🎥 Video")

        # === TAB 2: AUDIO ===
        tab_audio = QWidget()
        a_layout = QVBoxLayout(tab_audio)
        a_layout.setContentsMargins(8, 12, 8, 12)
        a_layout.setSpacing(12)

        self.chk_audio = QCheckBox("Forward Audio to PC (Requires Android 11+)")
        self.chk_audio.setChecked(True)
        self.chk_audio.toggled.connect(self._on_setting_changed)
        a_layout.addWidget(self.chk_audio)

        self.chk_audio_dup = QCheckBox("Duplicate Audio (Play on both PC and Device)")
        self.chk_audio_dup.toggled.connect(self._on_setting_changed)
        a_layout.addWidget(self.chk_audio_dup)

        form_a = QFormLayout()
        form_a.setSpacing(10)
        self.combo_acodec = QComboBox()
        self.combo_acodec.addItems(["Opus (Recommended)", "AAC", "RAW (Low Latency)", "FLAC (Lossless)"])
        self.combo_acodec.currentIndexChanged.connect(self._on_setting_changed)
        form_a.addRow("Audio Codec:", self.combo_acodec)
        a_layout.addLayout(form_a)

        a_layout.addStretch(1)
        self.tabs.addTab(tab_audio, "🔊 Audio")

        # === TAB 3: 🪟 WINDOW DIMENSIONS & MODES ===
        tab_win = QWidget()
        w_layout = QVBoxLayout(tab_win)
        w_layout.setContentsMargins(8, 12, 8, 12)
        w_layout.setSpacing(10)

        # Window Size & Presets Box
        win_size_box = QGroupBox("🪟 Mirroring Window Dimensions")
        win_size_layout = QVBoxLayout(win_size_box)
        win_size_layout.setSpacing(8)

        form_w = QFormLayout()
        form_w.setSpacing(8)

        self.combo_win_preset = QComboBox()
        self.combo_win_preset.addItems([
            "Auto / Native Aspect Ratio",
            "Compact Phone (420 × 900)",
            "Standard Phone (540 × 1140)",
            "Large Phone (720 × 1520)",
            "Tablet / iPad View (900 × 1200)",
            "Custom Window Size"
        ])
        self.combo_win_preset.currentIndexChanged.connect(self._on_win_preset_changed)
        form_w.addRow("Size Preset:", self.combo_win_preset)

        dim_row = QHBoxLayout()
        dim_row.setSpacing(6)
        self.edit_win_width = QLineEdit()
        self.edit_win_width.setPlaceholderText("Width (px)")
        self.edit_win_width.textChanged.connect(self._on_setting_changed)
        lbl_x = QLabel("×")
        lbl_x.setStyleSheet("color: #64748B; font-weight: bold;")
        self.edit_win_height = QLineEdit()
        self.edit_win_height.setPlaceholderText("Height (px)")
        self.edit_win_height.textChanged.connect(self._on_setting_changed)
        dim_row.addWidget(self.edit_win_width, 1)
        dim_row.addWidget(lbl_x)
        dim_row.addWidget(self.edit_win_height, 1)
        form_w.addRow("Width × Height:", dim_row)

        pos_row = QHBoxLayout()
        pos_row.setSpacing(6)
        self.edit_win_x = QLineEdit()
        self.edit_win_x.setPlaceholderText("X pos (opt)")
        self.edit_win_x.textChanged.connect(self._on_setting_changed)
        lbl_comma = QLabel(",")
        lbl_comma.setStyleSheet("color: #64748B; font-weight: bold;")
        self.edit_win_y = QLineEdit()
        self.edit_win_y.setPlaceholderText("Y pos (opt)")
        self.edit_win_y.textChanged.connect(self._on_setting_changed)
        pos_row.addWidget(self.edit_win_x, 1)
        pos_row.addWidget(lbl_comma)
        pos_row.addWidget(self.edit_win_y, 1)
        form_w.addRow("Position (X, Y):", pos_row)

        win_size_layout.addLayout(form_w)
        w_layout.addWidget(win_size_box)

        # Window Behavior Box
        win_behavior_box = QGroupBox("🖥️ Window Behavior")
        wb_layout = QGridLayout(win_behavior_box)
        wb_layout.setHorizontalSpacing(15)
        wb_layout.setVerticalSpacing(8)

        self.chk_always_top = QCheckBox("Always On Top")
        self.chk_always_top.toggled.connect(self._on_setting_changed)
        wb_layout.addWidget(self.chk_always_top, 0, 0)

        self.chk_fullscreen = QCheckBox("Start Fullscreen")
        self.chk_fullscreen.toggled.connect(self._on_setting_changed)
        wb_layout.addWidget(self.chk_fullscreen, 0, 1)

        self.chk_borderless = QCheckBox("Borderless Window")
        self.chk_borderless.toggled.connect(self._on_setting_changed)
        wb_layout.addWidget(self.chk_borderless, 1, 0)

        self.chk_companion_toolbar = QCheckBox("🧰 Magnetic Side Toolbar")
        self.chk_companion_toolbar.setToolTip("Attach a floating quick-actions toolbar directly to the right edge of the mirror window (QtScrcpy style)")
        self.chk_companion_toolbar.setChecked(True)
        self.chk_companion_toolbar.toggled.connect(self._on_setting_changed)
        wb_layout.addWidget(self.chk_companion_toolbar, 1, 1)

        w_layout.addWidget(win_behavior_box)
        w_layout.addStretch(1)
        self.tabs.addTab(tab_win, "🪟 Window")

        # === TAB 4: ⚡ DISPLAY & FLAGS ===
        tab_disp = QWidget()
        d_layout = QVBoxLayout(tab_disp)
        d_layout.setContentsMargins(8, 12, 8, 12)
        d_layout.setSpacing(10)

        grid_disp = QGridLayout()
        grid_disp.setHorizontalSpacing(15)
        grid_disp.setVerticalSpacing(8)

        self.chk_turn_off = QCheckBox("Turn Phone Screen Off")
        self.chk_turn_off.setToolTip("Save phone battery by turning physical display off while mirroring (-S)")
        self.chk_turn_off.toggled.connect(self._on_setting_changed)
        grid_disp.addWidget(self.chk_turn_off, 0, 0)

        self.chk_stay_awake = QCheckBox("Stay Awake While Connected (-w)")
        self.chk_stay_awake.setToolTip("Prevent device from sleeping while scrcpy is active (-w)")
        self.chk_stay_awake.setChecked(True)
        self.chk_stay_awake.toggled.connect(self._on_setting_changed)
        grid_disp.addWidget(self.chk_stay_awake, 0, 1)

        self.chk_force_stay_awake = QCheckBox("⚡ Force Stay Awake (Fix 30s sleep)")
        self.chk_force_stay_awake.setToolTip(
            "Temporarily extends Android screen_off_timeout to 24h during mirroring and automatically restores your original timeout when done.\n"
            "Solves aggressive OEM/Samsung OneUI 30-second screen sleep timeouts."
        )
        self.chk_force_stay_awake.setChecked(True)
        self.chk_force_stay_awake.toggled.connect(self._on_setting_changed)
        grid_disp.addWidget(self.chk_force_stay_awake, 1, 0)

        self.chk_show_touches = QCheckBox("Show Physical Touches")
        self.chk_show_touches.toggled.connect(self._on_setting_changed)
        grid_disp.addWidget(self.chk_show_touches, 1, 1)

        self.chk_clipboard = QCheckBox("Auto-Sync Clipboard")
        self.chk_clipboard.setChecked(True)
        self.chk_clipboard.toggled.connect(self._on_setting_changed)
        grid_disp.addWidget(self.chk_clipboard, 2, 0)

        d_layout.addLayout(grid_disp)

        # Recording Section
        rec_box = QGroupBox("📼 Video Recording")
        rec_layout = QVBoxLayout(rec_box)
        rec_layout.setSpacing(8)

        self.chk_record = QCheckBox("Record Stream to File")
        self.chk_record.toggled.connect(self._on_setting_changed)
        rec_layout.addWidget(self.chk_record)

        rec_path_row = QHBoxLayout()
        self.edit_rec_path = QLineEdit()
        self.edit_rec_path.setPlaceholderText("Save folder (Default: ~/Videos)")
        self.btn_browse_rec = QPushButton("📁 Browse")
        self.btn_browse_rec.clicked.connect(self._browse_record_path)
        rec_path_row.addWidget(self.edit_rec_path, 1)
        rec_path_row.addWidget(self.btn_browse_rec)
        rec_layout.addLayout(rec_path_row)

        d_layout.addWidget(rec_box)
        d_layout.addStretch(1)
        self.tabs.addTab(tab_disp, "⚡ Display & Flags")

        # === TAB 4: SPECIAL MODES & CUSTOM ===
        tab_spec = QWidget()
        s_layout = QVBoxLayout(tab_spec)
        s_layout.setContentsMargins(8, 12, 8, 12)
        s_layout.setSpacing(10)

        form_spec = QFormLayout()
        form_spec.setSpacing(10)

        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "Standard Display Mirroring",
            "🎮 OTG Mode (PC Keyboard/Mouse as HID)",
            "📷 Camera as Webcam (--video-source=camera)",
            "🎧 Audio Only Stream (--no-video)"
        ])
        self.combo_mode.currentIndexChanged.connect(self._on_setting_changed)
        form_spec.addRow("Special Operation Mode:", self.combo_mode)

        self.edit_custom_args = QLineEdit()
        self.edit_custom_args.setPlaceholderText("e.g. --render-driver=opengl --tunnel-host=...")
        self.edit_custom_args.textChanged.connect(self._on_setting_changed)
        form_spec.addRow("Custom Scrcpy CLI Args:", self.edit_custom_args)

        s_layout.addLayout(form_spec)
        s_layout.addStretch(1)
        self.tabs.addTab(tab_spec, "⚙️ Special Modes")

        main_layout.addWidget(self.tabs)

        # 3. Bottom Big Launch Button
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.btn_launch_main = QPushButton("🚀 LAUNCH MIRRORING")
        self.btn_launch_main.setObjectName("launchBtn")
        self.btn_launch_main.clicked.connect(self.launch_requested.emit)
        bottom_row.addWidget(self.btn_launch_main, 1)

        self.btn_stop_main = QPushButton("⏹ STOP")
        self.btn_stop_main.setObjectName("stopBtn")
        self.btn_stop_main.clicked.connect(self.stop_requested.emit)
        bottom_row.addWidget(self.btn_stop_main)

        main_layout.addLayout(bottom_row)

    def set_active_device(self, serial: Optional[str], alias: str = ""):
        """Switch stream panel settings to the active device profile."""
        self.active_serial = serial
        if not serial:
            self.device_banner.setVisible(False)
            self.load_settings(self.config.get("current_settings", {}))
            return

        self.device_banner.setVisible(True)
        display_name = alias or self.config.get_device_alias(serial) or serial
        self.lbl_device_title.setText(f"📱 Profile: {display_name}")

        is_custom = self.config.is_device_custom_settings(serial)
        self.chk_device_custom.blockSignals(True)
        self.chk_device_custom.setChecked(is_custom)
        self.chk_device_custom.blockSignals(False)

        device_settings = self.config.get_device_settings(serial)
        self.load_settings(device_settings)

    def _on_custom_profile_toggled(self, checked: bool):
        if self.active_serial:
            self.config.set_device_custom_settings(self.active_serial, checked)
            if checked:
                self.config.set_device_settings(self.active_serial, self.get_settings())
            self.settings_changed.emit()

    def _on_bitrate_slider_changed(self, val: int):
        self.lbl_bitrate_val.setText(f"{val} Mbps")
        self._on_setting_changed()

    def _on_setting_changed(self):
        if self._block_signals:
            return
        is_custom_size = self.combo_resolution.currentText() == "Custom"
        self.lbl_custom_size.setVisible(is_custom_size)
        self.edit_custom_size.setVisible(is_custom_size)

        cur_settings = self.get_settings()
        if self.active_serial and self.chk_device_custom.isChecked():
            self.config.set_device_settings(self.active_serial, cur_settings)
        else:
            self.config.set("current_settings", cur_settings)

        self.settings_changed.emit()

    def get_settings(self) -> Dict[str, Any]:
        """Collect current UI controls into a clean settings dict."""
        res_text = self.combo_resolution.currentText()
        if "1080p" in res_text:
            max_size = "1920"
        elif "720p" in res_text:
            max_size = "1280"
        elif "1440p" in res_text:
            max_size = "2560"
        elif "4K" in res_text:
            max_size = "3840"
        elif "480p" in res_text:
            max_size = "854"
        elif res_text == "Custom":
            max_size = self.edit_custom_size.text().strip()
        else:
            max_size = "0"

        fps_text = self.combo_fps.currentText()
        max_fps = "0"
        for fps in ["30", "60", "90", "120"]:
            if fps in fps_text:
                max_fps = fps
                break

        vcodec_text = self.combo_vcodec.currentText().lower()
        if "hevc" in vcodec_text or "h.265" in vcodec_text:
            vcodec = "h265"
        elif "av1" in vcodec_text:
            vcodec = "av1"
        else:
            vcodec = "h264"

        rot_text = self.combo_rotation.currentText()
        rotation = "0"
        if "90°" in rot_text:
            rotation = "90"
        elif "180°" in rot_text:
            rotation = "180"
        elif "270°" in rot_text:
            rotation = "270"

        acodec_text = self.combo_acodec.currentText().lower()
        if "aac" in acodec_text:
            acodec = "aac"
        elif "raw" in acodec_text:
            acodec = "raw"
        elif "flac" in acodec_text:
            acodec = "flac"
        else:
            acodec = "opus"

        mode_idx = self.combo_mode.currentIndex()
        otg = (mode_idx == 1)
        camera = (mode_idx == 2)
        no_video = (mode_idx == 3)

        return {
            "max_size": max_size,
            "bitrate": f"{self.slider_bitrate.value()}M",
            "max_fps": max_fps,
            "video_codec": vcodec,
            "rotation": rotation,
            "audio_enabled": self.chk_audio.isChecked(),
            "audio_codec": acodec,
            "audio_dup": self.chk_audio_dup.isChecked(),
            "turn_screen_off": self.chk_turn_off.isChecked(),
            "stay_awake": self.chk_stay_awake.isChecked(),
            "force_stay_awake": self.chk_force_stay_awake.isChecked(),
            "always_on_top": self.chk_always_top.isChecked(),
            "fullscreen": self.chk_fullscreen.isChecked(),
            "borderless": self.chk_borderless.isChecked(),
            "enable_companion_toolbar": self.chk_companion_toolbar.isChecked(),
            "show_touches": self.chk_show_touches.isChecked(),
            "sync_clipboard": self.chk_clipboard.isChecked(),
            "window_width": self.edit_win_width.text().strip(),
            "window_height": self.edit_win_height.text().strip(),
            "window_x": self.edit_win_x.text().strip(),
            "window_y": self.edit_win_y.text().strip(),
            "record": self.chk_record.isChecked(),
            "record_path": self.edit_rec_path.text().strip(),
            "record_format": "mp4",
            "otg_mode": otg,
            "camera_mode": camera,
            "no_video": no_video,
            "custom_args": self.edit_custom_args.text().strip()
        }

    def _on_win_preset_changed(self, idx: int):
        if self._block_signals:
            return
        if idx == 0:  # Auto
            self.edit_win_width.setText("")
            self.edit_win_height.setText("")
        elif idx == 1:  # Compact 420x900
            self.edit_win_width.setText("420")
            self.edit_win_height.setText("900")
        elif idx == 2:  # Standard 540x1140
            self.edit_win_width.setText("540")
            self.edit_win_height.setText("1140")
        elif idx == 3:  # Large 720x1520
            self.edit_win_width.setText("720")
            self.edit_win_height.setText("1520")
        elif idx == 4:  # Tablet 900x1200
            self.edit_win_width.setText("900")
            self.edit_win_height.setText("1200")
        self._on_setting_changed()

    def load_settings(self, s: Dict[str, Any]):
        """Load settings dict into UI controls."""
        self._block_signals = True
        try:
            # Resolution
            max_size = str(s.get("max_size", "1920"))
            if max_size == "1920":
                self.combo_resolution.setCurrentIndex(1)
            elif max_size == "1280":
                self.combo_resolution.setCurrentIndex(2)
            elif max_size == "2560":
                self.combo_resolution.setCurrentIndex(3)
            elif max_size == "3840":
                self.combo_resolution.setCurrentIndex(4)
            elif max_size == "854":
                self.combo_resolution.setCurrentIndex(5)
            elif max_size == "0" or not max_size:
                self.combo_resolution.setCurrentIndex(0)
            else:
                self.combo_resolution.setCurrentIndex(6)
                self.edit_custom_size.setText(max_size)

            # Bitrate
            bitrate_str = str(s.get("bitrate", "8M")).upper().replace("M", "")
            try:
                bval = int(bitrate_str)
                self.slider_bitrate.setValue(bval)
                self.lbl_bitrate_val.setText(f"{bval} Mbps")
            except ValueError:
                self.slider_bitrate.setValue(8)

            # FPS
            fps_val = str(s.get("max_fps", "60"))
            idx = 0
            for i, item in enumerate(["Default", "30", "60", "90", "120"]):
                if item == fps_val:
                    idx = i
                    break
            self.combo_fps.setCurrentIndex(idx)

            # Video Codec
            vcodec = s.get("video_codec", "h264").lower()
            if "h265" in vcodec or "hevc" in vcodec:
                self.combo_vcodec.setCurrentIndex(1)
            elif "av1" in vcodec:
                self.combo_vcodec.setCurrentIndex(2)
            else:
                self.combo_vcodec.setCurrentIndex(0)

            # Audio
            self.chk_audio.setChecked(s.get("audio_enabled", True))
            self.chk_audio_dup.setChecked(s.get("audio_dup", False))
            acodec = s.get("audio_codec", "opus").lower()
            if "aac" in acodec:
                self.combo_acodec.setCurrentIndex(1)
            elif "raw" in acodec:
                self.combo_acodec.setCurrentIndex(2)
            elif "flac" in acodec:
                self.combo_acodec.setCurrentIndex(3)
            else:
                self.combo_acodec.setCurrentIndex(0)

            # Flags
            self.chk_turn_off.setChecked(s.get("turn_screen_off", False))
            self.chk_stay_awake.setChecked(s.get("stay_awake", True))
            self.chk_force_stay_awake.setChecked(s.get("force_stay_awake", True))
            self.chk_always_top.setChecked(s.get("always_on_top", False))
            self.chk_fullscreen.setChecked(s.get("fullscreen", False))
            self.chk_borderless.setChecked(s.get("borderless", False))
            self.chk_companion_toolbar.setChecked(s.get("enable_companion_toolbar", self.config.get("enable_companion_toolbar", True)))
            self.chk_show_touches.setChecked(s.get("show_touches", False))
            self.chk_clipboard.setChecked(s.get("sync_clipboard", True))
            self.chk_record.setChecked(s.get("record", False))
            self.edit_rec_path.setText(s.get("record_path", ""))

            # Window Dimensions & Placement
            win_w = str(s.get("window_width", ""))
            win_h = str(s.get("window_height", ""))
            self.edit_win_width.setText(win_w)
            self.edit_win_height.setText(win_h)
            self.edit_win_x.setText(str(s.get("window_x", "")))
            self.edit_win_y.setText(str(s.get("window_y", "")))

            # Match combo preset
            if not win_w and not win_h:
                self.combo_win_preset.setCurrentIndex(0)
            elif win_w == "420" and win_h == "900":
                self.combo_win_preset.setCurrentIndex(1)
            elif win_w == "540" and win_h == "1140":
                self.combo_win_preset.setCurrentIndex(2)
            elif win_w == "720" and win_h == "1520":
                self.combo_win_preset.setCurrentIndex(3)
            elif win_w == "900" and win_h == "1200":
                self.combo_win_preset.setCurrentIndex(4)
            else:
                self.combo_win_preset.setCurrentIndex(5)

            # Special Mode
            if s.get("otg_mode", False):
                self.combo_mode.setCurrentIndex(1)
            elif s.get("camera_mode", False):
                self.combo_mode.setCurrentIndex(2)
            elif s.get("no_video", False):
                self.combo_mode.setCurrentIndex(3)
            else:
                self.combo_mode.setCurrentIndex(0)

            self.edit_custom_args.setText(s.get("custom_args", ""))
        finally:
            self._block_signals = False

    def load_presets_to_combo(self):
        presets = self.config.get("presets", {})
        self.combo_presets.blockSignals(True)
        self.combo_presets.clear()
        for name in presets.keys():
            self.combo_presets.addItem(name)
        active = self.config.get("active_preset", "Balanced (1080p 60fps 8M)")
        idx = self.combo_presets.findText(active)
        if idx >= 0:
            self.combo_presets.setCurrentIndex(idx)
        self.combo_presets.blockSignals(False)

    def _on_preset_changed(self, index: int):
        preset_name = self.combo_presets.currentText()
        if not preset_name:
            return
        preset_data = self.config.get_preset(preset_name)
        if preset_data:
            self.load_settings(preset_data)
            self.config.set("active_preset", preset_name)

    def _save_custom_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Enter a name for this preset:")
        if ok and name.strip():
            cur = self.get_settings()
            self.config.save_preset(name.strip(), cur)
            self.load_presets_to_combo()
            idx = self.combo_presets.findText(name.strip())
            if idx >= 0:
                self.combo_presets.setCurrentIndex(idx)

    def _delete_custom_preset(self):
        name = self.combo_presets.currentText()
        if not name:
            return
        if self.config.delete_preset(name):
            self.load_presets_to_combo()

    def _browse_record_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Recording Folder")
        if folder:
            self.edit_rec_path.setText(folder)
            self._on_setting_changed()
