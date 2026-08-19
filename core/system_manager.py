import os
import sys
import winreg
from pathlib import Path
from typing import Any, Dict

from core.config_manager import get_project_root

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "ScrcpyStudio"


class SystemManager:
    """Manages Windows startup registry, system tray preferences, and cache maintenance."""

    @staticmethod
    def is_start_on_boot_enabled() -> bool:
        """Check whether Scrcpy Studio is registered in Windows Startup."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, APP_NAME)
                return True
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"Error reading startup registry: {e}")
            return False

    @staticmethod
    def set_start_on_boot(enabled: bool, start_minimized: bool = False) -> bool:
        """Add or remove Scrcpy Studio from Windows Startup registry (HKCU Run)."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    if getattr(sys, "frozen", False):
                        exe_path = sys.executable
                        cmd = f'"{exe_path}"'
                    else:
                        python_exe = sys.executable
                        pythonw = python_exe.replace("python.exe", "pythonw.exe")
                        if not Path(pythonw).exists():
                            pythonw = python_exe
                        app_py = get_project_root() / "app.py"
                        cmd = f'"{pythonw}" "{app_py}"'

                    if start_minimized:
                        cmd += " --minimized"

                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError:
                        pass
            return True
        except Exception as e:
            print(f"Error modifying startup registry: {e}")
            return False

    @staticmethod
    def get_icon_cache_stats() -> Dict[str, Any]:
        """Return icon count and total disk usage in MB."""
        icons_dir = get_project_root() / "data" / "icons"
        if not icons_dir.exists():
            return {"count": 0, "size_mb": 0.0}

        count = 0
        total_bytes = 0
        for f in icons_dir.iterdir():
            if f.is_file() and f.suffix.lower() in [".png", ".ico", ".jpg"]:
                count += 1
                total_bytes += f.stat().st_size

        return {"count": count, "size_mb": round(total_bytes / (1024 * 1024), 2)}

    @staticmethod
    def clear_icon_cache() -> int:
        """Clear all cached PNG/ICO files in data/icons/."""
        icons_dir = get_project_root() / "data" / "icons"
        if not icons_dir.exists():
            return 0

        cleared = 0
        for f in icons_dir.iterdir():
            if f.is_file() and f.suffix.lower() in [".png", ".ico", ".jpg"]:
                try:
                    f.unlink()
                    cleared += 1
                except Exception:
                    pass
        return cleared
