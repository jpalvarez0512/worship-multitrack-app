"""
Script de Verificación y Diagnóstico del Servidor de Sincronización y WebSockets
"""

import os
import sys

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from src.server.app import app


def run_server_tests():
    print("=" * 60)
    print("🌐 INICIANDO PRUEBAS DEL SERVIDOR DE RED Y WEBSOCKETS")
    print("=" * 60)

    with TestClient(app) as client:
        # 1. Información de Red LAN
        print("\n1. Verificando endpoint de red LAN (/api/network-info)...")
        r = client.get("/api/network-info")
        assert r.status_code == 200, f"Error {r.status_code}: {r.text}"
        net_info = r.json()
        print(f"   ✓ IP Local detectada: {net_info['local_ip']}:{net_info['port']}")
        print(f"   ✓ URL Músicos:        {net_info['musicians_url']}")
        print(f"   ✓ URL Proyección:     {net_info['projection_url']}")

        # 2. Estado General del Reproductor
        print("\n2. Verificando estado inicial (/api/status)...")
        r = client.get("/api/status")
        assert r.status_code == 200, f"Error {r.status_code}: {r.text}"
        status = r.json()
        print(f"   ✓ Canción activa:     {status['song']['title']} ({status['song']['artist']})")
        print(f"   ✓ Duración:           {status['duration_seconds']}s | BPM: {status['song']['bpm']}")
        print(f"   ✓ Modo de ruteo:      {status['routing_mode']}")

        # 3. Canción y Transposición en Tiempo Real
        print("\n3. Verificando transposición dinámica (/api/song?transpose=2)...")
        r_orig = client.get("/api/song?transpose=0")
        assert r_orig.json()["key"] == "G"
        r_trans = client.get("/api/song?transpose=2")
        trans_key = r_trans.json()["key"]
        print(f"   ✓ Tono original:      {r_orig.json()['key']}")
        print(f"   ✓ Tono transcurrido +2 semitonos: {trans_key} (esperado: A)")
        assert trans_key == "A", f"Error en transposición: esperado A, obtenido {trans_key}"

        # 4. Mezclador de Stems
        print("\n4. Verificando stems (/api/stems)...")
        r = client.get("/api/stems")
        assert r.status_code == 200
        stems = r.json()
        print(f"   ✓ Stems cargados ({len(stems)}): {', '.join(s['name'] for s in stems)}")
        assert len(stems) >= 4, "Deberían haber al menos 4 stems cargados"

        # 5. Entrega de Páginas Web HTML
        print("\n5. Verificando entrega de interfaces web HTML...")
        r_mus = client.get("/musicians")
        assert r_mus.status_code == 200 and "Terminal Músicos" in r_mus.text
        print("   ✓ Página de músicos (/musicians): OK")

        r_proj = client.get("/projection")
        assert r_proj.status_code == 200 and "Pantalla de Proyección" in r_proj.text
        print("   ✓ Pantalla de proyección (/projection): OK")

        r_ctrl = client.get("/control")
        assert r_ctrl.status_code == 200 and "Consola Central de Control" in r_ctrl.text
        print("   ✓ Consola de control (/control): OK")

        # 6. WebSocket y Sincronización mini-NTP
        print("\n6. Verificando canal WebSocket (/ws/musicians)...")
        with client.websocket_connect("/ws/musicians") as websocket:
            # Enviar ping de calibración de reloj
            websocket.send_json({"type": "sync_ping", "client_time": 1000.0})
            data = websocket.receive_json()
            assert data["type"] == "sync_pong"
            print(f"   ✓ Sincronización mini-NTP: Recibido pong con latencia calculable.")
            print(f"     Server time: {data['server_time']}, Song pos: {data['song_pos']}")

    print("\n" + "=" * 60)
    print("✅ TODAS LAS PRUEBAS DEL SERVIDOR PASARON EXITOSAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    run_server_tests()
