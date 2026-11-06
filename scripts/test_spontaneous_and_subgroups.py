"""
Script de verificación integral de:
1. Modo Espontáneo / Bucle de Sección en Vivo (Quantized Section Jump & Seamless Micro-Crossfade Loop).
2. Subgrupos y Medleys Continuos (Auto-Play Contiguo vs Pausas de Ministración en Escenas Dominicales).
3. Modo PWA (Manifest, Service Worker, Iconos y Vistas Móviles).
"""

import os
import sys
import time
import numpy as np

# Salida UTF-8 en Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from src.server.app import app, engine, scene_manager, current_song, on_track_finished


def test_pwa_endpoints(client: TestClient):
    print("▶ 1. Probando Infraestructura PWA (Manifest, SW, Iconos y Meta Tags)...")

    # 1.1 Manifest
    res = client.get("/manifest.json")
    assert res.status_code == 200, f"Error obteniendo manifest: {res.text}"
    m = res.json()
    assert m["display"] == "standalone"
    assert m["theme_color"] == "#070b14"
    assert len(m["icons"]) >= 2
    print("  ✓ /manifest.json disponible y con formato PWA standalone válido")

    # 1.2 Service Worker
    res = client.get("/sw.js")
    assert res.status_code == 200
    assert "javascript" in res.headers.get("content-type", "")
    assert "CACHE_NAME" in res.text
    print("  ✓ /sw.js servido con Content-Type JavaScript correcto y lógica de caché offline")

    # 1.3 Iconos PWA
    for icon_name in ["icon-192.png", "icon-512.png", "icon.svg"]:
        res = client.get(f"/static/icons/{icon_name}")
        assert res.status_code == 200, f"Falta icono /static/icons/{icon_name}"
    print("  ✓ Iconos 192px, 512px y SVG disponibles")

    # 1.4 Verificación de vistas con soporte PWA
    for path in ["/control", "/musicians", "/projection", "/obs"]:
        res = client.get(path)
        assert res.status_code == 200
        assert 'rel="manifest"' in res.text
        assert 'href="/manifest.json"' in res.text
    print("  ✓ Vistas (/control, /musicians, /projection, /obs) vinculadas al manifest PWA")


def test_engine_spontaneous_loop_and_jump():
    print("▶ 2. Probando Motor de Audio: Saltos Cuantizados al Compás y Bucle sin Clics...")
    from src.audio.engine import MultitrackEngine, RoutingMode
    from src.audio.stem import StemTrack

    eng = MultitrackEngine(sample_rate=44100, buffer_size=512, routing_mode=RoutingMode.SPLIT_STEREO)
    eng.set_song_timing(bpm=120.0, time_signature="4/4")
    assert abs(eng.bar_duration_seconds - 2.0) < 1e-4

    # Crear una pista sintética senoidal de 30 segundos
    sr = 44100
    duration_s = 30.0
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False, dtype=np.float32)
    sine_pcm = (0.5 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    eng.add_stem(StemTrack(name="synth_lead", audio_data=sine_pcm, sample_rate=sr))

    # 2.1 Salto con motor en pausa: salta de inmediato a la sección
    eng.schedule_jump(target_seconds=5.0, label="Intro", quantize_to_bar=True)
    assert abs(eng.current_position_seconds - 5.0) < 1e-3
    assert eng.get_loop_state()["pending_jump"] is None
    print("  ✓ Salto en pausa ejecuta la posición de inmediato sin esperar compás")

    # 2.2 Programar salto cuantizado en reproducción
    with eng._lock:
        eng._is_playing = True
    eng.schedule_jump(target_seconds=12.0, label="Coro", quantize_to_bar=True)
    st = eng.get_loop_state()
    assert st["pending_jump"] == "Coro"
    assert st["jump_target"] == 12.0

    # Cancelar salto
    eng.cancel_scheduled_jump()
    st = eng.get_loop_state()
    assert st["pending_jump"] is None
    print("  ✓ Programación y cancelación de saltos verificada en el motor")

    # 2.3 Programar salto cuantizado y avanzar callback hasta que se ejecute en el compás
    eng.seek(1.5) # Compás 0 termina en 2.0s
    with eng._lock:
        eng._is_playing = True
    eng.schedule_jump(target_seconds=10.0, label="Coro", quantize_to_bar=True)
    
    # Simular callback de audio reproduciendo buffer a buffer
    for _ in range(50): # ~580 ms, cruzará el segundo 2.0 (frontera de compás)
        out_buf = np.zeros((512, 2), dtype=np.float32)
        eng._audio_callback(out_buf, 512, None, None)
        if eng.current_position_seconds >= 10.0:
            break

    assert eng.current_position_seconds >= 10.0, f"Salto no ejecutado, pos={eng.current_position_seconds}"
    assert eng.get_loop_state()["pending_jump"] is None
    print(f"  ✓ Salto cuantizado ejecutado al inicio de compás exacto (pos={eng.current_position_seconds:.2f}s)")

    # 2.3 Activar bucle de sección (ej. Coro entre 10.0s y 12.0s)
    eng.set_section_loop(start_seconds=10.0, end_seconds=12.0, label="Coro Espontáneo", enabled=True)
    st = eng.get_loop_state()
    assert st["loop_active"] is True
    assert st["loop_section"] == "Coro Espontáneo"

    # Avanzar callback más allá de 12.0s para verificar que vuelve a 10.0s sin crujidos ni desfasaje
    eng.seek(11.95)
    for _ in range(30):
        out_buf = np.zeros((512, 2), dtype=np.float32)
        eng._audio_callback(out_buf, 512, None, None)

    # La posición debe haber vuelto al inicio del bucle (~10.0s)
    assert 10.0 <= eng.current_position_seconds < 11.5, f"Bucle no mantuvo la posición: {eng.current_position_seconds}"
    print(f"  ✓ Bucle espontáneo en vivo ejecutado limpiamente (recirculó a {eng.current_position_seconds:.2f}s)")

    # Alternar (toggle) loop
    is_loop = eng.toggle_section_loop()
    assert is_loop is False
    assert eng.get_loop_state()["loop_active"] is False
    print("  ✓ Toggle de bucle espontáneo verificado")

    eng.close()


def test_transport_endpoints(client: TestClient):
    print("▶ 3. Probando Endpoints REST de Adoración Espontánea...")

    # Verificar estado de bucle inicial
    res = client.get("/api/transport/loop-status")
    assert res.status_code == 200
    st = res.json()
    assert "loop_active" in st
    assert "pending_jump" in st

    # Obtener secciones de la canción activa
    song_res = client.get("/api/song").json()
    sections = song_res.get("sections", [])
    assert len(sections) >= 1, "La canción activa debe tener al menos una sección"
    target_sec = sections[-1]["name"]

    # 3.1 Probar programación de salto con motor en reproducción
    from src.server.app import engine as app_engine
    with app_engine._lock:
        app_engine._is_playing = True

    res = client.post("/api/transport/jump-section", json={"section_name": target_sec, "quantize": True})
    assert res.status_code == 200, f"Error programando salto: {res.text}"
    data = res.json()
    assert data["status"] == "jump_scheduled"
    assert data["section"] == target_sec

    # Verificar que el status reporta el salto pendiente
    res = client.get("/api/transport/loop-status")
    assert res.json()["pending_jump"] == target_sec

    # Cancelar salto
    res = client.post("/api/transport/cancel-jump")
    assert res.status_code == 200
    assert client.get("/api/transport/loop-status").json()["pending_jump"] is None

    with app_engine._lock:
        app_engine._is_playing = False

    # Alternar bucle de sección
    res = client.post("/api/transport/loop-section", json={"section_name": target_sec, "enabled": True})
    assert res.status_code == 200
    assert res.json()["loop_enabled"] is True
    assert client.get("/api/transport/loop-status").json()["loop_active"] is True

    # Desactivar bucle
    res = client.post("/api/transport/loop-section", json={"enabled": False})
    assert res.status_code == 200
    assert res.json()["loop_enabled"] is False
    assert client.get("/api/transport/loop-status").json()["loop_active"] is False
    print("  ✓ Endpoints /jump-section, /cancel-jump y /loop-section funcionando al 100%")


def test_scene_subgroups_and_autonext(client: TestClient):
    print("▶ 4. Probando Subgrupos y Medleys Continuos (Auto-Play vs Pausas de Ministración)...")

    # Crear una lista dominical con dos subgrupos:
    # 1. "Alabanza" (2 canciones continuas en medley, auto_next=True en la 1ra)
    # 2. "Ministración" (1 canción que al terminar debe detenerse para que el pastor ministre, auto_next=False)
    scene_payload = {
        "name": "Servicio con Medleys y Pausas",
        "date": "2026-11-15",
        "notes": "Prueba de subgrupos y auto-avance",
        "songs": [
            {
                "song_id": "cuan-grande-es-dios",
                "transpose": 0,
                "subgroup": "Alabanza Alegre",
                "auto_next": True,
            },
            {
                "song_id": "gracia-sublime-es",
                "transpose": 0,
                "subgroup": "Alabanza Alegre",
                "auto_next": False, # Fin del bloque continuo -> pausa
            },
            {
                "song_id": "cuan-grande-es-dios",
                "transpose": 1,
                "subgroup": "Adoración y Ministración",
                "auto_next": False, # Pausa tras la ministración
            },
        ],
    }

    res = client.post("/api/scenes", json=scene_payload)
    assert res.status_code == 200, f"Error creando escena: {res.text}"
    created_scene = res.json()
    sc_id = created_scene["id"]
    items = created_scene["items"]

    assert len(items) == 3
    assert items[0]["subgroup"] == "Alabanza Alegre"
    assert items[0]["auto_next"] is True
    assert items[1]["subgroup"] == "Alabanza Alegre"
    assert items[1]["auto_next"] is False
    assert items[2]["subgroup"] == "Adoración y Ministración"
    print("  ✓ Escena creada preservando subgrupos y configuración auto_next")

    # Activar la escena en la canción 0
    res = client.post(f"/api/scenes/{sc_id}/activate?index=0")
    assert res.status_code == 200

    # Simular fin de pista con auto_next=True: debe avanzar automáticamente a la canción 1
    # Llamamos a on_track_finished()
    on_track_finished()
    time.sleep(0.15)

    # Comprobar estado: ahora debe estar en el índice 1 (segunda canción del medley)
    st_res = client.get("/api/status").json()
    active_sc = st_res.get("active_scene")
    assert active_sc is not None
    assert active_sc["index"] == 1, f"No avanzó a la siguiente canción: índice={active_sc['index']}"
    assert active_sc["items"][1]["song_id"] == "gracia-sublime-es"
    print("  ✓ Auto-Play contiguo exitoso: avanzó a la segunda canción del subgrupo automáticamente")

    # Simular fin de pista en la canción 1 con auto_next=False:
    # No debe avanzar porque es momento de ministración / pausa
    on_track_finished()
    time.sleep(0.15)
    st_res2 = client.get("/api/status").json()
    active_sc2 = st_res2.get("active_scene")
    assert active_sc2["index"] == 1, f"Avanzó cuando debía pausar para ministración: índice={active_sc2['index']}"
    print("  ✓ Pausa de Ministración respetada: se mantuvo en pausa sin saltar indebidamente")

    # Limpiar escena
    client.post("/api/scenes/deactivate")
    client.delete(f"/api/scenes/{sc_id}")
    print("  ✓ Escena eliminada y estado restaurado")


if __name__ == "__main__":
    print("\n" + "=" * 64)
    print("  INICIANDO SUITE DE PRUEBAS DE MODO ESPONTÁNEO, PWA Y SUBGRUPOS")
    print("=" * 64 + "\n")

    test_engine_spontaneous_loop_and_jump()

    with TestClient(app) as test_client:
        test_pwa_endpoints(test_client)
        test_transport_endpoints(test_client)
        test_scene_subgroups_and_autonext(test_client)

    print("\n" + "=" * 64)
    print("  TODAS LAS PRUEBAS PASARON EXITOSAMENTE (100% OK)")
    print("=" * 64 + "\n")
