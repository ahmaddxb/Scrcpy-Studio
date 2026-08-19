import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QObject, QThread, Signal


GITHUB_LATEST_RELEASE_URL = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"


def normalize_version(ver_str: str) -> Tuple[int, ...]:
    """Convert version string like 'v4.1' or '4.1.2' to tuple of integers for comparison."""
    clean = re.sub(r"[^0-9\.]", "", ver_str)
    parts = clean.split(".")
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    return tuple(nums) if nums else (0,)


class ScrcpyUpdateChecker(QThread):
    """Background worker to query GitHub for the latest Scrcpy release."""

    check_finished = Signal(bool, dict, str)  # (has_update, release_dict, message)

    def __init__(self, current_version: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.current_version = current_version

    def run(self):
        try:
            req = urllib.request.Request(
                GITHUB_LATEST_RELEASE_URL,
                headers={"User-Agent": "Scrcpy-Studio-App", "Accept": "application/vnd.github.v3+json"},
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

                # Find 64-bit Windows zip asset
                win64_asset = None
                for asset in assets:
                    name = asset.get("name", "").lower()
                    if "win64" in name and name.endswith(".zip"):
                        win64_asset = asset
                        break

                if not win64_asset:
                    self.check_finished.emit(False, {}, "No 64-bit Windows release asset found in latest release.")
                    return

                latest_ver_tuple = normalize_version(tag_name)
                curr_ver_tuple = normalize_version(self.current_version)

                has_update = latest_ver_tuple > curr_ver_tuple

                release_info = {
                    "tag": tag_name,
                    "name": release_name,
                    "body": body,
                    "download_url": win64_asset["browser_download_url"],
                    "asset_name": win64_asset["name"],
                    "asset_size": win64_asset["size"],
                    "published_at": data.get("published_at", ""),
                    "html_url": data.get("html_url", ""),
                }

                msg = "A newer version of Scrcpy is available!" if has_update else "You are running the latest version of Scrcpy."
                self.check_finished.emit(has_update, release_info, msg)
        except Exception as e:
            self.check_finished.emit(False, {}, f"Failed to check for updates: {e}")


class ScrcpyDownloadWorker(QThread):
    """Background worker to download, extract, and deploy official Scrcpy release."""

    progress_updated = Signal(int, int, str)  # (downloaded_bytes, total_bytes, status_text)
    step_changed = Signal(str)
    installation_completed = Signal(bool, str)  # (success, message)

    def __init__(self, download_url: str, target_scrcpy_dir: Path, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.download_url = download_url
        self.target_dir = Path(target_scrcpy_dir)
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="scrcpy_update_"))
        zip_path = temp_dir / "scrcpy_latest.zip"

        try:
            self.step_changed.emit("Connecting to GitHub...")
            req = urllib.request.Request(self.download_url, headers={"User-Agent": "Scrcpy-Studio-App"})

            with urllib.request.urlopen(req, timeout=15) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 64 * 1024  # 64 KB chunks
                t_start = time.time()

                with open(zip_path, "wb") as f_out:
                    while True:
                        if self._is_cancelled:
                            self.installation_completed.emit(False, "Download cancelled by user.")
                            return

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f_out.write(chunk)
                        downloaded += len(chunk)

                        dt = max(0.001, time.time() - t_start)
                        speed_kb = (downloaded / 1024) / dt
                        if total_size > 0:
                            status = f"Downloading: {downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB ({speed_kb:.0f} KB/s)"
                        else:
                            status = f"Downloading: {downloaded / (1024*1024):.1f} MB ({speed_kb:.0f} KB/s)"

                        self.progress_updated.emit(downloaded, total_size, status)

            # Extraction & Deployment
            self.step_changed.emit("Terminating running ADB server...")
            self._kill_adb()

            self.step_changed.emit("Extracting Scrcpy binaries...")
            extract_dir = temp_dir / "extracted"
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

            # Find inner root folder inside zip (e.g. scrcpy-win64-v4.1/)
            inner_dir = None
            for item in extract_dir.iterdir():
                if item.is_dir() and (item / "scrcpy.exe").exists():
                    inner_dir = item
                    break

            if not inner_dir:
                inner_dir = extract_dir

            if not (inner_dir / "scrcpy.exe").exists():
                self.installation_completed.emit(False, "Extracted archive did not contain scrcpy.exe.")
                return

            self.step_changed.emit("Deploying binaries to project directory...")
            self.target_dir.mkdir(parents=True, exist_ok=True)

            # Copy all files into target directory
            for item in inner_dir.iterdir():
                dest = self.target_dir / item.name
                if item.is_file():
                    shutil.copy2(item, dest)
                elif item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest, ignore_errors=True)
                    shutil.copytree(item, dest)

            self.step_changed.emit("Scrcpy runtime successfully updated!")
            self.installation_completed.emit(True, f"Successfully deployed latest Scrcpy binaries into {self.target_dir}")

        except Exception as e:
            self.installation_completed.emit(False, f"Update failed: {e}")
        finally:
            # Clean up temporary download folder
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _kill_adb(self):
        """Safely kill any active adb.exe daemon locking binary files."""
        try:
            adb_exe = self.target_dir / "adb.exe"
            if adb_exe.exists():
                creationflags = 0
                if os.name == "nt":
                    creationflags = subprocess.CREATE_NO_WINDOW
                subprocess.run([str(adb_exe), "kill-server"], capture_output=True, timeout=3, creationflags=creationflags)
        except Exception:
            pass
