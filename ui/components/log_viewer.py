from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LogViewer(QWidget):
    """Real-time console output window for ADB & Scrcpy processes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._msg_count = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 1. Header controls (Count label, Copy, Clear)
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        self.lbl_count = QLabel("0 messages logged")
        self.lbl_count.setStyleSheet("color: #64748B; font-size: 11px;")
        ctrl_row.addWidget(self.lbl_count)

        ctrl_row.addStretch(1)

        self.btn_copy = QPushButton("📋 Copy Logs")
        self.btn_copy.setFixedHeight(24)
        self.btn_copy.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self.btn_copy.clicked.connect(self._copy_all)
        ctrl_row.addWidget(self.btn_copy)

        self.btn_clear = QPushButton("🗑️ Clear")
        self.btn_clear.setFixedHeight(24)
        self.btn_clear.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self.btn_clear.clicked.connect(self.clear)
        ctrl_row.addWidget(self.btn_clear)

        layout.addLayout(ctrl_row)

        # 2. Text log area
        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setMaximumBlockCount(1000)
        self.text_area.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0B0C10;
                color: #A0AEC0;
                font-family: 'Consolas', 'Cascadia Code', monospace;
                font-size: 11px;
                line-height: 1.4;
                border: 1px solid #1E212A;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        layout.addWidget(self.text_area, 1)

    def _copy_all(self):
        if self.text_area:
            self.text_area.selectAll()
            self.text_area.copy()

    def append_log(self, source: str, message: str):
        time_str = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{time_str}] [{source}] {message}"
        self.text_area.appendPlainText(formatted)
        self.text_area.moveCursor(QTextCursor.End)
        self._msg_count += 1
        self.lbl_count.setText(f"{self._msg_count} messages logged")

    def clear(self):
        self.text_area.clear()
        self._msg_count = 0
        self.lbl_count.setText("0 messages logged")
