"""
Worship Multitrack App - Punto de Entrada Principal
Ejecuta el servidor de audio, red local y sincronización para iglesias.
"""

import sys
import uvicorn

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    uvicorn.run("src.server.app:app", host="0.0.0.0", port=8000, reload=False)
