import ctypes
from ctypes import wintypes
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QObject,
    QPropertyAnimation,
    QEasingCurve,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QCursor, QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFrame,
    QLabel,
    QToolTip,
    QApplication,
    QGraphicsOpacityEffect,
)

from core.adb_manager import AdbManager
from core.config_manager import ConfigManager
from core.process_manager import ProcessManager

# Vector SVG Nav Icons from Iconify (lsicon/menu-endways-filled, akar-icons/square, akar-icons/chevron-left)
SVG_NAV_ICONS = {
    "recents": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="{color}" fill-rule="evenodd" d="M3 14V2h1v12zm3 0V2h1v12zm3 0V2h1v12zm3 0V2h1v12z" clip-rule="evenodd"/></svg>""",
    "home": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect width="18" height="18" x="3" y="3" fill="none" stroke="{color}" stroke-width="2.2" rx="3"/></svg>""",
    "back": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="none" stroke="{color}" stroke-linecap="round" stroke-linejoin="round" stroke-width="2.4" d="m15 4l-8 8l8 8"/></svg>""",
}


def create_svg_icon(svg_template: str, color: str = "#CBD5E1", size: int = 18) -> QIcon:
    """Render crisp High-DPI QIcon from SVG path template."""
    svg_data = svg_template.replace("{color}", color).encode("utf-8")
    renderer = QSvgRenderer(QByteArray(svg_data))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2.0)
    return QIcon(pixmap)


class FloatingFadeToolTip(QWidget):
    """Custom floating tooltip window with modern smooth opacity fade-in/out transitions."""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = FloatingFadeToolTip()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.label = QLabel(self)
        self.label.setStyleSheet(
            """
            QLabel {
                background-color: rgba(15, 23, 42, 0.96);
                color: #F8FAFC;
                border: 1px solid rgba(56, 189, 248, 0.7);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-family: 'Segoe UI', sans-serif;
            }
            """
        )
        layout.addWidget(self.label)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.anim.setDuration(180)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def show_tip(self, text: str, target_rect: QRect):
        self.label.setText(text)
        self.adjustSize()

        # Place to the left of the button
        x = target_rect.left() - self.width() - 8
        y = target_rect.center().y() - (self.height() // 2)

        # Fallback to right if pushed off-screen to the left
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            if x < screen_geo.left():
                x = target_rect.right() + 8
            if y + self.height() > screen_geo.bottom():
                y = screen_geo.bottom() - self.height() - 10
            if y < screen_geo.top():
                y = screen_geo.top() + 10

        self.move(x, y)
        self.show()
        self.anim.stop()
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(1.0)
        self.anim.start()

    def hide_tip(self):
        self.anim.stop()
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(0.0)
        self.anim.setDuration(120)
        self.anim.finished.connect(self._on_fade_out_finished)
        self.anim.start()

    def _on_fade_out_finished(self):
        try:
            self.anim.finished.disconnect(self._on_fade_out_finished)
        except Exception:
            pass
        if self.opacity_effect.opacity() <= 0.05:
            self.hide()


class DelayedTooltipFilter(QObject):
    """Provides a smooth 1-second hover delay before fading in rich tooltips."""

    def __init__(self, tooltip: str, delay_ms: int = 1000, parent=None):
        super().__init__(parent)
        self.tooltip = tooltip
        self.delay_ms = delay_ms
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(self.delay_ms)
        self.target_widget: Optional[QWidget] = None
        self.timer.timeout.connect(self._show_tip)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Enter:
            self.target_widget = obj
            self.timer.start()
        elif event.type() in (QEvent.Type.Leave, QEvent.Type.MouseButtonPress, QEvent.Type.Hide):
            self.timer.stop()
            FloatingFadeToolTip.get_instance().hide_tip()
            self.target_widget = None
        return super().eventFilter(obj, event)

    def _show_tip(self):
        if self.target_widget and self.target_widget.underMouse() and self.target_widget.isVisible():
            tip = FloatingFadeToolTip.get_instance()
            global_top_left = self.target_widget.mapToGlobal(self.target_widget.rect().topLeft())
            target_rect = QRect(
                global_top_left.x(),
                global_top_left.y(),
                self.target_widget.width(),
                self.target_widget.height(),
            )
            tip.show_tip(self.tooltip, target_rect)


class CompanionToolBar(QWidget):
    """
    Floating, frameless companion toolbar that magnetically tracks and attaches
    to the active Scrcpy mirroring or Virtual Display window (QtScrcpy style).
    """

    action_triggered = Signal(str, str)

    def __init__(
        self,
        session_key: str,
        process_manager: ProcessManager,
        adb: AdbManager,
        config: Optional[ConfigManager] = None,
        on_pull_app: Optional[Callable[[str], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.session_key = session_key
        self.serial = session_key.split("::")[0]
        self.process_manager = process_manager
        self.adb = adb
        self.config = config
        self.on_pull_app = on_pull_app

        self.target_hwnd: Optional[int] = None
        self.is_collapsed: bool = False
        self._is_closed_by_user: bool = False
        self._last_win_rect: Optional[tuple] = None

        # Configure Frameless Tool window (Z-order is tied to Scrcpy owner window)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)

        self._setup_ui()
        self._init_tracker()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        # Outer Container Frame with dark glassmorphism
        self.container = QFrame(self)
        self.container.setObjectName("companionContainer")
        self.container.setStyleSheet(
            """
            QToolTip {
                background-color: #0F172A;
                color: #F8FAFC;
                border: 1px solid #38BDF8;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 11px;
                font-family: sans-serif;
            }
            QFrame#companionContainer {
                background-color: rgba(18, 21, 30, 0.96);
                border: 1px solid #2B3344;
                border-radius: 8px;
            }
            QPushButton.companionBtn {
                background-color: transparent;
                color: #CBD5E1;
                border: 1px solid transparent;
                border-radius: 6px;
                font-size: 14px;
                padding: 0px;
                text-align: center;
                min-width: 32px;
                max-width: 32px;
                min-height: 30px;
                max-height: 30px;
            }
            QPushButton.companionBtn:hover {
                background-color: rgba(56, 189, 248, 0.22);
                color: #38BDF8;
                border: 1px solid rgba(56, 189, 248, 0.45);
            }
            QPushButton.companionBtn:pressed {
                background-color: rgba(56, 189, 248, 0.4);
                color: #FFFFFF;
            }
            QPushButton.companionBtnToggle {
                background-color: #161B26;
                color: #64748B;
                border: 1px solid #283040;
                border-radius: 4px;
                font-size: 10px;
                padding: 0px;
                text-align: center;
                min-width: 22px;
                max-width: 32px;
                min-height: 18px;
                max-height: 18px;
            }
            QPushButton.companionBtnToggle:hover {
                color: #38BDF8;
                background-color: #1E293B;
                border-color: #38BDF855;
            }
            QFrame.companionDivider {
                background-color: #283040;
                max-height: 1px;
                min-height: 1px;
                margin: 2px 2px;
            }
            """
        )

        self.btn_layout = QVBoxLayout(self.container)
        self.btn_layout.setContentsMargins(5, 5, 5, 5)
        self.btn_layout.setSpacing(3)
        self.btn_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        self.btn_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # Toggle / Collapse handle button
        self.btn_collapse = QPushButton("◀")
        self.btn_collapse.setProperty("class", "companionBtnToggle")
        self.btn_collapse.setCursor(Qt.PointingHandCursor)
        self.collapse_filter = DelayedTooltipFilter("Collapse Toolbar", delay_ms=1000, parent=self.btn_collapse)
        self.btn_collapse.installEventFilter(self.collapse_filter)
        self.btn_collapse.clicked.connect(self._toggle_collapse)
        self.btn_layout.addWidget(self.btn_collapse)

        # Action Buttons Section
        self.actions_widget = QWidget()
        self.actions_layout = QVBoxLayout(self.actions_widget)
        self.actions_layout.setContentsMargins(0, 2, 0, 2)
        self.actions_layout.setSpacing(3)
        self.actions_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        self.actions_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # 1. Screen & Power State (Screen Off, Screen On, Unlock, Wake)
        self.btn_screen_off = self._create_btn("💤", "💤 Screen Off\nTurns off physical phone display while keeping mirroring active (Scrcpy Alt+O)", self._turn_screen_off)
        self.btn_screen_on = self._create_btn("📱", "📱 Screen On\nTurns physical phone display back on (Scrcpy Alt+Shift+O)", self._turn_screen_on)
        self.btn_unlock = self._create_btn("🔓", "🔓 Unlock Device\nWakes screen and executes unlock swipe", self._unlock_device)
        self.btn_wake = self._create_btn("⚡", "⚡ Wake Up\nWakes phone screen from sleep", self._wake_up_device)

        self.actions_layout.addWidget(self.btn_screen_off)
        self.actions_layout.addWidget(self.btn_screen_on)
        self.actions_layout.addWidget(self.btn_unlock)
        self.actions_layout.addWidget(self.btn_wake)

        self.actions_layout.addWidget(self._create_divider())

        # 2. Navigation Keys (Recents, Home, Back, Notifications - Vector SVG Icons)
        self.btn_app_switch = self._create_btn(
            "",
            "Recents / App Switcher\nOpen recent apps switcher (Keyevent 187)",
            lambda: self._send_key(187, "App Switch"),
            icon=create_svg_icon(SVG_NAV_ICONS["recents"], size=16),
        )
        self.btn_home = self._create_btn(
            "",
            "Home\nGo to Android Home screen (Keyevent 3)",
            lambda: self._send_key(3, "Home"),
            icon=create_svg_icon(SVG_NAV_ICONS["home"], size=16),
        )
        self.btn_back = self._create_btn(
            "",
            "Back\nSimulates Android Back button (Keyevent 4)",
            lambda: self._send_key(4, "Back"),
            icon=create_svg_icon(SVG_NAV_ICONS["back"], size=16),
        )
        self.btn_notif = self._create_btn("🔔", "🔔 Notifications\nPull down Android notification shade (Keyevent 83)", lambda: self._send_key(83, "Notifications"))

        self.actions_layout.addWidget(self.btn_app_switch)
        self.actions_layout.addWidget(self.btn_home)
        self.actions_layout.addWidget(self.btn_back)
        self.actions_layout.addWidget(self.btn_notif)

        self.actions_layout.addWidget(self._create_divider())

        # 3. Hardware / Audio / Capture (Power, Screenshot, Vol +, Vol -)
        self.btn_power = self._create_btn("⏻", "⏻ Power Button\nPress physical power button (Keyevent 26)", lambda: self._send_key(26, "Power Button"))
        self.btn_screenshot = self._create_btn("📸", "📸 Screenshot\nCapture phone screenshot and save to Pictures folder", self._take_screenshot)
        self.btn_vol_up = self._create_btn("🔊", "🔊 Volume Up\nIncrease device volume (Keyevent 24)", lambda: self._send_key(24, "Volume Up"))
        self.btn_vol_down = self._create_btn("🔉", "🔉 Volume Down\nDecrease device volume (Keyevent 25)", lambda: self._send_key(25, "Volume Down"))

        self.actions_layout.addWidget(self.btn_power)
        self.actions_layout.addWidget(self.btn_screenshot)
        self.actions_layout.addWidget(self.btn_vol_up)
        self.actions_layout.addWidget(self.btn_vol_down)

        self.actions_layout.addWidget(self._create_divider())

        # 4. Pull active app / Close toolbar
        self.btn_pull = self._create_btn("🔀", "🔀 Move to PC\nTransfer active phone app to dedicated PC Virtual Display window", self._pull_active_app)
        self.btn_close = self._create_btn("✖", "✖ Close Toolbar\nClose this floating companion toolbar", self.close_toolbar)
        self.btn_close.setStyleSheet(
            "QPushButton { background: transparent; color: #EF4444; border: 1px solid transparent; border-radius: 6px; font-size: 12px; padding: 0px; text-align: center; min-width: 32px; max-width: 32px; min-height: 30px; max-height: 30px; }"
            "QPushButton:hover { background-color: rgba(239, 68, 68, 0.2); border-color: rgba(239, 68, 68, 0.5); }"
        )

        self.actions_layout.addWidget(self.btn_pull)
        self.actions_layout.addWidget(self.btn_close)

        self.btn_layout.addWidget(self.actions_widget)
        root_layout.addWidget(self.container)

        self.setFixedWidth(46)
        self.adjustSize()

    def close_toolbar(self):
        """Explicitly shut down the tracker timer and destroy the companion bar."""
        self._is_closed_by_user = True
        if hasattr(self, "tracker_timer") and self.tracker_timer.isActive():
            self.tracker_timer.stop()
        tip = FloatingFadeToolTip.get_instance()
        if tip:
            tip.hide_tip()
        self.hide()
        self.close()
        self.deleteLater()

    def closeEvent(self, event):
        self._is_closed_by_user = True
        if hasattr(self, "tracker_timer") and self.tracker_timer.isActive():
            self.tracker_timer.stop()
        tip = FloatingFadeToolTip.get_instance()
        if tip:
            tip.hide_tip()
        super().closeEvent(event)

    def _create_btn(self, text: str, tooltip: str, callback, icon: Optional[QIcon] = None) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("class", "companionBtn")
        btn.setCursor(Qt.PointingHandCursor)
        if icon and not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QSize(18, 18))
        filt = DelayedTooltipFilter(tooltip, delay_ms=1000, parent=btn)
        btn.installEventFilter(filt)
        btn.clicked.connect(callback)
        return btn

    def _create_divider(self) -> QFrame:
        div = QFrame()
        div.setProperty("class", "companionDivider")
        return div

    def _toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        self.actions_widget.setVisible(not self.is_collapsed)
        if self.is_collapsed:
            self.btn_collapse.setText("▶")
            self.collapse_filter.tooltip = "Expand Toolbar"
            self.btn_collapse.setFixedSize(24, 20)
            self.setFixedSize(36, 32)
        else:
            self.btn_collapse.setText("◀")
            self.collapse_filter.tooltip = "Collapse Toolbar"
            self.btn_collapse.setFixedSize(32, 18)
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.setFixedWidth(46)
            self.adjustSize()
        self._sync_position(force=True)

    def _init_tracker(self):
        self._find_target_hwnd()
        self.tracker_timer = QTimer(self)
        self.tracker_timer.setInterval(25)  # 40 FPS smooth window tracking
        self.tracker_timer.timeout.connect(self._sync_position)
        self.tracker_timer.start()

    def _find_target_hwnd(self) -> Optional[int]:
        if os.name != "nt":
            return None

        try:
            user32 = ctypes.windll.user32

            # Gather target PIDs for this session
            target_pids = set()
            session = self.process_manager.sessions.get(self.session_key)
            if session and session.process and session.process.state() == session.process.ProcessState.Running:
                pid = session.process.processId()
                if pid:
                    target_pids.add(pid)

            if not target_pids:
                # Fallback: all sessions for this device serial
                for k, sess in self.process_manager.sessions.items():
                    dev = getattr(sess, "device_serial", "") or k.split("::")[0]
                    if dev == self.serial and sess.process and sess.process.state() == sess.process.ProcessState.Running:
                        pid = sess.process.processId()
                        if pid:
                            target_pids.add(pid)

            matching_hwnds = []

            def enum_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    # Check by process ID
                    if target_pids:
                        win_pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
                        if win_pid.value in target_pids:
                            matching_hwnds.append(hwnd)
                            return True

                    # Fallback check by title
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value
                        if "Scrcpy" in title and (not self.serial or self.serial in title or ":" in title):
                            matching_hwnds.append(hwnd)
                return True

            ENUM_WIN_PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(ENUM_WIN_PROC(enum_cb), 0)

            if matching_hwnds:
                self.target_hwnd = matching_hwnds[0]
                self._attach_to_owner(self.target_hwnd)
                return self.target_hwnd
        except Exception:
            pass
        return None

    def _attach_to_owner(self, owner_hwnd: int):
        """Bind toolbar as an owned Win32 tool window of Scrcpy so Z-order is matched naturally."""
        if os.name != "nt" or not owner_hwnd:
            return
        try:
            user32 = ctypes.windll.user32
            GWLP_HWNDPARENT = -8
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                user32.SetWindowLongPtrW(int(self.winId()), GWLP_HWNDPARENT, owner_hwnd)
            else:
                user32.SetWindowLongW(int(self.winId()), GWLP_HWNDPARENT, owner_hwnd)
        except Exception:
            pass

    def _sync_position(self, force: bool = False):
        """Track Scrcpy HWND coordinates and stick to the right outer edge."""
        if os.name != "nt" or getattr(self, "_is_closed_by_user", False):
            return

        # Ensure session is still alive
        if not self.process_manager.is_running(self.session_key):
            self.tracker_timer.stop()
            self.close()
            return

        user32 = ctypes.windll.user32

        if not self.target_hwnd or not user32.IsWindow(self.target_hwnd):
            self._find_target_hwnd()
            if not self.target_hwnd:
                return

        # Check if window is minimized or hidden
        if user32.IsIconic(self.target_hwnd) or not user32.IsWindowVisible(self.target_hwnd):
            if self.isVisible():
                self.hide()
            return

        # Use DWMWA_EXTENDED_FRAME_BOUNDS to get true visible window bounds (excluding drop-shadow margins)
        rect = wintypes.RECT()
        DWMWA_EXTENDED_FRAME_BOUNDS = 9
        try:
            dwmapi = ctypes.windll.dwmapi
            hr = dwmapi.DwmGetWindowAttribute(
                self.target_hwnd,
                DWMWA_EXTENDED_FRAME_BOUNDS,
                ctypes.byref(rect),
                ctypes.sizeof(rect),
            )
            if hr != 0:
                user32.GetWindowRect(self.target_hwnd, ctypes.byref(rect))
        except Exception:
            if not user32.GetWindowRect(self.target_hwnd, ctypes.byref(rect)):
                return

        win_rect = (rect.left, rect.top, rect.right, rect.bottom)
        if not force and win_rect == self._last_win_rect and self.isVisible():
            return

        self._last_win_rect = win_rect

        # Resolve the screen containing the Scrcpy window to get exact DPI scale factor
        screen = QApplication.screenAt(QCursor.pos()) or self.screen() or QApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0

        # Convert Win32 physical pixels to Qt logical coordinate space
        log_left = int(rect.left / dpr)
        log_right = int(rect.right / dpr)
        log_top = int(rect.top / dpr)
        log_bottom = int(rect.bottom / dpr)

        screen_geo = screen.geometry() if screen else None
        bar_width = self.width() or 46
        bar_height = self.sizeHint().height() or 380

        target_x = log_right + 2
        target_y = log_top  # Align flush with top of mirror window

        # If placed off-screen on the right, snap to left edge instead
        if screen_geo and (target_x + bar_width > screen_geo.right()):
            target_x = log_left - bar_width - 2

        # Ensure vertical bounds stay within visible screen
        if screen_geo:
            if target_y + bar_height > screen_geo.bottom():
                target_y = max(screen_geo.top(), screen_geo.bottom() - bar_height - 10)

        self.move(target_x, target_y)

        if not self.isVisible():
            self.show()

    # --- Actions ---

    def _turn_screen_off(self):
        ok = self.process_manager.send_scrcpy_shortcut(self.serial, "screen_off")
        msg = f"Sent Scrcpy Screen Off (Alt+O) to {self.serial}" if ok else "Failed to send Screen Off shortcut"
        self.action_triggered.emit("Screen Off", msg)

    def _turn_screen_on(self):
        ok = self.process_manager.send_scrcpy_shortcut(self.serial, "screen_on")
        msg = f"Sent Scrcpy Screen On (Alt+Shift+O) to {self.serial}" if ok else "Failed to send Screen On shortcut"
        self.action_triggered.emit("Screen On", msg)

    def _unlock_device(self):
        ok = self.adb.unlock_device(self.serial)
        if ok:
            self.action_triggered.emit("Unlock", f"Unlocked {self.serial}")

    def _wake_up_device(self):
        ok = self.adb.wake_up(self.serial)
        if ok:
            self.action_triggered.emit("Wake Up", f"Woke up {self.serial}")

    def _send_key(self, keycode: int, name: str):
        ok = self.adb.send_keyevent(self.serial, keycode)
        if ok:
            self.action_triggered.emit(name, f"Sent keyevent {keycode} ({name}) to {self.serial}")

    def _take_screenshot(self):
        pics_dir = Path.home() / "Pictures" / "Scrcpy_Screenshots"
        pics_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = pics_dir / f"screenshot_{self.serial}_{timestamp}.png"

        ok = self.adb.take_screenshot(self.serial, str(filepath))
        if ok:
            self.action_triggered.emit("Screenshot", f"Saved screenshot to {filepath}")
            try:
                os.startfile(str(filepath))
            except Exception:
                pass

    def _pull_active_app(self):
        if self.on_pull_app:
            self.on_pull_app(self.serial)
        else:
            self.action_triggered.emit("Move to PC", f"Move to PC requested for {self.serial}")
