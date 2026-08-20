import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QObject, QThread, Signal

APP_VERSION = "v1.0.1"
GITHUB_STUDIO_API = "https://api.github.com/repos/ahmaddxb/Scrcpy-Studio/releases/latest"


def normalize_version(ver_str: str) -> Tuple[int, ...]:
    """Convert version string like 'v1.0.1' or '1.0.0-rc1' to tuple of integers for comparison."""
    clean = re.sub(r"[^0-9\.]", "", ver_str)
    parts = clean.split(".")
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    return tuple(nums) if nums else (0,)


def get_current_executable_path() -> Path:
    """Return the Path to the running executable or compiled binary."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    # In development mode, target the binary in dist/
    return (Path(__file__).parent.parent / "dist" / "ScrcpyStudio.exe").resolve()


class AppUpdateChecker(QThread):
    """Background worker to check for new Scrcpy Studio releases on GitHub."""

    check_finished = Signal(bool, dict, str)  # (has_update, release_dict, message)

    def __init__(self, current_version: str = APP_VERSION, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.current_version = current_version

    def run(self):
        try:
            req = urllib.request.Request(
                GITHUB_STUDIO_API,
                headers={
                    "User-Agent": "Scrcpy-Studio-App",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status != 200:
                    self.check_finished.emit(False, {}, f"GitHub API returned HTTP {resp.status}")
                    return

                data = json.loads(resp.read().decode("utf-8"))
                tag_name = data.get("tag_name", "")
                release_name = data.get("name", tag_name)
                body = data.get("body", "")
                assets = data.get("assets", [])

                # Look for Windows release asset (.zip or .exe)
                target_asset = None
                for asset in assets:
                    name = asset.get("name", "").lower()
                    if ("scrcpy-studio" in name or "scrcpystudio" in name) and (name.endswith(".zip") or name.endswith(".exe")):
                        target_asset = asset
                        break
                    elif name.endswith(".zip") or name.endswith(".exe"):
                        target_asset = asset

                latest_ver_tuple = normalize_version(tag_name)
                curr_ver_tuple = normalize_version(self.current_version)

                has_update = latest_ver_tuple > curr_ver_tuple

                release_info = {
                    "tag": tag_name,
                    "name": release_name,
                    "body": body,
                    "download_url": target_asset["browser_download_url"] if target_asset else "",
                    "asset_name": target_asset["name"] if target_asset else "",
                    "asset_size": target_asset["size"] if target_asset else 0,
                    "published_at": data.get("published_at", ""),
                    "html_url": data.get("html_url", ""),
                }

                msg = f"A new version of Scrcpy Studio ({tag_name}) is available!" if has_update else "You are running the latest version of Scrcpy Studio."
                self.check_finished.emit(has_update, release_info, msg)
        except Exception as e:
            self.check_finished.emit(False, {}, f"Failed to check for updates: {e}")


class AppUpdateInstaller(QThread):
    """Background worker to download release package and prepare self-replacement on Windows."""

    progress_updated = Signal(int, int, str)  # (downloaded_bytes, total_bytes, status_text)
    step_changed = Signal(str)
    installation_completed = Signal(bool, str, str)  # (success, message, updater_bat_path)

    def __init__(self, download_url: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.download_url = download_url
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        temp_dir = Path(tempfile.gettempdir()) / "scrcpy_studio_update"
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Download asset
            self.step_changed.emit("📥 Downloading Scrcpy Studio update...")
            archive_name = self.download_url.split("/")[-1] or "update.zip"
            download_dest = temp_dir / archive_name

            req = urllib.request.Request(self.download_url, headers={"User-Agent": "Scrcpy-Studio-App"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                block_size = 65536

                with open(download_dest, "wb") as f:
                    while True:
                        if self._is_cancelled:
                            self.installation_completed.emit(False, "Update cancelled by user.", "")
                            return
                        chunk = resp.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress_updated.emit(downloaded, total_size, f"{downloaded // 1048576}MB / {total_size // 1048576}MB")

            # 2. Extract or locate executable
            self.step_changed.emit("📦 Preparing update files...")
            new_exe_path = None

            if download_dest.suffix.lower() == ".zip":
                extract_dir = temp_dir / "extracted"
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(download_dest, "r") as z:
                    z.extractall(extract_dir)

                for candidate in extract_dir.rglob("*.exe"):
                    if "scrcpystudio" in candidate.name.lower():
                        new_exe_path = candidate
                        break
                if not new_exe_path:
                    candidates = list(extract_dir.rglob("*.exe"))
                    if candidates:
                        new_exe_path = candidates[0]
            elif download_dest.suffix.lower() == ".exe":
                new_exe_path = download_dest

            if not new_exe_path or not new_exe_path.exists():
                self.installation_completed.emit(False, "Could not locate ScrcpyStudio.exe inside update archive.", "")
                return

            # 3. Create helper PowerShell updater script to safely swap executable upon application exit
            target_exe = get_current_executable_path()
            ps1_path = temp_dir / "update.ps1"

            ps1_script = f"""$ErrorActionPreference = 'SilentlyContinue'

# Purge any inherited PyInstaller bootloader environment tokens
[Environment]::SetEnvironmentVariable('_MEIPASS2', $null, 'Process')
[Environment]::SetEnvironmentVariable('_PYI_PARENT_PROCESS_ID', $null, 'Process')
[Environment]::SetEnvironmentVariable('_PYI_APPLICATION_HOME_DIR', $null, 'Process')
[Environment]::SetEnvironmentVariable('_PYI_ARCHIVE_FILE', $null, 'Process')
[Environment]::SetEnvironmentVariable('_PYI_SPLASH_IPC', $null, 'Process')
Remove-Item Env:_MEIPASS2 -ErrorAction SilentlyContinue
Remove-Item Env:_PYI_* -ErrorAction SilentlyContinue

Start-Sleep -Seconds 1
for ($i = 0; $i -lt 15; $i++) {{
    Stop-Process -Name "ScrcpyStudio" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    try {{
        Copy-Item -Path '{str(new_exe_path)}' -Destination '{str(target_exe)}' -Force -ErrorAction Stop
        break
    }} catch {{
        Start-Sleep -Seconds 1
    }}
}}
Start-Process -FilePath '{str(target_exe)}' -WorkingDirectory '{str(target_exe.parent)}'
"""
            with open(ps1_path, "w", encoding="utf-8") as f:
                f.write(ps1_script)

            self.installation_completed.emit(True, "Update ready to install!", str(ps1_path))

        except Exception as e:
            self.installation_completed.emit(False, f"Update failed: {e}", "")


def apply_update_and_restart(updater_script_path: str):
    """Launch the update helper script via PowerShell and exit the application."""
    if not updater_script_path or not Path(updater_script_path).exists():
        return False
    try:
        import ctypes

        # Clean PyInstaller environment variables in current process before spawning child
        for k in list(os.environ.keys()):
            if k.startswith("_PYI") or k == "_MEIPASS2":
                os.environ.pop(k, None)

        # ShellExecuteW launches PowerShell with -ExecutionPolicy Bypass -WindowStyle Hidden
        # PowerShell's Start-Process initializes full Windows desktop parent context for PyInstaller bootloader.
        res = ctypes.windll.shell32.ShellExecuteW(
            None,
            "open",
            "powershell.exe",
            f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{updater_script_path}"',
            None,
            0,  # SW_HIDE
        )
        return res > 32
    except Exception:
        try:
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(updater_script_path)],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return True
        except Exception:
            return False
