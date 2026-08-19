from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import AdbManager


class PinInjectorDialog(QDialog):
    """Secure popup dialog to inject PINs, passwords, or numeric codes directly into blacked-out apps."""

    pin_injected = Signal(str, str)  # serial, description

    def __init__(self, serial: str, adb: AdbManager, device_name: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.serial = serial
        self.adb = adb
        self.device_name = device_name or serial

        self.setWindowTitle(f"🔑 Inject PIN / Password — {self.device_name}")
        self.setFixedSize(400, 480)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(12)

        # 1. Header Banner
        header = QFrame()
        header.setStyleSheet("background-color: #161822; border: 1px solid #282C3C; border-radius: 8px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 10, 12, 10)
        h_layout.setSpacing(10)

        lbl_icon = QLabel("🔑")
        lbl_icon.setStyleSheet("font-size: 24px;")
        h_layout.addWidget(lbl_icon)

        t_layout = QVBoxLayout()
        t_layout.setSpacing(2)
        lbl_title = QLabel("Direct PIN / Credential Injector")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #38BDF8;")
        t_layout.addWidget(lbl_title)

        lbl_sub = QLabel(f"Target: {self.device_name}")
        lbl_sub.setStyleSheet("font-size: 11px; color: #64748B; font-family: monospace;")
        t_layout.addWidget(lbl_sub)
        h_layout.addLayout(t_layout)
        h_layout.addStretch(1)

        main_layout.addWidget(header)

        # Tip Note
        lbl_note = QLabel(
            "💡 Works when the screen is black on banking or biometric prompts (FLAG_SECURE)."
        )
        lbl_note.setWordWrap(True)
        lbl_note.setStyleSheet("color: #94A3B8; font-size: 11px; font-style: italic;")
        main_layout.addWidget(lbl_note)

        # 2. PIN Input Box with Show/Hide Toggle
        input_container = QFrame()
        input_container.setStyleSheet("background-color: #12141C; border: 1px solid #282C3C; border-radius: 6px;")
        in_layout = QHBoxLayout(input_container)
        in_layout.setContentsMargins(8, 4, 8, 4)
        in_layout.setSpacing(6)

        self.edit_pin = QLineEdit()
        self.edit_pin.setPlaceholderText("Enter PIN or Password...")
        self.edit_pin.setEchoMode(QLineEdit.Password)
        self.edit_pin.setStyleSheet(
            "QLineEdit { background: transparent; color: #F8FAFC; border: none; font-size: 16px; font-weight: bold; letter-spacing: 2px; }"
        )
        self.edit_pin.returnPressed.connect(self._inject_pin)
        in_layout.addWidget(self.edit_pin, 1)

        self.btn_toggle_echo = QPushButton("👁️")
        self.btn_toggle_echo.setFixedSize(28, 28)
        self.btn_toggle_echo.setToolTip("Show / Hide PIN")
        self.btn_toggle_echo.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 13px; }"
            "QPushButton:hover { background: #232734; border-radius: 4px; }"
        )
        self.btn_toggle_echo.clicked.connect(self._toggle_echo_mode)
        in_layout.addWidget(self.btn_toggle_echo)

        main_layout.addWidget(input_container)

        # Auto Enter Checkbox
        self.chk_auto_enter = QCheckBox("Automatically send Enter / Submit (Keycode 66)")
        self.chk_auto_enter.setChecked(True)
        self.chk_auto_enter.setStyleSheet("color: #CBD5E1; font-size: 11px; font-weight: 500;")
        main_layout.addWidget(self.chk_auto_enter)

        # 3. Numeric On-Screen Keypad
        keypad_frame = QFrame()
        keypad_frame.setStyleSheet("background-color: #141620; border: 1px solid #232734; border-radius: 8px;")
        kp_layout = QGridLayout(keypad_frame)
        kp_layout.setContentsMargins(10, 10, 10, 10)
        kp_layout.setSpacing(6)

        # Digits 1-9
        digits = [
            ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
            ("🧹 Clear", 3, 0), ("0", 3, 1), ("⌫", 3, 2),
        ]

        for text, r, c in digits:
            btn = QPushButton(text)
            btn.setFixedHeight(34)
            btn.setCursor(Qt.PointingHandCursor)
            if text == "🧹 Clear":
                btn.setStyleSheet("QPushButton { background-color: #1E222D; color: #94A3B8; border: 1px solid #334155; border-radius: 6px; font-size: 11px; font-weight: bold; } QPushButton:hover { background-color: #2D3240; color: #EF4444; }")
                btn.clicked.connect(self.edit_pin.clear)
            elif text == "⌫":
                btn.setStyleSheet("QPushButton { background-color: #1E222D; color: #94A3B8; border: 1px solid #334155; border-radius: 6px; font-size: 13px; font-weight: bold; } QPushButton:hover { background-color: #2D3240; color: #F59E0B; }")
                btn.clicked.connect(self.edit_pin.backspace)
            else:
                btn.setStyleSheet("QPushButton { background-color: #1E222D; color: #F8FAFC; border: 1px solid #334155; border-radius: 6px; font-size: 14px; font-weight: bold; } QPushButton:hover { background-color: #0284C7; color: #FFFFFF; border-color: #38BDF8; }")
                btn.clicked.connect(lambda _, d=text: self._on_digit_clicked(d))
            kp_layout.addWidget(btn, r, c)

        main_layout.addWidget(keypad_frame)

        main_layout.addStretch(1)

        # 4. Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.setFixedWidth(80)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_send = QPushButton("🚀 Inject PIN to App")
        self.btn_send.setObjectName("primaryBtn")
        self.btn_send.setFixedHeight(34)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.clicked.connect(self._inject_pin)
        btn_row.addWidget(self.btn_send, 1)

        main_layout.addLayout(btn_row)

        self.edit_pin.setFocus()

    def _on_digit_clicked(self, digit: str):
        self.edit_pin.insert(digit)

    def _toggle_echo_mode(self):
        if self.edit_pin.echoMode() == QLineEdit.Password:
            self.edit_pin.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_echo.setText("🔒")
        else:
            self.edit_pin.setEchoMode(QLineEdit.Password)
            self.btn_toggle_echo.setText("👁️")

    def _inject_pin(self):
        pin = self.edit_pin.text()
        if not pin:
            return

        # 1. Send text directly to focused window via ADB
        ok = self.adb.send_text(self.serial, pin)

        # 2. Optionally send ENTER keycode (66)
        if self.chk_auto_enter.isChecked():
            self.adb.send_keyevent(self.serial, 66)

        msg = f"Injected credential ({len(pin)} chars) into {self.serial}"
        self.pin_injected.emit(self.serial, msg)
        self.accept()
