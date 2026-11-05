"""
Modelo de Datos de Canciones, Secciones, Letras y Acordes Sincronizados
Subagente responsable: 01-lead-architect & 03-network-sync-engineer
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


CHROMATIC_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
CHROMATIC_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def transpose_chord(chord: str, semitones: int) -> str:
    """
    Transpone un acorde musical un número determinado de semitonos (+/-).
    Maneja sufijos como m, 7, maj7, sus4, add9, /B, etc.
    """
    if not chord or semitones == 0:
        return chord

    # Manejar acordes con bajo invertido (ej. D/F#)
    if "/" in chord:
        root_part, bass_part = chord.split("/", 1)
        return f"{transpose_chord(root_part, semitones)}/{transpose_chord(bass_part, semitones)}"

    # Extraer la nota raíz (1 o 2 letras: C, C#, Db, etc.)
    root = chord[0]
    rest = chord[1:]
    if len(chord) > 1 and chord[1] in ("#", "b"):
        root = chord[:2]
        rest = chord[2:]

    # Buscar en escala cromática
    index = -1
    use_flats = "b" in root
    scale = CHROMATIC_FLAT if use_flats else CHROMATIC_SHARP

    if root in CHROMATIC_SHARP:
        index = CHROMATIC_SHARP.index(root)
    elif root in CHROMATIC_FLAT:
        index = CHROMATIC_FLAT.index(root)
    else:
        return chord

    new_index = (index + semitones) % 12
    new_root = scale[new_index]
    return f"{new_root}{rest}"


@dataclass
class ChordMarker:
    """Representa un acorde en una posición temporal y silábica específica dentro de la línea."""
    time: float  # Tiempo en segundos relativo al inicio de la canción
    chord: str
    char_offset: int = 0  # Índice de carácter sobre la letra limpia donde cae el acorde


@dataclass
class SongLine:
    """Línea (compás/frase) de letra y acordes sincronizados."""
    start_time: float
    end_time: float
    lyrics: str
    chords: List[ChordMarker] = field(default_factory=list)

    def to_dict(self, transpose_semitones: int = 0) -> dict:
        return {
            "start_time": round(self.start_time, 3),
            "end_time": round(self.end_time, 3),
            "lyrics": self.lyrics,
            "chords": [
                {
                    "time": round(c.time, 3),
                    "chord": transpose_chord(c.chord, transpose_semitones),
                    "char_offset": c.char_offset,
                }
                for c in self.chords
            ],
        }


@dataclass
class SongSection:
    """Sección de la estructura musical (Intro, Verso, Coro, Puente, etc.)."""
    name: str
    start_time: float
    end_time: float
    lines: List[SongLine] = field(default_factory=list)

    def to_dict(self, transpose_semitones: int = 0) -> dict:
        return {
            "name": self.name,
            "start_time": round(self.start_time, 3),
            "end_time": round(self.end_time, 3),
            "lines": [line.to_dict(transpose_semitones) for line in self.lines],
        }


@dataclass
class Song:
    """Representación completa de una canción de adoración multitrack."""
    id: str
    title: str
    artist: str
    key: str
    bpm: float
    time_signature: str = "4/4"
    sections: List[SongSection] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if not self.sections:
            return 0.0
        return max(sec.end_time for sec in self.sections)

    def get_section_at(self, current_time: float) -> Optional[SongSection]:
        """Obtiene la sección que se está ejecutando en el tiempo dado (sin solapamiento en bordes)."""
        for idx, sec in enumerate(self.sections):
            is_last = idx == len(self.sections) - 1
            if sec.start_time <= current_time < sec.end_time or (is_last and sec.start_time <= current_time <= sec.end_time):
                return sec
        return None

    def get_active_line_at(self, current_time: float) -> Optional[SongLine]:
        """Obtiene la línea actual de letra y acordes."""
        sec = self.get_section_at(current_time)
        if sec:
            for idx, line in enumerate(sec.lines):
                is_last = idx == len(sec.lines) - 1
                if line.start_time <= current_time < line.end_time or (is_last and line.start_time <= current_time <= line.end_time):
                    return line
        return None

    def get_projection_lyric_at(self, current_time: float, lead_seconds: float = 1.5) -> Tuple[str, str]:
        """
        Obtiene (letra_limpia, nombre_seccion) para la pantalla de proyección,
        adelantándose `lead_seconds` segundos para dar tiempo de lectura a la congregación
        y ocultando marcadores instrumentales.
        """
        lookup_time = max(0.0, current_time + max(0.0, lead_seconds))
        sec = self.get_section_at(lookup_time)
        sec_name = sec.name if sec else ""
        line = self.get_active_line_at(lookup_time)
        if not line:
            return "", sec_name
        txt = (line.lyrics or "").strip()
        if txt.startswith("[") and txt.endswith("]"):
            return "", sec_name
        return txt, sec_name

    def to_summary_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "key": self.key,
            "bpm": self.bpm,
            "time_signature": self.time_signature,
            "duration": round(self.duration_seconds, 2),
            "sections_count": len(self.sections),
        }

    def to_full_dict(self, transpose_semitones: int = 0) -> dict:
        effective_key = transpose_chord(self.key, transpose_semitones)
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "key": effective_key,
            "original_key": self.key,
            "transpose_semitones": transpose_semitones,
            "bpm": self.bpm,
            "time_signature": self.time_signature,
            "duration": round(self.duration_seconds, 2),
            "sections": [sec.to_dict(transpose_semitones) for sec in self.sections],
        }


def create_demo_song() -> Song:
    """Genera una canción de adoración de demostración totalmente sincronizada."""
    song = Song(
        id="cuancuandios-demo",
        title="Cuán Grande es Dios",
        artist="En Espíritu y en Verdad",
        key="G",
        bpm=76.0,
        time_signature="4/4",
    )

    # 1. Intro (0.0s - 12.0s)
    intro = SongSection(name="Intro", start_time=0.0, end_time=12.0)
    intro.lines.append(
        SongLine(
            start_time=0.0,
            end_time=12.0,
            lyrics="[ Instrumental ]",
            chords=[
                ChordMarker(time=0.0, chord="G"),
                ChordMarker(time=6.0, chord="Em7"),
            ],
        )
    )
    song.sections.append(intro)

    # 2. Verso 1 (12.0s - 32.0s)
    verso1 = SongSection(name="Verso 1", start_time=12.0, end_time=32.0)
    verso1.lines.append(
        SongLine(
            start_time=12.0,
            end_time=22.0,
            lyrics="El esplendor de un Rey, vestido en Majestad",
            chords=[
                ChordMarker(time=12.0, chord="G"),
                ChordMarker(time=17.0, chord="Em7"),
            ],
        )
    )
    verso1.lines.append(
        SongLine(
            start_time=22.0,
            end_time=32.0,
            lyrics="La tierra gozará, la tierra gozará",
            chords=[
                ChordMarker(time=22.0, chord="C2"),
                ChordMarker(time=27.0, chord="D"),
            ],
        )
    )
    song.sections.append(verso1)

    # 3. Coro (32.0s - 56.0s)
    coro = SongSection(name="Coro", start_time=32.0, end_time=56.0)
    coro.lines.append(
        SongLine(
            start_time=32.0,
            end_time=44.0,
            lyrics="Cuán grande es Dios, cántale: Cuán grande es Dios",
            chords=[
                ChordMarker(time=32.0, chord="G"),
                ChordMarker(time=38.0, chord="Em7"),
            ],
        )
    )
    coro.lines.append(
        SongLine(
            start_time=44.0,
            end_time=56.0,
            lyrics="Y todos lo verán, cuán grande es Dios",
            chords=[
                ChordMarker(time=44.0, chord="C"),
                ChordMarker(time=49.0, chord="D"),
                ChordMarker(time=53.0, chord="G"),
            ],
        )
    )
    song.sections.append(coro)

    # 4. Puente (56.0s - 75.0s)
    puente = SongSection(name="Puente", start_time=56.0, end_time=75.0)
    puente.lines.append(
        SongLine(
            start_time=56.0,
            end_time=65.0,
            lyrics="Tu Nombre sobre todo es, digno de alabar",
            chords=[
                ChordMarker(time=56.0, chord="G"),
                ChordMarker(time=61.0, chord="Em7"),
            ],
        )
    )
    puente.lines.append(
        SongLine(
            start_time=65.0,
            end_time=75.0,
            lyrics="Y mi ser cantará: Cuán grande es Dios",
            chords=[
                ChordMarker(time=65.0, chord="C"),
                ChordMarker(time=70.0, chord="D"),
                ChordMarker(time=73.0, chord="G"),
            ],
        )
    )
    song.sections.append(puente)

    return song
