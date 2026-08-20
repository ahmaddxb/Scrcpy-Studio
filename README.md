# ⚡ Scrcpy Studio

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt6-41CD52?logo=qt&logoColor=white)](https://pypi.org/project/PySide6/)
[![Scrcpy](https://img.shields.io/badge/Scrcpy-v4.1+-blue?logo=android)](https://github.com/Genymobile/scrcpy)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6?logo=windows&logoColor=white)](https://microsoft.com/windows)
[![License](https://img.shields.io/badge/License-Apache%202.0-orange)](LICENSE.txt)

**Scrcpy Studio** is a modern, high-performance desktop GUI manager for [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy) and Android Debug Bridge (ADB), designed for power users, developers, and multi-app multitasking on Windows.

---

## ✨ Features & Highlights

### 🔀 1. Universal 1-Click "Move to PC" Live App Migration
* **Bypass Virtual Display Authentication Barriers**: Log in to banking or biometric-protected apps on your physical phone, then click **`🔀 Move to PC`** to instantly migrate the active authenticated task into a standalone PC Virtual Display window without restarting or re-authenticating.
* **Auto-Detect Focused App**: Zero configuration required—Scrcpy Studio automatically inspects the phone's physical screen (Display 0), resolves the running activity, and routes it to your PC.
* **Smart Multi-Window Isolation**: Each transferred app automatically claims its own dedicated Virtual Display window (`#180`, `#181`, `#182`) side-by-side on your desktop without collisions.

### 🪟 2. Independent Virtual Displays & PC Window Geometry
* **Dedicated Standalone Windows**: Launch any installed Android app in an independent virtual display window (`--new-display=...`) with custom PC window dimensions (`--window-width`, `--window-height`) without interrupting the physical phone screen.
* **Resolution & DPI Presets**: Pre-configured and customizable display profiles (`1080x2316/420`, `1080x1920`, `1920x1080 DeX`, etc.).

### ⭐ 3. Favorite Apps Dock & Live Icon Extraction
* **Authentic App Logos**: Dual-engine extractor pulls launcher icons directly from device APKs via ADB (`exec-out unzip`) with HD Google Play Store metadata fallback.
* **Batch ADB Scraper**: Multi-threaded parallel icon scraper extracts all installed app icons in seconds without installing any helper APKs on the phone.
* **Provenances & Tooltips**: Inspect exact icon origins (`📱 Device APK` vs `🌐 Online HD`) and force re-extraction anytime.

### 💡 4. Native Scrcpy Screen Power Controls
* **Live Display Mode Control**: Turn off your phone's physical display via native Scrcpy live shortcuts (<kbd>Alt</kbd> + <kbd>O</kbd> / `POWER_MODE_OFF`) so nobody can see your phone screen while you continue mirroring and multitasking from PC.
* **Wake On Demand**: Instantly restore the physical screen (<kbd>Alt</kbd> + <kbd>Shift</kbd> + <kbd>O</kbd>) directly from the Quick Actions dock.

### 🌐 5. Intelligent Network & Device Detection
* **Real Network Interface Inspection**: Accurately differentiates between **`🌐 LAN`** (Wired Ethernet `eth0`, e.g. Android TV), **`📶 WiFi`** (`wlan0`), and **`🔌 USB`**, including Android 11+ mDNS TLS wireless debugging.
* **Hardware Serial Profile Persistence**: All custom settings, presets, and friendly aliases are strictly tied to permanent hardware serials (`ro.serialno`), preventing lost configurations across IP/port changes.
* **Subnet & mDNS Network Scanner**: High-speed parallel Wi-Fi discovery across 254 subnet IPs in < 1.5 seconds.
* **Persistent Pinned Devices**: Pin frequently used USB/Wi-Fi/LAN devices with configurable auto-reconnect on startup and permanent offline badge memory.

### 🔔 6. Windows System Tray & Desktop Shortcuts
* **Taskbar System Tray (`QSystemTrayIcon`)**: Minimizes to tray on close/minimize with background execution.
* **Tray Quick-Launch**: Right-click the system tray icon to 1-click launch favorite apps directly into standalone virtual display windows without opening the main window.
* **1-Click Desktop Shortcuts (`.lnk`)**: Automatically converts app logos to `.ico` and creates desktop shortcuts on your Windows desktop.

### 🔄 7. Scrcpy GitHub Auto-Downloader & Updater
* **GitHub Release Integration**: Automatically checks for official [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy) 64-bit Windows releases.
* **One-Click Deploy**: Downloads, extracts, unlocks, and updates the local binary runtime (`scrcpy/`) with a progress bar and changelog viewer.

### 🔋 8. Screen Timeout Safety & Flicker-Free Architecture
* **24-Hour Timeout Boost**: Automatically extends phone screen timeout during mirroring sessions to prevent unwanted sleep.
* **Multi-Session Reference Counting**: Tracks all open virtual displays and safely restores your phone's original timeout when the last session closes.
* **Flicker-Free Windows Subprocess Engine**: Uses `DETACHED_PROCESS` and asynchronous Qt worker threads to eliminate pseudo-console flashes and maintain 60 FPS smooth GUI performance.

---

## 🚀 Getting Started

### 1. Requirements
* Windows 10 / 11 (64-bit)
* Python 3.10+ (Python 3.13 recommended)

### 2. Quick Start
```bash
# Clone the repository
git clone https://github.com/ahmaddxb/Scrcpy-Studio.git
cd Scrcpy-Studio

# Install Python dependencies
pip install -r requirements.txt

# Launch application
python app.py
```
*Or simply double-click **`run.bat`**.*

### 3. Build Standalone Portable Executable (`.exe`)
To compile a single portable `.exe` bundle:
```bash
python scripts/build_exe.py
```
*Outputs a standalone **`dist/ScrcpyStudio.exe`** ready to run anywhere without Python installed.*

---

## 📁 Project Architecture

```
z:/Github/Scrcpy-UI/
├── app.py                      # Main application entry point & theme initialization
├── run.bat                     # 1-click launcher batch script
├── backup.bat / backup.py      # Timestamped project backup utility
├── requirements.txt            # Python dependencies (PySide6)
├── TODO.md                     # Roadmap and completed feature checklist
├── AGENTS.md                   # AI developer blueprint & codebase context
│
├── scrcpy/                     # Official Scrcpy & ADB Windows runtime
│   ├── scrcpy.exe              # Scrcpy client binary
│   ├── adb.exe                 # Android Debug Bridge binary
│   └── scrcpy-server           # Android server JAR
│
├── data/                       # Application cache & user persistence
│   ├── config.json             # Presets, pinned devices & favorite apps
│   └── icons/                  # High-density cached icon assets & manifest
│
├── core/                       # Backend controllers & background workers
│   ├── adb_manager.py          # ADB execution interface & network scanner
│   ├── config_manager.py       # Thread-safe JSON configuration manager
│   ├── process_manager.py      # Scrcpy supervisor & screen timeout ref-counter
│   ├── icon_manager.py         # Dual-engine on-device & web icon scraper
│   ├── scrcpy_updater.py       # GitHub release checker & binary downloader
│   └── shortcut_manager.py     # Windows .lnk shortcut generator with ICO converter
│
└── ui/                         # Presentation layer (PySide6 Qt6 widgets)
    ├── main_window.py          # Main dashboard, top header & system tray
    └── components/
        ├── device_card.py      # Device tile (battery %, model, state badges)
        ├── favorites_bar.py    # Favorite apps dock with dynamic scroll grid
        ├── app_launcher.py     # Package manager & virtual display presets
        ├── stream_panel.py     # Scrcpy parameters (bitrate, fps, encoders)
        ├── command_injector.py # Keystroke simulator & custom shell CLI
        ├── scrcpy_updater_dialog.py # GitHub binary updater dialog
        ├── drop_zone.py        # Drag-and-drop APK installer & file pusher
        └── log_viewer.py       # Real-time color-coded diagnostics terminal
```

---

## 📄 License
Distributed under the Apache License 2.0. See [`LICENSE.txt`](LICENSE.txt) for more information.
