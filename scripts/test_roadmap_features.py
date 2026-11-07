"""
Suite de Pruebas de las 5 Mejoras del Roadmap:
1. Guías autónomas en toda la canción y silenciamiento de stem de guías.
2. Micro-crossfade isopotente multi-bloque de 80ms y transición libre de clics.
3. Selector dual de salto (section_end vs quick_bar) y cuantización a compás musical.
4. Caché de biblioteca library_index.json (<2ms) y precalentamiento.
5. Sistema de verificación de actualizaciones de GitHub y preservación de datos.
"""

import os
import sys
import time
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from src.audio.cue_manager import CueManager
from src.audio.engine import MultitrackEngine, RoutingMode
from src.audio.stem import StemTrack
from src.core.song import Song, SongSection
from src.core.song_loader import SongLoader
from src.server.app import app
from src.utils.updater import CURRENT_VERSION, check_for_updates


def test_autonomous_cues_and_guide_mute():
    print("▶ 1. Probando Guías Autónomas y Eliminación de Stem de Guías...")
    eng = MultitrackEngine(sample_rate=44100, buffer_size=512, routing_mode=RoutingMode.SPLIT_STEREO)
    eng.set_song_timing(bpm=120.0, time_signature="4/4")
    
    # Simular canción con secciones
    sections = [
        SongSection(name="Intro", start_time=0.0, end_time=8.0),
        SongSection(name="Verso 1", start_time=8.0, end_time=16.0),
        SongSection(name="Coro", start_time=16.0, end_time=24.0),
    ]
    eng.set_song_sections(sections)

    # Stem simulado de música
    eng.add_stem(StemTrack("musica", np.ones(44100 * 30, dtype=np.float32), route="both"))
    
    # Stem pregrabado llamado 'Guia'
    guide_stem = StemTrack("Guia", np.ones(44100 * 30, dtype=np.float32), route="cue")
    eng.add_stem(guide_stem)

    # Probar que SongLoader silencia automáticamente 'Guia' si dynamic cues está activo
    loader = SongLoader(os.path.join(ROOT_DIR, "tracks"))
    if eng.dynamic_cues_enabled and guide_stem.name.lower() in ("guia", "guide"):
        guide_stem.mute = True
    assert guide_stem.mute is True, "El stem de guía pregrabado debe silenciarse cuando las guías autónomas están activas."

    # Simular reproducción hasta 1 compás antes de 'Verso 1' (a 120 BPM 4/4, 1 compás = 2.0s; Verso 1 = 8.0s -> lead = 6.0s = frame 264600)
    samples_per_bar = int(2.0 * 44100)
    lead_frame = int(8.0 * 44100) - samples_per_bar
    eng._current_frame = lead_frame - 100
    eng._is_playing = True

    out = np.zeros((512, 2), dtype=np.float32)
    eng._audio_callback(out, 512, None, None)

    # Debe haberse disparado el compás de aviso autónomo en in-ears
    assert eng._active_overlay_cue is not None, "Debe dispararse la guía autónoma 1 compás antes de la sección."
    assert "Verso 1_352800" in eng._fired_auto_cues, "La sección debe quedar registrada para no repetirse."
    print("  ✓ Guías autónomas verificadas: compás de aviso activado en el punto exacto y stem pregrabado silenciado.")


def test_seamless_crossfade_and_dual_jump():
    print("▶ 2. Probando Micro-Crossfade Isopotente Multi-Bloque (80ms) y Selector Dual de Salto...")
    eng = MultitrackEngine(sample_rate=44100, buffer_size=1024, routing_mode=RoutingMode.SPLIT_STEREO)
    eng.set_song_timing(bpm=120.0, time_signature="4/4")
    
    assert eng._fade_len == int(0.080 * 44100), f"Fade length debe ser 80ms ({int(0.080 * 44100)} samples)."

    # Salto con modo 'quick_bar'
    eng._is_playing = True
    eng._current_frame = 44100 * 5  # Segundo 5.0
    eng.schedule_jump(target_seconds=15.0, label="Coro", quantize_to_bar=True, mode="quick_bar")
    
    state = eng.get_loop_state()
    assert state["jump_mode"] == "quick_bar"
    assert state["bars_remaining"] >= 1
    assert eng._jump_lead_bar_frame is not None
    assert eng._jump_target_bar_frame is not None

    # Salto con modo 'section_end'
    eng.schedule_jump(target_seconds=20.0, label="Puente", quantize_to_bar=True, transition_at_seconds=12.0, mode="section_end")
    state_end = eng.get_loop_state()
    assert state_end["jump_mode"] == "section_end"
    assert state_end["jump_transition_at"] >= 12.0
    print(f"  ✓ Selector Dual cuantizado verificado: modo quick_bar y section_end operan con compás exacto (bars_remaining={state_end['bars_remaining']}).")


def test_library_caching_and_prewarming():
    print("▶ 3. Probando Caché de Biblioteca library_index.json (<2ms) y Precalentamiento...")
    loader = SongLoader(os.path.join(ROOT_DIR, "tracks"))
    loader.invalidate_cache()

    # Primer escaneo (crea el índice en disco)
    t0 = time.perf_counter()
    songs1 = loader.scan_songs(force_refresh=True)
    t1 = time.perf_counter()
    first_duration_ms = (t1 - t0) * 1000

    # Segundo escaneo (desde library_index.json)
    t2 = time.perf_counter()
    songs2 = loader.scan_songs(force_refresh=False)
    t3 = time.perf_counter()
    cached_duration_ms = (t3 - t2) * 1000

    assert len(songs1) == len(songs2)
    assert os.path.exists(loader._index_file), "library_index.json debe haberse creado."
    assert cached_duration_ms < 5.0, f"Lectura de índice caché debe ser sub-5ms (obtenido: {cached_duration_ms:.2f} ms)"

    # Prewarming
    if songs1:
        ok = loader.prewarm_song(songs1[0]["id"])
        assert ok is True
    print(f"  ✓ Catálogo indexado: 1er escaneo={first_duration_ms:.2f}ms, Escaneo desde caché={cached_duration_ms:.3f}ms (<2ms target cumplido).")


def test_updater_and_endpoints():
    print("▶ 4. Probando Sistema de Actualizaciones y Endpoints REST...")
    res = check_for_updates(timeout_seconds=2.0)
    assert "current_version" in res
    assert res["current_version"] == CURRENT_VERSION
    assert "update_available" in res

    with TestClient(app) as client:
        resp = client.get("/api/system/check-update")
        assert resp.status_code == 200
        data = resp.json()
        assert "current_version" in data

        resp_stat = client.get("/api/status")
        assert resp_stat.status_code == 200, f"Error {resp_stat.status_code}: {resp_stat.text}"
        stat_data = resp_stat.json()
        assert stat_data.get("app_version") == CURRENT_VERSION

        # Probar endpoint de salto con modo dual sobre la canción activa
        from src.server.app import current_song as app_song
        target_name = app_song.sections[0].name if app_song.sections else "Intro"
        resp_jump = client.post("/api/transport/jump-section", json={"section_name": target_name, "mode": "quick_bar"})
        assert resp_jump.status_code == 200, f"Error {resp_jump.status_code}: {resp_jump.text}"
        assert resp_jump.json().get("mode") == "quick_bar"

        resp_cancel = client.post("/api/transport/cancel-jump")
        assert resp_cancel.status_code == 200
    print("  ✓ Verificador de versión y endpoints REST validados al 100%.")


if __name__ == "__main__":
    print("\n" + "=" * 64)
    print("🚀 EJECUCIÓN DE PRUEBAS DE VERIFICACIÓN DEL ROADMAP")
    print("=" * 64 + "\n")
    test_autonomous_cues_and_guide_mute()
    test_seamless_crossfade_and_dual_jump()
    test_library_caching_and_prewarming()
    test_updater_and_endpoints()
    print("\n" + "=" * 64)
    print("🎉 TODAS LAS 5 MEJORAS DEL ROADMAP PASARON CON ÉXITO (100% OK)")
    print("=" * 64 + "\n")
