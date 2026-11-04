"""
Cargador y Gestor de Paquetes de Canciones y Stems en Disco
Subagente responsable: 01-lead-architect & 02-audio-multitrack-engineer
"""

import os
import re
from typing import Dict, List, Optional
from src.audio.engine import MultitrackEngine
from src.audio.stem import StemTrack
from src.audio.synthetic import (
    generate_click_track,
    generate_guide_cues,
    generate_instrument_stem,
)
from src.core.chordpro import ChordProParser
from src.core.song import Song


AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}
CHORDPRO_FILENAMES = ["chart.pro", "chart.txt", "song.pro", "song.txt", "song.cho", "song.chordpro"]


class SongLoader:
    """
    Gestiona la biblioteca local de canciones en la carpeta tracks/,
    sincronizando el análisis de ChordPro con la carga de stems de audio en el motor.
    """

    def __init__(self, tracks_root: str):
        self.tracks_root = os.path.abspath(tracks_root)
        os.makedirs(self.tracks_root, exist_ok=True)

    def scan_songs(self) -> List[dict]:
        """
        Escanea la carpeta tracks/ y retorna la lista de todas las canciones disponibles.
        """
        songs_list = []
        if not os.path.exists(self.tracks_root):
            return songs_list

        for entry in os.scandir(self.tracks_root):
            if entry.is_dir():
                song_folder = entry.path
                info = self._inspect_song_folder(song_folder)
                if info:
                    songs_list.append(info)

        return sorted(songs_list, key=lambda s: s["title"].lower())

    def _inspect_song_folder(self, folder_path: str) -> Optional[dict]:
        folder_name = os.path.basename(folder_path)
        chart_file = None
        json_file = os.path.join(folder_path, "song.json")

        for fname in CHORDPRO_FILENAMES:
            candidate = os.path.join(folder_path, fname)
            if os.path.exists(candidate):
                chart_file = candidate
                break

        # Contar archivos de audio en la carpeta raíz de la canción o en subcarpeta stems/
        stems_dir = os.path.join(folder_path, "stems")
        audio_files = []
        if os.path.exists(stems_dir) and os.path.isdir(stems_dir):
            for f in os.listdir(stems_dir):
                if os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS:
                    audio_files.append(os.path.join(stems_dir, f))
        else:
            for f in os.listdir(folder_path):
                if os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS:
                    audio_files.append(os.path.join(folder_path, f))

        # Si no hay chart ni json ni audio, omitir carpeta vacía
        if not chart_file and not os.path.exists(json_file) and not audio_files:
            return None

        # Obtener metadatos de la canción
        song_obj = None
        try:
            if chart_file:
                # Si el chart es más reciente que el json o no hay json, parsear chart
                if not os.path.exists(json_file) or os.path.getmtime(chart_file) > os.path.getmtime(json_file):
                    song_obj = ChordProParser.parse_file(chart_file)
                    song_obj.id = folder_name
                    ChordProParser.export_to_json(song_obj, json_file)
                else:
                    song_obj = ChordProParser.load_from_json(json_file)
            elif os.path.exists(json_file):
                song_obj = ChordProParser.load_from_json(json_file)
        except Exception:
            pass

        if song_obj:
            summary = song_obj.to_summary_dict()
        else:
            summary = {
                "id": folder_name,
                "title": folder_name.replace("-", " ").title(),
                "artist": "Desconocido",
                "key": "C",
                "bpm": 120.0,
                "time_signature": "4/4",
                "duration": 0.0,
                "sections_count": 0,
            }

        summary["folder"] = folder_path
        summary["has_chart"] = chart_file is not None
        summary["stems_count"] = len(audio_files)
        return summary

    def load_song(self, song_id: str, engine: MultitrackEngine) -> Song:
        """
        Carga una canción específica y monta sus pistas en el motor de audio.
        """
        folder_path = os.path.join(self.tracks_root, song_id)
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Carpeta de canción no encontrada: {song_id}")

        json_file = os.path.join(folder_path, "song.json")
        chart_file = None
        for fname in CHORDPRO_FILENAMES:
            candidate = os.path.join(folder_path, fname)
            if os.path.exists(candidate):
                chart_file = candidate
                break

        if chart_file and (not os.path.exists(json_file) or os.path.getmtime(chart_file) > os.path.getmtime(json_file)):
            song = ChordProParser.parse_file(chart_file)
            song.id = song_id
            ChordProParser.export_to_json(song, json_file)
        elif os.path.exists(json_file):
            song = ChordProParser.load_from_json(json_file)
        else:
            raise ValueError("No se encontró archivo ChordPro (.pro) ni song.json en la carpeta.")

        # Cargar Stems de Audio
        stems_dir = os.path.join(folder_path, "stems")
        audio_paths = []
        if os.path.exists(stems_dir) and os.path.isdir(stems_dir):
            for f in os.listdir(stems_dir):
                if os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS:
                    audio_paths.append(os.path.join(stems_dir, f))
        else:
            for f in os.listdir(folder_path):
                if os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS:
                    audio_paths.append(os.path.join(folder_path, f))

        engine.clear_stems()

        if audio_paths:
            # Cargar pistas reales del usuario
            for path in audio_paths:
                stem_name = os.path.splitext(os.path.basename(path))[0]
                stem_track = StemTrack.load_from_file(path, name=stem_name)
                engine.add_stem(stem_track)
        else:
            # Generar audio sintético sincronizado con el BPM y la duración de la canción
            duration = max(song.duration_seconds, 60.0)
            click = generate_click_track(bpm=song.bpm, duration_seconds=duration)
            guide = generate_guide_cues(bpm=song.bpm, duration_seconds=duration)
            pad = generate_instrument_stem("Pad", frequency=196.0, duration_seconds=duration)
            bass = generate_instrument_stem("Bajo", frequency=98.0, duration_seconds=duration)

            engine.add_stem(click)
            engine.add_stem(guide)
            engine.add_stem(pad)
            engine.add_stem(bass)

        return song

    def import_chordpro_text(self, chordpro_content: str, custom_id: Optional[str] = None) -> Song:
        """
        Crea una nueva carpeta de canción a partir de texto ChordPro ingresado por el usuario.
        """
        song = ChordProParser.parse_string(chordpro_content, default_id="cancion-nueva")
        song_id = custom_id or song.id
        # Limpiar nombre para carpeta
        song_id = re.sub(r"[^a-zA-Z0-9_\-]", "", song_id.lower().replace(" ", "-"))
        if not song_id:
            song_id = "cancion-adoracion"
        song.id = song_id

        folder_path = os.path.join(self.tracks_root, song_id)
        os.makedirs(folder_path, exist_ok=True)
        stems_dir = os.path.join(folder_path, "stems")
        os.makedirs(stems_dir, exist_ok=True)

        chart_path = os.path.join(folder_path, "chart.pro")
        with open(chart_path, "w", encoding="utf-8") as f:
            f.write(chordpro_content)

        json_path = os.path.join(folder_path, "song.json")
        ChordProParser.export_to_json(song, json_path)

        return song
