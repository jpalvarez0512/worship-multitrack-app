"""
Servidor Central FastAPI y Rutas de Sincronización en Tiempo Real
Subagente responsable: 03-network-sync-engineer
"""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.audio.engine import MultitrackEngine, RoutingMode
from src.audio.synthetic import (
    generate_click_track,
    generate_guide_cues,
    generate_instrument_stem,
)
from src.core.chordpro import ChordProParser
from src.core.projection_config import ProjectionConfigManager
from src.core.scene_manager import SceneManager
from src.core.song import Song, create_demo_song
from src.core.song_loader import AUDIO_EXTENSIONS, CHART_EXTENSIONS, SongLoader
from src.server.websocket_manager import ChannelType, ConnectionManager
from src.utils.network import get_connection_url, get_local_ip, print_ascii_qr


# -----------------------------------------------------------------------------
# Instancias Globales
# -----------------------------------------------------------------------------
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRACKS_DIR = os.path.join(ROOT_DIR, "tracks")
CONFIG_DIR = os.path.join(ROOT_DIR, "config")

song_loader = SongLoader(tracks_root=TRACKS_DIR)
scene_manager = SceneManager(os.path.join(CONFIG_DIR, "scenes.json"))
projection_config = ProjectionConfigManager(CONFIG_DIR)

engine: Optional[MultitrackEngine] = None
ws_manager = ConnectionManager()
current_song: Song = create_demo_song()
main_event_loop: Optional[asyncio.AbstractEventLoop] = None

# Estado de Escena (Lista Dominical) activa
active_scene_id: Optional[str] = None
active_scene_index: int = 0
active_song_transpose: int = 0


def setup_demo_audio(eng: MultitrackEngine, song: Song) -> None:
    """Carga pistas de audio sintéticas sincronizadas con la canción activa."""
    duration = max(song.duration_seconds, 60.0)
    bpm = song.bpm

    click = generate_click_track(bpm=bpm, duration_seconds=duration)
    guide = generate_guide_cues(bpm=bpm, duration_seconds=duration)
    pad = generate_instrument_stem("Pad", frequency=196.0, duration_seconds=duration)  # Tono G
    bass = generate_instrument_stem("Bajo", frequency=98.0, duration_seconds=duration)  # Tono G bajo

    eng.clear_stems()
    eng.add_stem(click)
    eng.add_stem(guide)
    eng.add_stem(pad)
    eng.add_stem(bass)


def on_engine_tick(pos_seconds: float, is_playing: bool) -> None:
    """Callback invocado por el hilo del motor de audio (MultitrackEngine)."""
    global main_event_loop, ws_manager, current_song
    if main_event_loop is None or not main_event_loop.is_running():
        return

    # Extraer metadatos exactos de la canción para músicos
    sec = current_song.get_section_at(pos_seconds)
    sec_name = sec.name if sec else ""

    line = current_song.get_active_line_at(pos_seconds)
    lyric_text = line.lyrics if line else ""

    # Determinar el acorde activo actual
    active_chord = ""
    if line and line.chords:
        for cm in line.chords:
            if cm.time <= pos_seconds:
                active_chord = cm.chord

    # Letra anticipada para Proyector y OBS (permite a la congregación leer antes de cantar)
    proj_lyric, proj_sec = current_song.get_projection_lyric_at(
        pos_seconds, projection_config.lead_seconds
    )

    # Enviar al bucle asíncrono principal sin bloquear el hilo de audio
    coro = ws_manager.broadcast_tick(
        position_seconds=pos_seconds,
        is_playing=is_playing,
        current_section=sec_name,
        current_lyric=lyric_text,
        current_chord=active_chord,
        projection_lyric=proj_lyric,
        projection_section=proj_sec,
    )
    asyncio.run_coroutine_threadsafe(coro, main_event_loop)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejo de arranque y apagado del servidor."""
    global engine, main_event_loop, current_song
    main_event_loop = asyncio.get_running_loop()

    # Inicializar motor de audio en modo SPLIT_STEREO por defecto
    engine = MultitrackEngine(
        sample_rate=44100,
        buffer_size=256,
        routing_mode=RoutingMode.SPLIT_STEREO,
    )
    
    # Cargar primera canción disponible en tracks/ o demo
    available = song_loader.scan_songs()
    if available:
        try:
            current_song = song_loader.load_song(available[0]["id"], engine)
        except Exception as ex:
            print(f"⚠️ Error cargando canción inicial: {ex}")
            setup_demo_audio(engine, current_song)
    else:
        setup_demo_audio(engine, current_song)

    engine.register_tick_listener(on_engine_tick)

    local_ip = get_local_ip()
    port = 8000
    musician_url = get_connection_url(port, "/musicians")
    projection_url = get_connection_url(port, "/projection")
    obs_url = get_connection_url(port, "/obs")

    print("\n" + "=" * 64)
    print("🚀 SERVIDOR DE SINCRONIZACIÓN DE ADORACIÓN ACTIVO")
    print("=" * 64)
    print(f"📡 IP Local del PC:            {local_ip}")
    print(f"🎛 Panel de Control Central:   {get_connection_url(port, '/control')}")
    print(f"🎸 Pantalla Músicos:           {musician_url}")
    print(f"📽 Pantalla Proyector / Loops: {projection_url}")
    print(f"🎥 Letras para OBS Studio:     {obs_url}")
    print("=" * 64)
    print("📲 Escanea este código QR con tu móvil para abrir la vista de músicos:")
    print_ascii_qr(musician_url)
    print("=" * 64 + "\n")

    yield

    # Apagado limpio
    if engine is not None:
        engine.close()


app = FastAPI(
    title="Worship Multitrack & Sync Server",
    description="Servidor local de sincronización de audio, acordes y proyección de letras",
    version="1.0.0",
    lifespan=lifespan,
)

# Permitir conexiones desde cualquier navegador en la red local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir imágenes y video loops personalizados para la pantalla de proyección
app.mount(
    "/backgrounds",
    StaticFiles(directory=projection_config.backgrounds_dir),
    name="backgrounds",
)


def _build_library_map() -> dict:
    return {s["id"]: s for s in song_loader.scan_songs()}


def _get_active_scene_status() -> Optional[dict]:
    global active_scene_id, active_scene_index
    if not active_scene_id:
        return None
    try:
        scene = scene_manager.get_scene(active_scene_id, _build_library_map())
    except KeyError:
        active_scene_id = None
        active_scene_index = 0
        return None
    items = scene.get("items", [])
    idx = max(0, min(active_scene_index, max(len(items) - 1, 0)))
    return {
        "scene_id": scene["id"],
        "name": scene["name"],
        "date": scene["date"],
        "notes": scene.get("notes", ""),
        "index": idx,
        "total": len(items),
        "items": items,
        "prev_song": items[idx - 1] if idx > 0 and idx - 1 < len(items) else None,
        "next_song": items[idx + 1] if idx + 1 < len(items) else None,
    }


# -----------------------------------------------------------------------------
# Endpoints REST de Estado y Configuración
# -----------------------------------------------------------------------------

@app.get("/api/network-info")
def get_network_info():
    """Retorna información de conexión LAN y URLs para clientes."""
    ip = get_local_ip()
    port = 8000
    return {
        "local_ip": ip,
        "port": port,
        "musicians_url": get_connection_url(port, "/musicians"),
        "projection_url": get_connection_url(port, "/projection"),
        "obs_url": get_connection_url(port, "/obs"),
        "control_url": get_connection_url(port, "/control"),
    }


@app.get("/api/status")
def get_status():
    """Estado general del reproductor y clientes conectados."""
    if engine is None:
        raise HTTPException(status_code=503, detail="Motor no inicializado")

    return {
        "is_playing": engine.is_playing,
        "position_seconds": round(engine.current_position_seconds, 3),
        "duration_seconds": round(engine.duration_seconds, 2),
        "routing_mode": engine.routing_mode.value,
        "song": current_song.to_summary_dict(),
        "default_transpose": active_song_transpose,
        "active_scene": _get_active_scene_status(),
        "projection": {
            "blackout": ws_manager._projection_blackout,
            "clear": ws_manager._projection_clear_text,
        },
        "clients": ws_manager.get_stats(),
    }


@app.get("/api/song")
def get_current_song(transpose: int = 0):
    """Devuelve la estructura completa de la canción con acordes (con transposición opcional)."""
    return current_song.to_full_dict(transpose_semitones=transpose)


# -----------------------------------------------------------------------------
# Endpoints de Biblioteca de Canciones, ChordPro y Subida de Archivos
# -----------------------------------------------------------------------------
# Nota: estos endpoints son funciones normales (no async) a propósito. FastAPI las
# ejecuta en un hilo aparte, así la decodificación de WAV/MP3 pesados o el guardado
# de archivos grandes no congela los WebSockets de músicos y proyección.

def _broadcast_async(channel: str, payload: dict) -> None:
    """Envía un evento WebSocket de forma segura desde hilos síncronos o asíncronos."""
    if main_event_loop is None or not main_event_loop.is_running():
        return
    asyncio.run_coroutine_threadsafe(
        ws_manager.broadcast_to_channel(channel, payload),
        main_event_loop,
    )


def _notify_song_changed() -> None:
    """Avisa a músicos, proyección/OBS y controles que cambió la canción."""
    _broadcast_async(
        ChannelType.MUSICIANS,
        {
            "type": "song_changed",
            "song": current_song.to_summary_dict(),
            "default_transpose": active_song_transpose,
        },
    )
    _broadcast_async(
        ChannelType.PROJECTION,
        {"type": "song_changed", "title": current_song.title},
    )
    _broadcast_async(
        ChannelType.CONTROL,
        {
            "type": "song_changed",
            "song": current_song.to_summary_dict(),
            "default_transpose": active_song_transpose,
        },
    )


def _activate_song(
    song_id: str,
    default_transpose: int = 0,
    from_scene: bool = False,
) -> dict:
    """Detiene la reproducción, carga la canción en el motor y notifica a los clientes."""
    global current_song, active_song_transpose, active_scene_index
    if engine is None:
        raise HTTPException(status_code=503, detail="Motor no disponible")
    engine.stop()
    current_song = song_loader.load_song(song_id, engine)
    active_song_transpose = int(default_transpose)

    if not from_scene and active_scene_id:
        try:
            scene = scene_manager.get_scene(active_scene_id)
            for idx, entry in enumerate(scene.get("songs", [])):
                if entry.get("song_id") == song_id:
                    active_scene_index = idx
                    active_song_transpose = int(entry.get("transpose", 0))
                    break
        except KeyError:
            pass

    _notify_song_changed()
    return {
        "status": "loaded",
        "song": current_song.to_summary_dict(),
        "default_transpose": active_song_transpose,
        "warnings": list(song_loader.last_load_errors),
    }


def _read_text_upload(upload: UploadFile) -> str:
    """Lee un archivo de texto subido tolerando UTF-8 (con o sin BOM) y Latin-1 (Bloc de notas antiguo)."""
    raw = upload.file.read()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _validate_audio_uploads(files: List[UploadFile]) -> None:
    """Rechaza archivos que no sean audio antes de escribir nada en disco."""
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"'{f.filename}' no es un archivo de audio admitido "
                f"({', '.join(sorted(AUDIO_EXTENSIONS))}).",
            )


@app.get("/api/songs")
def list_available_songs():
    """Lista todas las canciones encontradas en la carpeta tracks/."""
    return song_loader.scan_songs()


@app.post("/api/songs/{song_id}/load")
def load_song_endpoint(song_id: str):
    """Carga una canción específica de tracks/ y la sincroniza con el motor de audio."""
    try:
        return _activate_song(song_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/songs/parse-preview")
def parse_chordpro_preview(payload: dict):
    """Parsea texto ChordPro en memoria y retorna la vista previa estructurada."""
    content = payload.get("content", "")
    if not content:
        raise HTTPException(status_code=400, detail="El contenido no puede estar vacío")
    parsed = ChordProParser.parse_string(content)
    return parsed.to_full_dict()


@app.post("/api/songs/import")
def import_song_endpoint(payload: dict):
    """Importa texto ChordPro, crea la carpeta en tracks/ y opcionalmente la carga."""
    content = payload.get("content", "")
    custom_id = payload.get("id")
    if not content:
        raise HTTPException(status_code=400, detail="El contenido no puede estar vacío")
    try:
        song = song_loader.import_chordpro_text(content, custom_id=custom_id)
        if payload.get("load_immediately", True):
            _activate_song(song.id)
        return {"status": "imported", "song": song.to_summary_dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/songs/upload")
def upload_song_endpoint(
    title: str = Form(""),
    artist: str = Form(""),
    key: str = Form(""),
    bpm: str = Form(""),
    chart_text: str = Form(""),
    load_immediately: bool = Form(True),
    chart_file: Optional[UploadFile] = File(None),
    stems: Optional[List[UploadFile]] = File(None),
):
    """
    Crea una canción nueva desde la web: título/metadatos, ChordPro (archivo o texto pegado)
    y pistas de audio (stems). Todo se guarda en tracks/<cancion>/.
    """
    stem_files = [s for s in (stems or []) if s.filename]
    _validate_audio_uploads(stem_files)

    content = chart_text.strip()
    if chart_file is not None and chart_file.filename:
        if os.path.splitext(chart_file.filename)[1].lower() not in CHART_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"El archivo de letra debe ser {', '.join(sorted(CHART_EXTENSIONS))}.",
            )
        content = _read_text_upload(chart_file).strip()

    if not title.strip() and not content:
        raise HTTPException(status_code=400, detail="Escribe un título o adjunta un archivo ChordPro.")

    try:
        bpm_value = float(bpm) if bpm.strip() else None
    except ValueError:
        raise HTTPException(status_code=400, detail="El BPM debe ser un número (ej. 76 o 104.5).")

    try:
        song_id = song_loader.create_song(
            title=title.strip(),
            chordpro_content=content,
            artist=artist.strip(),
            key=key.strip(),
            bpm=bpm_value,
        )
        saved = song_loader.save_stem_files(song_id, [(s.filename, s.file) for s in stem_files])

        result = {"status": "uploaded", "song_id": song_id, "stems_saved": saved, "warnings": []}
        if load_immediately:
            activation = _activate_song(song_id)
            result["song"] = activation["song"]
            result["warnings"] = activation["warnings"]
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/songs/{song_id}/stems")
def add_stems_endpoint(song_id: str, stems: List[UploadFile] = File(...)):
    """Agrega (o reemplaza si tienen el mismo nombre) pistas de audio a una canción existente."""
    stem_files = [s for s in stems if s.filename]
    if not stem_files:
        raise HTTPException(status_code=400, detail="No se recibió ningún archivo de audio.")
    _validate_audio_uploads(stem_files)
    try:
        saved = song_loader.save_stem_files(song_id, [(s.filename, s.file) for s in stem_files])
        result = {"status": "stems_added", "song_id": song_id, "stems_saved": saved, "warnings": []}
        if current_song.id == song_id:
            result["warnings"] = _activate_song(song_id)["warnings"]
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/songs/{song_id}/stems/{filename}")
def delete_stem_endpoint(song_id: str, filename: str):
    """Elimina una pista de audio de una canción."""
    try:
        song_loader.delete_stem(song_id, filename)
        if current_song.id == song_id:
            _activate_song(song_id)
        return {"status": "stem_deleted", "file": filename}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/songs/{song_id}/chart")
def get_chart_endpoint(song_id: str):
    """Devuelve el texto ChordPro de una canción para editarlo en la consola."""
    try:
        folder = song_loader._song_folder(song_id)
        chart_path = SongLoader._find_chart(folder)
        if not chart_path:
            return {"song_id": song_id, "content": ""}
        with open(chart_path, "r", encoding="utf-8") as f:
            return {"song_id": song_id, "content": f.read()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/songs/{song_id}/chart")
def update_chart_endpoint(song_id: str, payload: dict):
    """Reemplaza la letra/acordes (ChordPro) de una canción existente conservando sus stems."""
    content = payload.get("content", "")
    if not content.strip():
        raise HTTPException(status_code=400, detail="El contenido no puede estar vacío")
    try:
        folder = song_loader._song_folder(song_id)
        if not os.path.exists(folder):
            raise FileNotFoundError(f"Canción no encontrada: {song_id}")
        song_loader.import_chordpro_text(content, custom_id=song_id)
        if current_song.id == song_id:
            _activate_song(song_id)
        return {"status": "chart_updated", "song_id": song_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/songs/{song_id}")
def delete_song_endpoint(song_id: str):
    """Elimina una canción completa (letra, json y pistas de audio) de tracks/."""
    global current_song
    try:
        was_active = current_song.id == song_id
        if was_active and engine is not None:
            engine.stop()
        song_loader.delete_song(song_id)
        if was_active and engine is not None:
            current_song = create_demo_song()
            setup_demo_audio(engine, current_song)
            _notify_song_changed()
        return {"status": "song_deleted", "song_id": song_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------------------------------------------------------
# Endpoints de Transporte de Audio
# -----------------------------------------------------------------------------

@app.post("/api/transport/play")
def transport_play():
    if engine is None:
        raise HTTPException(status_code=503, detail="Motor no disponible")
    try:
        engine.play()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "playing", "pos": engine.current_position_seconds}


@app.post("/api/transport/pause")
def transport_pause():
    if engine is None:
        raise HTTPException(status_code=503, detail="Motor no disponible")
    engine.pause()
    return {"status": "paused", "pos": engine.current_position_seconds}


@app.post("/api/transport/stop")
def transport_stop():
    if engine is None:
        raise HTTPException(status_code=503, detail="Motor no disponible")
    engine.stop()
    return {"status": "stopped", "pos": 0.0}


@app.post("/api/transport/seek")
def transport_seek(pos: float):
    if engine is None:
        raise HTTPException(status_code=503, detail="Motor no disponible")
    engine.seek(pos)
    return {"status": "seeked", "pos": engine.current_position_seconds}


# -----------------------------------------------------------------------------
# Endpoints de Mezcla de Stems
# -----------------------------------------------------------------------------

@app.get("/api/stems")
def list_stems():
    if engine is None:
        raise HTTPException(status_code=503, detail="Motor no disponible")
    stems = engine.list_stems()
    return [
        {
            "name": s.name,
            "route": s.route,
            "volume": s.volume,
            "pan": s.pan,
            "mute": s.mute,
            "solo": s.solo,
            "duration": s.duration_seconds,
        }
        for s in stems
    ]


@app.post("/api/stems/{name}/volume")
def set_stem_volume(name: str, volume: float):
    if engine is None:
        raise HTTPException(status_code=503, detail="Motor no disponible")
    stem = engine.get_stem(name)
    if not stem:
        raise HTTPException(status_code=404, detail=f"Stem '{name}' no encontrado")
    stem.volume = max(0.0, float(volume))
    return {"name": stem.name, "volume": stem.volume}


@app.post("/api/stems/{name}/mute")
def toggle_stem_mute(name: str, mute: bool):
    if engine is None:
        raise HTTPException(status_code=503, detail="Motor no disponible")
    stem = engine.get_stem(name)
    if not stem:
        raise HTTPException(status_code=404, detail=f"Stem '{name}' no encontrado")
    stem.mute = bool(mute)
    return {"name": stem.name, "mute": stem.mute}


@app.post("/api/stems/{name}/solo")
def toggle_stem_solo(name: str, solo: bool):
    if engine is None:
        raise HTTPException(status_code=503, detail="Motor no disponible")
    stem = engine.get_stem(name)
    if not stem:
        raise HTTPException(status_code=404, detail=f"Stem '{name}' no encontrado")
    stem.solo = bool(solo)
    return {"name": stem.name, "solo": stem.solo}


@app.post("/api/stems/{name}/route")
def set_stem_route(name: str, route: str):
    """Cambia el ruteo en vivo de una pista ('cue' para in-ears, 'master' para sala/FOH, 'both' para ambos)."""
    if engine is None:
        raise HTTPException(status_code=503, detail="Motor no disponible")
    if route not in ("cue", "master", "both"):
        raise HTTPException(status_code=400, detail="Ruta inválida (usa 'cue', 'master' o 'both')")
    stem = engine.get_stem(name)
    if not stem:
        raise HTTPException(status_code=404, detail=f"Stem '{name}' no encontrado")
    stem.route = route
    return {"name": stem.name, "route": stem.route}


# -----------------------------------------------------------------------------
# Endpoints de Escenas / Listas Dominicales (Setlists)
# -----------------------------------------------------------------------------

@app.get("/api/scenes")
def list_scenes_endpoint():
    """Lista todas las escenas creadas (ordenadas por fecha más reciente)."""
    return scene_manager.list_scenes(_build_library_map())


@app.post("/api/scenes")
def create_scene_endpoint(payload: dict):
    """Crea una nueva escena / lista para un servicio (con nombre, fecha, notas y canciones)."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Escribe un nombre para la escena (ej. Servicio Dominical).")
    scene = scene_manager.create_scene(
        name=name,
        date=payload.get("date") or "",
        notes=payload.get("notes") or "",
        songs=payload.get("songs") or [],
    )
    return scene_manager.get_scene(scene["id"], _build_library_map())


@app.put("/api/scenes/{scene_id}")
def update_scene_endpoint(scene_id: str, payload: dict):
    """Actualiza el nombre, fecha, notas o el orden de canciones de una escena existente."""
    try:
        scene_manager.update_scene(
            scene_id=scene_id,
            name=payload.get("name"),
            date=payload.get("date"),
            notes=payload.get("notes"),
            songs=payload.get("songs"),
        )
        return scene_manager.get_scene(scene_id, _build_library_map())
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/scenes/{scene_id}")
def delete_scene_endpoint(scene_id: str):
    """Elimina una escena guardada (sin borrar las canciones de la Biblioteca)."""
    global active_scene_id, active_scene_index, active_song_transpose
    try:
        scene_manager.delete_scene(scene_id)
        if active_scene_id == scene_id:
            active_scene_id = None
            active_scene_index = 0
            active_song_transpose = 0
        return {"status": "scene_deleted", "scene_id": scene_id}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/scenes/{scene_id}/activate")
def activate_scene_endpoint(scene_id: str, index: int = 0):
    """Activa una escena dominical y carga la canción en la posición indicada."""
    global active_scene_id, active_scene_index
    try:
        scene = scene_manager.get_scene(scene_id, _build_library_map())
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    items = scene.get("items", [])
    active_scene_id = scene_id
    warnings = []

    if items:
        clamped = max(0, min(int(index), len(items) - 1))
        active_scene_index = clamped
        target = items[clamped]
        if not target.get("missing"):
            activation = _activate_song(
                target["song_id"],
                default_transpose=int(target.get("transpose", 0)),
                from_scene=True,
            )
            warnings = activation["warnings"]
    else:
        active_scene_index = 0

    return {
        "status": "scene_activated",
        "active_scene": _get_active_scene_status(),
        "song": current_song.to_summary_dict(),
        "warnings": warnings,
    }


@app.post("/api/scenes/navigate")
def navigate_scene_endpoint(direction: str = "next"):
    """Avanza o retrocede a la siguiente/anterior canción dentro de la escena activa."""
    global active_scene_index
    if not active_scene_id:
        raise HTTPException(status_code=400, detail="No hay ninguna escena activa.")

    try:
        scene = scene_manager.get_scene(active_scene_id, _build_library_map())
    except KeyError:
        raise HTTPException(status_code=404, detail="La escena activa ya no existe.")

    items = scene.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="La escena activa no tiene canciones.")

    delta = -1 if direction == "prev" else 1
    new_idx = active_scene_index + delta
    if new_idx < 0 or new_idx >= len(items):
        raise HTTPException(status_code=400, detail="Ya estás en el extremo de la lista.")

    target = items[new_idx]
    if target.get("missing"):
        raise HTTPException(
            status_code=400,
            detail=f"La canción '{target['song_id']}' ya no está en la biblioteca.",
        )

    active_scene_index = new_idx
    activation = _activate_song(
        target["song_id"],
        default_transpose=int(target.get("transpose", 0)),
        from_scene=True,
    )
    return {
        "status": "scene_navigated",
        "active_scene": _get_active_scene_status(),
        "song": activation["song"],
        "warnings": activation["warnings"],
    }


@app.post("/api/scenes/deactivate")
def deactivate_scene_endpoint():
    """Cierra el modo escena sin detener la canción actual."""
    global active_scene_id, active_scene_index, active_song_transpose
    active_scene_id = None
    active_scene_index = 0
    active_song_transpose = 0
    return {"status": "scene_deactivated"}


# -----------------------------------------------------------------------------
# Endpoints de Configuración de Proyección, Video Loops y Fondos
# -----------------------------------------------------------------------------

def _refresh_projection_live_state() -> None:
    """Empuja configuración y letra actual (con nueva anticipación) a Proyector y OBS."""
    settings = projection_config.get_settings()
    _broadcast_async(
        ChannelType.PROJECTION,
        {"type": "projection_config", "settings": settings},
    )
    if engine is not None:
        pos = engine.current_position_seconds
        proj_lyric, proj_sec = current_song.get_projection_lyric_at(
            pos, projection_config.lead_seconds
        )
        _broadcast_async(
            ChannelType.PROJECTION,
            {
                "type": "projection_tick",
                "pos": round(pos, 3),
                "playing": engine.is_playing,
                "sec": proj_sec,
                "lyric": "" if ws_manager._projection_clear_text else proj_lyric,
                "blackout": ws_manager._projection_blackout,
                "clear": ws_manager._projection_clear_text,
            },
        )


@app.get("/api/projection/settings")
def get_projection_settings():
    """Devuelve ajustes actuales de proyección, lista de fondos/loops y estado de blackout."""
    return {
        "settings": projection_config.get_settings(),
        "backgrounds": projection_config.list_backgrounds(),
        "blackout": ws_manager._projection_blackout,
        "clear": ws_manager._projection_clear_text,
        "song_title": current_song.title,
    }


@app.put("/api/projection/settings")
def update_projection_settings(payload: dict):
    """Actualiza fondo/video loop activo, oscurecimiento, anticipación de letra o color."""
    updated = projection_config.update_settings(
        background=payload.get("background"),
        dim_opacity=payload.get("dim_opacity"),
        lead_seconds=payload.get("lead_seconds"),
        text_color=payload.get("text_color"),
        lower_thirds=payload.get("lower_thirds"),
    )
    _refresh_projection_live_state()
    return {
        "settings": updated,
        "backgrounds": projection_config.list_backgrounds(),
    }


@app.post("/api/projection/backgrounds")
def upload_projection_background(
    file: UploadFile = File(...),
    apply_immediately: bool = Form(True),
):
    """Sube una imagen o video loop (.mp4, .webm, .mov) para usar de fondo en /projection."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Selecciona una imagen o video loop.")
    try:
        saved = projection_config.save_background_file(file.filename, file.file)
        if apply_immediately:
            projection_config.update_settings(background=saved["id"])
            _refresh_projection_live_state()
        return {
            "status": "background_uploaded",
            "background": saved,
            "settings": projection_config.get_settings(),
            "backgrounds": projection_config.list_backgrounds(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/projection/backgrounds/{filename}")
def delete_projection_background(filename: str):
    """Elimina un fondo o video loop personalizado del disco."""
    try:
        projection_config.delete_background_file(filename)
        _refresh_projection_live_state()
        return {
            "status": "background_deleted",
            "settings": projection_config.get_settings(),
            "backgrounds": projection_config.list_backgrounds(),
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# -----------------------------------------------------------------------------
# Canales WebSockets
# -----------------------------------------------------------------------------

@app.websocket("/ws/musicians")
async def websocket_musicians_endpoint(websocket: WebSocket):
    """Canal de alta resolución para tablets/teléfonos de músicos (acordes + letra + reloj)."""
    await ws_manager.connect(websocket, ChannelType.MUSICIANS)
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "song_changed",
                    "song": current_song.to_summary_dict(),
                    "default_transpose": active_song_transpose,
                }
            )
        )
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
                pos = engine.current_position_seconds if engine else 0.0
                playing = engine.is_playing if engine else False
                await ws_manager.handle_client_message(
                    websocket, ChannelType.MUSICIANS, data, pos, playing
                )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, ChannelType.MUSICIANS)


@app.websocket("/ws/projection")
async def websocket_projection_endpoint(websocket: WebSocket):
    """Canal limpio para proyector (/projection) y letras OBS (/obs)."""
    await ws_manager.connect(websocket, ChannelType.PROJECTION)
    try:
        # Enviar estado inicial inmediato al conectar
        pos = engine.current_position_seconds if engine else 0.0
        playing = engine.is_playing if engine else False
        proj_lyric, proj_sec = current_song.get_projection_lyric_at(
            pos, projection_config.lead_seconds
        )
        await websocket.send_text(
            json.dumps(
                {
                    "type": "projection_config",
                    "settings": projection_config.get_settings(),
                }
            )
        )
        await websocket.send_text(
            json.dumps({"type": "song_changed", "title": current_song.title})
        )
        await websocket.send_text(
            json.dumps(
                {
                    "type": "projection_tick",
                    "pos": round(pos, 3),
                    "playing": playing,
                    "sec": proj_sec,
                    "lyric": "" if ws_manager._projection_clear_text else proj_lyric,
                    "blackout": ws_manager._projection_blackout,
                    "clear": ws_manager._projection_clear_text,
                }
            )
        )

        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
                pos = engine.current_position_seconds if engine else 0.0
                playing = engine.is_playing if engine else False
                await ws_manager.handle_client_message(
                    websocket, ChannelType.PROJECTION, data, pos, playing
                )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, ChannelType.PROJECTION)


@app.websocket("/ws/control")
async def websocket_control_endpoint(websocket: WebSocket):
    """Canal para consola y mandos remotos."""
    await ws_manager.connect(websocket, ChannelType.CONTROL)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
                pos = engine.current_position_seconds if engine else 0.0
                playing = engine.is_playing if engine else False
                await ws_manager.handle_client_message(
                    websocket, ChannelType.CONTROL, data, pos, playing
                )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, ChannelType.CONTROL)


# -----------------------------------------------------------------------------
# Entrega de Aplicaciones Web Clientes (Control, Músicos, Proyección y OBS)
# -----------------------------------------------------------------------------

CLIENTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "clients", "web"))


@app.get("/", response_class=HTMLResponse)
@app.get("/control", response_class=HTMLResponse)
def serve_control_page():
    path = os.path.join(CLIENTS_DIR, "control.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Panel de Control no encontrado</h1>"


@app.get("/musicians", response_class=HTMLResponse)
def serve_musicians_page():
    path = os.path.join(CLIENTS_DIR, "musicians.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Terminal de Músicos no encontrada</h1>"


@app.get("/projection", response_class=HTMLResponse)
def serve_projection_page():
    path = os.path.join(CLIENTS_DIR, "projection.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Pantalla de Proyección no encontrada</h1>"


@app.get("/obs", response_class=HTMLResponse)
def serve_obs_page():
    """Ruta independiente exclusiva para OBS Studio (Browser Source con transparencia real)."""
    path = os.path.join(CLIENTS_DIR, "obs.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Salida OBS no encontrada</h1>"
