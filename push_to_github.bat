@echo off
title Scrcpy Studio — Push to GitHub
echo ============================================================
echo           Scrcpy Studio — GitHub Sync & Push Tool
echo ============================================================
echo.

:: Check if git is installed
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Error: Git is not found in your PATH.
    echo Please install Git for Windows from https://git-scm.com/
    pause
    exit /b 1
)

:: Check if remote 'origin' exists
git remote get-url origin >nul 2>nul
if %errorlevel% neq 0 (
    echo [*] No GitHub remote repository configured yet.
    echo.
    set /p REPO_URL="Enter your GitHub Repository URL (e.g. https://github.com/username/Scrcpy-Studio.git): "
    if "%REPO_URL%"=="" (
        echo [!] No URL provided. Aborting.
        pause
        exit /b 1
    )
    echo [*] Adding remote origin: %REPO_URL%
    git remote add origin %REPO_URL%
)

echo.
echo [*] Current Git Remote:
git remote -v
echo.

echo [*] Staging tracked file changes...
git add .

git status --short
echo.

set /p COMMIT_MSG="Enter commit message (Press Enter for 'Update Scrcpy Studio'): "
if "%COMMIT_MSG%"=="" set COMMIT_MSG=Update Scrcpy Studio

echo.
echo [*] Committing changes...
git commit -m "%COMMIT_MSG%"

echo.
echo [*] Pushing to GitHub (main branch)...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo [✓] Successfully pushed to GitHub!
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo [!] Push encountered an issue. Check your credentials or branch permissions.
    echo ============================================================
)

echo.
echo Press any key to exit.
pause >nul
