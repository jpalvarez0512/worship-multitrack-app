@echo off
chcp 65001 >nul
title Worship Multitrack Live Launcher

if exist "dist\WorshipMultitrack\WorshipMultitrack.exe" (
    cd dist\WorshipMultitrack
    start WorshipMultitrack.exe
    exit /b 0
)

if exist ".venv\Scripts\python.exe" (
    start "" "http://localhost:8000/control"
    .\.venv\Scripts\python.exe main.py
    exit /b 0
)

echo [ERROR] No se encontró el entorno de Python ni el ejecutable compilado.
echo Ejecuta 'iniciar_servidor.bat' o compila con 'scripts/build_standalone.py'.
pause
