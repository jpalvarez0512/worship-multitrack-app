@echo off
chcp 65001 >nul
title Actualizador Automatico - Worship Multitrack Live
cd /d "%~dp0"

echo ================================================================
echo    WORSHIP MULTITRACK LIVE - ACTUALIZADOR DE SISTEMA
echo ================================================================
echo.

echo [1/4] Cerrando instancia previa si se encuentra abierta...
taskkill /F /IM WorshipMultitrack.exe >nul 2>&1
timeout /t 1 /nobreak >nul

if exist ".git" (
    echo [2/4] Carpeta de desarrollo detectada. Conectando con GitHub via Git...
    git fetch origin main
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] No se pudo conectar a GitHub. Verifica tu conexion a Internet.
        pause
        exit /b 1
    )
    echo [3/4] Aplicando cambios desde origin/main...
    git pull origin main
    if %ERRORLEVEL% neq 0 (
        git stash
        git pull origin main
        git stash pop
    )
    if exist ".venv\Scripts\python.exe" (
        echo [4/4] Verificando dependencias Python...
        .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
    )
) else (
    echo [2/4] Modo Portable detectado. Descargando ultima version desde GitHub...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ErrorActionPreference = 'Stop'; " ^
      "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
      "$zipPath = Join-Path $env:TEMP 'wml_portable_update.zip'; " ^
      "$extPath = Join-Path $env:TEMP 'wml_portable_extracted'; " ^
      "if (Test-Path $zipPath) { Remove-Item $zipPath -Force }; " ^
      "if (Test-Path $extPath) { Remove-Item $extPath -Recurse -Force }; " ^
      "Write-Host '      Descargando paquete desde GitHub (main)...'; " ^
      "Invoke-WebRequest -Uri 'https://github.com/jpalvarez0512/worship-multitrack-app/archive/refs/heads/main.zip' -OutFile $zipPath -UseBasicParsing; " ^
      "Write-Host '[3/4] Extrayendo e instalando archivos actualizados...'; " ^
      "Expand-Archive -Path $zipPath -DestinationPath $extPath -Force; " ^
      "$repoRoot = Get-ChildItem -Path $extPath -Directory | Select-Object -First 1 -ExpandProperty FullName; " ^
      "$exeSrc = Join-Path $repoRoot 'portable_bin\WorshipMultitrack.exe'; " ^
      "if (Test-Path $exeSrc) { Copy-Item $exeSrc -Destination '.\WorshipMultitrack.exe' -Force }; " ^
      "$baseZipSrc = Join-Path $repoRoot 'portable_bin\base_library.zip'; " ^
      "if ((Test-Path $baseZipSrc) -and (Test-Path '.\_internal')) { Copy-Item $baseZipSrc -Destination '.\_internal\base_library.zip' -Force }; " ^
      "$srcDir = Join-Path $repoRoot 'src'; " ^
      "if ((Test-Path $srcDir) -and (Test-Path '.\_internal')) { Copy-Item $srcDir -Destination '.\_internal' -Recurse -Force }; " ^
      "$staticDir = Join-Path $repoRoot 'static'; " ^
      "if ((Test-Path $staticDir) -and (Test-Path '.\_internal')) { Copy-Item $staticDir -Destination '.\_internal' -Recurse -Force }; " ^
      "$verFile = Join-Path $repoRoot 'version.json'; " ^
      "if (Test-Path $verFile) { Copy-Item $verFile -Destination '.\version.json' -Force }; " ^
      "Remove-Item $zipPath -Force -ErrorAction SilentlyContinue; " ^
      "Remove-Item $extPath -Recurse -Force -ErrorAction SilentlyContinue; " ^
      "Write-Host '[4/4] Archivos del sistema actualizados correctamente.'"
    if %ERRORLEVEL% neq 0 (
        echo.
        echo [ERROR] Ocurrio un problema al descargar o aplicar la actualizacion.
        echo Verifica que la computadora tenga conexion a Internet.
        pause
        exit /b 1
    )
)

echo.
echo ================================================================
echo [OK] ACTUALIZACION COMPLETADA CON EXITO
echo Tus canciones (tracks/), configuracion (config/) y recursos (assets/)
echo estan intactos y 100%% preservados.
echo ================================================================
echo.

if exist "WorshipMultitrack.exe" (
    echo Iniciando WorshipMultitrack.exe...
    start "" "WorshipMultitrack.exe"
    timeout /t 3 /nobreak >nul
    exit /b 0
)

pause
