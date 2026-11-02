@echo off
set "UNINSTALL_SCRIPT=%~dp0uninstall.ps1"
cd /d "%TEMP%" || exit /b 1
start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%UNINSTALL_SCRIPT%"
exit /b 0
