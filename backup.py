import datetime
import os
import sys
import zipfile
from pathlib import Path
from typing import Optional

# Directories to exclude from backup
EXCLUDE_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".gemini",
    "backups",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".tmp",
    ".log",
}


def create_project_backup(
    project_root: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    include_binaries: bool = True,
) -> Path:
    """Create a clean, timestamped ZIP backup of the entire Scrcpy Studio project."""
    if project_root is None:
        project_root = Path(__file__).parent.resolve()

    if output_dir is None:
        output_dir = project_root / "backups"

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_type = "Full" if include_binaries else "CodeOnly"
    zip_filename = f"Scrcpy_Studio_Backup_{backup_type}_{timestamp}.zip"
    zip_path = output_dir / zip_filename

    print(f"[*] Creating {backup_type} backup for: {project_root}")
    print(f"[*] Destination: {zip_path}\n")

    files_count = 0
    total_uncompressed_bytes = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(project_root):
            rel_dir = Path(root).relative_to(project_root)

            # Filter excluded directories
            dirs[:] = [
                d
                for d in dirs
                if d not in EXCLUDE_DIRS
                and (include_binaries or (d != "scrcpy" and not d.startswith("scrcpy-win64")))
            ]

            # Don't backup inside output directory
            if output_dir in Path(root).parents or Path(root) == output_dir:
                continue

            for file in files:
                ext = Path(file).suffix.lower()
                if ext in EXCLUDE_EXTENSIONS:
                    continue

                full_path = Path(root) / file
                arcname = str(rel_dir / file) if str(rel_dir) != "." else file

                try:
                    zip_file.write(full_path, arcname)
                    files_count += 1
                    total_uncompressed_bytes += full_path.stat().st_size
                except Exception as e:
                    print(f"[!] Warning: Could not add {file}: {e}")

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    raw_size_mb = total_uncompressed_bytes / (1024 * 1024)

    print(f"[+] Backup created successfully!")
    print(f"    - Total Files Archived: {files_count}")
    print(f"    - Uncompressed Size:    {raw_size_mb:.2f} MB")
    print(f"    - Compressed Zip Size:  {zip_size_mb:.2f} MB")
    print(f"    - Archive Path:         {zip_path}\n")

    return zip_path


if __name__ == "__main__":
    include_bin = True
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("--code-only", "-c", "code"):
        include_bin = False

    create_project_backup(include_binaries=include_bin)
