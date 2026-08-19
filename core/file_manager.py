from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from core.adb_manager import AdbManager


class FileTransferWorker(QThread):
    """Background worker for installing APKs or pushing files without freezing the GUI."""

    progress = Signal(str)  # status message
    finished = Signal(bool, str)  # success, message

    def __init__(self, adb: AdbManager, serial: str, file_path: str, is_apk: bool = False, remote_dir: str = "/sdcard/Download/", parent=None):
        super().__init__(parent)
        self.adb = adb
        self.serial = serial
        self.file_path = file_path
        self.is_apk = is_apk
        self.remote_dir = remote_dir

    def run(self):
        p = Path(self.file_path)
        if not p.exists():
            self.finished.emit(False, f"File does not exist: {self.file_path}")
            return

        if self.is_apk or p.suffix.lower() == ".apk":
            self.progress.emit(f"Installing {p.name} on {self.serial}...")
            ok, msg = self.adb.install_apk(self.serial, self.file_path)
            if ok:
                self.finished.emit(True, f"Successfully installed {p.name}")
            else:
                self.finished.emit(False, f"Installation failed: {msg}")
        else:
            self.progress.emit(f"Pushing {p.name} to {self.remote_dir}...")
            ok, msg = self.adb.push_file(self.serial, self.file_path, self.remote_dir)
            if ok:
                self.finished.emit(True, f"Successfully pushed {p.name} to {self.remote_dir}")
            else:
                self.finished.emit(False, f"File push failed: {msg}")
