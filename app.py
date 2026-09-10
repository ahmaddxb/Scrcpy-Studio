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
    icon_path = get_bundle_dir() / "ui" / "assets" / "icon.ico"
    if not icon_path.exists():
        icon_path = get_bundle_dir() / "ui" / "assets" / "icon.png"
    if not icon_path.exists():
        icon_path = get_project_root() / "assets" / "icons" / "app_icon_option_2_minimal_emblem.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    config = ConfigManager()
    window = MainWindow(config)

    start_min = (
        "--minimized" in sys.argv
        or "-m" in sys.argv
        or config.get("start_minimized", False)
    ) and ("--show" not in sys.argv)

    if start_min:
        # Start minimized to system tray
        if config.get("notifications_enabled", True) and hasattr(window, "tray_icon") and window.tray_icon.isVisible():
            window.tray_icon.showMessage(
                "Scrcpy Studio",
                "Started minimized to system tray.",
                window.tray_icon.MessageIcon.Information,
                2500,
            )
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
