"""
Cargador y Gestor de Paquetes de Canciones y Stems en Disco
Subagente responsable: 01-lead-architect & 02-audio-multitrack-engineer
"""

import json
import os
import re
import shutil
from typing import BinaryIO, Iterable, List, Optional, Tuple
from src.audio.engine import MultitrackEngine
from src.audio.stem import StemTrack
from src.audio.synthetic import (
    generate_click_track,
    generate_guide_cues,
    generate_instrument_stem,
)
from src.core.chordpro import ChordProParser, slugify
from src.core.song import Song


AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aiff", ".aif"}
CHART_EXTENSIONS = {".pro", ".txt", ".cho", ".chordpro", ".crd"}
CHORDPRO_FILENAMES = ["chart.pro", "chart.txt", "song.pro", "song.txt", "song.cho", "song.chordpro"]
COPY_CHUNK_SIZE = 1024 * 1024  # 1 MB por bloque al guardar archivos subidos


def sanitize_filename(filename: str) -> str:
    """
    Limpia el nombre de un archivo subido para evitar rutas maliciosas (../)
    y caracteres no válidos en Windows, preservando la extensión.
    """
    base = os.path.basename(filename.replace("\\", "/"))
    name, ext = os.path.splitext(base)
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip(" .")
    if not safe_name:
        safe_name = "pista"
    return f"{safe_name}{ext.lower()}"


class SongLoader:
    """
    Gestiona la biblioteca local de canciones en la carpeta tracks/,
    sincronizando el análisis de ChordPro con la carga de stems de audio en el motor.
    """

    def __init__(self, tracks_root: str):
        self.tracks_root = os.path.abspath(tracks_root)
        os.makedirs(self.tracks_root, exist_ok=True)
        # Archivos de audio que no se pudieron decodificar en la última carga
        self.last_load_errors: List[str] = []
        self._index_file = os.path.join(self.tracks_root, "library_index.json")
        self._cached_songs: Optional[List[dict]] = None
        self._last_scan_mtime: float = 0.0

    def invalidate_cache(self) -> None:
        """Invalida el índice en memoria y fuerza su regeneración."""
        self._cached_songs = None
        self._last_scan_mtime = 0.0
        if os.path.exists(self._index_file):
            try:
                os.remove(self._index_file)
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # Utilidades de rutas
    # --------------------------------------------------------------------------

    def _song_folder(self, song_id: str) -> str:
        """Ruta absoluta de la carpeta de una canción, validando que esté dentro de tracks/."""
        folder = os.path.abspath(os.path.join(self.tracks_root, song_id))
        if os.path.dirname(folder) != self.tracks_root:
            raise ValueError(f"Identificador de canción inválido: {song_id}")
        return folder

    def _stems_dir(self, song_id: str) -> str:
        return os.path.join(self._song_folder(song_id), "stems")

    @staticmethod
    def _find_chart(folder_path: str) -> Optional[str]:
        for fname in CHORDPRO_FILENAMES:
            candidate = os.path.join(folder_path, fname)
            if os.path.exists(candidate):
                return candidate
        return None

    @staticmethod
    def _list_audio_files(folder_path: str) -> List[str]:
        """Busca audios en <cancion>/stems/ y, si no existe, en la raíz de la canción."""
        stems_dir = os.path.join(folder_path, "stems")
        search_dir = stems_dir if os.path.isdir(stems_dir) else folder_path
        files = []
        for f in sorted(os.listdir(search_dir)):
            if os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS:
                files.append(os.path.join(search_dir, f))
        return files

    # --------------------------------------------------------------------------
    # Lectura y Caché de la biblioteca (library_index.json <2ms)
    # --------------------------------------------------------------------------

    def scan_songs(self, force_refresh: bool = False) -> List[dict]:
        """
        Escanea la carpeta tracks/ y retorna la lista de todas las canciones disponibles.
        Utiliza library_index.json y caché en memoria para resoluciones ultra rápidas (<2ms).
        """
        if not os.path.exists(self.tracks_root):
            return []

        try:
            current_mtime = os.path.getmtime(self.tracks_root)
        except OSError:
            current_mtime = 0.0

        if not force_refresh and self._cached_songs is not None and self._last_scan_mtime == current_mtime:
            return self._cached_songs

        # Intentar leer desde library_index.json en disco
        if not force_refresh and os.path.exists(self._index_file):
            try:
                with open(self._index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "songs" in data:
                        if data.get("tracks_mtime") == current_mtime:
                            self._cached_songs = data["songs"]
                            self._last_scan_mtime = current_mtime
                            return self._cached_songs
            except Exception:
                pass

        # Escaneo completo del directorio
        songs_list = []
        for entry in os.scandir(self.tracks_root):
            if entry.is_dir():
                info = self._inspect_song_folder(entry.path)
                if info:
                    songs_list.append(info)

        sorted_songs = sorted(songs_list, key=lambda s: s["title"].lower())
        self._cached_songs = sorted_songs

        # Persistir índice a disco
        try:
            temp_idx = self._index_file + ".tmp"
            with open(temp_idx, "w", encoding="utf-8") as f:
                json.dump({"tracks_mtime": current_mtime, "count": len(sorted_songs), "songs": sorted_songs}, f, indent=2, ensure_ascii=False)
            if os.path.exists(self._index_file):
                os.remove(self._index_file)
            os.rename(temp_idx, self._index_file)
            self._last_scan_mtime = os.path.getmtime(self.tracks_root)
        except Exception:
            self._last_scan_mtime = current_mtime

        return sorted_songs

    def prewarm_song(self, song_id: str) -> bool:
        """
        Pre-calienta en la memoria de disco del sistema operativo los archivos de audio
        de una canción (por ejemplo, el siguiente tema del setlist del domingo).
        """
        try:
            folder = self._song_folder(song_id)
            for path in self._list_audio_files(folder):
                with open(path, "rb") as fh:
                    while fh.read(1024 * 512):
                        pass
            return True
        except Exception:
            return False

    def load_song_metadata(self, song_id: str) -> Optional[Song]:
        """Retorna el objeto Song estructurado de una canción por su ID sin requerir audio."""
        folder = self._song_folder(song_id)
        if not os.path.exists(folder):
            raise FileNotFoundError(f"Carpeta de canción no encontrada: {song_id}")
        return self._read_song_metadata(folder)

    def _read_song_metadata(self, folder_path: str) -> Optional[Song]:
        """Obtiene el objeto Song desde chart.pro (regenerando song.json si cambió) o song.json."""
        folder_name = os.path.basename(folder_path)
        chart_file = self._find_chart(folder_path)
        json_file = os.path.join(folder_path, "song.json")

        needs_recompile = False
        if chart_file:
            if not os.path.exists(json_file) or os.path.getmtime(chart_file) > os.path.getmtime(json_file):
                needs_recompile = True
            else:
                try:
                    with open(json_file, "r", encoding="utf-8") as jf:
                        if json.load(jf).get("schema_version") != ChordProParser.SCHEMA_VERSION:
                            needs_recompile = True
                except Exception:
                    needs_recompile = True

        if chart_file and needs_recompile:
            song = ChordProParser.parse_file(chart_file)
            song.id = folder_name
            ChordProParser.export_to_json(song, json_file)
            return song
        if os.path.exists(json_file):
            song = ChordProParser.load_from_json(json_file)
            song.id = folder_name
            return song
        return None

    def _inspect_song_folder(self, folder_path: str) -> Optional[dict]:
        folder_name = os.path.basename(folder_path)
        chart_file = self._find_chart(folder_path)
        json_file = os.path.join(folder_path, "song.json")
        audio_files = self._list_audio_files(folder_path)

        # Si no hay chart ni json ni audio, omitir carpeta vacía
        if not chart_file and not os.path.exists(json_file) and not audio_files:
            return None

        song_obj = None
        try:
            song_obj = self._read_song_metadata(folder_path)
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

        summary["id"] = folder_name
        summary["folder"] = folder_path
        summary["has_chart"] = chart_file is not None
        summary["stems_count"] = len(audio_files)
        summary["stems"] = [
            {"file": os.path.basename(p), "size_mb": round(os.path.getsize(p) / (1024 * 1024), 1)}
            for p in audio_files
        ]
        return summary

    # --------------------------------------------------------------------------
    # Carga en el motor de audio
    # --------------------------------------------------------------------------

    def load_song(self, song_id: str, engine: MultitrackEngine) -> Song:
        """
        Carga una canción específica y monta sus pistas en el motor de audio.
        """
        folder_path = self._song_folder(song_id)
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Carpeta de canción no encontrada: {song_id}")

        song = self._read_song_metadata(folder_path)
        audio_paths = self._list_audio_files(folder_path)

        if song is None:
            if not audio_paths:
                raise ValueError("No se encontró archivo ChordPro (.pro), song.json ni pistas de audio.")
            # Canción solo con audio: crear metadatos mínimos (sin letras todavía)
            song = Song(
                id=song_id,
                title=song_id.replace("-", " ").title(),
                artist="Desconocido",
                key="C",
                bpm=120.0,
            )

        # Decodificar primero y luego reemplazar, para no dejar el motor vacío si un archivo falla
        loaded_stems: List[StemTrack] = []
        errors: List[str] = []
        for path in audio_paths:
            stem_name = os.path.splitext(os.path.basename(path))[0]
            try:
                loaded_stems.append(StemTrack.load_from_file(path, name=stem_name))
            except Exception as ex:
                errors.append(f"{os.path.basename(path)}: {ex}")

        if audio_paths and not loaded_stems:
            raise ValueError("No se pudo leer ninguna pista de audio. " + " | ".join(errors))

        engine.clear_stems()

        if loaded_stems:
            for stem_track in loaded_stems:
                # Si las guías autónomas están habilitadas y la pista es un stem de guía pregrabado,
                # silenciarla automáticamente para que el motor autónomo sea el único que dé las indicaciones
                st_name = stem_track.name.lower().strip()
                if st_name in ("guia", "guide", "guías", "guias", "click y guia"):
                    if engine.dynamic_cues_enabled:
                        stem_track.mute = True
                engine.add_stem(stem_track)
        else:
            # Generar audio sintético sincronizado con el BPM y la duración de la canción
            duration = max(song.duration_seconds, 60.0)
            engine.add_stem(generate_click_track(bpm=song.bpm, duration_seconds=duration))
            engine.add_stem(generate_guide_cues(bpm=song.bpm, duration_seconds=duration))
            engine.add_stem(generate_instrument_stem("Pad", frequency=196.0, duration_seconds=duration))
            engine.add_stem(generate_instrument_stem("Bajo", frequency=98.0, duration_seconds=duration))

        self.last_load_errors = errors
        return song

    # --------------------------------------------------------------------------
    # Creación e importación (texto ChordPro y archivos subidos desde la web)
    # --------------------------------------------------------------------------

    def import_chordpro_text(self, chordpro_content: str, custom_id: Optional[str] = None) -> Song:
        """
        Crea (o actualiza) una carpeta de canción a partir de texto ChordPro.
        """
        song = ChordProParser.parse_string(chordpro_content, default_id="cancion-nueva")
        song_id = slugify(custom_id or song.id) or "cancion-adoracion"
        song.id = song_id

        folder_path = self._song_folder(song_id)
        os.makedirs(os.path.join(folder_path, "stems"), exist_ok=True)

        with open(os.path.join(folder_path, "chart.pro"), "w", encoding="utf-8") as f:
            f.write(chordpro_content)

        ChordProParser.export_to_json(song, os.path.join(folder_path, "song.json"))
        self.invalidate_cache()
        return song

    def create_song(
        self,
        title: str,
        chordpro_content: Optional[str] = None,
        artist: str = "",
        key: str = "",
        bpm: Optional[float] = None,
    ) -> str:
        """
        Crea una canción nueva. Si hay texto ChordPro se usa tal cual; si no, se genera
        un chart.pro mínimo con los metadatos para poder agregar la letra más tarde.
        Retorna el identificador (nombre de carpeta) de la canción.
        """
        content = (chordpro_content or "").strip()
        if not content:
            # Si la canción ya existe con su letra, no sobrescribirla: solo se agregarán stems
            existing_id = slugify(title or "")
            if existing_id:
                existing_folder = self._song_folder(existing_id)
                if os.path.isdir(existing_folder) and self._find_chart(existing_folder):
                    os.makedirs(os.path.join(existing_folder, "stems"), exist_ok=True)
                    return existing_id

            lines = [f"{{title: {title or 'Canción nueva'}}}"]
            if artist:
                lines.append(f"{{artist: {artist}}}")
            if key:
                lines.append(f"{{key: {key}}}")
            if bpm:
                lines.append(f"{{bpm: {bpm:g}}}")
            content = "\n".join(lines) + "\n"
        elif title and not re.search(r"^\{\s*(title|t)\s*:", content, re.MULTILINE | re.IGNORECASE):
            # El chart no trae título: anteponer el que escribió el usuario
            content = f"{{title: {title}}}\n" + content

        song = self.import_chordpro_text(content, custom_id=title or None)
        return song.id

    def save_stem_files(self, song_id: str, files: Iterable[Tuple[str, BinaryIO]]) -> List[str]:
        """
        Guarda archivos de audio subidos en tracks/<cancion>/stems/.
        `files` es una secuencia de tuplas (nombre_original, flujo_binario).
        Retorna la lista de nombres de archivo guardados.
        """
        folder_path = self._song_folder(song_id)
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Canción no encontrada: {song_id}")

        stems_dir = self._stems_dir(song_id)
        os.makedirs(stems_dir, exist_ok=True)

        saved = []
        for original_name, stream in files:
            safe_name = sanitize_filename(original_name)
            if os.path.splitext(safe_name)[1] not in AUDIO_EXTENSIONS:
                raise ValueError(
                    f"'{original_name}' no es un formato de audio admitido "
                    f"({', '.join(sorted(AUDIO_EXTENSIONS))})."
                )
            dest = os.path.join(stems_dir, safe_name)
            with open(dest, "wb") as out:
                shutil.copyfileobj(stream, out, COPY_CHUNK_SIZE)
            saved.append(safe_name)
        self.invalidate_cache()
        return saved

    def delete_stem(self, song_id: str, filename: str) -> None:
        """Elimina una pista de audio de una canción."""
        safe_name = sanitize_filename(filename)
        path = os.path.join(self._stems_dir(song_id), safe_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Pista no encontrada: {filename}")
        os.remove(path)
        self.invalidate_cache()

    def delete_song(self, song_id: str) -> None:
        """Elimina por completo la carpeta de una canción (chart, json y stems)."""
        folder_path = self._song_folder(song_id)
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Canción no encontrada: {song_id}")
        shutil.rmtree(folder_path)
        self.invalidate_cache()
