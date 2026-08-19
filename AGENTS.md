# 🤖 AGENTS.md — Scrcpy Studio Developer Context & Project Blueprint

This document is the **single source of truth** for AI agents, developers, and future sessions working on **Scrcpy Studio**. Read this file first when starting a new session to immediately understand the project architecture, conventions, workflows, and current status.

---

## 🎯 1. Project Overview & Tech Stack

**Scrcpy Studio** is a modern, high-performance desktop GUI manager for [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy) and Android Debug Bridge (ADB), designed for power users, developers, and multi-app multitasking.

* **Language**: Python 3.13+
* **GUI Framework**: PySide6 (Qt 6.x) with custom dark theme stylesheets (`QSS`)
* **Bundled Binaries**: Scrcpy v4.1 (64-bit Windows) located at [`scrcpy/`](file:///z:/Github/Scrcpy-UI/scrcpy/)
* **Platform**: Windows 10 / 11 (Supports standalone `.exe` distribution and `.bat` runners)
* **Target / Test Device**: Samsung Galaxy S25 Ultra (`SM_S938B`) on `192.168.1.x:5555`

---

## 📂 2. File & Directory Architecture

```
z:/Github/Scrcpy-UI/
├── app.py                      # Main entrypoint (initializes ConfigManager, MainWindow, QApplication)
├── run.bat                     # 1-click Windows launcher batch script
├── TODO.md                     # Roadmap, backlog, and completed feature checklist
├── AGENTS.md                   # This file (AI developer blueprint & codebase context)
│
├── scrcpy/                     # Bundled official Scrcpy v4.1 runtime
│   ├── scrcpy.exe              # Scrcpy client binary
│   ├── adb.exe                 # Android Debug Bridge binary
│   └── scrcpy-server           # Android server JAR
│
├── data/                       # Application persistence & cache
│   ├── config.json             # User settings, presets, pinned devices, favorite apps
│   └── icons/                  # Cached app icons (.png and converted .ico)
│       ├── manifest.json       # Provenance metadata ("adb" vs "web")
│       └── *.png / *.ico       # High-density cached icon assets
│
├── docs/                       # Technical architecture & research docs
│   └── icon_helper_architecture.md # Native on-device icon extraction research
│
├── core/                       # Backend logic, controllers & workers
│   ├── adb_manager.py          # ADB execution interface, AdbDevice dataclass, device scanner QThread
│   ├── config_manager.py       # Thread-safe JSON config manager & preset getter/setter
│   ├── process_manager.py      # Scrcpy process supervisor, screen timeout ref-counter, multi-session tracker
│   ├── icon_manager.py         # Dual-engine icon fetcher (ADB exec-out unzip + Web Store fallback + bulk scraper)
│   └── shortcut_manager.py     # Windows .lnk desktop shortcut generator & PNG->ICO converter
│
└── ui/                         # Presentation layer (PySide6 widgets)
    ├── main_window.py          # Main dashboard, top header, QSystemTrayIcon, sidebar, session routing
    └── components/
        ├── device_card.py      # Device tile (battery %, model, state badges, pin/unpin, OTG, stop)
        ├── favorites_bar.py    # Favorite apps dock with dynamic scroll grid, icon tooltips, context menu
        ├── app_launcher.py     # Package manager, 3rd-party filter, virtual display dialog, ADB bulk scraper
        ├── stream_panel.py     # Scrcpy settings (bitrate, fps, encoders, turn off screen, stay awake, DeX)
        ├── command_injector.py # Keystroke simulator, volume, navigation, custom shell CLI
        ├── drop_zone.py        # Drag-and-drop APK installer and file pusher
        ├── log_viewer.py       # Timestamped real-time log terminal with color-coded categories
        └── wireless_dialog.py  # Android 11+ pairing code dialog & direct IP connect tool
```

---

## 🔑 3. Key Systems & Mechanisms

### A. Independent Virtual Displays & PC Window Sizing
Scrcpy v4.1 allows creating independent virtual displays with standalone PC window geometry:
```bash
scrcpy -s 192.168.1.100:5555 --new-display=1080x2316/420 --window-width=450 --window-height=965 --start-app=tw.tib.financisto
```
* **Virtual Display Presets**: Stored in `config.json` under `virtual_display_presets` with fields: `id`, `label`, `value` (`WIDTHxHEIGHT/DPI`), `win_w` (PC window width), and `win_h` (PC window height).
* Configurable globally in **App Launcher** and individually per favorite app in **Favorite Apps Bar**.

### B. Screen Timeout Safety & Reference Counting (`core/process_manager.py`)
To prevent the phone's physical screen from going to sleep during mirroring without permanently modifying system settings:
* On session start: Queries original timeout via `settings get system screen_off_timeout` (e.g. `30000` ms) and sets it to 24 hours (`86400000` ms).
* **Reference Counter**: Tracks active sessions across multiple windows/apps. When the last session closes (count drops to 0), it automatically restores the original timeout on the phone.

### C. Dual-Engine App Icon Extraction (`core/icon_manager.py`)
* **Engine 1 (Direct ADB)**: Queries `pm path <pkg>`, lists APK contents via `zipinfo -1`, and streams the highest density PNG (`mipmap-xxxhdpi`, `drawable-xxhdpi`) via `adb exec-out "unzip -p <apk> <icon>"`.
* **Engine 2 (HD Web Store Fallback)**: For Android 14/15 apps using compiled Adaptive Vector XMLs, fetches the crisp 512×512 official icon from Google Play Store metadata.
* **Bulk Scraper**: `BulkIconScraperWorker(QThread)` runs a 4-worker thread pool to scrape all device apps in seconds.
* **Manifest Tracking**: Saved to `data/icons/manifest.json` (`"source": "adb" | "web"`) and displayed in hover tooltips and context menus.

### D. Windows Desktop Integration & System Tray
* **System Tray (`QSystemTrayIcon`)**: When closed/minimized, the app runs in the notification tray.
* **Tray Quick-Launch**: Right-click tray menu lists all favorite apps with their real icons to launch in virtual displays with 1-click without opening the GUI.
* **Desktop Shortcuts (`.lnk`)**: Uses Windows Script Host (`WScript.Shell`) via PowerShell to generate standalone `.lnk` shortcuts on the user's Desktop with converted `.ico` app logos.

---

## 🛠️ 4. Common Developer Commands

* **Run Application**:
  ```powershell
  python app.py
  ```
* **Run Tests / Headless Verification**:
  ```powershell
  python -c "import app; print('App syntax and imports OK')"
  ```
* **Check ADB Connected Devices**:
  ```powershell
  .\scrcpy\adb.exe devices -l
  ```

---

## 📋 5. Active Roadmap & Next Tasks (from `TODO.md`)

1. **🔄 Scrcpy Downloader & Auto-Updater**: Query Genymobile/scrcpy GitHub API, download and extract latest official 64-bit releases into project root with 1-click.
2. **📦 Build Standalone Executable (`.exe`)**: Create `build_exe.bat` using PyInstaller to package Python, PySide6, and `scrcpy` into a portable release.
3. **🚀 GitHub Repository Setup**: Configure `.gitignore` and push clean codebase to GitHub.
4. **📸 Media Studio Tab**: Add 1-click clipboard screenshots and lossless MP4/MKV recording gallery.
5. **⌨️ Global Windows Hotkeys**: Add background hotkeys (`Ctrl+Alt+F`, `Ctrl+Alt+M`).
6. **📂 Two-Way Android File Explorer**: Browse `/sdcard/Download` and `/sdcard/DCIM/Camera`.

---

## ⚠️ 6. Important Conventions & Rules

1. **Never kill background tasks unnecessarily**: When long commands run, use appropriate tools without polling loops.
2. **Always link files properly**: Use `[filename](file:///z:/Github/Scrcpy-UI/path/to/file)` with forward slashes.
3. **Preserve existing comments & docstrings**: Do not delete unrelated code or helper methods during edits.
4. **Windows Pathing**: Always convert `Path` objects to `str` when passing to `subprocess` or `QIcon`.
