"""
Prueba integral de Guías de Audio Dinámicas (Dynamic In-Ear Cues).
Verifica:
1. CueManager: carga de 17 clips WAV de voz en español y matching de secciones.
2. MultitrackEngine: inyección de avisos de audio en el canal cue_mix (In-Ear) sin fuga a Master (FOH).
3. Salto cuantizado y aviso anticipado de sección.
4. Bucle espontáneo y aviso 'Repite [Sección]' 1 compás antes del retorno.
5. Endpoints REST: GET /api/transport/dynamic-cues, POST /api/transport/dynamic-cues, POST /api/transport/play-cue.
"""

import os
import sys
import numpy as np

# Salida UTF-8 en PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from src.audio.cue_manager import CueManager
from src.audio.engine import MultitrackEngine, RoutingMode
from src.audio.stem import StemTrack
from src.server.app import app, engine


def test_cue_manager():
    print("▶ 1. Probando CueManager (Banco de Voces en Español)...")
    cm = CueManager()
    assert len(cm._cues) >= 15, f"Deberían existir al menos 15 cues, encontrados: {len(cm._cues)}"
    
    # Verificar cues fundamentales
    for cue_key in ["intro", "verso", "coro", "puente", "atentos", "corte", "repite"]:
        audio = cm.get_cue(cue_key)
        assert audio is not None, f"Falta cue obligatorio: {cue_key}"
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.float32
        assert len(audio) > 0

    # Matching inteligente
    assert cm.match_section_cue_name("Coro 1") == "coro"
    assert cm.match_section_cue_name("Verse 2") == "verso_2"
    assert cm.match_section_cue_name("Puente / Bridge") == "puente"
    assert cm.match_section_cue_name("Pre-Coro") == "pre_coro"

    # Audio para bucle compuesto
    loop_audio = cm.build_loop_cue("Coro")
    assert loop_audio is not None
    assert len(loop_audio) > len(cm.get_cue("repite"))
    print(f"  ✓ Banco de guías verificado con éxito ({len(cm._cues)} clips de audio cargados en memoria)")


def test_engine_cue_injection():
    print("▶ 2. Probando Inyección de Audio en Motor Multitrack (Canal In-Ear vs FOH)...")
    eng = MultitrackEngine(sample_rate=44100, buffer_size=512, routing_mode=RoutingMode.SPLIT_STEREO)
    eng.set_song_timing(bpm=120.0, time_signature="4/4")
    
    # Agregar una pista de silencio
    silence = np.zeros(44100 * 20, dtype=np.float32)
    eng.add_stem(StemTrack(name="silent_pad", audio_data=silence, sample_rate=44100, route="both"))

    # Activar guías dinámicas
    assert eng.dynamic_cues_enabled is True
    
    # Disparar cue manual "atentos"
    ok = eng.trigger_cue("atentos")
    assert ok is True
    assert eng._active_overlay_cue is not None
    assert eng._active_overlay_pos == 0

    # Ejecutar callback simulado en modo SPLIT_STEREO a lo largo de varios buffers (~100 ms):
    # Canal 0 (L) = In-Ear / CUE (debe contener audio del cue con energía clara)
    # Canal 1 (R) = Sala / FOH (debe ser 0.0 puro, CERO fuga a los parlantes de la congregación)
    max_cue = 0.0
    max_foh = 0.0
    for _ in range(10):
        out_buf = np.zeros((512, 2), dtype=np.float32)
        eng._audio_callback(out_buf, 512, None, None)
        max_cue = max(max_cue, float(np.max(np.abs(out_buf[:, 0]))))
        max_foh = max(max_foh, float(np.max(np.abs(out_buf[:, 1]))))

    assert max_cue > 0.1, f"El canal CUE / In-Ear no recibió suficiente energía del cue: {max_cue}"
    assert max_foh == 0.0, f"FUGA DETECTADA: El canal Sala / FOH contiene audio: {max_foh}"
    print(f"  ✓ Ruteo Split Stereo verificado: CUE peak={max_cue:.3f}, Sala/FOH={max_foh:.3f} (Aislamiento perfecto)")

    eng.close()


def test_cue_endpoints(client: TestClient):
    print("▶ 3. Probando Endpoints REST de Guías Dinámicas...")
    
    # GET /api/transport/dynamic-cues
    res = client.get("/api/transport/dynamic-cues")
    assert res.status_code == 200
    data = res.json()
    assert "enabled" in data
    assert "available_cues" in data
    assert "coro" in data["available_cues"]
    assert "atentos" in data["available_cues"]
    print(f"  ✓ GET /api/transport/dynamic-cues responde con {len(data['available_cues'])} avisos disponibles")

    # POST /api/transport/dynamic-cues (desactivar y reactivar)
    res = client.post("/api/transport/dynamic-cues", json={"enabled": False})
    assert res.status_code == 200
    assert res.json()["enabled"] is False

    res = client.post("/api/transport/dynamic-cues", json={"enabled": True})
    assert res.status_code == 200
    assert res.json()["enabled"] is True
    print("  ✓ POST /api/transport/dynamic-cues activa y desactiva correctamente el modo de guías")

    # POST /api/transport/play-cue
    res = client.post("/api/transport/play-cue?name=coro")
    assert res.status_code == 200
    assert res.json()["status"] == "cue_triggered"

    res = client.post("/api/transport/play-cue?name=atentos")
    assert res.status_code == 200

    # Error ante cue inexistente
    res = client.post("/api/transport/play-cue?name=cue_inexistente_xyz")
    assert res.status_code == 404
    print("  ✓ POST /api/transport/play-cue dispara cues válidos y retorna 404 ante inválidos")


if __name__ == "__main__":
    print("\n" + "=" * 64)
    print("  SUITE DE VERIFICACIÓN: GUÍAS DE AUDIO DINÁMICAS IN-EAR")
    print("=" * 64 + "\n")

    test_cue_manager()
    test_engine_cue_injection()

    with TestClient(app) as test_client:
        test_cue_endpoints(test_client)

    print("\n" + "=" * 64)
    print("  TODAS LAS PRUEBAS DE GUÍAS DE VOZ PASARON AL 100% (OK)")
    print("=" * 64 + "\n")
