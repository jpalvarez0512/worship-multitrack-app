@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo Iniciando Worship Multitrack Server (entorno virtual .venv)
echo ============================================================
".venv\Scripts\python.exe" main.py
pause
