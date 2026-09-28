@echo off
rem SOS: joins the image parts in this folder and checks them against SHA256SUMS.
rem Put the .part files, SHA256SUMS, sos-join.ps1 and this file into one folder, double-click it.
cd /d "%~dp0"
if not exist "%~dp0sos-join.ps1" (
    echo sos-join.ps1 is missing: download it from the same release page into this folder.
    echo.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sos-join.ps1"
echo.
pause
