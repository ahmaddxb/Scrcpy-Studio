from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.scrcpy_updater import ScrcpyDownloadWorker, ScrcpyUpdateChecker


class ScrcpyUpdaterDialog(QDialog):
    """Modern UI dialog for checking, downloading, and auto-updating official Scrcpy releases from GitHub."""

    scrcpy_updated = Signal(str)  # Emits new version string when update completes

    def __init__(self, config: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config
        self.checker: Optional[ScrcpyUpdateChecker] = None
        self.downloader: Optional[ScrcpyDownloadWorker] = None
        self.latest_release_info: dict = {}

        self.setWindowTitle("Scrcpy Binary Updater")
        self.setFixedSize(540, 520)
        self.setModal(True)

        self._setup_ui()
        self._check_for_updates()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. Header Banner
        header = QFrame()
        header.setStyleSheet("background-color: #161822; border: 1px solid #282C3C; border-radius: 8px; padding: 6px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 10, 12, 10)

        lbl_icon = QLabel("⚡")
        lbl_icon.setStyleSheet("font-size: 24px;")
        h_layout.addWidget(lbl_icon)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("Scrcpy Runtime Manager")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38BDF8;")
        title_box.addWidget(lbl_title)

        lbl_sub = QLabel("Official Genymobile/scrcpy 64-bit Windows release channel")
        lbl_sub.setStyleSheet("font-size: 11px; color: #64748B;")
        title_box.addWidget(lbl_sub)
        h_layout.addLayout(title_box)
        h_layout.addStretch(1)

        layout.addWidget(header)

        # 2. Version Comparison Card
        ver_card = QFrame()
        ver_card.setStyleSheet("background-color: #12141C; border: 1px solid #222634; border-radius: 8px;")
        ver_layout = QVBoxLayout(ver_card)
        ver_layout.setContentsMargins(14, 12, 14, 12)
        ver_layout.setSpacing(8)

        # Installed row
        row_curr = QHBoxLayout()
        lbl_c_title = QLabel("Installed Version:")
        lbl_c_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")
        row_curr.addWidget(lbl_c_title)

        current_ver = self.config.get_scrcpy_version()
        self.lbl_curr_ver = QLabel("")
        self._update_version_display()
        row_curr.addWidget(self.lbl_curr_ver)
        row_curr.addStretch(1)
        ver_layout.addLayout(row_curr)

        # Latest row
        row_latest = QHBoxLayout()
        lbl_l_title = QLabel("Latest on GitHub:")
        lbl_l_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")
        row_latest.addWidget(lbl_l_title)

        self.lbl_latest_ver = QLabel("Checking...")
        self.lbl_latest_ver.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 13px; font-family: monospace;")
        row_latest.addWidget(self.lbl_latest_ver)
        row_latest.addStretch(1)

        self.badge_status = QLabel("Checking...")
        self.badge_status.setStyleSheet("background: #334155; color: #94A3B8; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold;")
        row_latest.addWidget(self.badge_status)
        ver_layout.addLayout(row_latest)

        layout.addWidget(ver_card)

        # 3. Changelog / Release Notes
        layout.addWidget(QLabel("Release Notes:"))
        self.text_notes = QTextBrowser()
        self.text_notes.setOpenExternalLinks(True)
        self.text_notes.setStyleSheet(
            "QTextBrowser { background-color: #0E1017; color: #CBD5E1; border: 1px solid #222634; border-radius: 6px; padding: 8px; font-size: 11px; font-family: sans-serif; }"
        )
        self.text_notes.setPlaceholderText("Querying GitHub release notes...")
        layout.addWidget(self.text_notes, 1)

        # 4. Progress Bar & Status
        self.lbl_progress_status = QLabel("Ready")
        self.lbl_progress_status.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(self.lbl_progress_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #1E222D; border-radius: 3px; } "
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8); border-radius: 3px; }"
        )
        layout.addWidget(self.progress_bar)

        # 5. Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_check = QPushButton("🔄 Check Again")
        self.btn_check.setFixedHeight(32)
        self.btn_check.setCursor(Qt.PointingHandCursor)
        self.btn_check.clicked.connect(self._check_for_updates)
        btn_row.addWidget(self.btn_check)

        btn_row.addStretch(1)

        self.btn_action = QPushButton("⬇️ Download Scrcpy")
        self.btn_action.setObjectName("primaryBtn")
        self.btn_action.setFixedHeight(32)
        self.btn_action.setEnabled(False)
        self.btn_action.setCursor(Qt.PointingHandCursor)
        self.btn_action.clicked.connect(self._start_download_and_install)
        btn_row.addWidget(self.btn_action)

        self.btn_close = QPushButton("Close")
        self.btn_close.setFixedHeight(32)
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_close)

        layout.addLayout(btn_row)

    def _update_version_display(self):
        """Update the installed version label with matching clean styling."""
        if self.config.is_scrcpy_installed():
            current_ver = self.config.get_scrcpy_version()
            self.lbl_curr_ver.setText(current_ver)
            self.lbl_curr_ver.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 13px; font-family: monospace;")
        else:
            self.lbl_curr_ver.setText("Not Downloaded")
            self.lbl_curr_ver.setStyleSheet("color: #F87171; font-weight: bold; font-size: 13px; font-family: monospace;")

    def _check_for_updates(self):
        self.btn_check.setEnabled(False)
        self.btn_action.setEnabled(False)
        self.lbl_latest_ver.setText("Checking GitHub...")
        self.badge_status.setText("Connecting...")
        self.badge_status.setStyleSheet("background: #334155; color: #94A3B8; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold;")
        self.lbl_progress_status.setText("Fetching release metadata from GitHub...")

        current_ver = self.config.get_scrcpy_version()
        self.checker = ScrcpyUpdateChecker(current_ver, self)
        self.checker.check_finished.connect(self._on_check_finished)
        self.checker.start()

    def _on_check_finished(self, has_update: bool, release_info: dict, message: str):
        self.btn_check.setEnabled(True)
        self.latest_release_info = release_info

        if not release_info:
            self.lbl_latest_ver.setText("Failed")
            self.badge_status.setText("Error")
            self.badge_status.setStyleSheet("background: #7F1D1D; color: #FCA5A5; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold;")
            self.lbl_progress_status.setText(message)
            self.text_notes.setPlainText(message)
            return

        tag = release_info.get("tag", "")
        self.lbl_latest_ver.setText(tag)

        # Render release notes
        body = release_info.get("body", "No release notes provided.")
        self.text_notes.setMarkdown(body)

        self._update_version_display()

        is_installed = self.config.is_scrcpy_installed()
        if not is_installed:
            self.badge_status.setText("Ready to Download ⬇️")
            self.badge_status.setStyleSheet("background: #0369A1; color: #E0F2FE; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold;")
            self.btn_action.setText(f"⬇️ Download & Install {tag}")
            self.btn_action.setEnabled(True)
            self.lbl_progress_status.setText(f"Official Scrcpy runtime {tag} is ready to download ({release_info.get('asset_size', 0)/(1024*1024):.1f} MB)")
        elif has_update:
            self.badge_status.setText("Update Available! ✨")
            self.badge_status.setStyleSheet("background: #0369A1; color: #E0F2FE; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold;")
            self.btn_action.setText(f"⬇️ Update to {tag}")
            self.btn_action.setEnabled(True)
            self.lbl_progress_status.setText(f"New release {tag} available ({release_info.get('asset_size', 0)/(1024*1024):.1f} MB)")
        else:
            self.badge_status.setText("Up to Date ✓")
            self.badge_status.setStyleSheet("background: #14532D; color: #BBF7D0; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold;")
            self.btn_action.setText("🔄 Reinstall / Repair Scrcpy")
            self.btn_action.setEnabled(True)
            self.lbl_progress_status.setText(f"Active version {tag} matches the latest official release.")

    def _start_download_and_install(self):
        download_url = self.latest_release_info.get("download_url", "")
        if not download_url:
            QMessageBox.warning(self, "No Download URL", "Could not find binary download link.")
            return

        self.btn_check.setEnabled(False)
        self.btn_action.setEnabled(False)
        self.btn_close.setEnabled(False)
        self.progress_bar.setValue(0)

        target_dir = self.config.get_scrcpy_bin_dir()
        self.downloader = ScrcpyDownloadWorker(download_url, target_dir, self)
        self.downloader.progress_updated.connect(self._on_download_progress)
        self.downloader.step_changed.connect(lambda text: self.lbl_progress_status.setText(text))
        self.downloader.installation_completed.connect(self._on_installation_completed)
        self.downloader.start()

    def _on_download_progress(self, downloaded: int, total: int, status_text: str):
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.progress_bar.setValue(pct)
        self.lbl_progress_status.setText(status_text)

    def _on_installation_completed(self, success: bool, message: str):
        self.btn_check.setEnabled(True)
        self.btn_action.setEnabled(True)
        self.btn_close.setEnabled(True)

        if success:
            self.progress_bar.setValue(100)
            self._update_version_display()
            self.badge_status.setText("Up to Date ✓")
            self.badge_status.setStyleSheet("background: #14532D; color: #BBF7D0; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold;")
            self.btn_action.setText("🔄 Reinstall / Repair Scrcpy")
            self.lbl_progress_status.setText("Update installed successfully!")
            new_ver = self.config.get_scrcpy_version()
            self.scrcpy_updated.emit(new_ver)
            QMessageBox.information(self, "Scrcpy Updated", f"Scrcpy runtime has been updated successfully to {new_ver}!\n\nLocation: {self.config.get_scrcpy_bin_dir()}")
        else:
            self.lbl_progress_status.setText(f"Installation error: {message}")
            QMessageBox.critical(self, "Update Failed", f"Failed to install Scrcpy update:\n\n{message}")

    def _cleanup_workers(self):
        checker = getattr(self, "checker", None)
        downloader = getattr(self, "downloader", None)
        self.checker = None
        self.downloader = None

        if checker:
            try:
                checker.check_finished.disconnect()
            except Exception:
                pass
            if checker.isRunning():
                checker.quit()
                checker.wait(1000)

        if downloader:
            try:
                downloader.progress.disconnect()
                downloader.finished.disconnect()
            except Exception:
                pass
            if downloader.isRunning():
                downloader.quit()
                downloader.wait(1000)

    def reject(self):
        self._cleanup_workers()
        super().reject()

    def accept(self):
        self._cleanup_workers()
        super().accept()

    def closeEvent(self, event):
        self._cleanup_workers()
        super().closeEvent(event)
