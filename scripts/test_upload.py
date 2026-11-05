"""
Pruebas Automatizadas de Subida de Canciones, ChordPro y Stems desde la Web
"""

import io
import os
import sys
import wave
import numpy as np

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from src.server.app import app


def make_wav_bytes(freq: float = 440.0, duration_sec: float = 1.0, sr: int = 44100) -> bytes:
    """Genera un archivo WAV PCM 16-bit en memoria para pruebas de subida."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    samples = (0.4 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def run_upload_tests():
    print("=" * 60)
    print("⬆️  INICIANDO PRUEBAS DE SUBIDA WEB (CHORDPRO + STEMS)")
    print("=" * 60)

    chart_text = """{title: Canción de Prueba Web}
{artist: Banda Local}
{key: D}
{bpm: 92}

{section: Verso 1}
[00:00.00] Cantaré de tu a[D]mor por [A]siempre
[00:05.00] Tu bondad no [Bm7]tiene [G]fin
"""
    click_wav = make_wav_bytes(1000.0, 1.5)
    bajo_wav = make_wav_bytes(110.0, 1.5)
    pad_wav = make_wav_bytes(220.0, 1.5)

    with TestClient(app) as client:
        # 1. Subir canción nueva con archivo ChordPro + 2 stems WAV
        print("\n1. Probando POST /api/songs/upload (multipart: chart + 2 stems WAV)...")
        files = [
            ("chart_file", ("letra.pro", chart_text.encode("utf-8"), "text/plain")),
            ("stems", ("Click.wav", click_wav, "audio/wav")),
            ("stems", ("Bajo.wav", bajo_wav, "audio/wav")),
        ]
        data = {
            "title": "Canción de Prueba Web",
            "artist": "Banda Local",
            "key": "D",
            "bpm": "92",
            "load_immediately": "true",
        }
        r = client.post("/api/songs/upload", data=data, files=files)
        assert r.status_code == 200, f"Error {r.status_code}: {r.text}"
        res = r.json()
        song_id = res["song_id"]
        assert song_id == "cancion-de-prueba-web", f"Slug inesperado: {song_id}"
        assert set(res["stems_saved"]) == {"Click.wav", "Bajo.wav"}
        print(f"   ✓ Canción creada: id='{song_id}', stems={res['stems_saved']}")

        # 2. Verificar ruteo automático en /api/stems
        print("\n2. Verificando ruteo automático de stems cargados en el motor...")
        stems = {s["name"]: s["route"] for s in client.get("/api/stems").json()}
        assert stems.get("Click") == "cue", f"Click debería ir a cue: {stems}"
        assert stems.get("Bajo") == "master", f"Bajo debería ir a master: {stems}"
        print(f"   ✓ Ruteo verificado: {stems}")

        # 3. Agregar un tercer stem a la canción existente
        print("\n3. Probando POST /api/songs/{id}/stems (agregar Pad.wav)...")
        r_add = client.post(
            f"/api/songs/{song_id}/stems",
            files=[("stems", ("Pad.wav", pad_wav, "audio/wav"))],
        )
        assert r_add.status_code == 200, r_add.text
        stems_after = [s["name"] for s in client.get("/api/stems").json()]
        assert "Pad" in stems_after
        print(f"   ✓ Stems activos tras agregar Pad: {stems_after}")

        # 4. Leer y editar el ChordPro desde la web
        print("\n4. Probando GET/PUT /api/songs/{id}/chart...")
        r_chart = client.get(f"/api/songs/{song_id}/chart")
        assert r_chart.status_code == 200
        assert "Cantaré de tu a[D]mor" in r_chart.json()["content"]

        updated_chart = chart_text + "\n{section: Coro}\n[00:10.00] Santo es el Se[D]ñor\n"
        r_put = client.put(f"/api/songs/{song_id}/chart", json={"content": updated_chart})
        assert r_put.status_code == 200, f"Error {r_put.status_code}: {r_put.text}"
        song_full = client.get("/api/song").json()
        assert len(song_full["sections"]) == 2
        print("   ✓ Letra actualizada en vivo manteniendo los 3 stems intactos")

        # 5. Reemplazar documento subiendo archivo directamente
        print("\n5. Probando POST /api/songs/{id}/chart-file (reemplazo por archivo)...")
        new_chart_file = "{title: Canción Reemplazada}\n{key: A}\n{c: Coro}\n[00:00.00] Gloria a [A]Dios\n"
        r_file = client.post(
            f"/api/songs/{song_id}/chart-file",
            files={"chart_file": ("nueva_letra.pro", new_chart_file.encode("utf-8"), "text/plain")},
        )
        assert r_file.status_code == 200, r_file.text
        r_chart_after = client.get(f"/api/songs/{song_id}/chart")
        assert "Gloria a [A]Dios" in r_chart_after.json()["content"]
        print("   ✓ Documento de letras reemplazado exitosamente mediante subida de archivo")

        # 6. Eliminar un stem individual
        print("\n6. Probando DELETE /api/songs/{id}/stems/Pad.wav...")
        r_del_stem = client.delete(f"/api/songs/{song_id}/stems/Pad.wav")
        assert r_del_stem.status_code == 200
        stems_remaining = [s["name"] for s in client.get("/api/stems").json()]
        assert "Pad" not in stems_remaining and "Click" in stems_remaining
        print(f"   ✓ Stem eliminado; restantes: {stems_remaining}")

        # 7. Eliminar la canción de prueba para dejar tracks/ limpio
        print("\n7. Limpiando canción de prueba (DELETE /api/songs/{id})...")
        r_del_song = client.delete(f"/api/songs/{song_id}")
        assert r_del_song.status_code == 200
        ids = [s["id"] for s in client.get("/api/songs").json()]
        assert song_id not in ids
        print("   ✓ Canción de prueba eliminada limpiamente")

        # 8. Subida rápida por lotes de documentos (Batch / Fast Docs)
        print("\n8. Probando POST /api/songs/upload-documents (lote de múltiples documentos)...")
        doc1 = "{title: Al que está en el Trono}\n{key: E}\n{c: Coro}\nSanto, Santo\n"
        doc2 = "{title: Digno y Santo}\n{key: C}\n{c: Verso 1}\nTe adoramos\n"
        r_batch = client.post(
            "/api/songs/upload-documents",
            files=[
                ("files", ("al-trono.pro", doc1.encode("utf-8"), "text/plain")),
                ("files", ("digno.txt", doc2.encode("utf-8"), "text/plain")),
            ],
            data={"load_immediately": "false"},
        )
        assert r_batch.status_code == 200, r_batch.text
        batch_res = r_batch.json()
        assert batch_res["imported_count"] == 2
        print(f"   ✓ {batch_res['imported_count']} documentos importados en milisegundos: {batch_res['imported_ids']}")

        # Limpiar las 2 canciones importadas por lote
        for b_id in batch_res["imported_ids"]:
            client.delete(f"/api/songs/{b_id}")
        print("   ✓ Canciones de prueba por lote eliminadas limpiamente")

    print("\n" + "=" * 60)
    print("✅ TODAS LAS PRUEBAS DE SUBIDA WEB PASARON EXITOSAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    run_upload_tests()
