"""Fluent Dark Theme Stylesheet for Scrcpy Studio."""

DARK_THEME_QSS = """
/* Global Window & Fonts */
QWidget {
    background-color: #121318;
    color: #E2E8F0;
    font-family: "Segoe UI", sans-serif;
    selection-background-color: #3B82F6;
    selection-color: #FFFFFF;
}

/* Main Window */
QMainWindow {
    background-color: #121318;
}

/* Group Boxes & Panels */
QGroupBox {
    background-color: #1A1C23;
    border: 1px solid #2D3139;
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 16px;
    padding-bottom: 12px;
    padding-left: 12px;
    padding-right: 12px;
    font-weight: bold;
    font-size: 13px;
    color: #94A3B8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    background-color: #1A1C23;
    color: #38BDF8;
}

/* Scroll Area */
QScrollArea {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    border: none;
    background: #181A20;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #333846;
    min-height: 25px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #4A5164;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Push Buttons */
QPushButton {
    background-color: #262933;
    color: #F1F5F9;
    border: 1px solid #373C4B;
    border-radius: 7px;
    padding: 7px 14px;
    font-weight: 500;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #323745;
    border-color: #4C5367;
}

QPushButton:pressed {
    background-color: #1F222B;
}

QPushButton:disabled {
    background-color: #191B22;
    color: #555C6E;
    border-color: #232732;
}

/* Primary / Action Buttons */
QPushButton#primaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #3B82F6);
    color: #FFFFFF;
    border: 1px solid #3B82F6;
    font-weight: 600;
    font-size: 13px;
}

QPushButton#primaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #2563EB);
    border-color: #60A5FA;
}

QPushButton#launchBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10B981);
    color: #FFFFFF;
    border: 1px solid #10B981;
    font-weight: bold;
    font-size: 14px;
    padding: 10px 20px;
    border-radius: 8px;
}

QPushButton#launchBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
    border-color: #34D399;
}

QPushButton#stopBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #DC2626, stop:1 #EF4444);
    color: #FFFFFF;
    border: 1px solid #EF4444;
    font-weight: bold;
    font-size: 13px;
    padding: 8px 16px;
    border-radius: 8px;
}

QPushButton#stopBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #B91C1C, stop:1 #DC2626);
    border-color: #F87171;
}

/* Quick Action Buttons */
QPushButton.quickAction {
    background-color: #21242D;
    border: 1px solid #313644;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 500;
    text-align: left;
}

QPushButton.quickAction:hover {
    background-color: #2D3240;
    border-color: #3B82F6;
    color: #60A5FA;
}

/* Top Navigation Segmented Tab Control */
QPushButton.navPill {
    background-color: transparent;
    color: #94A3B8;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.navPill:hover {
    background-color: #1E222E;
    color: #F8FAFC;
}

QPushButton.navPill[selected="true"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1E293B, stop:1 #131A29);
    color: #38BDF8;
    border: 1px solid #0284C7;
    font-weight: 700;
}

/* Combo Boxes */
QComboBox {
    background-color: #21242D;
    color: #F1F5F9;
    border: 1px solid #333846;
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 22px;
}

QComboBox:hover {
    border-color: #4C5367;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #1A1D26;
    border: 1px solid #383E4E;
    selection-background-color: #2D3748;
    selection-color: #60A5FA;
    border-radius: 8px;
    padding: 6px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 10px;
    border-radius: 5px;
    color: #E2E8F0;
    font-size: 12px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #262B38;
    color: #FFFFFF;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #3B82F633;
    color: #60A5FA;
    font-weight: 600;
}

/* Line Edit & Text Edit */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #171920;
    color: #F1F5F9;
    border: 1px solid #2E3340;
    border-radius: 6px;
    padding: 6px 10px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #3B82F6;
    background-color: #1B1E27;
}

/* Check Boxes */
QCheckBox {
    spacing: 8px;
    color: #E2E8F0;
    font-weight: 500;
}

QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border-radius: 4px;
    border: 1px solid #3D4457;
    background-color: #1C1F28;
}

QCheckBox::indicator:hover {
    border-color: #3B82F6;
}

QCheckBox::indicator:checked {
    background-color: #3B82F6;
    border-color: #3B82F6;
    image: none;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #252834;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #3B82F6;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #60A5FA;
    border: 2px solid #FFFFFF;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #93C5FD;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #2D3139;
    border-radius: 8px;
    background-color: #16181F;
    top: -1px;
}

QTabBar::tab {
    background-color: #1C1F28;
    color: #94A3B8;
    border: 1px solid #2D3139;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 7px 16px;
    margin-right: 2px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #16181F;
    color: #38BDF8;
    border-color: #3B82F6;
    border-bottom: 2px solid #3B82F6;
}

QTabBar::tab:hover:!selected {
    background-color: #252936;
    color: #F1F5F9;
}

/* Status Bar */
QStatusBar {
    background-color: #0E1015;
    color: #717A8C;
    border-top: 1px solid #21242D;
    font-size: 11px;
}

/* Labels */
QLabel {
    color: #E2E8F0;
}

QLabel#headingLabel {
    font-size: 16px;
    font-weight: bold;
    color: #FFFFFF;
}

QLabel#subLabel {
    font-size: 11px;
    color: #64748B;
}

QLabel#badge {
    background-color: #1E293B;
    color: #38BDF8;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 11px;
    font-weight: 600;
}
"""
