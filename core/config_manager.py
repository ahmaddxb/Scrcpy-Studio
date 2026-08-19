import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_project_root() -> Path:
    """Return project directory where executable or script lives (for user config and data)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.parent.resolve()


def get_bundle_dir() -> Path:
    """Return internal bundled assets directory (supports PyInstaller --onefile and --onedir)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return get_project_root()


DEFAULT_CONFIG: Dict[str, Any] = {
    "scrcpy_path": str(get_project_root() / "scrcpy"),
    "theme": "dark",
    "auto_refresh_interval_ms": 2000,
    "last_selected_serial": "",
    "recent_wireless_ips": [],
    "active_preset": "Balanced (1080p 60fps 8M)",
    "presets": {
        "Balanced (1080p 60fps 8M)": {
            "max_size": "1920",
            "bitrate": "8M",
            "max_fps": "60",
            "video_codec": "h264",
            "audio_enabled": True,
            "audio_codec": "opus",
            "audio_dup": False,
            "stay_awake": True,
            "turn_screen_off": False,
            "show_touches": False,
            "always_on_top": False,
            "fullscreen": False,
            "borderless": False,
            "record": False,
            "record_format": "mp4",
            "sync_clipboard": True,
            "otg_mode": False,
            "camera_mode": False
        },
        "High Quality (1440p 60fps 16M)": {
            "max_size": "2560",
            "bitrate": "16M",
            "max_fps": "60",
            "video_codec": "h265",
            "audio_enabled": True,
            "audio_codec": "opus",
            "audio_dup": False,
            "stay_awake": True,
            "turn_screen_off": False,
            "show_touches": False,
            "always_on_top": False,
            "fullscreen": False,
            "borderless": False,
            "record": False,
            "record_format": "mp4",
            "sync_clipboard": True,
            "otg_mode": False,
            "camera_mode": False
        },
        "Low Latency / Gaming (720p 90fps 6M)": {
            "max_size": "1280",
            "bitrate": "6M",
            "max_fps": "90",
            "video_codec": "h264",
            "audio_enabled": True,
            "audio_codec": "raw",
            "audio_dup": False,
            "stay_awake": True,
            "turn_screen_off": True,
            "show_touches": False,
            "always_on_top": True,
            "fullscreen": False,
            "borderless": False,
            "record": False,
            "record_format": "mp4",
            "sync_clipboard": True,
            "otg_mode": False,
            "camera_mode": False
        },
        "Audio Only Stream": {
            "max_size": "0",
            "bitrate": "0",
            "max_fps": "0",
            "video_codec": "h264",
            "audio_enabled": True,
            "audio_codec": "opus",
            "audio_dup": False,
            "stay_awake": False,
            "turn_screen_off": False,
            "show_touches": False,
            "always_on_top": False,
            "fullscreen": False,
            "borderless": False,
            "record": False,
            "record_format": "mp4",
            "sync_clipboard": False,
            "otg_mode": False,
            "camera_mode": False,
            "no_video": True
        }
    },
    "current_settings": {
        "max_size": "1920",
        "bitrate": "8M",
        "max_fps": "60",
        "video_codec": "h264",
        "audio_enabled": True,
        "audio_codec": "opus",
        "audio_dup": False,
        "stay_awake": True,
        "force_stay_awake": True,
        "turn_screen_off": False,
        "show_touches": False,
        "always_on_top": False,
        "fullscreen": False,
        "borderless": False,
        "record": False,
        "record_format": "mp4",
        "record_path": "",
        "sync_clipboard": True,
        "otg_mode": False,
        "camera_mode": False,
        "no_video": False,
        "rotation": "0",
        "window_width": "",
        "window_height": "",
        "window_x": "",
        "window_y": "",
        "custom_args": ""
    }
}


class ConfigManager:
    """Manages application configuration, presets, and path resolution."""

    def __init__(self, config_file: str = "config.json"):
        self.config_path = get_project_root() / config_file
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                    self.data = DEFAULT_CONFIG.copy()
                    self._deep_update(self.data, saved_data)
            except Exception as e:
                print(f"Error loading config, falling back to defaults: {e}")
                self.data = DEFAULT_CONFIG.copy()
        else:
            self.data = DEFAULT_CONFIG.copy()
            self.save()
        return self.data

    def save(self) -> None:
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def _deep_update(self, target: dict, source: dict):
        for k, v in source.items():
            if isinstance(v, dict) and k in target and isinstance(target[k], dict):
                self._deep_update(target[k], v)
            else:
                target[k] = v

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def get_preset(self, name: str) -> Dict[str, Any]:
        return self.data.get("presets", {}).get(name, DEFAULT_CONFIG["presets"]["Balanced (1080p 60fps 8M)"])

    def save_preset(self, name: str, settings: Dict[str, Any]) -> None:
        if "presets" not in self.data:
            self.data["presets"] = {}
        self.data["presets"][name] = settings
        self.save()

    def delete_preset(self, name: str) -> bool:
        if "presets" in self.data and name in self.data["presets"]:
            del self.data["presets"][name]
            self.save()
            return True
        return False

    def add_recent_ip(self, ip: str) -> None:
        recent = self.data.get("recent_wireless_ips", [])
        if ip in recent:
            recent.remove(ip)
        recent.insert(0, ip)
        self.data["recent_wireless_ips"] = recent[:10]
        self.save()

    def get_pinned_devices(self) -> list:
        return self.data.get("pinned_devices", [])

    def pin_device(self, serial: str, name: str = "", is_wireless: bool = False) -> None:
        pinned = self.get_pinned_devices()
        clean_name = name.strip() if (name and name.strip() != serial) else serial
        for p in pinned:
            if p.get("serial") == serial:
                if clean_name != serial or not p.get("name"):
                    p["name"] = clean_name
                self.save()
                return
        pinned.append({
            "serial": serial,
            "name": clean_name,
            "is_wireless": is_wireless
        })
        self.data["pinned_devices"] = pinned
        self.save()

    def unpin_device(self, serial: str) -> None:
        pinned = self.get_pinned_devices()
        self.data["pinned_devices"] = [p for p in pinned if p.get("serial") != serial]
        self.save()

    def is_pinned(self, serial: str) -> bool:
        return any(p.get("serial") == serial for p in self.get_pinned_devices())

    # === PER-CONNECTED DEVICE PROFILES ===

    def get_device_profiles(self) -> Dict[str, Any]:
        """Return the dictionary of all saved per-device profiles."""
        return self.data.get("device_profiles", {})

    def get_device_profile(self, serial: str) -> Dict[str, Any]:
        """Return profile data for a specific device serial, or an empty dict."""
        if not serial:
            return {}
        return self.get_device_profiles().get(serial, {})

    def save_device_profile(self, serial: str, profile_data: Dict[str, Any]) -> None:
        """Save or update profile dictionary for a specific device serial."""
        if not serial:
            return
        if "device_profiles" not in self.data:
            self.data["device_profiles"] = {}
        self.data["device_profiles"][serial] = profile_data
        self.save()

    def get_device_alias(self, serial: str, fallback: str = "") -> str:
        """Get custom friendly alias for a device if set, else fallback to model / display name."""
        if not serial:
            return fallback or ""
        profile = self.get_device_profile(serial)
        alias = profile.get("alias", "").strip()
        if alias and alias != serial:
            return alias
        # Also check pinned_devices
        for p in self.get_pinned_devices():
            if p.get("serial") == serial:
                p_name = p.get("name", "").strip()
                if p_name and p_name != serial:
                    return p_name
        return fallback or serial

    def set_device_alias(self, serial: str, alias: str) -> None:
        """Set a friendly name/alias for a device."""
        if not serial:
            return
        clean_alias = alias.strip()
        profile = self.get_device_profile(serial)
        if clean_alias and clean_alias != serial:
            profile["alias"] = clean_alias
        elif "alias" in profile:
            del profile["alias"]
        self.save_device_profile(serial, profile)
        # Also update pinned devices if pinned
        pinned = self.get_pinned_devices()
        for p in pinned:
            if p.get("serial") == serial:
                p["name"] = clean_alias or serial
                self.data["pinned_devices"] = pinned
                self.save()
                break

    def get_device_settings(self, serial: str) -> Dict[str, Any]:
        """Return device-specific mirroring settings if custom settings are enabled, else global settings."""
        if not serial:
            return self.data.get("current_settings", {})
        profile = self.get_device_profile(serial)
        if profile.get("use_custom_settings", False) and "settings" in profile:
            return profile["settings"]
        if profile.get("active_preset"):
            preset_name = profile["active_preset"]
            if preset_name in self.data.get("presets", {}):
                return self.data["presets"][preset_name]
        return self.data.get("current_settings", {})

    def set_device_settings(self, serial: str, settings: Dict[str, Any]) -> None:
        """Save current stream settings specifically for a device."""
        if not serial:
            return
        profile = self.get_device_profile(serial)
        profile["settings"] = settings
        profile["use_custom_settings"] = True
        self.save_device_profile(serial, profile)

    def is_device_custom_settings(self, serial: str) -> bool:
        """Check if a device has custom settings enabled."""
        profile = self.get_device_profile(serial)
        return bool(profile.get("use_custom_settings", False))

    def set_device_custom_settings(self, serial: str, enabled: bool) -> None:
        """Toggle whether a device uses custom overrides vs global settings."""
        if not serial:
            return
        profile = self.get_device_profile(serial)
        profile["use_custom_settings"] = enabled
        self.save_device_profile(serial, profile)

    def get_favorite_apps(self) -> list:
        default_favs = [
            {"name": "YouTube", "package": "com.google.android.youtube", "icon": "▶️"},
            {"name": "Chrome", "package": "com.android.chrome", "icon": "🌐"},
            {"name": "Settings", "package": "com.android.settings", "icon": "⚙️"},
            {"name": "Camera", "package": "com.sec.android.app.camera", "icon": "📷"},
            {"name": "Files", "package": "com.google.android.documentsui", "icon": "📁"},
            {"name": "Play Store", "package": "com.android.vending", "icon": "🛍️"},
        ]
        return self.data.get("favorite_apps", default_favs)

    def add_favorite_app(self, package: str, name: str = "", icon: str = "📱", display_res: str = "") -> None:
        favs = self.get_favorite_apps()
        for f in favs:
            if f.get("package") == package:
                if name:
                    f["name"] = name
                if icon:
                    f["icon"] = icon
                if display_res:
                    f["display_res"] = display_res
                self.data["favorite_apps"] = favs
                self.save()
                return
        favs.append({
            "name": name or package.split(".")[-1].capitalize(),
            "package": package,
            "icon": icon,
            "display_res": display_res
        })
        self.data["favorite_apps"] = favs
        self.save()

    def update_favorite_app(self, package: str, name: str, icon: str = "📱", display_res: str = "") -> None:
        favs = self.get_favorite_apps()
        for f in favs:
            if f.get("package") == package:
                f["name"] = name
                f["icon"] = icon
                f["display_res"] = display_res
                self.data["favorite_apps"] = favs
                self.save()
                return
        self.add_favorite_app(package, name, icon, display_res)

    def remove_favorite_app(self, package: str) -> None:
        favs = self.get_favorite_apps()
        self.data["favorite_apps"] = [f for f in favs if f.get("package") != package]
        self.save()

    def is_favorite_app(self, package: str) -> bool:
        return any(f.get("package") == package for f in self.get_favorite_apps())

    def get_virtual_display_presets(self) -> list:
        default_presets = [
            {"label": "📱 Native Resolution (Auto)", "value": ""},
            {"label": "📱 1080x1920 (FHD Portrait Phone)", "value": "1080x1920"},
            {"label": "💻 1920x1080 (FHD Landscape / DeX)", "value": "1920x1080"},
            {"label": "📱 720x1280 (Compact Portrait)", "value": "720x1280"},
            {"label": "💻 1280x720 (Compact Landscape)", "value": "1280x720"},
            {"label": "📱 1440x2560 (2K Ultra Portrait)", "value": "1440x2560"},
            {"label": "💻 2560x1440 (2K Ultra Landscape)", "value": "2560x1440"},
        ]
        return self.data.get("virtual_display_presets", default_presets)

    def add_virtual_display_preset(self, label: str, value: str, win_w: str = "", win_h: str = "") -> None:
        presets = self.get_virtual_display_presets()
        for p in presets:
            if p.get("value") == value:
                p["label"] = label
                p["win_w"] = win_w
                p["win_h"] = win_h
                self.data["virtual_display_presets"] = presets
                self.save()
                return
        presets.append({"label": label, "value": value, "win_w": win_w, "win_h": win_h})
        self.data["virtual_display_presets"] = presets
        self.save()

    def update_virtual_display_preset(self, old_value: str, new_label: str, new_value: str, win_w: str = "", win_h: str = "") -> None:
        presets = self.get_virtual_display_presets()
        for p in presets:
            if p.get("value") == old_value:
                p["label"] = new_label
                p["value"] = new_value
                p["win_w"] = win_w
                p["win_h"] = win_h
                self.data["virtual_display_presets"] = presets
                self.save()
                return
        self.add_virtual_display_preset(new_label, new_value, win_w, win_h)

    def get_preset_by_value(self, value: str) -> Optional[dict]:
        for p in self.get_virtual_display_presets():
            if p.get("value") == value:
                return p
        return None

    def remove_virtual_display_preset(self, value: str) -> None:
        presets = self.get_virtual_display_presets()
        self.data["virtual_display_presets"] = [p for p in presets if p.get("value") != value]
        self.save()

    def is_scrcpy_installed(self) -> bool:
        """Check whether scrcpy.exe and adb.exe binaries exist and are runnable."""
        bin_dir = self.get_scrcpy_bin_dir()
        return (bin_dir / "scrcpy.exe").exists() and (bin_dir / "adb.exe").exists()

    def get_scrcpy_bin_dir(self) -> Path:
        custom_path = self.data.get("scrcpy_path", "")
        if custom_path and Path(custom_path).exists() and (Path(custom_path) / "scrcpy.exe").exists():
            return Path(custom_path)

        # 1. Look for scrcpy folder next to executable or project root
        project_root = get_project_root()
        scrcpy_dir = project_root / "scrcpy"
        if scrcpy_dir.exists() and (scrcpy_dir / "scrcpy.exe").exists():
            return scrcpy_dir

        # 2. Look for any bundled scrcpy-win64-* directory
        candidates = sorted(project_root.glob("scrcpy-win64-*"), reverse=True)
        if candidates and candidates[0].is_dir() and (candidates[0] / "scrcpy.exe").exists():
            return candidates[0]

        # Default destination for downloads
        return project_root / "scrcpy"

    def get_scrcpy_version(self) -> str:
        """Query real Scrcpy version directly from the scrcpy.exe binary."""
        bin_dir = self.get_scrcpy_bin_dir()
        scrcpy_exe = bin_dir / "scrcpy.exe"
        if scrcpy_exe.exists():
            try:
                creationflags = 0
                startupinfo = None
                if os.name == "nt":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    creationflags = subprocess.CREATE_NO_WINDOW
                r = subprocess.run(
                    [str(scrcpy_exe), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    startupinfo=startupinfo,
                    creationflags=creationflags,
                )
                m = re.search(r"scrcpy\s+([0-9\.]+)", r.stdout, re.IGNORECASE)
                if m:
                    return f"v{m.group(1)}"
            except Exception:
                pass

            m_dir = re.search(r"v([0-9\.]+)", bin_dir.name)
            if m_dir:
                return f"v{m_dir.group(1)}"
            return "v4.1"

        return "Not Downloaded"
