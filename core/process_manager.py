import datetime
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, QProcess, Signal

from core.config_manager import get_project_root


@dataclass
class ScrcpySession:
    serial: str
    process: QProcess
    command: List[str]
    device_serial: str = ""
    start_time: datetime.datetime = field(default_factory=datetime.datetime.now)
    is_recording: bool = False
    record_file: Optional[str] = None
    display_id: Optional[int] = None


class ProcessManager(QObject):
    """Manages spawning, tracking, and terminating scrcpy instances per device."""

    session_started = Signal(str)  # serial
    session_stopped = Signal(str, int)  # serial, exit_code
    display_id_ready = Signal(str, int)  # session_key, display_id
    log_output = Signal(str, str)  # serial, message
    error_occurred = Signal(str, str)  # serial, error_msg

    def __init__(self, scrcpy_dir: Optional[Path] = None, adb=None, parent=None):
        super().__init__(parent)
        if scrcpy_dir is None:
            project_root = get_project_root()
            scrcpy_dir = project_root / "scrcpy"
            if not scrcpy_dir.exists():
                candidates = sorted(project_root.glob("scrcpy-win64-*"), reverse=True)
                scrcpy_dir = candidates[0] if candidates else project_root / "scrcpy"
        self.scrcpy_dir = Path(scrcpy_dir)
        self.scrcpy_bin = self.scrcpy_dir / "scrcpy.exe"
        if not self.scrcpy_bin.exists():
            self.scrcpy_bin = "scrcpy"
        else:
            self.scrcpy_bin = str(self.scrcpy_bin)

        self.adb = adb
        self.sessions: Dict[str, ScrcpySession] = {}
        self.original_screen_timeouts: Dict[str, int] = {}

    def build_args(self, serial: str, settings: Dict[str, Any], device_name: str = "") -> List[str]:
        """Construct scrcpy command-line argument list based on settings dictionary."""
        args: List[str] = ["-s", serial]

        # Window title
        title = f"Scrcpy - {device_name or serial}"
        args.extend(["--window-title", title])

        # OTG Mode overrides regular mirroring
        if settings.get("otg_mode", False):
            args.append("--otg")
            return args

        # Camera Mode
        if settings.get("camera_mode", False):
            args.append("--video-source=camera")

        # Audio Only (no video)
        if settings.get("no_video", False):
            args.append("--no-video")
        else:
            # Video Resolution
            max_size = str(settings.get("max_size", "0")).strip()
            if max_size and max_size != "0":
                args.extend(["--max-size", max_size])

            # Video Bitrate
            bitrate = str(settings.get("bitrate", "8M")).strip()
            if bitrate and bitrate != "0":
                args.extend(["--video-bit-rate", bitrate])

            # Max FPS
            max_fps = str(settings.get("max_fps", "0")).strip()
            if max_fps and max_fps != "0":
                args.extend(["--max-fps", max_fps])

            # Video Codec (h264, h265, av1)
            video_codec = settings.get("video_codec", "h264")
            if video_codec:
                args.extend(["--video-codec", video_codec.lower()])

            # Rotation lock
            rotation = str(settings.get("rotation", "0"))
            if rotation in ("90", "180", "270"):
                args.extend(["--lock-video-orientation", rotation])

        # Audio Settings
        if not settings.get("audio_enabled", True):
            args.append("--no-audio")
        else:
            audio_codec = settings.get("audio_codec", "opus")
            if audio_codec:
                args.extend(["--audio-codec", audio_codec.lower()])
            if settings.get("audio_dup", False):
                args.append("--audio-dup")

        # Window & Display flags
        if settings.get("turn_screen_off", False):
            args.append("--turn-screen-off")
        if settings.get("stay_awake", False):
            args.append("--stay-awake")
        if settings.get("show_touches", False):
            args.append("--show-touches")
        if settings.get("always_on_top", False):
            args.append("--always-on-top")
        if settings.get("fullscreen", False):
            args.append("--fullscreen")
        if settings.get("borderless", False):
            args.append("--window-borderless")
        if not settings.get("sync_clipboard", True):
            args.append("--no-clipboard-autosync")

        # Window Size and Position
        win_w = str(settings.get("window_width", "")).strip()
        if win_w and win_w != "0":
            args.extend(["--window-width", win_w])

        win_h = str(settings.get("window_height", "")).strip()
        if win_h and win_h != "0":
            args.extend(["--window-height", win_h])

        win_x = str(settings.get("window_x", "")).strip()
        if win_x:
            args.extend(["--window-x", win_x])

        win_y = str(settings.get("window_y", "")).strip()
        if win_y:
            args.extend(["--window-y", win_y])

        # Start App / New Display Virtual Window
        if settings.get("start_app"):
            app_pkg = str(settings.get("start_app")).strip()
            args.append(f"--start-app=+{app_pkg}")

        if settings.get("new_display", False):
            disp_res = str(settings.get("new_display_res", "")).strip()
            if disp_res and disp_res.lower() not in ("auto", "none", "native", ""):
                args.append(f"--new-display={disp_res}")
            else:
                args.append("--new-display")

        if settings.get("no_vd_system_decorations", False):
            args.append("--no-vd-system-decorations")

        ime_policy = str(settings.get("display_ime_policy", "")).strip()
        if ime_policy and ime_policy.lower() in ("local", "hide", "fallback"):
            args.append(f"--display-ime-policy={ime_policy.lower()}")

        # Recording
        if settings.get("record", False):
            record_dir = settings.get("record_path", "")
            if not record_dir or not Path(record_dir).exists():
                record_dir = str(Path.home() / "Videos")
                Path(record_dir).mkdir(parents=True, exist_ok=True)
            
            fmt = settings.get("record_format", "mp4")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"scrcpy_{serial}_{timestamp}.{fmt}"
            full_path = str(Path(record_dir) / filename)
            args.extend(["--record", full_path])

        # Custom arguments if provided
        custom_args = settings.get("custom_args", "").strip()
        if custom_args:
            args.extend(custom_args.split())

        return args

    def start_session(self, serial: str, settings: Dict[str, Any], device_name: str = "", session_id: Optional[str] = None) -> bool:
        """Start a scrcpy process for the given serial or unique session_id."""
        key = session_id or serial
        if self.is_running(key):
            self.stop_session(key)

        # Extended screen timeout when force_stay_awake is requested or app session launched
        force_awake = settings.get("force_stay_awake", True)
        if force_awake and self.adb:
            if serial not in self.original_screen_timeouts:
                orig = self.adb.get_screen_off_timeout(serial)
                if orig is not None and orig < 86400000:
                    self.original_screen_timeouts[serial] = orig
            
            # Extend timeout to 24 hours while any session is active
            self.adb.set_screen_off_timeout(serial, 86400000)
            self.adb.wake_up(serial)
            orig_val = self.original_screen_timeouts.get(serial, 30000)
            self.log_output.emit(key, f"[FORCE-STAY-AWAKE] Extended screen timeout to 24h for {serial} (Original: {orig_val // 1000}s)")

        args = self.build_args(serial, settings, device_name)
        process = QProcess(self)
        process.setProgram(self.scrcpy_bin)
        process.setArguments(args)
        if Path(self.scrcpy_bin).is_file():
            process.setWorkingDirectory(str(self.scrcpy_dir))

        # Wire signals
        process.readyReadStandardOutput.connect(
            lambda: self._on_stdout(key, process)
        )
        process.readyReadStandardError.connect(
            lambda: self._on_stderr(key, process)
        )
        process.finished.connect(
            lambda exit_code, exit_status: self._on_finished(key, exit_code)
        )

        process.start()
        if not process.waitForStarted(3000):
            err = process.errorString()
            self._restore_timeout(serial)
            self.error_occurred.emit(key, f"Failed to start scrcpy: {err}")
            return False

        is_rec = settings.get("record", False)
        rec_file = None
        if is_rec and "--record" in args:
            rec_file = args[args.index("--record") + 1]

        session = ScrcpySession(
            serial=key,
            process=process,
            command=[self.scrcpy_bin] + args,
            device_serial=serial,
            is_recording=is_rec,
            record_file=rec_file
        )
        self.sessions[key] = session
        self.session_started.emit(key)
        cmd_str = " ".join([self.scrcpy_bin] + args)
        self.log_output.emit(key, f"[LAUNCH] {cmd_str}")
        return True

    def _restore_timeout(self, key_or_serial: str):
        """Restore device's original screen_off_timeout only when all sessions for that device have ended."""
        real_serial = key_or_serial.split("::")[0]
        
        # Check if there are any remaining running sessions for this device
        still_running = False
        for k, sess in self.sessions.items():
            dev = getattr(sess, "device_serial", "") or k.split("::")[0]
            if dev == real_serial and sess.process and sess.process.state() == QProcess.ProcessState.Running:
                still_running = True
                break

        if not still_running and self.adb and real_serial in self.original_screen_timeouts:
            orig = self.original_screen_timeouts.pop(real_serial, None)
            if orig is not None:
                self.adb.set_screen_off_timeout(real_serial, orig)
                self.log_output.emit(real_serial, f"[STAY-AWAKE] All sessions closed for {real_serial}. Restored screen timeout back to {orig // 1000}s.")

    def stop_session(self, key: str) -> None:
        """Terminate a running session and restore screen timeout if no other sessions remain."""
        session = self.sessions.get(key)
        dev_serial = session.device_serial if (session and session.device_serial) else key.split("::")[0]
        if session and session.process:
            session.process.terminate()
            if not session.process.waitForFinished(1500):
                session.process.kill()
            self.sessions.pop(key, None)
        self._restore_timeout(dev_serial)

    def stop_all(self) -> None:
        """Stop all active scrcpy sessions and restore all device timeouts."""
        for key in list(self.sessions.keys()):
            session = self.sessions.get(key)
            if session and session.process:
                session.process.terminate()
                if not session.process.waitForFinished(1500):
                    session.process.kill()
                self.sessions.pop(key, None)
        for serial in list(self.original_screen_timeouts.keys()):
            self._restore_timeout(serial)

    def is_running(self, key: str) -> bool:
        session = self.sessions.get(key)
        if not session or not session.process:
            return False
        return session.process.state() == QProcess.ProcessState.Running

    def _check_display_id_in_line(self, key: str, line: str):
        import re
        # Match Scrcpy v4.1 logs: "New display: 1080x2316/445 (id=167)" or "Display: [167]"
        m = re.search(r"\(id=(\d+)\)", line, re.IGNORECASE)
        if not m:
            m = re.search(r"Display:\s*\[(\d+)\]", line, re.IGNORECASE)
        if not m:
            m = re.search(r"displayId\s+(\d+)", line, re.IGNORECASE)
        if m:
            disp_id = int(m.group(1))
            if key in self.sessions:
                if self.sessions[key].display_id != disp_id:
                    self.sessions[key].display_id = disp_id
                    self.display_id_ready.emit(key, disp_id)

    def get_active_display_id(self, key_or_serial: str) -> Optional[int]:
        """Get the active virtual display ID for a given session key or device serial."""
        if key_or_serial in self.sessions and self.sessions[key_or_serial].display_id is not None:
            return self.sessions[key_or_serial].display_id
        for k, sess in self.sessions.items():
            dev = getattr(sess, "device_serial", "") or k.split("::")[0]
            if dev == key_or_serial and sess.display_id is not None:
                return sess.display_id
        return None

    def _on_stdout(self, key: str, process: QProcess):
        data = process.readAllStandardOutput().data().decode("utf-8", errors="replace").strip()
        if data:
            self._check_display_id_in_line(key, data)
            self.log_output.emit(key, data)

    def _on_stderr(self, key: str, process: QProcess):
        data = process.readAllStandardError().data().decode("utf-8", errors="replace").strip()
        if data:
            self._check_display_id_in_line(key, data)
            self.log_output.emit(key, data)

    def _on_finished(self, key: str, exit_code: int):
        sess = self.sessions.pop(key, None)
        dev_serial = sess.device_serial if (sess and sess.device_serial) else key.split("::")[0]
        self._restore_timeout(dev_serial)
        self.session_stopped.emit(key, exit_code)
        self.log_output.emit(key, f"[STOPPED] Process exited with code {exit_code}")

    def send_scrcpy_shortcut(self, serial: str, action: str = "screen_off") -> bool:
        """
        Send Scrcpy native live shortcut to active mirroring window.
        - 'screen_off': Alt + O (MOD + o -> SurfaceControl.POWER_MODE_OFF, keeps mirroring alive)
        - 'screen_on': Alt + Shift + O (MOD + Shift + o -> SurfaceControl.POWER_MODE_NORMAL)
        """
        if os.name != "nt":
            return False

        try:
            import ctypes
            from ctypes import wintypes
            import time
            user32 = ctypes.windll.user32

            # Gather target PIDs for this device serial / session
            target_pids = set()
            for k, sess in self.sessions.items():
                dev = getattr(sess, "device_serial", "") or k.split("::")[0]
                if dev == serial or not serial:
                    if sess.process and sess.process.state() == QProcess.ProcessState.Running:
                        pid = sess.process.processId()
                        if pid:
                            target_pids.add(pid)

            matching_hwnds = []

            def enum_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    # Check by process ID first
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
                        if "Scrcpy" in title and (not serial or serial in title or ":" in title):
                            matching_hwnds.append(hwnd)
                return True

            ENUM_WIN_PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(ENUM_WIN_PROC(enum_cb), 0)

            if matching_hwnds:
                VK_MENU = 0x12     # Alt
                VK_SHIFT = 0x10    # Shift
                VK_O = 0x4F        # 'O'
                KEYEVENTF_KEYUP = 0x0002

                for hwnd in matching_hwnds:
                    # Ensure Scrcpy window is restored & brought to foreground
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    time.sleep(0.04)

                    if action == "screen_on":
                        # Alt + Shift + O (Scrcpy Screen On / POWER_MODE_NORMAL)
                        user32.keybd_event(VK_MENU, 0, 0, 0)
                        user32.keybd_event(VK_SHIFT, 0, 0, 0)
                        user32.keybd_event(VK_O, 0, 0, 0)
                        time.sleep(0.02)
                        user32.keybd_event(VK_O, 0, KEYEVENTF_KEYUP, 0)
                        user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
                        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
                    else:
                        # Alt + O (Scrcpy Screen Off / POWER_MODE_OFF)
                        user32.keybd_event(VK_MENU, 0, 0, 0)
                        user32.keybd_event(VK_O, 0, 0, 0)
                        time.sleep(0.02)
                        user32.keybd_event(VK_O, 0, KEYEVENTF_KEYUP, 0)
                        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
                    time.sleep(0.02)
                return True
        except Exception:
            pass
        return False
