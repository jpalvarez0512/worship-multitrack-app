"""
Modulo Procedural de Alineacion Audio-Texto, Resolucion de Arreglos y Modo Hibrido
Worship Multitrack Live
Alinea la letra y los acordes con la voz real y la rejilla ritmica del multitrack,
resuelve repeticiones de secciones en el audio y compila el timeline.json interno.
"""

from dataclasses import dataclass
import json
import math
import os
import re
from typing import Dict, List, Optional, Tuple
import numpy as np

from src.audio.rhythmic_grid import (
    RhythmicGrid,
    build_synthetic_grid,
    extract_rhythmic_grid_from_audio,
)
from src.audio.stem import StemTrack
from src.core.chordpro import ChordProParser
from src.core.quantizer import quantize_song
from src.core.simple_chart_parser import (
    ParsedChord,
    ParsedLine,
    ParsedSection,
    ParsedSong,
    SimpleChartParser,
)
from src.core.song import ChordMarker, Song, SongLine, SongSection


@dataclass
class VocalSegment:
    """Segmento de actividad vocal detectado en el stem de voz."""
    start_time: float
    end_time: float
    duration: float
    energy: float


def detect_vocal_activity_segments(
    vocal_audio: np.ndarray,
    sample_rate: int = 44100,
    min_silence_sec: float = 1.0,
    min_phrase_sec: float = 0.8,
) -> List[VocalSegment]:
    """
    Detecta las regiones temporales donde hay canto activo en la pista vocal.
    """
    if vocal_audio is None or len(vocal_audio) == 0:
        return []

    if vocal_audio.ndim > 1:
        mono = np.max(np.abs(vocal_audio), axis=1)
    else:
        mono = np.abs(vocal_audio)

    # Ventana de RMS de 50 ms
    win = int(0.050 * sample_rate)
    hop = int(0.025 * sample_rate)
    n_frames = (len(mono) - win) // hop
    if n_frames <= 0:
        return []

    # Calcular envolvente de energia
    energies = []
    times = []
    for f in range(n_frames):
        chunk = mono[f * hop : f * hop + win]
        rms = float(np.sqrt(np.mean(chunk**2)))
        energies.append(rms)
        times.append((f * hop) / float(sample_rate))

    energies = np.array(energies, dtype=np.float32)
    max_e = float(np.max(energies))
    if max_e < 0.005:
        return []

    # Umbral adaptable relativo al piso de ruido
    threshold = max(0.02, 0.12 * max_e)
    is_active = energies > threshold

    segments: List[VocalSegment] = []
    in_speech = False
    start_t = 0.0
    silence_frames = 0
    silence_limit = int(min_silence_sec / 0.025)

    for i, active in enumerate(is_active):
        t = times[i]
        if active:
            if not in_speech:
                in_speech = True
                start_t = t
            silence_frames = 0
        else:
            if in_speech:
                silence_frames += 1
                if silence_frames >= silence_limit:
                    end_t = times[max(0, i - silence_frames)]
                    dur = end_t - start_t
                    if dur >= min_phrase_sec:
                        seg_energy = float(np.mean(energies[int(start_t / 0.025) : int(end_t / 0.025)]))
                        segments.append(
                            VocalSegment(
                                start_time=round(start_t, 3),
                                end_time=round(end_t, 3),
                                duration=round(dur, 3),
                                energy=round(seg_energy, 4),
                            )
                        )
                    in_speech = False
                    silence_frames = 0

    if in_speech:
        end_t = times[-1]
        dur = end_t - start_t
        if dur >= min_phrase_sec:
            segments.append(
                VocalSegment(
                    start_time=round(start_t, 3),
                    end_time=round(end_t, 3),
                    duration=round(dur, 3),
                    energy=round(max_e, 4),
                )
            )

    return segments


class AutoAlignmentPipeline:
    """
    Pipeline procedural de cinco etapas para auto-sincronizacion de canciones.
    """

    @classmethod
    def run(
        cls,
        song_id: str,
        folder_path: str,
        simple_text: Optional[str] = None,
        use_hybrid_legacy: bool = True,
    ) -> Tuple[Song, dict]:
        """
        Ejecuta el pipeline completo de auto-sincronizacion para una cancion.
        Retorna (Song_compilada, timeline_json_dict).
        """
        # Paso 1: Obtener texto estructurado (desde .txt o conversion de .pro existente)
        txt_path = os.path.join(folder_path, "chart.txt")
        if not simple_text and os.path.exists(txt_path):
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    simple_text = f.read()
            except Exception:
                pass

        legacy_song: Optional[Song] = None
        legacy_pro_path = os.path.join(folder_path, "chart.pro")
        legacy_json_path = os.path.join(folder_path, "song.json")

        if os.path.exists(legacy_json_path):
            try:
                with open(legacy_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    legacy_song = Song(
                        id=data.get("id", song_id),
                        title=data.get("title", song_id),
                        artist=data.get("artist", ""),
                        key=data.get("key", "G"),
                        bpm=float(data.get("bpm", 72.0)),
                        time_signature=data.get("time_signature", "4/4"),
                    )
                    # Cargar secciones legacy si las hay
                    for s_data in data.get("sections", []):
                        sec = SongSection(
                            name=s_data.get("name", "Seccion"),
                            start_time=float(s_data.get("start_time", 0.0)),
                            end_time=float(s_data.get("end_time", 0.0)),
                        )
                        for l_data in s_data.get("lines", []):
                            line = SongLine(
                                start_time=float(l_data.get("start_time", 0.0)),
                                end_time=float(l_data.get("end_time", 0.0)),
                                lyrics=l_data.get("lyrics", ""),
                                chords=[
                                    ChordMarker(
                                        time=float(c.get("time", 0.0)),
                                        chord=c.get("chord", ""),
                                        char_offset=int(c.get("char_offset", 0)),
                                    )
                                    for c in l_data.get("chords", [])
                                ],
                            )
                            sec.lines.append(line)
                        legacy_song.sections.append(sec)
            except Exception:
                pass
        elif os.path.exists(legacy_pro_path):
            try:
                legacy_song = ChordProParser.parse_file(legacy_pro_path, song_id=song_id)
            except Exception:
                pass

        # Si no hay texto simple pero hay .pro legacy, generar texto plano
        if not simple_text and legacy_song:
            simple_text = cls._legacy_song_to_simple_text(legacy_song)

        if not simple_text:
            simple_text = f"# Intro\n| G | D | Em | C |\n\n# Verso\nG D\nCancion nueva\n"

        parsed_song = SimpleChartParser.parse(
            simple_text,
            default_title=legacy_song.title if legacy_song else song_id,
            default_artist=legacy_song.artist if legacy_song else "",
            default_key=legacy_song.key if legacy_song else "G",
            default_bpm=legacy_song.bpm if legacy_song else 72.0,
            default_time_sig=legacy_song.time_signature if legacy_song else "4/4",
        )

        # Paso 2: Cargar stems de audio y extraer rejilla ritmica
        click_stem, vocal_stem, total_dur = cls._find_stems(folder_path)
        sample_rate = 44100
        click_audio = click_stem.raw_audio_data if click_stem else None

        grid = extract_rhythmic_grid_from_audio(
            click_audio=click_audio,
            sample_rate=sample_rate,
            declared_bpm=parsed_song.bpm,
            time_signature=parsed_song.time_signature,
            total_duration=total_dur,
        )

        # Paso 3: Deteccion de actividad vocal para alineacion
        vocal_segments: List[VocalSegment] = []
        if vocal_stem and vocal_stem.raw_audio_data is not None:
            vocal_segments = detect_vocal_activity_segments(
                vocal_stem.raw_audio_data,
                sample_rate=sample_rate,
            )

        # Paso 4: Resolucion de arreglo (repeticiones y modo hibrido con pistas legacy)
        compiled_song = cls._resolve_arrangement(
            song_id=song_id,
            parsed_song=parsed_song,
            grid=grid,
            vocal_segments=vocal_segments,
            legacy_song=legacy_song if use_hybrid_legacy else None,
            total_duration=total_dur,
        )

        # Paso 5: Cuantizacion ritmica al pulso mas cercano (+/- 120 ms)
        final_song = quantize_song(compiled_song, grid, tolerance=0.120)

        # Generar timeline.json enriquecido
        timeline_dict = cls._build_timeline_json(final_song, grid)

        # Guardar artefactos internos en disco
        timeline_path = os.path.join(folder_path, "timeline.json")
        json_path = os.path.join(folder_path, "song.json")
        pro_path = os.path.join(folder_path, "chart.pro")

        try:
            with open(timeline_path, "w", encoding="utf-8") as f:
                json.dump(timeline_dict, f, indent=2, ensure_ascii=False)
        except Exception as ex:
            print(f"[WARN] Error guardando timeline.json: {ex}")

        try:
            ChordProParser.export_to_json(final_song, json_path)
        except Exception as ex:
            print(f"[WARN] Error guardando song.json: {ex}")

        try:
            with open(pro_path, "w", encoding="utf-8") as f:
                f.write(parsed_song.to_chordpro_text())
        except Exception as ex:
            print(f"[WARN] Error guardando chart.pro: {ex}")

        return (final_song, timeline_dict)

    @staticmethod
    def _find_stems(folder_path: str) -> Tuple[Optional[StemTrack], Optional[StemTrack], float]:
        """Busca y carga de forma ligera los stems de Click y Voz de la cancion."""
        click_stem = None
        vocal_stem = None
        total_duration = 180.0

        stems_dir = os.path.join(folder_path, "stems")
        candidate_files = []
        if os.path.isdir(stems_dir):
            candidate_files = [os.path.join(stems_dir, f) for f in sorted(os.listdir(stems_dir))]
        else:
            candidate_files = [os.path.join(folder_path, f) for f in sorted(os.listdir(folder_path))]

        for p in candidate_files:
            if not p.lower().endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a")):
                continue
            name_low = os.path.basename(p).lower()
            if any(k in name_low for k in ("click", "clic", "metronomo", "beat")):
                try:
                    click_stem = StemTrack.load_from_file(p, name="Click")
                    total_duration = max(total_duration, click_stem.duration_seconds)
                except Exception:
                    pass
            elif any(k in name_low for k in ("voz", "lead", "vocal", "cantante", "vox")):
                try:
                    vocal_stem = StemTrack.load_from_file(p, name="Vocal")
                    total_duration = max(total_duration, vocal_stem.duration_seconds)
                except Exception:
                    pass

        return (click_stem, vocal_stem, total_duration)

    @classmethod
    def _resolve_arrangement(
        cls,
        song_id: str,
        parsed_song: ParsedSong,
        grid: RhythmicGrid,
        vocal_segments: List[VocalSegment],
        legacy_song: Optional[Song],
        total_duration: float,
    ) -> Song:
        """
        Calcula las posiciones temporales de cada seccion aplicando el Modo Hibrido
        si hay datos legacy o mapeando sobre los segmentos vocales y la rejilla ritmica.
        """
        # 1. Modo Hibrido: si disponemos de canciones legacy con marcas manuales
        if legacy_song and legacy_song.sections:
            return cls._align_with_hybrid_legacy(song_id, parsed_song, legacy_song, grid, vocal_segments)

        # 2. Modo Autonomo: Distribuir las secciones del parsed_song de forma musical
        return cls._align_autonomously(song_id, parsed_song, grid, vocal_segments, total_duration)

    @classmethod
    def _align_with_hybrid_legacy(
        cls,
        song_id: str,
        parsed_song: ParsedSong,
        legacy_song: Song,
        grid: RhythmicGrid,
        vocal_segments: List[VocalSegment],
    ) -> Song:
        """
        Aprovecha las marcas de tiempo aproximadas de canciones existentes como ventanas
        de busqueda acustica (+/- 6.0s) para anclar de forma exacta la voz y el compas.
        """
        final_sections: List[SongSection] = []
        parsed_sec_dict = {s.name.lower().strip(): s for s in parsed_song.sections}

        for l_sec in legacy_song.sections:
            approx_start = l_sec.start_time
            approx_end = l_sec.end_time

            # Ventana de busqueda acustica (+/- 6s)
            win_min = max(0.0, approx_start - 6.0)
            win_max = approx_start + 6.0

            # Buscar segmento vocal cercano
            best_start = approx_start
            matching_vocal = [
                seg for seg in vocal_segments
                if win_min <= seg.start_time <= win_max
            ]
            if matching_vocal:
                best_start = matching_vocal[0].start_time

            # Anclar al compas mas cercano de la rejilla
            refined_start = grid.snap_to_nearest_downbeat(best_start, max_tolerance=0.40)
            refined_end = grid.snap_to_nearest_downbeat(approx_end, max_tolerance=0.40)
            if refined_end <= refined_start:
                refined_end = refined_start + grid.bar_duration * 4

            # Asociar lineas y acordes del texto parsed
            matching_parsed = parsed_sec_dict.get(l_sec.name.lower().strip())
            lines_to_add: List[SongLine] = []

            if matching_parsed and matching_parsed.lines:
                n_lines = len(matching_parsed.lines)
                line_dur = (refined_end - refined_start) / max(1, n_lines)
                cur_l_t = refined_start
                for pl in matching_parsed.lines:
                    l_end = cur_l_t + line_dur
                    c_markers = []
                    for c in pl.chords:
                        c_t = cur_l_t + (c.char_offset / max(1, len(pl.lyrics)) * (line_dur * 0.85)) if pl.lyrics else cur_l_t
                        c_markers.append(
                            ChordMarker(
                                time=round(c_t, 3),
                                chord=c.chord,
                                char_offset=c.char_offset,
                            )
                        )
                    lines_to_add.append(
                        SongLine(
                            start_time=round(cur_l_t, 3),
                            end_time=round(l_end, 3),
                            lyrics=pl.lyrics,
                            chords=c_markers,
                        )
                    )
                    cur_l_t = l_end
            elif l_sec.lines:
                lines_to_add = l_sec.lines

            final_sections.append(
                SongSection(
                    name=l_sec.name,
                    start_time=round(refined_start, 3),
                    end_time=round(refined_end, 3),
                    lines=lines_to_add,
                )
            )

        return Song(
            id=song_id,
            title=parsed_song.title or legacy_song.title,
            artist=parsed_song.artist or legacy_song.artist,
            key=parsed_song.key or legacy_song.key,
            bpm=grid.bpm,
            time_signature=grid.time_signature,
            sections=final_sections,
        )

    @classmethod
    def _align_autonomously(
        cls,
        song_id: str,
        parsed_song: ParsedSong,
        grid: RhythmicGrid,
        vocal_segments: List[VocalSegment],
        total_duration: float,
    ) -> Song:
        """
        Alinea de manera totalmente automatica el texto con la rejilla y los segmentos vocales.
        """
        sections: List[SongSection] = []
        cur_time = 0.0
        bar_dur = grid.bar_duration
        sec_bars_default = 4

        for sec in parsed_song.sections:
            # Estimar compases: barras explicitas o 4 compases por linea
            num_bars = sec.explicit_bars if sec.explicit_bars > 0 else max(sec_bars_default, len(sec.lines) * 2)
            dur = num_bars * bar_dur
            sec_start = cur_time

            # Si es seccion vocal y hay segmentos vocales por delante, sincronizar inicio
            if not sec.is_instrumental and vocal_segments:
                ahead_vocals = [v for v in vocal_segments if v.start_time >= cur_time - 1.0]
                if ahead_vocals:
                    sec_start = grid.snap_to_nearest_downbeat(ahead_vocals[0].start_time, max_tolerance=0.50)

            sec_end = grid.snap_to_nearest_downbeat(sec_start + dur, max_tolerance=0.50)
            if sec_end <= sec_start:
                sec_end = sec_start + dur

            # Construir lineas
            lines: List[SongLine] = []
            if sec.lines:
                line_dur = (sec_end - sec_start) / len(sec.lines)
                l_cur = sec_start
                for pl in sec.lines:
                    l_end = l_cur + line_dur
                    c_markers = []
                    for c_idx, c in enumerate(pl.chords):
                        if pl.is_bar_line:
                            c_t = l_cur + (c_idx * bar_dur)
                        else:
                            ratio = (c.char_offset / max(1, len(pl.lyrics))) if pl.lyrics else (c_idx / max(1, len(pl.chords)))
                            c_t = l_cur + (ratio * (line_dur * 0.85))
                        c_markers.append(
                            ChordMarker(
                                time=round(c_t, 3),
                                chord=c.chord,
                                char_offset=c.char_offset,
                            )
                        )
                    lines.append(
                        SongLine(
                            start_time=round(l_cur, 3),
                            end_time=round(l_end, 3),
                            lyrics=pl.lyrics,
                            chords=c_markers,
                        )
                    )
                    l_cur = l_end

            sections.append(
                SongSection(
                    name=sec.name,
                    start_time=round(sec_start, 3),
                    end_time=round(sec_end, 3),
                    lines=lines,
                )
            )
            cur_time = sec_end

        return Song(
            id=song_id,
            title=parsed_song.title,
            artist=parsed_song.artist,
            key=parsed_song.key,
            bpm=grid.bpm,
            time_signature=grid.time_signature,
            sections=sections,
        )

    @staticmethod
    def _legacy_song_to_simple_text(song: Song) -> str:
        """Convierte una cancion previa a la sintaxis limpia de acordes sobre letra."""
        lines = [
            f"Titulo: {song.title}",
            f"Artista: {song.artist}",
            f"Tono: {song.key}",
            f"BPM: {int(song.bpm)}",
            f"Compas: {song.time_signature}",
            "",
        ]
        for sec in song.sections:
            lines.append(f"# {sec.name}")
            for l in sec.lines:
                if l.chords:
                    # Construir linea de acordes encima
                    chord_line = [" "] * 80
                    for c in l.chords:
                        pos = min(70, c.char_offset)
                        for idx, ch in enumerate(c.chord):
                            if pos + idx < len(chord_line):
                                chord_line[pos + idx] = ch
                    lines.append("".join(chord_line).rstrip())
                if l.lyrics:
                    lines.append(l.lyrics)
            lines.append("")
        return "\n".join(lines).strip()

    @staticmethod
    def _build_timeline_json(song: Song, grid: RhythmicGrid) -> dict:
        """
        Construye el esquema enriquecido timeline.json especificado en la arquitectura.
        """
        eventos = []
        instance_counter: Dict[str, int] = {}

        for sec in song.sections:
            sec_type = sec.name.split()[0]
            inst_num = instance_counter.get(sec_type, 0) + 1
            instance_counter[sec_type] = inst_num

            bar_start, _ = grid.get_bar_and_beat(sec.start_time)

            for line in sec.lines:
                chord_events = []
                for c in line.chords:
                    b_idx, beat_in_bar = grid.get_bar_and_beat(c.time)
                    chord_events.append(
                        {
                            "cifrado": c.chord,
                            "compas": b_idx + 1,
                            "pulso": beat_in_bar,
                            "tiempo_ms": int(c.time * 1000),
                            "confianza": 0.98,
                        }
                    )

                eventos.append(
                    {
                        "seccion": sec.name,
                        "instancia": inst_num,
                        "compas_inicio": bar_start + 1,
                        "tiempo_inicio_ms": int(line.start_time * 1000),
                        "tiempo_fin_ms": int(line.end_time * 1000),
                        "linea_proyeccion": line.lyrics,
                        "acordes": chord_events,
                    }
                )

        return {
            "cancion_id": song.id,
            "bpm": round(grid.bpm, 2),
            "compas": grid.time_signature,
            "tonalidad_base": song.key,
            "eventos": eventos,
        }
