import multiprocessing
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from core.config_manager import ConfigManager, get_bundle_dir, get_project_root
from ui.main_window import MainWindow
from ui.styles import DARK_THEME_QSS


def main():
    multiprocessing.freeze_support()
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Scrcpy Studio")
    app.setOrganizationName("ScrcpyUI")

    # Set modern default font
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)

    # Apply Dark Fluent Stylesheet
    app.setStyleSheet(DARK_THEME_QSS)

    # Load App Icon if exists
    icon_path = get_bundle_dir() / "ui" / "assets" / "icon.png"
    if not icon_path.exists():
        icon_path = get_project_root() / "scrcpy" / "scrcpy.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    config = ConfigManager()
    window = MainWindow(config)
    
    if "--minimized" in sys.argv or "-m" in sys.argv:
        # Start minimized to system tray
        pass
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
