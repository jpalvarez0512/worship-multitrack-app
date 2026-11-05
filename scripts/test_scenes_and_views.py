"""
Script de verificación integral de Escenas Dominicales, Fondos/Video Loops de Proyección,
Salida OBS independiente, Ruteo de Stems y Vista de Compás Único para Músicos.
"""

import io
import os
import sys

# Asegurar salida utf-8 en Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from src.server.app import app, scene_manager, projection_config, song_loader


def test_scenes_crud_and_navigation(client: TestClient):
    print("▶ 1. Probando CRUD y Navegación de Escenas Dominicales...")

    # Listar escenas iniciales
    res = client.get("/api/scenes")
    assert res.status_code == 200, f"Error listando escenas: {res.text}"
    initial_scenes = res.json()

    # Crear una escena nueva para el domingo
    new_scene_payload = {
        "name": "Servicio Dominical Prueba",
        "date": "2026-11-08",
        "notes": "Lista de prueba automatizada",
        "songs": [
            {"song_id": "cuan-grande-es-dios", "transpose": 0},
            {"song_id": "gracia-sublime-es", "transpose": 2},
        ],
    }
    res = client.post("/api/scenes", json=new_scene_payload)
    assert res.status_code == 200, f"Error creando escena: {res.text}"
    scene = res.json()
    scene_id = scene["id"]
    assert scene["name"] == "Servicio Dominical Prueba"
    assert len(scene["items"]) == 2
    assert scene["items"][1]["transpose"] == 2
    print(f"  ✓ Escena creada con éxito (ID: {scene_id})")

    # Activar la escena
    res = client.post(f"/api/scenes/{scene_id}/activate?index=0")
    assert res.status_code == 200, f"Error activando escena: {res.text}"
    act_data = res.json()
    assert act_data["active_scene"]["scene_id"] == scene_id
    assert act_data["active_scene"]["index"] == 0
    print("  ✓ Escena activada en la primera canción")

    # Navegar a la siguiente canción
    res = client.post("/api/scenes/navigate?direction=next")
    assert res.status_code == 200, f"Error navegando a siguiente: {res.text}"
    nav_data = res.json()
    assert nav_data["active_scene"]["index"] == 1
    assert nav_data["song"]["id"] == "gracia-sublime-es"
    print("  ✓ Navegación a la siguiente canción exitosa (gracia-sublime-es)")

    # Navegar de regreso a la canción anterior
    res = client.post("/api/scenes/navigate?direction=prev")
    assert res.status_code == 200, f"Error navegando a anterior: {res.text}"
    nav_data = res.json()
    assert nav_data["active_scene"]["index"] == 0
    assert nav_data["song"]["id"] == "cuan-grande-es-dios"
    print("  ✓ Navegación a la canción anterior exitosa (cuan-grande-es-dios)")

    # Desactivar la escena
    res = client.post("/api/scenes/deactivate")
    assert res.status_code == 200
    print("  ✓ Desactivación limpia de escena")

    # Eliminar la escena de prueba
    res = client.delete(f"/api/scenes/{scene_id}")
    assert res.status_code == 200
    print("  ✓ Eliminación limpia de escena de prueba")


def test_projection_settings_and_video_loops(client: TestClient):
    print("\n▶ 2. Probando Configuración de Proyección, Video Loops y Anticipación...")

    # Obtener configuración actual
    res = client.get("/api/projection/settings")
    assert res.status_code == 200
    data = res.json()
    assert "settings" in data
    assert "backgrounds" in data
    print(f"  ✓ Ajustes obtenidos: {len(data['backgrounds'])} fondos/loops disponibles")

    # Actualizar fondo a un preset de loop animado y ajustar anticipación a 1.5s
    update_payload = {
        "background": "loop-aurora",
        "dim_opacity": 0.35,
        "lead_seconds": 1.5,
        "text_color": "#FFE600",
    }
    res = client.put("/api/projection/settings", json=update_payload)
    assert res.status_code == 200
    updated = res.json()["settings"]
    assert updated["background"] == "loop-aurora"
    assert updated["lead_seconds"] == 1.5
    assert updated["dim_opacity"] == 0.35
    assert updated["text_color"] == "#FFE600"
    print("  ✓ Ajustes actualizados: loop-aurora, anticipación 1.5s, amarillo intenso")

    # Subir un video loop de prueba (archivo simulado en memoria)
    dummy_video_bytes = b"\x00\x00\x00\x18ftypmp42" + b"A" * 1024
    files = {"file": ("worship_loop_test.mp4", io.BytesIO(dummy_video_bytes), "video/mp4")}
    data = {"apply_immediately": "true"}
    res = client.post("/api/projection/backgrounds", files=files, data=data)
    assert res.status_code == 200, f"Error subiendo video loop: {res.text}"
    upload_res = res.json()
    assert upload_res["background"]["kind"] == "video"
    assert upload_res["settings"]["background_is_video"] is True
    print("  ✓ Video loop (.mp4) subido y aplicado inmediatamente")

    # Verificar que /backgrounds/worship_loop_test.mp4 se sirve correctamente
    res = client.get(upload_res["background"]["url"])
    assert res.status_code == 200
    assert len(res.content) == len(dummy_video_bytes)
    print("  ✓ Endpoint estático /backgrounds entrega el archivo de video loop")

    # Eliminar el video loop de prueba
    res = client.delete("/api/projection/backgrounds/worship_loop_test.mp4")
    assert res.status_code == 200
    print("  ✓ Video loop de prueba eliminado correctamente")


def test_stem_routing_and_views_delivery(client: TestClient):
    print("\n▶ 3. Probando Ruteo de Stems y Entrega de Páginas Web...")

    # Cargar primera canción para tener stems
    client.post("/api/songs/cuan-grande-es-dios/load")

    # Probar endpoint de cambio de ruta de stem
    res = client.post("/api/stems/Click/route?route=master")
    assert res.status_code == 200
    assert res.json()["route"] == "master"
    # Restaurar a cue
    client.post("/api/stems/Click/route?route=cue")
    print("  ✓ Endpoint /api/stems/{name}/route responde y conmuta ruteo")

    # Verificar entrega de /control
    res = client.get("/control")
    assert res.status_code == 200
    assert "Mezclador de Stems en Vivo" in res.text
    assert "Listas Dominicales" in res.text
    print("  ✓ Vista /control entregada con soporte para escenas y stems sin truncar")

    # Verificar entrega de /musicians
    res = client.get("/musicians")
    assert res.status_code == 200
    assert "hero-chord" in res.text
    assert "Compás actual" in res.text
    print("  ✓ Vista /musicians entregada con modo de compás único y acorde gigante")

    # Verificar entrega de /projection
    res = client.get("/projection")
    assert res.status_code == 200
    assert "bg-video" in res.text
    assert "--lyric-color: #FFE600" in res.text
    print("  ✓ Vista /projection entregada con soporte de video loops y amarillo nítido")

    # Verificar entrega de la nueva vista independiente /obs
    res = client.get("/obs")
    assert res.status_code == 200
    assert "background: transparent" in res.text
    assert "obs-stage" in res.text
    print("  ✓ Vista /obs entregada con transparencia pura para OBS Studio")


def test_projection_lead_time_anticipation():
    print("\n▶ 4. Probando Anticipación Temporal de Letras (Lead Time)...")
    song = song_loader.load_song_metadata("cuan-grande-es-dios")

    # Verso 1 inicia en t = 12.50s con "El esplendor de un Rey, vestido en majestad"
    # A t = 11.2s (1.3s antes del verso), con lead_seconds = 1.5s:
    # La congregación ya debe ver el primer verso de la canción para anticipar la lectura.
    lyric, sec = song.get_projection_lyric_at(11.2, lead_seconds=1.5)
    assert "El esplendor de un Rey" in lyric, f"No se anticipó la letra: got '{lyric}'"
    print("  ✓ Letra anticipada con éxito 1.3s antes de la entrada cantada")

    # Con lead_seconds = 0.0s (sin anticipación), a t = 11.2s todavía está en Intro (línea instrumental limpia)
    lyric_no_lead, _ = song.get_projection_lyric_at(11.2, lead_seconds=0.0)
    assert lyric_no_lead == "", f"Sin lead time no debería verse la letra: got '{lyric_no_lead}'"
    print("  ✓ Verificación correcta: sin anticipación la letra no entra antes")


if __name__ == "__main__":
    with TestClient(app) as test_client:
        test_scenes_crud_and_navigation(test_client)
        test_projection_settings_and_video_loops(test_client)
        test_stem_routing_and_views_delivery(test_client)
    test_projection_lead_time_anticipation()
    print("\n" + "=" * 60)
    print("🎉 TODAS LAS PRUEBAS DE ESCENAS, VISTAS Y LOOPS PASARON 100%")
    print("=" * 60)
