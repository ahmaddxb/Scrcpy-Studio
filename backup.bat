@echo off
title Scrcpy Studio - Project Backup
echo ============================================================
echo           Scrcpy Studio - Automated Project Backup
echo ============================================================
echo.

python "%~dp0backup.py" %*

echo.
echo ============================================================
echo Backup complete! Press any key to exit.
pause >nul
