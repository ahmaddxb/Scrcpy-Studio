import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def create_windows_shortcut(
    shortcut_name: str,
    target_exe: str,
    arguments: str = "",
    icon_path: str = "",
    working_dir: str = "",
    desktop: bool = True,
) -> bool:
    """Create a Windows .lnk shortcut on the user's Desktop."""
    try:
        desktop_dir = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
        if not desktop_dir.exists():
            desktop_dir = Path.home() / "Desktop"

        safe_title = "".join(c for c in shortcut_name if c.isalnum() or c in (" ", "_", "-", "(", ")")).strip()
        lnk_path = desktop_dir / f"{safe_title}.lnk"

        if not working_dir:
            working_dir = str(Path(target_exe).parent)

        ps_commands = [
            f"$ws = New-Object -ComObject WScript.Shell",
            f"$s = $ws.CreateShortcut('{str(lnk_path)}')",
            f"$s.TargetPath = '{target_exe}'",
            f"$s.Arguments = '{arguments}'",
            f"$s.WorkingDirectory = '{working_dir}'",
        ]
        if icon_path and Path(icon_path).exists():
            ps_commands.append(f"$s.IconLocation = '{icon_path}, 0'")
        ps_commands.append("$s.Save()")

        ps_script = "; ".join(ps_commands)
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return lnk_path.exists()
    except Exception as e:
        print("Shortcut creation error:", e)
        return False


def convert_png_to_ico(png_path: str) -> Optional[str]:
    """Convert PNG icon to ICO format for Windows desktop shortcuts."""
    try:
        p = Path(png_path)
        if not p.exists():
            return None
        ico_path = p.with_suffix(".ico")
        if not ico_path.exists() or ico_path.stat().st_mtime < p.stat().st_mtime:
            from PySide6.QtGui import QPixmap

            pix = QPixmap(str(p))
            if not pix.isNull():
                pix.save(str(ico_path), "ICO")
        if ico_path.exists() and ico_path.stat().st_size > 0:
            return str(ico_path)
    except Exception:
        pass
    return None


def create_app_desktop_shortcut(
    scrcpy_exe: str,
    serial: str,
    package: str,
    app_name: str,
    display_res: str = "",
    win_w: str = "",
    win_h: str = "",
    icon_png: str = "",
) -> Tuple[bool, str]:
    """Generate a 1-click standalone desktop shortcut for an Android app."""
    try:
        scrcpy_path = Path(scrcpy_exe)
        if not scrcpy_path.exists():
            return False, f"Scrcpy executable not found at {scrcpy_exe}"

        # Build arguments
        args = []
        if serial:
            args.append(f"-s {serial}")

        clean_title = app_name or package.split(".")[-1].capitalize()
        args.append(f'--window-title="[{clean_title}] {serial}"')

        # Virtual display or main display
        if display_res:
            args.append(f"--new-display={display_res}")
        else:
            args.append("--new-display")

        if win_w:
            args.append(f"--window-width={win_w}")
        if win_h:
            args.append(f"--window-height={win_h}")

        args.append("--stay-awake")
        args.append(f"--start-app={package}")

        args_str = " ".join(args)

        # Convert icon if available
        ico_path = ""
        if icon_png and Path(icon_png).exists():
            ico_path = convert_png_to_ico(icon_png) or ""

        safe_name = f"{clean_title} (Scrcpy)"
        ok = create_windows_shortcut(
            shortcut_name=safe_name,
            target_exe=str(scrcpy_path),
            arguments=args_str,
            icon_path=ico_path,
            working_dir=str(scrcpy_path.parent),
            desktop=True,
        )

        desktop_path = Path(os.environ.get("USERPROFILE", "")) / "Desktop" / f"{safe_name}.lnk"
        return ok, str(desktop_path)
    except Exception as e:
        return False, str(e)
