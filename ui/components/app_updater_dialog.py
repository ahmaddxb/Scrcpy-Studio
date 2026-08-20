from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
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

from core.app_updater import (
    APP_VERSION,
    AppUpdateChecker,
    AppUpdateInstaller,
    apply_update_and_restart,
)


class AppUpdaterDialog(QDialog):
    """Modern UI dialog for checking, downloading, and auto-updating Scrcpy Studio releases from GitHub."""

    app_updated = Signal(str)  # Emits new version string when update completes

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.checker: Optional[AppUpdateChecker] = None
        self.installer: Optional[AppUpdateInstaller] = None
        self.latest_release_info: dict = {}
        self.updater_bat_path: str = ""

        self.setWindowTitle("Scrcpy Studio In-App Updater")
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

        lbl_icon = QLabel("🚀")
        lbl_icon.setStyleSheet("font-size: 24px;")
        h_layout.addWidget(lbl_icon)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("Scrcpy Studio Self-Updater")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38BDF8;")
        title_box.addWidget(lbl_title)

        lbl_sub = QLabel("Official Scrcpy Studio GitHub release channel")
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
        lbl_c_title = QLabel("Current App Version:")
        lbl_c_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")
        row_curr.addWidget(lbl_c_title)

        self.lbl_curr_ver = QLabel(APP_VERSION)
        self.lbl_curr_ver.setStyleSheet("background-color: #1E293B; color: #38BDF8; font-weight: bold; padding: 2px 8px; border-radius: 4px; font-family: monospace;")
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

        self.lbl_status_badge = QLabel("")
        self.lbl_status_badge.setVisible(False)
        row_latest.addWidget(self.lbl_status_badge)

        ver_layout.addLayout(row_latest)
        layout.addWidget(ver_card)

        # 3. Release Notes / Changelog Viewer
        lbl_notes_title = QLabel("Release Notes & Changelog:")
        lbl_notes_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: bold;")
        layout.addWidget(lbl_notes_title)

        self.txt_notes = QTextBrowser()
        self.txt_notes.setOpenExternalLinks(True)
        self.txt_notes.setStyleSheet(
            "QTextBrowser { background-color: #0F1117; border: 1px solid #1E222D; border-radius: 6px; padding: 10px; color: #E2E8F0; font-size: 12px; line-height: 1.4; }"
        )
        self.txt_notes.setPlaceholderText("Checking GitHub for the latest release notes...")
        layout.addWidget(self.txt_notes, 1)

        # 4. Download Progress Card (Hidden until downloading)
        self.progress_card = QFrame()
        self.progress_card.setStyleSheet("background-color: #12141C; border: 1px solid #222634; border-radius: 8px;")
        p_layout = QVBoxLayout(self.progress_card)
        p_layout.setContentsMargins(14, 12, 14, 12)
        p_layout.setSpacing(6)

        self.lbl_progress_status = QLabel("Preparing update...")
        self.lbl_progress_status.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: 500;")
        p_layout.addWidget(self.lbl_progress_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #1E222D; border-radius: 6px; border: none; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8); border-radius: 6px; }"
        )
        p_layout.addWidget(self.progress_bar)

        self.lbl_progress_bytes = QLabel("")
        self.lbl_progress_bytes.setStyleSheet("color: #64748B; font-size: 11px; font-family: monospace;")
        p_layout.addWidget(self.lbl_progress_bytes)

        self.progress_card.setVisible(False)
        layout.addWidget(self.progress_card)

        # 5. Action Buttons Footer
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_check_again = QPushButton("🔄 Refresh")
        self.btn_check_again.setCursor(Qt.PointingHandCursor)
        self.btn_check_again.clicked.connect(self._check_for_updates)
        btn_row.addWidget(self.btn_check_again)

        btn_row.addStretch(1)

        self.btn_close = QPushButton("Close")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_close)

        self.btn_action = QPushButton("⚡ Update & Restart")
        self.btn_action.setObjectName("primaryBtn")
        self.btn_action.setCursor(Qt.PointingHandCursor)
        self.btn_action.setFixedHeight(34)
        self.btn_action.setEnabled(False)
        self.btn_action.setVisible(False)
        self.btn_action.clicked.connect(self._start_update_download)
        btn_row.addWidget(self.btn_action)

        layout.addLayout(btn_row)

    def _check_for_updates(self):
        self.lbl_latest_ver.setText("Checking GitHub API...")
        self.lbl_status_badge.setVisible(False)
        self.btn_action.setVisible(False)
        self.btn_action.setEnabled(False)
        self.btn_check_again.setEnabled(False)
        self.txt_notes.setHtml("<i>Contacting GitHub Releases API...</i>")

        self.checker = AppUpdateChecker(APP_VERSION, parent=self)
        self.checker.check_finished.connect(self._on_check_finished)
        self.checker.finished.connect(self.checker.deleteLater)
        self.checker.start()

    def _on_check_finished(self, has_update: bool, release_info: dict, msg: str):
        self.btn_check_again.setEnabled(True)

        if not release_info:
            self.lbl_latest_ver.setText("Check Failed")
            self.txt_notes.setHtml(f"<span style='color:#EF4444;'>{msg}</span>")
            return

        self.latest_release_info = release_info
        tag = release_info.get("tag", "Unknown")
        self.lbl_latest_ver.setText(tag)

        # Populate Changelog Viewer
        body_text = release_info.get("body", "").strip() or "<i>No release description provided on GitHub.</i>"
        html_body = body_text.replace("\n", "<br>")
        self.txt_notes.setHtml(
            f"<h3 style='color:#38BDF8; margin-bottom:4px;'>{release_info.get('name', tag)}</h3>"
            f"<p style='color:#94A3B8; font-size:11px; margin-top:0px;'>Tag: {tag} • Published: {release_info.get('published_at', '')[:10]}</p>"
            f"<hr style='border: 1px solid #232734;'>"
            f"<div style='color:#F1F5F9;'>{html_body}</div>"
        )

        if has_update:
            self.lbl_status_badge.setText("⚡ Update Available")
            self.lbl_status_badge.setStyleSheet(
                "background-color: #0369A1; color: #E0F2FE; font-weight: bold; font-size: 11px; padding: 2px 8px; border-radius: 4px;"
            )
            self.lbl_status_badge.setVisible(True)
            self.btn_action.setVisible(True)
            self.btn_action.setEnabled(True)
            self.btn_action.setText(f"⚡ Update to {tag}")
        else:
            self.lbl_status_badge.setText("✅ Up to Date")
            self.lbl_status_badge.setStyleSheet(
                "background-color: #065F46; color: #D1FAE5; font-weight: bold; font-size: 11px; padding: 2px 8px; border-radius: 4px;"
            )
            self.lbl_status_badge.setVisible(True)
            self.btn_action.setVisible(False)

    def _start_update_download(self):
        download_url = self.latest_release_info.get("download_url", "")
        if not download_url:
            QMessageBox.warning(
                self,
                "Manual Download Required",
                f"No direct Windows binary found in release {self.latest_release_info.get('tag')}.\n"
                f"Please download the release manually from GitHub.",
            )
            return

        self.btn_action.setEnabled(False)
        self.btn_check_again.setEnabled(False)
        self.btn_close.setEnabled(False)
        self.progress_card.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.installer = AppUpdateInstaller(download_url, parent=self)
        self.installer.progress_updated.connect(self._on_download_progress)
        self.installer.step_changed.connect(self.lbl_progress_status.setText)
        self.installer.installation_completed.connect(self._on_installation_completed)
        self.installer.finished.connect(self.installer.deleteLater)
        self.installer.start()

    def _on_download_progress(self, downloaded: int, total: int, status_text: str):
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.progress_bar.setValue(pct)
        self.lbl_progress_bytes.setText(status_text)

    def _on_installation_completed(self, success: bool, message: str, updater_bat_path: str):
        self.btn_close.setEnabled(True)
        self.btn_check_again.setEnabled(True)

        if success and updater_bat_path:
            self.updater_bat_path = updater_bat_path
            self.lbl_progress_status.setText("✅ Update ready! Click Restart to apply.")
            self.btn_action.setEnabled(True)
            self.btn_action.setText("🚀 Restart Scrcpy Studio")
            self.btn_action.clicked.disconnect()
            self.btn_action.clicked.connect(self._apply_and_restart)

            res = QMessageBox.question(
                self,
                "Restart Scrcpy Studio",
                f"Scrcpy Studio {self.latest_release_info.get('tag')} has been downloaded successfully!\n\n"
                "Would you like to restart Scrcpy Studio now to apply the update?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if res == QMessageBox.Yes:
                self._apply_and_restart()
        else:
            self.lbl_progress_status.setText(f"❌ {message}")
            self.btn_action.setEnabled(True)
            self.btn_action.setText("Retry Update")
            QMessageBox.critical(self, "Update Failed", message)

    def _apply_and_restart(self):
        if self.updater_bat_path:
            apply_update_and_restart(self.updater_bat_path)
            QApplication.quit()
