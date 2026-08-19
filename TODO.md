# 📋 Scrcpy Studio — Roadmap & TODO List

This document tracks planned features, enhancements, and deployment tasks for Scrcpy Studio.

---

## 📦 0. Release & Deployment (High Priority)
- [x] **Scrcpy Binary Downloader & Auto-Updater from GitHub**:
  - Automatically query the official [Genymobile/scrcpy GitHub API](https://api.github.com/repos/Genymobile/scrcpy/releases/latest) for the latest release.
  - Download official Windows 64-bit binaries (`scrcpy-win64-vX.X.zip`) with a progress bar.
  - Auto-extract and deploy into the project folder (`scrcpy/`).
  - Seamlessly switch active runtime paths in `ConfigManager` without needing manual installation.
  - 1-click `[ 🔄 Check for Scrcpy Updates ]` button in GUI header/settings.
- [ ] **Build Standalone Windows Executable (`.exe`)**:
  - Package application using PyInstaller or Nuitka with embedded PySide6, bundled  icons, and theme assets.
  - Create single-click build script (`build_exe.bat`).
  - Ensure portable zero-dependency execution on any Windows 10/11 PC.
- [x] **Push to GitHub**:
  - Initialize clean `.gitignore` (ignore `__pycache__`, `data/icons/`, `build/`, `dist/`, `.gemini/`, `backups/`).
  - Initialize git repository and create initial commit.
  - Set up GitHub Actions CI/CD release workflow (`.github/workflows/build.yml`).

---

## 🪟 1. Windows Desktop Integration & System Tray
- [x] **Minimize to Windows System Tray**:
  - Keep the app running in the notification area with a sleek custom tray icon.
  - Option to start minimized on Windows boot.
- [x] **Tray Quick-Launch Menu**:
  - Right-click tray menu to 1-click launch any **Favorite App** (`Financisto`, `ENBD`, `Mashreq`, etc.) in a virtual display window without opening the main window.
- [x] **Create Windows Desktop Shortcuts (`.lnk`)**:
  - One-click button in Favorite Apps / App Launcher to create desktop shortcuts that launch specific apps directly in customized resolutions/windows.

---

## 📸 2. Media Studio (Screenshots & Screen Recording)
- [ ] **Instant Clipboard Screenshot**:
  - 1-click button to take a high-resolution phone screenshot and immediately copy it to the Windows clipboard for fast sharing.
- [ ] **Built-in Lossless MP4 / MKV Recorder**:
  - Dedicated record button with recording indicator.
  - Automatic saving to `Videos/Scrcpy/`.
  - Built-in Gallery / Playback viewer tab.

---

## ⌨️ 3. Global Hotkeys & Shortcut Management
- [ ] **System-Wide Global Hotkeys**:
  - Configurable hotkeys (e.g. `Ctrl + Alt + F` to open Financisto, `Ctrl + Alt + M` to mirror screen).
- [ ] **Keymapping & Gaming Overlays**:
  - Virtual on-screen touch simulation mapped to PC keyboard & mouse.

---

## 🪟 4. Multi-Window & Active Sessions Manager
- [ ] **Live Active Sessions Bar**:
  - Visual panel showing all active Scrcpy instances and virtual displays.
- [ ] **Tile Windows on Desktop**:
  - Automatically arrange and snap all open Scrcpy windows side-by-side on your desktop monitor.
- [ ] **1-Click "Close All"**:
  - Instantly terminate all active mirroring/app sessions and restore normal device settings.

---

## 📂 5. Two-Way Android File Explorer & Media Manager
- [ ] **Integrated Android File Browser Tab**:
  - Browse `/sdcard/Download`, `/sdcard/DCIM/Camera`, `/sdcard/Documents`.
  - Image and document preview viewer.
  - Batch upload/download with progress bars.

---

## ⚡ 6. Automation & Smart Triggers
- [ ] **Auto-Connect on Wi-Fi Discovery**:
  - Automatically pair and connect to pinned devices when they appear on the local network.
- [ ] **Auto-Launch App on Connect**:
  - Trigger favorite apps automatically upon connecting to a specific device.

---

## 📱 7. On-Device Native Icon Helper (Headless DEX)
- [ ] **Headless `app_process` DEX Runner**:
  - Compile lightweight `iconhelper.dex` to render 100% native Android 8–15 adaptive vector icons on-device without installing full APKs (refer to [`docs/icon_helper_architecture.md`](docs/icon_helper_architecture.md)).
