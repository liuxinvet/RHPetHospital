@echo off
title RHPetHospital - Build EXE
cd /d %~dp0

echo ============================================
echo   RHPetHospital - One-click EXE Builder
echo ============================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found.
    echo Install Python from https://www.python.org/downloads/
    echo IMPORTANT: during install, check "Add python.exe to PATH"
    echo Then close this window and double-click this file again.
    pause
    exit /b 1
)

echo [1/3] Checking PyInstaller ...
python -m pip install pyinstaller -q
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller install failed. Check network and retry.
    pause
    exit /b 1
)

echo [2/3] Building EXE (about 1-3 minutes) ...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "RHPetHospital" ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "schema.sql;." ^
  --hidden-import "flask" ^
  --collect-all "webview" ^
  desktop_client.py

if %errorlevel% neq 0 (
    echo [ERROR] Build failed. Send the error text above to the developer.
    pause
    exit /b 1
)

echo [3/3] DONE!
echo.
echo Output file: dist\RHPetHospital.exe
echo.
echo HOW TO USE:
echo   1. Copy dist\RHPetHospital.exe anywhere (e.g. Desktop)
echo      You may rename it to whatever you like, e.g. "RHPetHospital.exe"
echo   2. Double-click it. A desktop window opens automatically.
echo   3. Data is saved in "data" folder next to the exe. Back up that folder to back up all data.
echo   4. Default login: admin / 123456
echo.
echo NOTE: First launch takes a few seconds. That is normal.
pause
