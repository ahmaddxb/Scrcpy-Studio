import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QThread, Signal

from core.config_manager import get_project_root


@dataclass
class AdbDevice:
    serial: str
    state: str  # 'device', 'unauthorized', 'offline', etc.
    model: str = "Unknown"
    product: str = "Unknown"
    device: str = "Unknown"
    transport_id: str = ""
    is_wireless: bool = False
    ip_port: str = ""
    battery_level: Optional[int] = None
    battery_status: str = ""
    wifi_ip: str = ""

    @property
    def display_name(self) -> str:
        if self.model and self.model != "Unknown":
            # Format model nicely (e.g. Pixel_8_Pro -> Pixel 8 Pro)
            clean_model = self.model.replace("_", " ")
            return clean_model
        return self.serial


class AdbManager:
    """Interface to execute ADB commands and query device information."""

    def __init__(self, adb_dir: Optional[Path] = None):
        if adb_dir is None:
            project_root = get_project_root()
            adb_dir = project_root / "scrcpy"
            if not adb_dir.exists():
                candidates = sorted(project_root.glob("scrcpy-win64-*"), reverse=True)
                adb_dir = candidates[0] if candidates else project_root / "scrcpy"
        self.adb_dir = Path(adb_dir)
        self.adb_bin = self.adb_dir / "adb.exe"
        if not self.adb_bin.exists():
            # Fallback to system adb
            self.adb_bin = "adb"
        else:
            self.adb_bin = str(self.adb_bin)

    @property
    def adb_path(self) -> str:
        return str(self.adb_bin)

    def _run_cmd(self, args: List[str], timeout: int = 10) -> Tuple[int, str, str]:
        """Execute an ADB command quietly with startupinfo to hide Windows console popup."""
        cmd = [self.adb_bin] + args
        try:
            startupinfo = None
            creationflags = 0
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                startupinfo=startupinfo,
                creationflags=creationflags,
                cwd=str(self.adb_dir) if Path(self.adb_bin).is_file() else None
            )
            return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)

    def list_devices(self) -> List[AdbDevice]:
        """Parse `adb devices -l` to return a list of connected AdbDevice objects."""
        code, out, _ = self._run_cmd(["devices", "-l"])
        if code != 0 or not out:
            return []

        devices: List[AdbDevice] = []
        lines = out.splitlines()
        for line in lines[1:]:  # Skip 'List of devices attached'
            line = line.strip()
            if not line:
                continue

            parts = re.split(r"\s+", line)
            if len(parts) < 2:
                continue

            serial = parts[0]
            state = parts[1]

            # Detect wireless (IP:PORT format)
            is_wireless = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$", serial))
            ip_port = serial if is_wireless else ""

            # Parse key-value metadata (e.g. model:Pixel_8 transport_id:1)
            meta: Dict[str, str] = {}
            for token in parts[2:]:
                if ":" in token:
                    k, v = token.split(":", 1)
                    meta[k] = v

            model = meta.get("model", "Android Device")
            product = meta.get("product", "Unknown")
            device_name = meta.get("device", "Unknown")
            transport_id = meta.get("transport_id", "")

            dev = AdbDevice(
                serial=serial,
                state=state,
                model=model,
                product=product,
                device=device_name,
                transport_id=transport_id,
                is_wireless=is_wireless,
                ip_port=ip_port
            )

            # Query battery and screen timeout if device is authorized
            if state == "device":
                bat, charging = self.get_battery_info(serial)
                dev.battery_level = bat
                dev.is_charging = charging
                dev.screen_off_timeout = self.get_screen_off_timeout(serial)

            devices.append(dev)

        return devices

    def get_battery_info(self, serial: str) -> Tuple[Optional[int], bool]:
        """Fetch battery level percentage and charging status."""
        code, out, _ = self._run_cmd(["-s", serial, "shell", "dumpsys", "battery"], timeout=4)
        if code != 0:
            return None, False

        level = None
        charging = False
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("level:"):
                try:
                    level = int(line.split(":")[1].strip())
                except ValueError:
                    pass
            elif line.startswith("status:"):
                # 2 = CHARGING, 5 = FULL
                val = line.split(":")[1].strip()
                charging = (val in ("2", "5"))

        return level, charging

    def connect_wireless(self, ip_port: str) -> Tuple[bool, str]:
        """Connect to wireless ADB endpoint (e.g. 192.168.1.50:5555)."""
        code, out, err = self._run_cmd(["connect", ip_port], timeout=10)
        msg = out if out else err
        success = "connected to" in msg.lower() and "failed" not in msg.lower()
        return success, msg

    def pair_wireless(self, ip_port: str, pairing_code: str) -> Tuple[bool, str]:
        """Pair Android 11+ device using `adb pair <ip:port> <code>`."""
        code, out, err = self._run_cmd(["pair", ip_port, pairing_code], timeout=15)
        msg = out if out else err
        success = "successfully paired" in msg.lower()
        return success, msg

    def enable_tcpip(self, serial: str, port: int = 5555) -> Tuple[bool, str]:
        """Switch USB device to TCP/IP mode on specified port."""
        code, out, err = self._run_cmd(["-s", serial, "tcpip", str(port)], timeout=8)
        msg = out if out else err
        success = (code == 0) and ("restarting in tcpip" in msg.lower() or not msg)
        return success, msg

    def disconnect_wireless(self, ip_port: str = "") -> Tuple[bool, str]:
        """Disconnect wireless device (or all wireless devices if ip_port is empty)."""
        args = ["disconnect"]
        if ip_port:
            args.append(ip_port)
        code, out, err = self._run_cmd(args, timeout=5)
        msg = out if out else err
        return code == 0, msg

    def get_device_ip(self, serial: str) -> Optional[str]:
        """Try to discover device Wi-Fi IP address via shell."""
        code, out, _ = self._run_cmd(["-s", serial, "shell", "ip", "-f", "inet", "addr", "show", "wlan0"], timeout=4)
        if code == 0 and out:
            match = re.search(r"inet\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", out)
            if match:
                return match.group(1)
        return None

    def send_keyevent(self, serial: str, keycode: int) -> bool:
        """Send Android keyevent code."""
        code, _, _ = self._run_cmd(["-s", serial, "shell", "input", "keyevent", str(keycode)], timeout=3)
        return code == 0

    def send_text(self, serial: str, text: str) -> bool:
        """Send alphanumeric text/PIN to active focused window via ADB."""
        if not text:
            return False
        escaped_text = (
            text.replace(" ", "%s")
            .replace("&", "\\&")
            .replace("<", "\\<")
            .replace(">", "\\>")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        code, _, _ = self._run_cmd(["-s", serial, "shell", "input", "text", escaped_text], timeout=4)
        return code == 0

    def wake_up(self, serial: str) -> bool:
        """Wake up device screen (KEYCODE_WAKEUP = 224)."""
        return self.send_keyevent(serial, 224)

    def turn_off_screen(self, serial: str) -> bool:
        """Turn off device screen / sleep (KEYCODE_SLEEP = 223)."""
        return self.send_keyevent(serial, 223)

    def get_current_focused_package(self, serial: str) -> Optional[str]:
        """Get the package name of the currently focused app on the device."""
        code, out, _ = self._run_cmd(["-s", serial, "shell", "dumpsys", "window"], timeout=4)
        if code == 0:
            m = re.search(r"mFocusedApp=ActivityRecord\{[^\}]*\s+([a-zA-Z0-9_\.]+)/", out)
            if m:
                return m.group(1)
            m2 = re.search(r"mCurrentFocus=Window\{[^\}]*\s+([a-zA-Z0-9_\.]+)/", out)
            if m2:
                return m2.group(1)
        return None

    def get_virtual_display_ids(self, serial: str) -> List[int]:
        """Query all active virtual display IDs from dumpsys display."""
        code, out, _ = self._run_cmd(["-s", serial, "shell", "dumpsys", "display"], timeout=4)
        if code == 0:
            found = re.findall(r"DisplayInfo\{.*?scrcpy.*?, displayId (\d+)", out)
            if not found:
                found = re.findall(r"DisplayInfo\{[^\}]*displayId (\d+)[^\}]*VIRTUAL", out)
            return [int(x) for x in found if int(x) > 0]
        return []

    def move_app_to_display(self, serial: str, package: str, display_id: int) -> Tuple[bool, str]:
        """Move / launch an active app directly onto a specific display ID."""
        # 1. Try intent start on target display
        code, out, err = self._run_cmd(
            ["-s", serial, "shell", "am", "start", "--display", str(display_id), "-a", "android.intent.action.MAIN", "-p", package],
            timeout=5
        )
        if code == 0 and "error" not in (out + err).lower():
            return True, f"Moved '{package}' to Display {display_id}"

        # 2. Fallback to monkey launch with display flag
        code2, out2, err2 = self._run_cmd(
            ["-s", serial, "shell", "monkey", "-p", package, "--display", str(display_id), "-c", "android.intent.category.LAUNCHER", "1"],
            timeout=5
        )
        if code2 == 0:
            return True, f"Moved '{package}' to Display {display_id}"

        return False, out or err or "Failed to transfer app to display"

    def unlock_device(self, serial: str) -> bool:
        """Wake up device and dismiss swipe lock screen."""
        self.send_keyevent(serial, 224)  # WAKEUP
        self.send_keyevent(serial, 82)   # MENU (unlocks/dismisses keyguard)
        self._run_cmd(["-s", serial, "shell", "input", "swipe", "500", "1500", "500", "400", "200"], timeout=3)
        return True

    def install_apk(self, serial: str, apk_path: str) -> Tuple[bool, str]:
        """Install APK with replace (-r) option."""
        code, out, err = self._run_cmd(["-s", serial, "install", "-r", apk_path], timeout=60)
        msg = out if out else err
        return "Success" in msg, msg

    def push_file(self, serial: str, local_path: str, remote_dest: str = "/sdcard/Download/") -> Tuple[bool, str]:
        """Push file/folder to device storage."""
        code, out, err = self._run_cmd(["-s", serial, "push", local_path, remote_dest], timeout=60)
        msg = out if out else err
        return code == 0, msg

    def take_screenshot(self, serial: str, save_path: str) -> bool:
        """Take screenshot and save to local PC path."""
        try:
            cmd = [self.adb_bin, "-s", serial, "exec-out", "screencap", "-p"]
            startupinfo = None
            creationflags = 0
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW

            with open(save_path, "wb") as f:
                proc = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    startupinfo=startupinfo,
                    creationflags=creationflags
                )
            return proc.returncode == 0
        except Exception:
            return False

    def restart_server(self) -> Tuple[bool, str]:
        """Kill and restart ADB server."""
        self._run_cmd(["kill-server"], timeout=5)
        code, out, err = self._run_cmd(["start-server"], timeout=10)
        return code == 0, out or err

    def list_packages(self, serial: str, third_party_only: bool = True) -> List[str]:
        """List package names on device (optionally filter to 3rd-party)."""
        args = ["-s", serial, "shell", "pm", "list", "packages"]
        if third_party_only:
            args.append("-3")
        code, out, _ = self._run_cmd(args, timeout=10)
        if code != 0 or not out:
            return []

        packages = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                pkg = line.replace("package:", "").strip()
                if pkg:
                    packages.append(pkg)
        packages.sort()
        return packages

    def launch_app(self, serial: str, package_name: str) -> Tuple[bool, str]:
        """Launch the main launcher activity of a package using monkey intent."""
        package_name = package_name.strip()
        if not package_name:
            return False, "Package name is empty"

        # Monkey tool launches default CATEGORY_LAUNCHER activity without needing activity name
        code, out, err = self._run_cmd(
            ["-s", serial, "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"],
            timeout=5
        )
        msg = out or err
        if code == 0 or "Events injected: 1" in msg:
            return True, f"Launched {package_name}"
        
        # Fallback to am start
        code2, out2, err2 = self._run_cmd(
            ["-s", serial, "shell", "monkey", "-p", package_name, "1"],
            timeout=5
        )
        if code2 == 0:
            return True, f"Launched {package_name}"
        return False, msg

    def force_stop_app(self, serial: str, package_name: str) -> bool:
        """Force stop a package."""
        code, _, _ = self._run_cmd(["-s", serial, "shell", "am", "force-stop", package_name.strip()], timeout=4)
        return code == 0

    def uninstall_package(self, serial: str, package_name: str) -> Tuple[bool, str]:
        """Uninstall a package from device."""
        code, out, err = self._run_cmd(["-s", serial, "uninstall", package_name.strip()], timeout=15)
        msg = out or err
        return "Success" in msg or code == 0, msg

    def open_app_info(self, serial: str, package_name: str) -> bool:
        """Open System App Info settings page for a package."""
        code, _, _ = self._run_cmd(
            ["-s", serial, "shell", "am", "start", "-a", "android.settings.APPLICATION_DETAILS_SETTINGS", "-d", f"package:{package_name.strip()}"],
            timeout=4
        )
        return code == 0

    def clear_app_data(self, serial: str, package_name: str) -> bool:
        """Clear data & cache for a package."""
        code, out, _ = self._run_cmd(["-s", serial, "shell", "pm", "clear", package_name.strip()], timeout=6)
        return "Success" in out or code == 0

    def get_screen_off_timeout(self, serial: str) -> Optional[int]:
        """Get the current screen_off_timeout in milliseconds."""
        code, out, _ = self._run_cmd(["-s", serial, "shell", "settings", "get", "system", "screen_off_timeout"], timeout=4)
        if code == 0:
            val = out.strip()
            if val.isdigit():
                return int(val)
        return None

    def set_screen_off_timeout(self, serial: str, timeout_ms: int) -> bool:
        """Set screen_off_timeout in milliseconds."""
        code, _, _ = self._run_cmd(["-s", serial, "shell", "settings", "put", "system", "screen_off_timeout", str(timeout_ms)], timeout=4)
        return code == 0

    def exec_custom_command(self, command_str: str, serial: Optional[str] = None, timeout: int = 30) -> Tuple[int, str, str]:
        """Execute an arbitrary ADB command string (with or without target device serial)."""
        command_str = command_str.strip()
        if not command_str:
            return 0, "", ""

        # Remove leading 'adb' if user typed it
        if command_str.lower().startswith("adb "):
            command_str = command_str[4:].strip()

        # Build argument list using shlex or regex to handle quotes properly
        import shlex
        try:
            tokens = shlex.split(command_str, posix=False)
        except Exception:
            tokens = command_str.split()

        # If serial is specified and not already in tokens, prepend -s <serial>
        args = []
        if serial and "-s" not in tokens:
            args.extend(["-s", serial])
        args.extend(tokens)

        return self._run_cmd(args, timeout=timeout)


class AdbCommandWorker(QThread):
    """Background worker for running custom injected ADB commands."""

    finished = Signal(int, str, str)  # returncode, stdout, stderr

    def __init__(self, adb: AdbManager, command_str: str, serial: Optional[str] = None, timeout: int = 30, parent=None):
        super().__init__(parent)
        self.adb = adb
        self.command_str = command_str
        self.serial = serial
        self.timeout = timeout

    def run(self):
        code, out, err = self.adb.exec_custom_command(self.command_str, self.serial, self.timeout)
        self.finished.emit(code, out, err)



class AdbDeviceScanner(QThread):
    """Background worker thread to continuously poll ADB devices."""

    devices_updated = Signal(list)  # List[AdbDevice]
    error_occurred = Signal(str)

    def __init__(self, adb_manager: AdbManager, interval_ms: int = 2000, parent=None):
        super().__init__(parent)
        self.adb = adb_manager
        self.interval_ms = interval_ms
        self._running = True
        self._last_devices_fingerprint = ""

    def run(self):
        while self._running:
            try:
                devices = self.adb.list_devices()
                # Create a fingerprint to only emit when status or devices change
                fingerprint = "|".join(
                    f"{d.serial}:{d.state}:{d.battery_level}:{d.is_charging}:{d.screen_off_timeout}" for d in devices
                )
                if fingerprint != self._last_devices_fingerprint:
                    self._last_devices_fingerprint = fingerprint
                    self.devices_updated.emit(devices)
            except Exception as e:
                self.error_occurred.emit(str(e))

            self.msleep(self.interval_ms)

    def stop(self):
        self._running = False
        self.wait(1500)


class AdbAppListWorker(QThread):
    """Background worker to query installed packages asynchronously."""

    packages_loaded = Signal(str, list)  # serial, List[str]
    error_occurred = Signal(str, str)  # serial, error_msg

    def __init__(self, adb: AdbManager, serial: str, third_party_only: bool = True, parent=None):
        super().__init__(parent)
        self.adb = adb
        self.serial = serial
        self.third_party_only = third_party_only

    def run(self):
        try:
            packages = self.adb.list_packages(self.serial, self.third_party_only)
            self.packages_loaded.emit(self.serial, packages)
        except Exception as e:
            self.error_occurred.emit(self.serial, str(e))
