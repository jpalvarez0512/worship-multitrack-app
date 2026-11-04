"""
Parser y Serializador de Formato ChordPro Sincronizado con Marcas de Tiempo
Subagente responsable: 01-lead-architect & 03-network-sync-engineer
"""

import json
import os
import re
from typing import List, Optional, Tuple
from src.core.song import ChordMarker, Song, SongLine, SongSection


# Expresiones regulares para directivas y marcado
DIRECTIVE_REGEX = re.compile(r"^\{([a-zA-Z0-9_\-]+)\s*:\s*(.*?)\}$")
TIMESTAMP_REGEX = re.compile(r"^\[(?:(\d{1,2}):)?(\d{1,2}(?:\.\d+)?)\]\s*(.*)$")
CHORD_TAG_REGEX = re.compile(r"\[([A-G][b#]?(?:m|maj|min|sus|add|dim|aug|[0-9])*(?:\/[A-G][b#]?)?)\]")
SECTION_HEADER_REGEX = re.compile(r"^\[([a-zA-Z0-9_\-\s]+)\]$")


def parse_timestamp(time_str: str, minutes_str: Optional[str] = None) -> float:
    """Convierte cadenas [mm:ss.xx] o [ss.xx] a segundos flotantes."""
    seconds = float(time_str)
    if minutes_str is not None and minutes_str != "":
        seconds += int(minutes_str) * 60
    return max(0.0, seconds)


class ChordProParser:
    """
    Parsea archivos ChordPro (.txt, .pro, .cho) con marcas de tiempo sincronizadas
    y los transforma en instancias del modelo estructurado Song.
    """

    @classmethod
    def parse_string(cls, content: str, default_id: str = "custom-song") -> Song:
        lines = content.splitlines()

        # Metadatos por defecto
        meta = {
            "title": "Canción sin título",
            "artist": "Artista Desconocido",
            "key": "C",
            "bpm": 120.0,
            "time_signature": "4/4",
            "id": default_id,
        }

        raw_sections: List[Tuple[str, List[dict]]] = []
        current_section_name = "General"
        current_section_lines: List[dict] = []

        for raw_line in lines:
            line_str = raw_line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            # 1. Comprobar directivas {directive: value}
            dir_match = DIRECTIVE_REGEX.match(line_str)
            if dir_match:
                key = dir_match.group(1).lower()
                val = dir_match.group(2).strip()

                if key in ("title", "t"):
                    meta["title"] = val
                    slug = re.sub(r"[^a-zA-Z0-9_\-]", "", val.lower().replace(" ", "-"))
                    if slug:
                        meta["id"] = slug
                elif key in ("artist", "a", "subtitle", "st"):
                    meta["artist"] = val
                elif key in ("key", "k"):
                    meta["key"] = val
                elif key in ("bpm", "tempo"):
                    try:
                        meta["bpm"] = float(val)
                    except ValueError:
                        pass
                elif key in ("time", "time_signature"):
                    meta["time_signature"] = val
                elif key in ("section", "c", "comment", "s"):
                    # Nueva sección encontrada
                    if current_section_lines:
                        raw_sections.append((current_section_name, current_section_lines))
                        current_section_lines = []
                    current_section_name = val
                continue

            # 2. Comprobar encabezados de sección tipo [Coro] o [Intro]
            sec_hdr_match = SECTION_HEADER_REGEX.match(line_str)
            if sec_hdr_match:
                candidate = sec_hdr_match.group(1).strip()
                # Verificar que no sea un acorde aislado
                if not CHORD_TAG_REGEX.match(f"[{candidate}]") or len(candidate) > 4:
                    if current_section_lines:
                        raw_sections.append((current_section_name, current_section_lines))
                        current_section_lines = []
                    current_section_name = candidate
                    continue

            # 3. Comprobar marcas de tiempo [mm:ss.xx]
            ts_match = TIMESTAMP_REGEX.match(line_str)
            start_sec = 0.0
            body = line_str

            if ts_match:
                min_part = ts_match.group(1)
                sec_part = ts_match.group(2)
                body = ts_match.group(3).strip()
                start_sec = parse_timestamp(sec_part, min_part)

            # Extraer acordes y limpiar letra
            chords_extracted, clean_lyric = cls._extract_chords_and_lyrics(body, start_sec)

            current_section_lines.append({
                "start_time": start_sec,
                "body": body,
                "clean_lyric": clean_lyric,
                "chords": chords_extracted,
            })

        if current_section_lines:
            raw_sections.append((current_section_name, current_section_lines))

        # 4. Construir objeto Song calculando los end_time de cada línea
        song = Song(
            id=meta["id"],
            title=meta["title"],
            artist=meta["artist"],
            key=meta["key"],
            bpm=meta["bpm"],
            time_signature=meta["time_signature"],
        )

        all_flattened_lines = []
        for sec_name, s_lines in raw_sections:
            for item in s_lines:
                all_flattened_lines.append(item)

        # Ordenar por tiempo de inicio para calcular duración de línea
        all_flattened_lines.sort(key=lambda x: x["start_time"])

        for idx, item in enumerate(all_flattened_lines):
            st = item["start_time"]
            if idx + 1 < len(all_flattened_lines):
                et = all_flattened_lines[idx + 1]["start_time"]
                if et <= st:
                    et = st + 4.0
            else:
                et = st + 8.0  # Duración por defecto para la última línea
            item["end_time"] = et

        # Agrupar en SongSections
        for sec_name, s_lines in raw_sections:
            if not s_lines:
                continue
            sec_start = s_lines[0]["start_time"]
            sec_end = s_lines[-1]["end_time"]
            section_obj = SongSection(name=sec_name, start_time=sec_start, end_time=sec_end)

            for line_data in s_lines:
                lyrics = line_data["clean_lyric"]
                # Si la línea no tiene texto audible, etiquetar como Instrumental para proyección
                if not lyrics and line_data["chords"]:
                    lyrics = "[ Instrumental ]"

                line_obj = SongLine(
                    start_time=line_data["start_time"],
                    end_time=line_data["end_time"],
                    lyrics=lyrics,
                    chords=[ChordMarker(time=c["time"], chord=c["chord"]) for c in line_data["chords"]],
                )
                section_obj.lines.append(line_obj)

            song.sections.append(section_obj)

        return song

    @classmethod
    def _extract_chords_and_lyrics(cls, text_with_chords: str, line_start_time: float) -> Tuple[List[dict], str]:
        """
        Separa los acordes [C] de la letra limpia y calcula la posición temporal aproximada
        de cada acorde dentro del compás de la frase.
        """
        chords = []
        clean_chars = []
        cursor_in_clean = 0

        # Buscar todos los acordes y sus posiciones en el texto original
        matches = list(CHORD_TAG_REGEX.finditer(text_with_chords))

        last_idx = 0
        for m in matches:
            # Texto antes del acorde
            prefix = text_with_chords[last_idx:m.start()]
            clean_chars.append(prefix)
            cursor_in_clean += len(prefix)

            chord_name = m.group(1)
            # Acorde asignado al cursor de caracteres actual
            chords.append({
                "chord": chord_name,
                "char_offset": cursor_in_clean,
                "time": line_start_time,  # Se ajusta proporcionalmente abajo
            })
            last_idx = m.end()

        # Texto restante
        clean_chars.append(text_with_chords[last_idx:])
        clean_lyric = "".join(clean_chars).strip()

        # Calcular tiempo relativo de cada acorde según su posición en la frase
        total_len = max(len(clean_lyric), 1)
        # Asumiendo una duración base de frase de 4 a 6 segundos
        for idx, c in enumerate(chords):
            char_pos = c.pop("char_offset")
            # Los acordes posteriores se desfasan progresivamente según su posición
            time_offset = (char_pos / float(total_len)) * 4.0
            c["time"] = round(line_start_time + time_offset, 3)

        return chords, clean_lyric

    @classmethod
    def parse_file(cls, file_path: str) -> Song:
        """Carga y parsea un archivo de texto o ChordPro."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        default_id = os.path.splitext(os.path.basename(file_path))[0]
        return cls.parse_string(content, default_id=default_id)

    @classmethod
    def export_to_json(cls, song: Song, output_path: str) -> None:
        """Serializa la canción estructurada a song.json."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(song.to_full_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load_from_json(cls, json_path: str) -> Song:
        """Reconstruye un objeto Song a partir de song.json."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        song = Song(
            id=data["id"],
            title=data["title"],
            artist=data["artist"],
            key=data["key"],
            bpm=data["bpm"],
            time_signature=data.get("time_signature", "4/4"),
        )
        for sec_data in data.get("sections", []):
            sec = SongSection(
                name=sec_data["name"],
                start_time=sec_data["start_time"],
                end_time=sec_data["end_time"],
            )
            for line_data in sec_data.get("lines", []):
                line = SongLine(
                    start_time=line_data["start_time"],
                    end_time=line_data["end_time"],
                    lyrics=line_data["lyrics"],
                    chords=[
                        ChordMarker(time=c["time"], chord=c["chord"])
                        for c in line_data.get("chords", [])
                    ],
                )
                sec.lines.append(line)
            song.sections.append(sec)
        return song
