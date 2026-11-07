@echo off
chcp 65001 >nul
title Actualizador - Worship Multitrack App

echo ================================================================
echo    WORSHIP MULTITRACK LIVE - ACTUALIZADOR DE SISTEMA
echo ================================================================
echo.
echo Verificando actualizaciones para la versión local...
echo.

where git >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [1/3] Conectando con el repositorio oficial en GitHub...
    git fetch origin main
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] No se pudo conectar a Internet o a GitHub. Verifica tu conexión de red.
        pause
        exit /b 1
    )

    echo [2/3] Descargando últimas mejoras de código y motor de audio...
    git pull origin main
    if %ERRORLEVEL% neq 0 (
        echo [AVISO] Git pull detectó cambios locales. Aplicando actualización segura...
        git stash
        git pull origin main
        git stash pop
    )

    if exist .venv\Scripts\python.exe (
        echo [3/3] Verificando dependencias del sistema...
        .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
    )

    echo.
    echo ================================================================
    echo [OK] ¡ACTUALIZACIÓN COMPLETADA CON ÉXITO!
    echo Tus canciones (tracks/), configuración (config/) y guías de voz (assets/)
    echo están intactas y 100%% preservadas.
    echo ================================================================
    echo.
    echo Puedes iniciar el servidor ejecutando: iniciar_servidor.bat
    echo.
) else (
    echo [MODO PORTÁTIL] Git no está instalado en este equipo.
    echo Para actualizar la versión portable:
    echo 1. Descarga el paquete más reciente desde:
    echo    https://github.com/jpalvarez0512/worship-multitrack-app/releases/latest
    echo 2. Extrae el contenido en esta misma carpeta.
    echo 3. Tus carpetas 'tracks/', 'config/' y 'assets/' NUNCA se borran.
    echo.
)

pause
