"""
Worship Multitrack App - Punto de Entrada Principal
Ejecuta el servidor de audio, red local y sincronización para iglesias.
"""

import importlib.machinery
import os
import socket
import sys
import threading
import time
import webbrowser

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# En modo portable (PyInstaller), priorizar archivos en _internal/src para que
# actualizar.bat pueda actualizar código Python y vistas HTML sin recompilar.
if getattr(sys, "frozen", False):
    _bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    if _bundle_dir not in sys.path:
        sys.path.insert(0, _bundle_dir)
    if os.path.isdir(os.path.join(_bundle_dir, "src")):
        if importlib.machinery.PathFinder in sys.meta_path:
            sys.meta_path.remove(importlib.machinery.PathFinder)
        sys.meta_path.insert(0, importlib.machinery.PathFinder)


def open_url_in_browser(url: str) -> None:
    """Abre la URL en el navegador predeterminado de Windows o multiplataforma."""
    try:
        if sys.platform.startswith("win") and hasattr(os, "startfile"):
            os.startfile(url)
            return
    except Exception:
        pass
    try:
        webbrowser.open(url, new=2)
    except Exception:
        pass


def is_port_in_use(port: int = 8000, host: str = "127.0.0.1") -> bool:
    """Verifica si el puerto local ya está siendo utilizado por una instancia activa."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def wait_and_open_browser(url: str = "http://localhost:8000/control", port: int = 8000, timeout: float = 45.0) -> None:
    """Espera a que el servidor escuche en el puerto indicado y abre el navegador inmediatamente."""
    start_t = time.time()
    while time.time() - start_t < timeout:
        if is_port_in_use(port=port):
            time.sleep(0.25)
            open_url_in_browser(url)
            return
        time.sleep(0.25)


if __name__ == "__main__":
    PORT = 8000
    CONTROL_URL = f"http://localhost:{PORT}/control"

    print("================================================================", flush=True)
    print("  WORSHIP MULTITRACK LIVE - INICIANDO SISTEMA...", flush=True)
    print("  Cargando motor de audio y consola local, por favor espera...", flush=True)
    print("================================================================", flush=True)

    # Si el servidor ya está corriendo en este equipo (puerto 8000 ocupado),
    # abrir directamente el navegador en la consola de control sin fallar.
    if is_port_in_use(port=PORT):
        print("\n[OK] El servidor Worship Multitrack ya se encuentra activo en este equipo.", flush=True)
        print(f"Abriendo Consola de Control en: {CONTROL_URL}", flush=True)
        open_url_in_browser(CONTROL_URL)
        time.sleep(2.5)
        sys.exit(0)

    try:
        import uvicorn
        from src.server.app import app

        threading.Thread(
            target=wait_and_open_browser,
            args=(CONTROL_URL, PORT),
            daemon=True,
        ).start()

        uvicorn.run(app, host="0.0.0.0", port=PORT, reload=False)
    except Exception as exc:
        print(f"\n[ERROR AL INICIAR EL SERVIDOR]: {exc}", flush=True)
        try:
            input("\nPresiona ENTER para cerrar esta ventana...")
        except Exception:
            time.sleep(10)
