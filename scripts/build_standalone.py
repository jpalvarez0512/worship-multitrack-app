"""
Script de Compilación Portable y Empaquetado Autónomo para Windows
Genera la carpeta portable y el ejecutable 'WorshipMultitrack.exe'
listo para ser copiado en cualquier PC de iglesia sin requerir Python instalado.
"""

import os
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIST_DIR = os.path.join(ROOT_DIR, "dist")
BUILD_DIR = os.path.join(ROOT_DIR, "build")
APP_OUTPUT_DIR = os.path.join(DIST_DIR, "WorshipMultitrack")


def build_portable_app():
    print("=" * 64)
    print("COMPILADOR PORTABLE: WORSHIP MULTITRACK LIVE")
    print("=" * 64)

    os.chdir(ROOT_DIR)

    # Separador de datos en Windows es ';'
    sep = ";" if sys.platform.startswith("win") else ":"

    add_data_args = [
        f"--add-data={os.path.join('src', 'clients', 'web')}{sep}{os.path.join('src', 'clients', 'web')}",
        f"--add-data=assets{sep}assets",
    ]
    if os.path.exists(os.path.join(ROOT_DIR, "static")):
        add_data_args.append(f"--add-data=static{sep}static")

    hidden_imports = [
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=sounddevice",
        "--hidden-import=cffi",
        "--hidden-import=numpy",
        "--hidden-import=fastapi",
        "--hidden-import=starlette",
        "--hidden-import=websockets",
        "--hidden-import=multipart",
        "--hidden-import=python_multipart",
        "--hidden-import=soundfile",
        "--collect-submodules=src",
    ]

    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=WorshipMultitrack",
        "--onedir",
        "--noconfirm",
        "--clean",
    ] + add_data_args + hidden_imports + ["main.py"]

    print("[1/3] Ejecutando PyInstaller para empaquetar binario autonomo...")
    res = subprocess.run(pyinstaller_cmd)
    if res.returncode != 0:
        print("[ERROR] Error durante la compilacion con PyInstaller.")
        sys.exit(res.returncode)

    print("[2/3] Estructurando carpetas protegidas de datos en el paquete portable...")
    # Crear carpetas de usuario tracks/ y config/ en dist/WorshipMultitrack
    target_tracks = os.path.join(APP_OUTPUT_DIR, "tracks")
    target_config = os.path.join(APP_OUTPUT_DIR, "config")
    target_assets = os.path.join(APP_OUTPUT_DIR, "assets")

    os.makedirs(target_tracks, exist_ok=True)
    os.makedirs(target_config, exist_ok=True)
    os.makedirs(target_assets, exist_ok=True)

    # Copiar canciones existentes si hay y pre-generar library_index.json
    src_tracks = os.path.join(ROOT_DIR, "tracks")
    if os.path.exists(src_tracks):
        for item in os.listdir(src_tracks):
            src_item = os.path.join(src_tracks, item)
            dst_item = os.path.join(target_tracks, item)
            if os.path.isdir(src_item) and not os.path.exists(dst_item):
                shutil.copytree(src_item, dst_item)
    try:
        sys.path.insert(0, ROOT_DIR)
        from src.core.song_loader import SongLoader
        SongLoader(tracks_root=target_tracks).scan_songs(force_refresh=True)
    except Exception as ex:
        print(f"[WARN] No se pudo pre-generar library_index.json: {ex}")

    # Copiar config existente si hay
    src_config = os.path.join(ROOT_DIR, "config")
    if os.path.exists(src_config):
        for item in os.listdir(src_config):
            src_item = os.path.join(src_config, item)
            dst_item = os.path.join(target_config, item)
            if not os.path.exists(dst_item):
                if os.path.isdir(src_item):
                    shutil.copytree(src_item, dst_item)
                else:
                    shutil.copy2(src_item, dst_item)

    # Copiar assets (cues y video loops)
    src_assets = os.path.join(ROOT_DIR, "assets")
    if os.path.exists(src_assets):
        for item in os.listdir(src_assets):
            src_item = os.path.join(src_assets, item)
            dst_item = os.path.join(target_assets, item)
            if not os.path.exists(dst_item):
                if os.path.isdir(src_item):
                    shutil.copytree(src_item, dst_item)
                else:
                    shutil.copy2(src_item, dst_item)

    # Copiar script de actualizacion
    src_updater = os.path.join(ROOT_DIR, "actualizar.bat")
    if os.path.exists(src_updater):
        shutil.copy2(src_updater, os.path.join(APP_OUTPUT_DIR, "actualizar.bat"))

    # Crear lanzador directo 1-clic dentro de la carpeta portable
    launcher_path = os.path.join(APP_OUTPUT_DIR, "Iniciar_WorshipMultitrack.bat")
    with open(launcher_path, "w", encoding="utf-8") as lf:
        lf.write(
            "@echo off\n"
            "chcp 65001 >nul\n"
            "title Worship Multitrack Live\n"
            "cd /d \"%~dp0\"\n"
            "WorshipMultitrack.exe\n"
        )

    print("\n" + "=" * 64)
    print("[OK] PAQUETE PORTABLE GENERADO CON EXITO")
    print(f"Carpeta: {APP_OUTPUT_DIR}")
    print(f"Ejecutable: {os.path.join(APP_OUTPUT_DIR, 'WorshipMultitrack.exe')}")
    print("Esta carpeta puede copiarse directamente en un pendrive o en cualquier")
    print("computadora de iglesia y funcionara al instante con doble clic.")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    build_portable_app()
