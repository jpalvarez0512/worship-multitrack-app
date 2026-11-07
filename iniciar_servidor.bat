@echo off
chcp 65001 >nul
title Worship Multitrack Server - Consola Master
cd /d "%~dp0"

echo ======================================================================
echo          WORSHIP LIVE MULTITRACK ENGINE - CONSOLA MASTER
echo ======================================================================
echo.

:: 1. Comprobar si existe el entorno virtual .venv
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] No se encontro el entorno virtual local.
    echo Configurando la aplicacion por primera vez en esta computadora...
    echo.
    
    :: Comprobar si Python esta instalado en el sistema
    python --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python no esta instalado o no se encuentra en el PATH.
        echo ------------------------------------------------------------------
        echo Por favor descarga e instala Python 3.10 o 3.11 desde:
        echo https://www.python.org/downloads/
        echo.
        echo IMPORTANTE AL INSTALAR:
        echo Marca la casilla "Add python.exe to PATH" en la primera pantalla.
        echo ------------------------------------------------------------------
        echo.
        pause
        exit /b 1
    )
    
    echo [1/3] Creando entorno virtual local (.venv)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    
    echo [2/3] Instalando librerias de audio y servidor (toma ~1 minuto)...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
    ".venv\Scripts\pip.exe" install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Hubo un problema instalando las dependencias.
        pause
        exit /b 1
    )
    echo [3/3] Instalacion completada exitosamente!
    echo.
)

:: 2. Iniciar el servidor y abrir navegador
echo ======================================================================
echo  Iniciando servidor local y abriendo consola de control...
echo ======================================================================
echo.

:: Abrir navegador en segundo plano tras 2 segundos
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000/control"

:: Ejecutar el motor multitrack
".venv\Scripts\python.exe" main.py

if %errorlevel% neq 0 (
    echo.
    echo El servidor se ha detenido con un codigo de salida inesperado.
    pause
)
