"""
Parser de Entrada Simplificado de Canciones ("Acordes sobre Letra")
Worship Multitrack Live
Permite a cualquier musico u operador pegar la letra con acordes encima
en formato texto plano (.txt) con encabezados #, sin necesidad de escribir corchetes
ni marcas de tiempo manuales.
"""

from dataclasses import dataclass, field
import re
from typing import List, Optional, Tuple

from src.core.song import ChordMarker, Song, SongLine, SongSection


CHORD_TOKEN_REGEX = re.compile(
    r"^[A-G](?:#|b)?"
    r"(?:m|min|maj|M|dim|aug|sus|sus2|sus4|add9|add2|add4|maj7|maj9|m7|m9|7|9|11|13|2|4|5|6)?"
    r"(?:/[A-G](?:#|b)?)?$"
)

MEASURE_BAR_REGEX = re.compile(r"^[\s|:0-9A-G#bm/.-]+$")


@dataclass
class ParsedChord:
    """Representa un acorde detectado con su columna horizontal y desplazamiento sobre la letra."""
    chord: str
    col_index: int
    char_offset: int
    bar_index: Optional[int] = None
    beat_index: Optional[int] = None
    time_seconds: Optional[float] = None
    confidence: float = 1.0


@dataclass
class ParsedLine:
    """Linea compuesta por acordes y su texto lirico correspondiente."""
    lyrics: str
    chords: List[ParsedChord] = field(default_factory=list)
    raw_chord_line: str = ""
    is_bar_line: bool = False
    bars: List[str] = field(default_factory=list)

    def to_chordpro(self) -> str:
        """Convierte esta linea al formato estandar [Acorde]Letra."""
        if self.is_bar_line:
            return " | ".join(f"[{c}]" for c in self.bars) if self.bars else ""

        if not self.lyrics:
            return " ".join(f"[{c.chord}]" for c in self.chords)

        # Ordenar acordes por char_offset descendente para insertar corchetes de derecha a izquierda
        chars = list(self.lyrics)
        sorted_chords = sorted(self.chords, key=lambda c: c.char_offset, reverse=True)
        for c in sorted_chords:
            pos = max(0, min(len(chars), c.char_offset))
            chars.insert(pos, f"[{c.chord}]")
        return "".join(chars)


@dataclass
class ParsedSection:
    """Bloque estructural musical (Intro, Verso, Coro, Puente, etc.)."""
    name: str
    lines: List[ParsedLine] = field(default_factory=list)
    is_instrumental: bool = False
    explicit_bars: int = 0


@dataclass
class ParsedSong:
    """Representacion estructurada extraida del texto plano simplificado."""
    title: str = "Cancion de Adoracion"
    artist: str = ""
    key: str = "G"
    bpm: float = 72.0
    time_signature: str = "4/4"
    sections: List[ParsedSection] = field(default_factory=list)

    def to_chordpro_text(self) -> str:
        """Genera el texto ChordPro completo compatible con motores de proyeccion."""
        out = [
            f"{{title: {self.title}}}",
            f"{{artist: {self.artist}}}",
            f"{{key: {self.key}}}",
            f"{{tempo: {int(self.bpm)}}}",
            f"{{time: {self.time_signature}}}",
            "",
        ]
        for sec in self.sections:
            out.append(f"{{comment: {sec.name}}}")
            for line in sec.lines:
                pro_line = line.to_chordpro()
                if pro_line:
                    out.append(pro_line)
            out.append("")
        return "\n".join(out).strip()

    def to_song_object(self, song_id: str = "custom-song", total_duration: float = 180.0) -> Song:
        """
        Convierte el ParsedSong en un objeto Song del dominio de la aplicacion.
        Si aun no hay marcas de tiempo calculadas, distribuye tiempos estimados
        segun el BPM y los compases para inicializar el modelo.
        """
        song = Song(
            id=song_id,
            title=self.title,
            artist=self.artist,
            key=self.key,
            bpm=self.bpm,
            time_signature=self.time_signature,
            sections=[],
        )

        seconds_per_beat = 60.0 / max(30.0, self.bpm)
        beats_per_bar = 4
        if "/" in self.time_signature:
            try:
                beats_per_bar = int(self.time_signature.split("/")[0])
            except ValueError:
                pass
        seconds_per_bar = seconds_per_beat * beats_per_bar

        cur_time = 0.0
        for s_idx, sec in enumerate(self.sections):
            sec_start = cur_time
            sec_lines = []

            for line in sec.lines:
                # Estimar duracion de linea: 2 compases por defecto o compases explicitos
                line_bars = max(1, len(line.bars)) if line.is_bar_line else 2
                line_duration = line_bars * seconds_per_bar
                line_start = cur_time
                line_end = line_start + line_duration

                chord_markers = []
                for c_idx, c in enumerate(line.chords):
                    if c.time_seconds is not None:
                        c_time = c.time_seconds
                    elif line.is_bar_line:
                        c_time = line_start + (c_idx * seconds_per_bar)
                    else:
                        rel_ratio = (c.char_offset / max(1, len(line.lyrics))) if line.lyrics else (c_idx / max(1, len(line.chords)))
                        c_time = line_start + (rel_ratio * (line_duration * 0.8))

                    chord_markers.append(
                        ChordMarker(
                            time=round(c_time, 3),
                            chord=c.chord,
                            char_offset=c.char_offset,
                        )
                    )

                sec_lines.append(
                    SongLine(
                        start_time=round(line_start, 3),
                        end_time=round(line_end, 3),
                        lyrics=line.lyrics,
                        chords=chord_markers,
                    )
                )
                cur_time = line_end

            sec_end = cur_time
            song.sections.append(
                SongSection(
                    name=sec.name,
                    start_time=round(sec_start, 3),
                    end_time=round(sec_end, 3),
                    lines=sec_lines,
                )
            )

        return song


class SimpleChartParser:
    """Analizador determinista de documentos de letra con acordes encima."""

    @staticmethod
    def is_chord_token(token: str) -> bool:
        """Determina si una palabra o simbolo corresponde a un cifrado americano valido."""
        t = token.strip("()[]{},.:;")
        if not t:
            return False
        return bool(CHORD_TOKEN_REGEX.match(t))

    @classmethod
    def is_chord_line(cls, line: str) -> bool:
        """
        Determina si una linea de texto es exclusivamente de acordes.
        Verifica que contenga al menos un acorde y que todos los tokens sean cifrados o compases.
        """
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            return False

        # Si tiene barras de compas como | G | D | Em | C |
        if "|" in stripped and MEASURE_BAR_REGEX.match(stripped):
            bars = [b.strip() for b in stripped.split("|") if b.strip()]
            if bars and any(cls.is_chord_token(b) for b in bars):
                return True

        tokens = stripped.split()
        if not tokens:
            return False

        chord_count = 0
        for tok in tokens:
            cleaned = tok.strip("()[]{},.:;")
            if cls.is_chord_token(cleaned):
                chord_count += 1
            elif cleaned in ("-", "/", "//", "%", "|", ":|", "|:"):
                continue
            else:
                return False

        return chord_count > 0

    @classmethod
    def extract_chords_with_positions(cls, line: str) -> List[Tuple[str, int]]:
        """Extrae los acordes y su posicion de columna horizontal en la linea."""
        res = []
        for m in re.finditer(r"\S+", line):
            token = m.group()
            cleaned = token.strip("()[]{},.:;")
            if cls.is_chord_token(cleaned):
                res.append((cleaned, m.start()))
        return res

    @classmethod
    def parse_bar_line(cls, line: str) -> List[str]:
        """Extrae los acordes por compas de lineas con notacion de barras | G | D |."""
        bars = []
        parts = line.split("|")
        for p in parts:
            p_strip = p.strip()
            if p_strip:
                sub_tokens = [tok.strip("()[]{},.:;") for tok in p_strip.split()]
                chords_in_bar = [tok for tok in sub_tokens if cls.is_chord_token(tok)]
                if chords_in_bar:
                    bars.append(chords_in_bar[0])
        return bars

    @classmethod
    def parse(
        cls,
        text: str,
        default_title: str = "Nueva Cancion",
        default_artist: str = "",
        default_key: str = "G",
        default_bpm: float = 72.0,
        default_time_sig: str = "4/4",
    ) -> ParsedSong:
        """
        Parsea un documento de texto simple y devuelve la estructura de canciones y secciones.
        """
        song = ParsedSong(
            title=default_title,
            artist=default_artist,
            key=default_key,
            bpm=default_bpm,
            time_signature=default_time_sig,
        )

        raw_lines = text.splitlines()
        current_section: Optional[ParsedSection] = None
        i = 0
        n = len(raw_lines)

        while i < n:
            raw = raw_lines[i]
            stripped = raw.strip()

            if not stripped:
                i += 1
                continue

            # 1. Metadatos de cabecera opcionales (Key: G, BPM: 76, Title: ...)
            lower_s = stripped.lower()
            if lower_s.startswith("tono:") or lower_s.startswith("key:"):
                song.key = stripped.split(":", 1)[1].strip()
                i += 1
                continue
            if lower_s.startswith("bpm:") or lower_s.startswith("tempo:"):
                try:
                    song.bpm = float(stripped.split(":", 1)[1].strip())
                except ValueError:
                    pass
                i += 1
                continue
            if lower_s.startswith("titulo:") or lower_s.startswith("title:"):
                song.title = stripped.split(":", 1)[1].strip()
                i += 1
                continue
            if lower_s.startswith("artista:") or lower_s.startswith("artist:"):
                song.artist = stripped.split(":", 1)[1].strip()
                i += 1
                continue
            if lower_s.startswith("compas:") or lower_s.startswith("time:"):
                song.time_signature = stripped.split(":", 1)[1].strip()
                i += 1
                continue

            # 2. Encabezados de seccion (# Intro, # Coro, [Coro], etc.)
            if stripped.startswith("#"):
                sec_name = stripped.lstrip("#").strip()
                current_section = ParsedSection(name=sec_name)
                song.sections.append(current_section)
                # Deteccion de secciones instrumentales
                low_name = sec_name.lower()
                if any(k in low_name for k in ("intro", "instrumental", "solo", "interludio", "outro")):
                    current_section.is_instrumental = True
                i += 1
                continue

            # Si no hay seccion activa aun, crear una seccion inicial por defecto
            if current_section is None:
                current_section = ParsedSection(name="Seccion 1")
                song.sections.append(current_section)

            # 3. Detectar si la linea actual es una linea de acordes
            if cls.is_chord_line(raw):
                # Verificar si es una linea de compases con barras | G | D |
                if "|" in raw and any(cls.is_chord_token(b) for b in raw.split("|") if b.strip()):
                    bars = cls.parse_bar_line(raw)
                    p_line = ParsedLine(
                        lyrics="",
                        raw_chord_line=raw,
                        is_bar_line=True,
                        bars=bars,
                    )
                    for b_idx, chord_str in enumerate(bars):
                        p_line.chords.append(
                            ParsedChord(
                                chord=chord_str,
                                col_index=b_idx * 4,
                                char_offset=0,
                                bar_index=b_idx,
                                beat_index=1,
                            )
                        )
                    current_section.lines.append(p_line)
                    current_section.explicit_bars += len(bars)
                    i += 1
                    continue

                # Es una linea de acordes normal sobre letra
                chord_positions = cls.extract_chords_with_positions(raw)
                
                # Mirar si la linea siguiente es la letra
                next_raw = raw_lines[i + 1] if i + 1 < n else ""
                next_stripped = next_raw.strip()

                # Si la siguiente linea no es seccion (#) y no es otra linea de acordes
                if next_stripped and not next_stripped.startswith("#") and not cls.is_chord_line(next_raw):
                    lyrics_text = next_stripped
                    p_line = ParsedLine(lyrics=lyrics_text, raw_chord_line=raw)
                    lyric_len = len(lyrics_text)

                    # Vincular cada acorde con la posicion en la letra
                    for chord_str, col in chord_positions:
                        # Si la columna cae despues del final de la letra, anclar al final
                        offset = min(col, max(0, lyric_len - 1)) if lyric_len > 0 else 0
                        p_line.chords.append(
                            ParsedChord(
                                chord=chord_str,
                                col_index=col,
                                char_offset=offset,
                            )
                        )
                    current_section.lines.append(p_line)
                    i += 2  # Consumir linea de acordes y linea de letra
                    continue
                else:
                    # Linea de acordes solitaria (sin letra debajo, ej. puente instrumental sin barras)
                    p_line = ParsedLine(lyrics="", raw_chord_line=raw)
                    for chord_str, col in chord_positions:
                        p_line.chords.append(
                            ParsedChord(
                                chord=chord_str,
                                col_index=col,
                                char_offset=0,
                            )
                        )
                    current_section.lines.append(p_line)
                    i += 1
                    continue

            # 4. Linea de letra sola (sin acordes arriba)
            p_line = ParsedLine(lyrics=stripped, raw_chord_line="")
            current_section.lines.append(p_line)
            i += 1

        return song
