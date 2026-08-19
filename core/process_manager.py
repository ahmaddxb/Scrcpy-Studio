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


class ProcessManager(QObject):
    """Manages spawning, tracking, and terminating scrcpy instances per device."""

    session_started = Signal(str)  # serial
    session_stopped = Signal(str, int)  # serial, exit_code
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

    def _on_stdout(self, key: str, process: QProcess):
        data = process.readAllStandardOutput().data().decode("utf-8", errors="replace").strip()
        if data:
            self.log_output.emit(key, data)

    def _on_stderr(self, key: str, process: QProcess):
        data = process.readAllStandardError().data().decode("utf-8", errors="replace").strip()
        if data:
            self.log_output.emit(key, data)

    def _on_finished(self, key: str, exit_code: int):
        sess = self.sessions.pop(key, None)
        dev_serial = sess.device_serial if (sess and sess.device_serial) else key.split("::")[0]
        self._restore_timeout(dev_serial)
        self.session_stopped.emit(key, exit_code)
        self.log_output.emit(key, f"[STOPPED] Process exited with code {exit_code}")
