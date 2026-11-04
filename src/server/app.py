"""
Servidor Central FastAPI y Rutas de Sincronización en Tiempo Real
Subagente responsable: 03-network-sync-engineer
"""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
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
from src.core.song import Song, create_demo_song
from src.core.song_loader import SongLoader
from src.server.websocket_manager import ChannelType, ConnectionManager
from src.utils.network import get_connection_url, get_local_ip, print_ascii_qr


# -----------------------------------------------------------------------------
# Instancias Globales
# -----------------------------------------------------------------------------
TRACKS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tracks"))
song_loader = SongLoader(tracks_root=TRACKS_DIR)

engine: Optional[MultitrackEngine] = None
ws_manager = ConnectionManager()
current_song: Song = create_demo_song()
main_event_loop: Optional[asyncio.AbstractEventLoop] = None


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

    # Extraer metadatos de la canción en la posición actual
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

    # Enviar al bucle asíncrono principal sin bloquear el hilo de audio
    coro = ws_manager.broadcast_tick(
        position_seconds=pos_seconds,
        is_playing=is_playing,
        current_section=sec_name,
        current_lyric=lyric_text,
        current_chord=active_chord,
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

    print("\n" + "=" * 60)
    print("🚀 SERVIDOR DE SINCRONIZACIÓN DE ADORACIÓN ACTIVO")
    print("=" * 60)
    print(f"📡 IP Local del PC:          {local_ip}")
    print(f"🎸 Pantalla Músicos:         {musician_url}")
    print(f"📽 Pantalla Proyección / OBS: {projection_url}")
    print(f"🎛 Panel de Control Central: {get_connection_url(port, '/control')}")
    print("=" * 60)
    print("📲 Escanea este código QR con tu móvil para abrir la vista de músicos:")
    print_ascii_qr(musician_url)
    print("=" * 60 + "\n")

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
        "clients": ws_manager.get_stats(),
    }


@app.get("/api/song")
def get_current_song(transpose: int = 0):
    """Devuelve la estructura completa de la canción con acordes (con transposición opcional)."""
    return current_song.to_full_dict(transpose_semitones=transpose)


# -----------------------------------------------------------------------------
# Endpoints de Biblioteca de Canciones y ChordPro
# -----------------------------------------------------------------------------

@app.get("/api/songs")
def list_available_songs():
    """Lista todas las canciones encontradas en la carpeta tracks/."""
    return song_loader.scan_songs()


@app.post("/api/songs/{song_id}/load")
async def load_song_endpoint(song_id: str):
    """Carga una canción específica de tracks/ y la sincroniza con el motor de audio."""
    global current_song, engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Motor no disponible")
    try:
        engine.stop()
        current_song = song_loader.load_song(song_id, engine)
        await ws_manager.broadcast_to_channel(
            ChannelType.MUSICIANS,
            {"type": "song_changed", "song": current_song.to_summary_dict()},
        )
        await ws_manager.broadcast_to_channel(
            ChannelType.PROJECTION,
            {"type": "song_changed", "title": current_song.title},
        )
        return {"status": "loaded", "song": current_song.to_summary_dict()}
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
async def import_song_endpoint(payload: dict):
    """Importa texto ChordPro, crea la carpeta en tracks/ y opcionalmente la carga."""
    global current_song, engine
    content = payload.get("content", "")
    custom_id = payload.get("id")
    if not content:
        raise HTTPException(status_code=400, detail="El contenido no puede estar vacío")
    try:
        song = song_loader.import_chordpro_text(content, custom_id=custom_id)
        if payload.get("load_immediately", True) and engine is not None:
            engine.stop()
            current_song = song_loader.load_song(song.id, engine)
            await ws_manager.broadcast_to_channel(
                ChannelType.MUSICIANS,
                {"type": "song_changed", "song": current_song.to_summary_dict()},
            )
            await ws_manager.broadcast_to_channel(
                ChannelType.PROJECTION,
                {"type": "song_changed", "title": current_song.title},
            )
        return {"status": "imported", "song": song.to_summary_dict()}
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


# -----------------------------------------------------------------------------
# Canales WebSockets
# -----------------------------------------------------------------------------

@app.websocket("/ws/musicians")
async def websocket_musicians_endpoint(websocket: WebSocket):
    """Canal de alta resolución para tablets/teléfonos de músicos (acordes + letra + reloj)."""
    await ws_manager.connect(websocket, ChannelType.MUSICIANS)
    try:
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
    """Canal limpio para proyector o pantalla de transmisión (solo letra)."""
    await ws_manager.connect(websocket, ChannelType.PROJECTION)
    try:
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
# Entrega de Aplicaciones Web Clientes (Músicos, Proyección, Control)
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
