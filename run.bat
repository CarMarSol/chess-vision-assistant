@echo off
title Chess Vision Assistant
cd /d "%~dp0"

echo =======================================================
echo   Iniciando Chess Vision Assistant
echo =======================================================
echo Verificando dependencias y ejecutable de Stockfish...

if not exist "bin\stockfish.exe" (
    echo [ERROR] No se encontro bin\stockfish.exe
    pause
    exit /b 1
)

python main.py %*
if errorlevel 1 (
    echo [AVISO] La aplicacion finalizo con codigo de error %errorlevel%
    pause
)
