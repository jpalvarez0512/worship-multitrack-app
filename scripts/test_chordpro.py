"""
Suite de Pruebas Automatizadas para el Parser de ChordPro y el Gestor de Canciones
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
from src.core.chordpro import ChordProParser
from src.core.song_loader import SongLoader
from src.server.app import app


SAMPLE_CHORDPRO = """{title: Gracia Sublime Es}
{artist: Evan Craft}
{key: Bb}
{bpm: 104}
{time: 4/4}

{section: Intro}
[00:00.00] [Bb]       [Eb]

{section: Verso 1}
[00:10.00] ¿Quién rompe el po[Bb]der del pecado y la oscu[Eb]ridad?
[00:20.50] Su amor es tan [Gm]fuerte, y es tan pode[F]roso
[00:30.00] El Rey de [Eb]gloria, el Rey de Majes[F]tad

{section: Coro}
[00:40.00] Gracia sub[Bb]lime es, perfecto es tu a[Eb]mor
[00:52.00] Tomaste mi lu[Gm]gar, cargaste tú mi [F]cruz
"""


def run_tests():
    print("=" * 60)
    print("🎼 INICIANDO PRUEBAS DE CHORDPRO Y GESTIÓN DE CANCIONES")
    print("=" * 60)

    # 1. Prueba de Parsing en Memoria
    print("\n1. Probando ChordProParser.parse_string...")
    song = ChordProParser.parse_string(SAMPLE_CHORDPRO, default_id="gracia-sublime")
    assert song.title == "Gracia Sublime Es", f"Error en título: {song.title}"
    assert song.artist == "Evan Craft", f"Error en artista: {song.artist}"
    assert song.key == "Bb", f"Error en tono: {song.key}"
    assert song.bpm == 104.0, f"Error en BPM: {song.bpm}"
    assert len(song.sections) == 3, f"Esperadas 3 secciones, obtenidas {len(song.sections)}"
    print(f"   ✓ Metadatos correctos: {song.title} - {song.artist} ({song.key}, {song.bpm} BPM)")

    # 2. Prueba de Separación de Acordes vs Letra Limpia
    print("\n2. Verificando separación limpia para músicos y proyección...")
    verso1 = song.sections[1]
    assert verso1.name == "Verso 1"
    line1 = verso1.lines[0]
    print(f"   ✓ Letra limpia (Proyección): '{line1.lyrics}'")
    assert "[" not in line1.lyrics and "]" not in line1.lyrics, "La letra de proyección contiene corchetes de acordes"
    assert len(line1.chords) == 2, f"Esperados 2 acordes, encontrados {len(line1.chords)}"
    print(f"   ✓ Acordes detectados (Músicos): {[c.chord for c in line1.chords]}")
    assert line1.chords[0].chord == "Bb"
    assert line1.chords[1].chord == "Eb"

    # 3. Prueba de SongLoader y escaneo de tracks/
    print("\n3. Probando SongLoader.scan_songs...")
    tracks_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tracks"))
    loader = SongLoader(tracks_root=tracks_dir)
    songs = loader.scan_songs()
    print(f"   ✓ Canciones detectadas en disco ({len(songs)}):")
    for s in songs:
        print(f"     - [{s['key']}] {s['title']} | Stems: {s['stems_count']} | Chart: {s['has_chart']}")
    assert len(songs) >= 1, "Debe haber al menos 1 canción en tracks/"

    # 4. Pruebas de API REST con TestClient
    print("\n4. Verificando endpoints REST de canciones...")
    with TestClient(app) as client:
        # GET /api/songs
        r_list = client.get("/api/songs")
        assert r_list.status_code == 200
        assert len(r_list.json()) >= 1
        print("   ✓ GET /api/songs: OK")

        # POST /api/songs/parse-preview
        r_prev = client.post("/api/songs/parse-preview", json={"content": SAMPLE_CHORDPRO})
        assert r_prev.status_code == 200
        prev_data = r_prev.json()
        assert prev_data["title"] == "Gracia Sublime Es"
        print("   ✓ POST /api/songs/parse-preview: OK")

        # POST /api/songs/import
        r_imp = client.post("/api/songs/import", json={"content": SAMPLE_CHORDPRO, "load_immediately": True})
        assert r_imp.status_code == 200
        imp_data = r_imp.json()
        print(f"   ✓ POST /api/songs/import: OK (Canción importada y cargada: {imp_data['song']['title']})")

        # Verificar que el status actual ahora refleja la nueva canción
        r_status = client.get("/api/status")
        assert r_status.status_code == 200
        curr_song = r_status.json()["song"]
        assert curr_song["title"] == "Gracia Sublime Es"
        print(f"   ✓ Verificado estado activo: '{curr_song['title']}' en tono {curr_song['key']}")

    print("\n" + "=" * 60)
    print("✅ TODAS LAS PRUEBAS DE CHORDPRO PASARON EXITOSAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
