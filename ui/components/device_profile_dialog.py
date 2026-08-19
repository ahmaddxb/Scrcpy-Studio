from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import AdbDevice
from core.config_manager import ConfigManager


class DeviceProfileDialog(QDialog):
    """Modern dark-themed modal for configuring per-device profiles, custom aliases, and presets."""

    profile_saved = Signal(str)  # serial

    def __init__(self, serial: str, config: ConfigManager, device: Optional[AdbDevice] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.serial = serial
        self.config = config
        self.device = device
        self.profile = self.config.get_device_profile(self.serial)

        alias = self.config.get_device_alias(self.serial, fallback=self.serial)
        self.setWindowTitle(f"Device Profile — {alias}")
        self.setFixedSize(520, 530)
        self.setModal(True)

        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # 1. Header Banner
        header = QFrame()
        header.setStyleSheet("background-color: #161822; border: 1px solid #282C3C; border-radius: 8px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 12, 14, 12)
        h_layout.setSpacing(12)

        lbl_icon = QLabel("📱")
        lbl_icon.setStyleSheet("font-size: 26px;")
        h_layout.addWidget(lbl_icon)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        lbl_title = QLabel("Device Profile & Settings")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38BDF8;")
        title_box.addWidget(lbl_title)

        model_info = f" ({self.device.model})" if self.device and self.device.model else ""
        lbl_sub = QLabel(f"Hardware Serial: {self.serial}{model_info}")
        lbl_sub.setStyleSheet("font-size: 11px; color: #64748B; font-family: monospace;")
        title_box.addWidget(lbl_sub)
        h_layout.addLayout(title_box)
        h_layout.addStretch(1)

        main_layout.addWidget(header)

        # 2. Main Form Card
        card = QFrame()
        card.setStyleSheet("background-color: #12141C; border: 1px solid #222634; border-radius: 8px;")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 16, 16, 16)
        c_layout.setSpacing(12)

        # Friendly Alias Section
        lbl_alias = QLabel("Device Friendly Name / Alias:")
        lbl_alias.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;")
        c_layout.addWidget(lbl_alias)

        self.edit_alias = QLineEdit()
        self.edit_alias.setFixedHeight(34)
        self.edit_alias.setPlaceholderText("e.g. Ahmad's Galaxy S25 Ultra")
        self.edit_alias.setStyleSheet(
            "QLineEdit { background-color: #1E222D; color: #F8FAFC; border: 1px solid #334155; border-radius: 6px; padding: 4px 10px; font-size: 13px; }"
            "QLineEdit:focus { border-color: #38BDF8; }"
        )
        c_layout.addWidget(self.edit_alias)

        # Preferred Preset Section
        lbl_preset = QLabel("Preferred Mirroring Preset:")
        lbl_preset.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;")
        c_layout.addWidget(lbl_preset)

        self.combo_preset = QComboBox()
        self.combo_preset.setFixedHeight(34)
        self.combo_preset.setStyleSheet(
            "QComboBox { background-color: #1E222D; color: #F8FAFC; border: 1px solid #334155; border-radius: 6px; padding: 4px 10px; font-size: 12px; }"
            "QComboBox::drop-down { border: none; width: 24px; }"
            "QComboBox QAbstractItemView { background-color: #1E222D; color: #F8FAFC; selection-background-color: #0284C7; }"
        )
        presets = self.config.get("presets", {})
        self.combo_preset.addItem("🌐 Follow Global Active Preset", "")
        for p_name in presets.keys():
            self.combo_preset.addItem(f"⚡ {p_name}", p_name)
        c_layout.addWidget(self.combo_preset)

        # Default Virtual Display Resolution Section
        lbl_disp = QLabel("Default Virtual Display Size:")
        lbl_disp.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;")
        c_layout.addWidget(lbl_disp)

        self.combo_display = QComboBox()
        self.combo_display.setFixedHeight(34)
        self.combo_display.setStyleSheet(
            "QComboBox { background-color: #1E222D; color: #F8FAFC; border: 1px solid #334155; border-radius: 6px; padding: 4px 10px; font-size: 12px; }"
            "QComboBox::drop-down { border: none; width: 24px; }"
            "QComboBox QAbstractItemView { background-color: #1E222D; color: #F8FAFC; selection-background-color: #0284C7; }"
        )
        disp_presets = self.config.get_virtual_display_presets()
        for dp in disp_presets:
            lbl = dp.get("label", dp.get("value", "Native"))
            val = dp.get("value", "")
            self.combo_display.addItem(lbl, val)
        c_layout.addWidget(self.combo_display)

        c_layout.addSpacing(4)

        # Checkbox 1: Independent Settings
        self.chk_custom_settings = QCheckBox("Enable Independent Settings Profile for this device")
        self.chk_custom_settings.setStyleSheet("QCheckBox { color: #E2E8F0; font-size: 12px; font-weight: 500; } QCheckBox::indicator { width: 16px; height: 16px; }")
        c_layout.addWidget(self.chk_custom_settings)

        # Checkbox 2: Pinning
        self.chk_pinned = QCheckBox("📌 Remember & Pin this device in sidebar across restarts")
        self.chk_pinned.setStyleSheet("QCheckBox { color: #E2E8F0; font-size: 12px; font-weight: 500; } QCheckBox::indicator { width: 16px; height: 16px; }")
        c_layout.addWidget(self.chk_pinned)

        main_layout.addWidget(card)

        main_layout.addStretch(1)

        # 3. Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_row.addStretch(1)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.setFixedWidth(90)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("💾 Save Profile")
        self.btn_save.setObjectName("primaryBtn")
        self.btn_save.setFixedHeight(34)
        self.btn_save.setFixedWidth(130)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._save_profile)
        btn_row.addWidget(self.btn_save)

        main_layout.addLayout(btn_row)

    def _load_values(self):
        # Load Alias: Check custom alias first, fallback to device display_name or clean model
        alias = self.config.get_device_alias(self.serial, fallback="")
        if not alias or alias == self.serial:
            if self.device:
                alias = self.device.display_name
                if not alias or alias == "Unknown" or alias == self.serial:
                    alias = self.device.model.replace("_", " ") if (self.device.model and self.device.model != "Unknown") else ""
            else:
                alias = ""
        self.edit_alias.setText(alias)

        # Load Preferred Preset
        active_preset = self.profile.get("active_preset", "")
        idx = self.combo_preset.findData(active_preset)
        if idx >= 0:
            self.combo_preset.setCurrentIndex(idx)

        # Load Default Display
        disp_res = self.profile.get("default_display_res", "")
        idx_disp = self.combo_display.findData(disp_res)
        if idx_disp >= 0:
            self.combo_display.setCurrentIndex(idx_disp)

        # Checkboxes
        self.chk_custom_settings.setChecked(self.profile.get("use_custom_settings", True))
        self.chk_pinned.setChecked(self.config.is_pinned(self.serial))

    def _save_profile(self):
        alias = self.edit_alias.text().strip()
        # If user leaves empty or puts raw serial, fallback to hardware display name
        if not alias or alias == self.serial:
            if self.device and self.device.display_name and self.device.display_name != self.serial:
                alias = self.device.display_name
            else:
                alias = self.serial

        preferred_preset = self.combo_preset.currentData()
        display_res = self.combo_display.currentData()
        use_custom = self.chk_custom_settings.isChecked()
        is_pinned = self.chk_pinned.isChecked()

        # Update profile
        self.profile["alias"] = alias
        self.profile["active_preset"] = preferred_preset
        self.profile["default_display_res"] = display_res
        self.profile["use_custom_settings"] = use_custom

        self.config.save_device_profile(self.serial, self.profile)
        self.config.set_device_alias(self.serial, alias)

        # Handle Pin
        if is_pinned:
            is_wireless = ":" in self.serial or (self.device.is_wireless if self.device else False)
            self.config.pin_device(self.serial, alias, is_wireless=is_wireless)
        else:
            self.config.unpin_device(self.serial)

        self.profile_saved.emit(self.serial)
        self.accept()
