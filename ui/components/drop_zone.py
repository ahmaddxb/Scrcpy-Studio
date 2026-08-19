from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import AdbManager
from core.file_manager import FileTransferWorker


class DropZoneWidget(QFrame):
    """Interactive drag-and-drop zone to install APKs or push files to the active device."""

    status_message = Signal(str)

    def __init__(self, adb: AdbManager, parent=None):
        super().__init__(parent)
        self.adb = adb
        self.selected_serial: Optional[str] = None
        self.current_worker: Optional[FileTransferWorker] = None

        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        self._setup_ui()
        self._set_idle_style()

    def set_device(self, serial: Optional[str]):
        self.selected_serial = serial
        self.setEnabled(bool(serial))
        if not serial:
            self.lbl_main.setText("Select a connected device to install APKs or transfer files")
        else:
            self.lbl_main.setText("Drag & Drop APK or Files here to install / push to device")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        self.lbl_icon = QLabel("📦")
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        self.lbl_icon.setStyleSheet("font-size: 24px;")
        layout.addWidget(self.lbl_icon)

        self.lbl_main = QLabel("Drag & Drop APK or Files here to install / push to device")
        self.lbl_main.setAlignment(Qt.AlignCenter)
        self.lbl_main.setWordWrap(True)
        self.lbl_main.setStyleSheet("font-weight: 500; color: #CBD5E1; font-size: 12px;")
        layout.addWidget(self.lbl_main)

        self.lbl_sub = QLabel("APKs will auto-install; other files are sent to /sdcard/Download/")
        self.lbl_sub.setAlignment(Qt.AlignCenter)
        self.lbl_sub.setStyleSheet("font-size: 10px; color: #64748B;")
        layout.addWidget(self.lbl_sub)

        # Progress bar (hidden when idle)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Browse buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setAlignment(Qt.AlignCenter)

        self.btn_pick_apk = QPushButton("📥 Select APK")
        self.btn_pick_apk.setCursor(Qt.PointingHandCursor)
        self.btn_pick_apk.clicked.connect(self._browse_apk)
        btn_row.addWidget(self.btn_pick_apk)

        self.btn_pick_file = QPushButton("📁 Send Files")
        self.btn_pick_file.setCursor(Qt.PointingHandCursor)
        self.btn_pick_file.clicked.connect(self._browse_files)
        btn_row.addWidget(self.btn_pick_file)

        layout.addLayout(btn_row)

    def _browse_apk(self):
        if not self.selected_serial:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select APK to Install", "", "Android Package (*.apk)")
        if path:
            self._handle_file(path)

    def _browse_files(self):
        if not self.selected_serial:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Push", "")
        for f in files:
            self._handle_file(f)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() and self.selected_serial:
            event.acceptProposedAction()
            self._set_active_drop_style()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_idle_style()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self._set_idle_style()
        if not self.selected_serial:
            return

        urls = event.mimeData().urls()
        for url in urls:
            local_path = url.toLocalFile()
            if local_path:
                self._handle_file(local_path)
        event.acceptProposedAction()

    def _handle_file(self, file_path: str):
        if not self.selected_serial:
            return

        is_apk = Path(file_path).suffix.lower() == ".apk"
        self.progress_bar.setVisible(True)
        self.lbl_sub.setText(f"Processing {Path(file_path).name}...")

        self.current_worker = FileTransferWorker(self.adb, self.selected_serial, file_path, is_apk=is_apk)
        self.current_worker.progress.connect(self._on_worker_progress)
        self.current_worker.finished.connect(self._on_worker_finished)
        self.current_worker.start()

    def _on_worker_progress(self, msg: str):
        self.lbl_sub.setText(msg)
        self.status_message.emit(msg)

    def _on_worker_finished(self, ok: bool, msg: str):
        self.progress_bar.setVisible(False)
        self.lbl_sub.setText(msg)
        self.status_message.emit(msg)

    def _set_idle_style(self):
        self.setStyleSheet("""
            QFrame#dropZone {
                background-color: #171920;
                border: 2px dashed #2E3340;
                border-radius: 8px;
            }
        """)

    def _set_active_drop_style(self):
        self.setStyleSheet("""
            QFrame#dropZone {
                background-color: #1E2433;
                border: 2px dashed #3B82F6;
                border-radius: 8px;
            }
        """)
