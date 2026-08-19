import hashlib
import os
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Set

from PySide6.QtCore import QObject, QRunnable, QSize, QThread, QThreadPool, Signal
from PySide6.QtGui import QIcon, QPixmap


class IconFetchRunnable(QRunnable):
    """Background task to extract app icon directly via ADB or fetch from metadata."""

    def __init__(self, package_name: str, cache_path: Path, adb_bin: str, serial: Optional[str], callback_signal):
        super().__init__()
        self.package_name = package_name
        self.cache_path = cache_path
        self.adb_bin = adb_bin
        self.serial = serial
        self.callback_signal = callback_signal

    def run(self):
        # 1. Try Direct ADB Extraction from connected phone
        extracted, icon_entry = self._try_adb_extract()
        if extracted:
            self.callback_signal.emit(self.package_name, str(self.cache_path), "adb", icon_entry)
            return

        # 2. Fallback to HD Web / Google Play Store Metadata
        self._try_web_fetch()

    def _try_adb_extract(self):
        if not self.adb_bin or not self.serial or not Path(self.adb_bin).exists():
            return False, ""
        try:
            # 1. Get APK paths on device
            r = subprocess.run(
                [self.adb_bin, "-s", self.serial, "shell", f"pm path {self.package_name}"],
                capture_output=True,
                text=True,
                timeout=4,
            )
            lines = [l.replace("package:", "").strip() for l in r.stdout.splitlines() if l.startswith("package:")]
            if not lines:
                return False, ""

            apk_path = next((l for l in lines if "base.apk" in l), lines[0])

            # 2. List APK files
            r2 = subprocess.run(
                [self.adb_bin, "-s", self.serial, "shell", f'zipinfo -1 "{apk_path}"'],
                capture_output=True,
                text=True,
                timeout=4,
            )
            files = [f.strip() for f in r2.stdout.splitlines() if f.strip()]

            # 3. Find launcher icon PNGs
            candidates = []
            for f in files:
                fl = f.lower()
                if fl.endswith(".png") and ("mipmap" in fl or "drawable" in fl):
                    if "ic_launcher" in fl or "icon" in fl or "logo" in fl or "app" in fl:
                        candidates.append(f)

            if not candidates:
                return False, ""

            def priority(path: str) -> int:
                p = path.lower()
                if "xxxhdpi" in p and "launcher" in p: return 0
                if "xxhdpi" in p and "launcher" in p: return 1
                if "xhdpi" in p and "launcher" in p: return 2
                if "hdpi" in p and "launcher" in p: return 3
                if "launcher" in p: return 4
                if "icon" in p: return 5
                return 6

            candidates.sort(key=priority)
            best_icon = candidates[0]

            # 4. Stream icon bytes directly from device
            r3 = subprocess.run(
                [self.adb_bin, "-s", self.serial, "exec-out", f'unzip -p "{apk_path}" "{best_icon}"'],
                capture_output=True,
                timeout=4,
            )
            if r3.returncode == 0 and len(r3.stdout) > 200:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.cache_path, "wb") as f:
                    f.write(r3.stdout)
                return True, best_icon
        except Exception:
            pass
        return False, ""

    def _try_web_fetch(self):
        try:
            url = f"https://play.google.com/store/apps/details?id={self.package_name}&hl=en"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=4) as response:
                html = response.read().decode("utf-8", errors="ignore")
                matches = re.findall(r"https://play-lh\.googleusercontent\.com/[a-zA-Z0-9_\-]+", html)
                if matches:
                    img_url = f"{matches[0]}=w128-h128"
                    img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(img_req, timeout=4) as img_resp:
                        img_data = img_resp.read()
                        if img_data:
                            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(self.cache_path, "wb") as f:
                                f.write(img_data)
                            self.callback_signal.emit(self.package_name, str(self.cache_path), "web", "Google Play Store")
        except Exception:
            pass


class IconManager(QObject):
    """Manages extracting (via ADB), downloading, caching, and serving official app icons."""

    icon_ready = Signal(str, str, str, str)  # package_name, local_path, source, detail

    _instance = None

    @classmethod
    def get_instance(cls, adb_bin: Optional[str] = None):
        if cls._instance is None:
            cls._instance = IconManager(adb_bin=adb_bin)
        elif adb_bin:
            cls._instance.adb_bin = adb_bin
        return cls._instance

    def __init__(self, cache_dir: Optional[Path] = None, adb_bin: Optional[str] = None, parent=None):
        super().__init__(parent)
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent / "data" / "icons"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_file = self.cache_dir / "manifest.json"
        self.manifest = self._load_manifest()
        self.thread_pool = QThreadPool.globalInstance()
        self.fetching: Set[str] = set()

        if adb_bin is None:
            project_root = Path(__file__).parent.parent
            adb_file = project_root / "scrcpy" / "adb.exe"
            if not adb_file.exists():
                candidates = sorted(project_root.glob("scrcpy-win64-*/adb.exe"), reverse=True)
                adb_file = candidates[0] if candidates else project_root / "scrcpy" / "adb.exe"
            adb_bin = str(adb_file)
        self.adb_bin = adb_bin
        self.icon_ready.connect(self._on_icon_ready_internal)

    def _load_manifest(self) -> dict:
        if self.manifest_file.exists():
            try:
                import json
                with open(self.manifest_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_manifest(self):
        try:
            import json
            with open(self.manifest_file, "w", encoding="utf-8") as f:
                json.dump(self.manifest, f, indent=2)
        except Exception:
            pass

    def _on_icon_ready_internal(self, pkg: str, path: str, source: str, detail: str):
        self.manifest[pkg] = {"source": source, "detail": detail}
        self._save_manifest()
        if pkg in self.fetching:
            self.fetching.remove(pkg)

    def get_icon_source(self, package_name: str) -> Optional[dict]:
        """Return source metadata for cached icon if available."""
        if package_name in self.manifest:
            return self.manifest[package_name]
        if self.get_icon_path(package_name):
            return {"source": "cached", "detail": "Local HD Cache"}
        return None

    def get_icon_path(self, package_name: str) -> Optional[str]:
        """Return local cached icon file path if available."""
        if not package_name:
            return None
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", package_name)
        target = self.cache_dir / f"{safe_name}.png"
        if target.exists() and target.stat().st_size > 0:
            return str(target)
        return None

    def get_icon(self, package_name: str, serial: Optional[str] = None, force_refresh: bool = False) -> Optional[QIcon]:
        """Return QIcon from local cache or dispatch async background fetch via ADB / web."""
        cached_path = self.get_icon_path(package_name)
        if cached_path and not force_refresh:
            return QIcon(cached_path)

        # Trigger background fetch if not already in flight
        if package_name and package_name not in self.fetching:
            self.fetching.add(package_name)
            safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", package_name)
            target = self.cache_dir / f"{safe_name}.png"
            runnable = IconFetchRunnable(package_name, target, self.adb_bin, serial, self.icon_ready)
            self.thread_pool.start(runnable)

        return None

    def force_web_icon(self, package_name: str):
        """Force fetch high-res icon directly from Google Play Store."""
        if not package_name:
            return
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", package_name)
        target = self.cache_dir / f"{safe_name}.png"
        runnable = WebIconFetchRunnable(package_name, target, self.icon_ready)
        self.thread_pool.start(runnable)


class WebIconFetchRunnable(QRunnable):
    """Background task to directly fetch high-res icon from Google Play Store."""

    def __init__(self, package_name: str, cache_path: Path, callback_signal):
        super().__init__()
        self.package_name = package_name
        self.cache_path = cache_path
        self.callback_signal = callback_signal

    def run(self):
        try:
            url = f"https://play.google.com/store/apps/details?id={self.package_name}&hl=en"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=5) as response:
                html = response.read().decode("utf-8", errors="ignore")
                matches = re.findall(r"https://play-lh\.googleusercontent\.com/[a-zA-Z0-9_\-]+", html)
                if matches:
                    img_url = f"{matches[0]}=w128-h128"
                    img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(img_req, timeout=5) as img_resp:
                        img_data = img_resp.read()
                        if img_data:
                            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(self.cache_path, "wb") as f:
                                f.write(img_data)
                            self.callback_signal.emit(self.package_name, str(self.cache_path), "web", "Google Play Store")
        except Exception:
            pass


class BulkIconScraperWorker(QThread):
    """Background worker to batch-scrape all installed app icons purely via ADB with fallback."""

    progress_updated = Signal(int, int, str)  # current, total, pkg_name
    icon_extracted = Signal(str, str, str, str)  # pkg, path, source, detail
    finished_scraping = Signal(int, int)  # success_count, total_count

    def __init__(self, adb_bin: str, serial: str, packages: list, icon_manager: IconManager, parent=None):
        super().__init__(parent)
        self.adb_bin = adb_bin
        self.serial = serial
        self.packages = list(packages)
        self.icon_manager = icon_manager
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        total = len(self.packages)
        success = 0
        import concurrent.futures

        def scrape_app(pkg: str):
            if not self._is_running:
                return pkg, False, "", "none", ""
            safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", pkg)
            cache_path = self.icon_manager.cache_dir / f"{safe_name}.png"
            runnable = IconFetchRunnable(pkg, cache_path, self.adb_bin, self.serial, self.icon_manager.icon_ready)
            # 1. Try Direct ADB
            extracted, icon_entry = runnable._try_adb_extract()
            if extracted:
                return pkg, True, str(cache_path), "adb", icon_entry
            # 2. Fallback to web metadata
            runnable._try_web_fetch()
            if cache_path.exists() and cache_path.stat().st_size > 0:
                return pkg, True, str(cache_path), "web", "Google Play Store"
            return pkg, False, "", "none", ""

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_pkg = {executor.submit(scrape_app, p): p for p in self.packages}
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_pkg):
                if not self._is_running:
                    break
                completed_count += 1
                try:
                    pkg, ok, path, src, detail = future.result()
                    if ok:
                        success += 1
                        self.icon_extracted.emit(pkg, path, src, detail)
                        self.icon_manager._on_icon_ready_internal(pkg, path, src, detail)
                    self.progress_updated.emit(completed_count, total, pkg)
                except Exception:
                    pass

        self.finished_scraping.emit(success, total)

