from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import AdbCommandWorker, AdbManager

SNIPPET_PRESETS = [
    ("Battery Status", "shell dumpsys battery"),
    ("Android Version", "shell getprop ro.build.version.release"),
    ("Device Model & Brand", "shell getprop ro.product.model"),
    ("List Installed Apps (3rd party)", "shell pm list packages -3"),
    ("Current Focused App/Activity", "shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'"),
    ("Screen Resolution & DPI", "shell wm size && adb shell wm density"),
    ("Wi-Fi IP Address", "shell ip -f inet addr show wlan0"),
    ("Disk / Storage Free Space", "shell df -h /sdcard"),
    ("Recent Logcat Dump (50 lines)", "shell logcat -d -t 50"),
    ("Input Text String", "shell input text 'HelloFromScrcpy'"),
    ("Open Device Settings", "shell am start -a android.settings.SETTINGS"),
    ("Set Screen Timeout (30s)", "shell settings put system screen_off_timeout 30000"),
    ("Set Screen Timeout (24h)", "shell settings put system screen_off_timeout 86400000"),
    ("Get Screen Timeout", "shell settings get system screen_off_timeout"),
    ("Turn Screen Off", "shell input keyevent 26"),
    ("Wake Screen Up", "shell input keyevent 224"),
    ("Restart in TCPIP 5555", "tcpip 5555"),
    ("Reboot Device", "reboot"),
    ("Reboot to Recovery", "reboot recovery"),
    ("Reboot to Bootloader", "reboot bootloader"),
]


class CommandInjectorWidget(QWidget):
    """Clean and spacious ADB command injection terminal with snippet presets and history."""

    command_executed = Signal(str, str)  # command, result

    def __init__(self, adb: AdbManager, parent=None):
        super().__init__(parent)
        self.adb = adb
        self.selected_serial: Optional[str] = None
        self.worker: Optional[AdbCommandWorker] = None
        self.history: List[str] = []

        self._setup_ui()

    def set_device(self, serial: Optional[str]):
        self.selected_serial = serial
        if serial:
            self.chk_target_device.setText(f"Target: {serial}")
            self.chk_target_device.setToolTip(f"Prepend -s {serial} to commands")
            self.chk_target_device.setEnabled(True)
        else:
            self.chk_target_device.setText("Target: (No device)")
            self.chk_target_device.setToolTip("No device currently connected")
            self.chk_target_device.setEnabled(False)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 1. Main Command Input Bar
        cmd_bar = QHBoxLayout()
        cmd_bar.setSpacing(6)

        prefix_lbl = QLabel("adb")
        prefix_lbl.setStyleSheet(
            "font-family: monospace; font-weight: bold; color: #10B981; "
            "padding: 5px 8px; background-color: #171920; border-radius: 5px; "
            "border: 1px solid #282C37; font-size: 12px;"
        )
        cmd_bar.addWidget(prefix_lbl)

        self.edit_cmd = QLineEdit()
        self.edit_cmd.setPlaceholderText("Type command (e.g. shell pm list packages, shell dumpsys battery, reboot)...")
        self.edit_cmd.returnPressed.connect(self.execute_command)
        cmd_bar.addWidget(self.edit_cmd, 1)

        self.combo_snippets = QComboBox()
        self.combo_snippets.addItem("⚡ Snippets ▼", "")
        for label, cmd in SNIPPET_PRESETS:
            self.combo_snippets.addItem(f"{label}  ({cmd})", cmd)
        self.combo_snippets.currentIndexChanged.connect(self._on_snippet_selected)
        self.combo_snippets.setFixedWidth(135)
        # Expand dropdown popup list so all snippet titles & commands are fully readable
        self.combo_snippets.view().setMinimumWidth(380)
        cmd_bar.addWidget(self.combo_snippets)

        self.btn_run = QPushButton("⚡ Execute")
        self.btn_run.setObjectName("primaryBtn")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.clicked.connect(self.execute_command)
        cmd_bar.addWidget(self.btn_run)

        layout.addLayout(cmd_bar)

        # 2. Terminal Output Display
        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setStyleSheet("""
            QTextEdit {
                background-color: #0B0C10;
                color: #C5C6C7;
                font-family: 'Consolas', 'Cascadia Code', monospace;
                font-size: 11px;
                line-height: 1.4;
                border: 1px solid #1F222B;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        layout.addWidget(self.output_view, 1)

        # 3. Bottom Toolbar (Target checkbox, Quick chips, Copy & Clear)
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(6)

        self.chk_target_device = QCheckBox("Target: (No device)")
        self.chk_target_device.setChecked(True)
        self.chk_target_device.setStyleSheet("font-size: 11px; color: #38BDF8; font-weight: 500;")
        bottom_bar.addWidget(self.chk_target_device)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #2D3139;")
        bottom_bar.addWidget(sep)

        # Quick action chips
        chip_bat = QPushButton("🔋 Battery")
        chip_bat.setProperty("class", "quickAction")
        chip_bat.clicked.connect(lambda: self.run_snippet("shell dumpsys battery"))
        bottom_bar.addWidget(chip_bat)

        chip_apps = QPushButton("📦 3rd Party Apps")
        chip_apps.setProperty("class", "quickAction")
        chip_apps.clicked.connect(lambda: self.run_snippet("shell pm list packages -3"))
        bottom_bar.addWidget(chip_apps)

        chip_ip = QPushButton("🌐 Wi-Fi IP")
        chip_ip.setProperty("class", "quickAction")
        chip_ip.clicked.connect(lambda: self.run_snippet("shell ip -f inet addr show wlan0"))
        bottom_bar.addWidget(chip_ip)

        chip_reboot = QPushButton("🔄 Reboot")
        chip_reboot.setProperty("class", "quickAction")
        chip_reboot.clicked.connect(lambda: self.run_snippet("reboot"))
        bottom_bar.addWidget(chip_reboot)

        bottom_bar.addStretch(1)

        btn_copy = QPushButton("📋 Copy")
        btn_copy.setFixedHeight(24)
        btn_copy.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        btn_copy.clicked.connect(self._copy_all)
        bottom_bar.addWidget(btn_copy)

        btn_clear = QPushButton("🗑️ Clear")
        btn_clear.setFixedHeight(24)
        btn_clear.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        btn_clear.clicked.connect(self.output_view.clear)
        bottom_bar.addWidget(btn_clear)

        layout.addLayout(bottom_bar)

    def _on_snippet_selected(self, index: int):
        cmd = self.combo_snippets.currentData()
        if cmd:
            self.edit_cmd.setText(cmd)
            # Reset combo back to placeholder
            self.combo_snippets.blockSignals(True)
            self.combo_snippets.setCurrentIndex(0)
            self.combo_snippets.blockSignals(False)

    def run_snippet(self, cmd: str):
        self.edit_cmd.setText(cmd)
        self.execute_command()

    def execute_command(self):
        cmd_str = self.edit_cmd.text().strip()
        if not cmd_str:
            return

        target_serial = self.selected_serial if self.chk_target_device.isChecked() else None

        # Display command in output
        self._append_formatted(f"> adb {f'-s {target_serial} ' if target_serial else ''}{cmd_str}", "#38BDF8")
        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳ Running...")

        self.worker = AdbCommandWorker(self.adb, cmd_str, target_serial)
        self.worker.finished.connect(self._on_command_finished)
        self.worker.start()

    def _on_command_finished(self, code: int, stdout: str, stderr: str):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("⚡ Execute")

        if stdout:
            self._append_formatted(stdout, "#E2E8F0")
        if stderr:
            self._append_formatted(f"[STDERR] {stderr}", "#F87171")
        if not stdout and not stderr:
            status_text = "Command completed (no output)" if code == 0 else f"Command exited with code {code}"
            self._append_formatted(status_text, "#10B981" if code == 0 else "#F87171")

        self._append_formatted("─" * 45, "#2D3139")

        # Emit signal for main logs
        cmd_text = self.edit_cmd.text().strip()
        self.command_executed.emit(cmd_text, stdout or stderr)

    def _copy_all(self):
        if self.output_view:
            self.output_view.selectAll()
            self.output_view.copy()

    def stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(500)

    def _append_formatted(self, text: str, color_hex: str):
        cursor = self.output_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color_hex))
        cursor.insertText(text + "\n", fmt)
        self.output_view.moveCursor(QTextCursor.End)
