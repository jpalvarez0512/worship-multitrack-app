"""
Worship Multitrack App - Punto de Entrada Principal
Ejecuta el servidor de audio, red local y sincronización para iglesias.
"""

import os
import sys
import threading
import time
import webbrowser
import uvicorn

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def open_browser_delayed(url: str = "http://localhost:8000/control", delay: float = 1.2):
    """Abre el navegador web en el Panel de Control automáticamente tras iniciar el servidor."""
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    threading.Thread(target=open_browser_delayed, daemon=True).start()
    uvicorn.run("src.server.app:app", host="0.0.0.0", port=8000, reload=False)
