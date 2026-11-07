#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "======================================================================"
echo "         WORSHIP LIVE MULTITRACK ENGINE - CONSOLA MASTER"
echo "======================================================================"
echo ""

if [ ! -f ".venv/bin/python" ]; then
    echo "[INFO] Configurando entorno virtual por primera vez..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip --quiet
    .venv/bin/pip install -r requirements.txt
    echo "[INFO] Instalación de dependencias completada."
fi

# Abrir navegador tras 2 segundos (macOS o Linux)
if command -v open >/dev/null 2>&1; then
    (sleep 2 && open http://localhost:8000/control) &
elif command -v xdg-open >/dev/null 2>&1; then
    (sleep 2 && xdg-open http://localhost:8000/control) &
fi

echo "Iniciando servidor Worship Multitrack..."
.venv/bin/python main.py
